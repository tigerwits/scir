"""One-use, hash-locked transport of the locally verified migration tree.

The dictionary replay runs only in a disposable baseline copy. It is a compression
step, not the resulting repository implementation. The complete final files are
then decoded, preflighted and staged; the exact Git tree is checked before any
commit or push. This script never commits or pushes and removes its own carrier.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

BASE = "095c9ab6c2e6897135123494470e80c5c4446228"
BASE_TREE = "49d7daa8b2e49db6d5506dd98790f5786685f6be"
TREE = "5eeed6c8dfd9496d06e23df81ed3cacb378df18c"
BASE_DICT = "f513436166e7203e7fbd5fb8c51bbe25d3c909c20f63e6138c595e7a56809d5c"
REPLAY_DICT = "5ce9539680c4bfa3c7a3a3d30cb3cdaa0e38c7db1ceb9189e2d6ebf282de269c"
CARRIERS = frozenset((".github/migration/apply.py", ".github/migration/recipe.zst",
    ".github/migration/changes-0.zst", ".github/migration/changes-1.zst",
    ".github/migration/changes-2.zst", ".github/workflows/migrate-once.yml"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def chunks(text):
    return (json.dumps(text, ensure_ascii=True).encode(), b"\0",
            json.dumps(json.dumps(text, ensure_ascii=False)[1:-1],
                       ensure_ascii=True)[1:-1].encode(), b"\0")


def decode(temp, packed, packed_hash, dictionary, output_hash, size):
    require(sha(packed.read_bytes()) == packed_hash, "carrier checksum mismatch")
    pool = temp / "dictionary"
    pool.write_bytes(dictionary)
    raw = subprocess.check_output(["zstd", "-d", "-q", "-c", "-D", str(pool), str(packed)])
    require(len(raw) == size and sha(raw) == output_hash, "decoded content mismatch")
    return raw


def apply(root, baseline=BASE):
    root = Path(root).resolve()
    require(not git(root, "status", "--porcelain"), "checkout must be clean")
    require(git(root, "rev-parse", baseline + "^{tree}").decode().strip() == BASE_TREE,
            "wrong baseline tree")
    changed = set(git(root, "diff", "--name-only", "-z", baseline, "HEAD").decode().strip("\0").split("\0"))
    require(changed == CARRIERS, "unreviewed changes outside the carrier")
    for name in CARRIERS:
        path = root / name
        require(path.is_file() and not path.is_symlink(), "missing or linked carrier")
    with tempfile.TemporaryDirectory(prefix="scir-transfer-", dir=os.environ.get("RUNNER_TEMP")) as tmp:
        temp = Path(tmp)
        replay = temp / "baseline"
        replay.mkdir()
        archive = git(root, "archive", "--format=tar", baseline)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            for member in source.getmembers():
                path = PurePosixPath(member.name)
                require(not path.is_absolute() and ".." not in path.parts and
                        (member.isfile() or member.isdir()), "unsafe baseline archive")
                target = replay.joinpath(*path.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.extractfile(member).read())
        pool = []
        for path in sorted((p for p in replay.rglob("*") if p.is_file()),
                           key=lambda p: p.relative_to(replay).as_posix()):
            raw = path.read_bytes()
            pool.extend((*chunks(raw.decode("utf-8")), sha(raw).encode(), b"\0"))
        dictionary = b"".join(pool)
        require(sha(dictionary) == BASE_DICT, "baseline dictionary mismatch")
        recipe = decode(temp, root / ".github/migration/recipe.zst",
            "afc22f974eb452006e324dbf7dd72c75555618dd65cc506aa570544459900973",
            dictionary, "20eccb9044c301ac6598a8ef6e3ffc7ce3ba016adba7d23bab10279a2a2dad3f", 21029)
        script = temp / "replay.py"
        script.write_bytes(recipe)
        subprocess.run([sys.executable, str(script)], cwd=replay, check=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        pool = [dictionary]
        for path in sorted(replay.rglob("*")):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
                pool.extend(chunks(path.read_bytes().decode("utf-8")))
        dictionary = b"".join(pool)
        require(sha(dictionary) == REPLAY_DICT, "replay dictionary mismatch")
        packed = temp / "changes.zst"
        packed.write_bytes(b"".join((root / f".github/migration/changes-{i}.zst").read_bytes() for i in range(3)))
        raw = decode(temp, packed,
            "f57cbb589b742313c51c12d225df8eec7283173a5fb3553ce6f578424081c3ce",
            dictionary, "b64aaa82c56c63d474578c6c5b3ab564a355153d9d1f87f960c310f44043c795", 715144)
        data = json.loads(raw)
        require((data["version"], data["base"], data["base_tree"], data["dictionary"], data["tree"])
                == (1, BASE, BASE_TREE, BASE_DICT, TREE), "incorrect patch identity")
        names, plan = set(), []
        require(len(data["changes"]) == 95, "incorrect patch size")
        for name, content in data["changes"]:
            path = PurePosixPath(name)
            require(name not in names and not path.is_absolute() and
                    all(p not in ("", ".", "..", ".git") for p in name.split("/")) and
                    "\\" not in name and ":" not in name, "unsafe or duplicate patch path")
            names.add(name)
            target = root
            for part in path.parts:
                target /= part
                require(not target.is_symlink(), "linked patch destination")
            require(content is None or isinstance(content, str) and len(content.encode()) <= 2_000_000,
                    "invalid patch content")
            plan.append((target, None if content is None else content.encode("utf-8")))
        for target, content in plan:
            if content is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        for name in CARRIERS:
            (root / name).unlink()
        (root / ".github/migration").rmdir()
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        require(git(root, "write-tree").decode().strip() == TREE, "final Git tree differs from local verification")
        print(json.dumps({"base": BASE, "tree": TREE, "changed_files": 95,
                          "carrier_removed": True, "committed": False, "pushed": False}))


if __name__ == "__main__":
    require(os.environ.get("GITHUB_REPOSITORY") == "tigerwits/scir" and
            os.environ.get("GITHUB_REF") == "refs/heads/migration/scir-owned-knowledge",
            "transport is restricted to the approved migration branch")
    apply(Path.cwd())
