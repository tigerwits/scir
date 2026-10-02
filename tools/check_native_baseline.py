"""Verify a fixed historical checkout, not freeze the current implementation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REVISION = "3ceeb1ea9ae2c0f52a1568a1f7b611469384571c"
BLOBS = {
    "core.py": "9c6de235945901658b8fe06104eb52ac2bc64ff6",
    "patterns.py": "c5c1e8e70eb3a3b67356135e52bb30dadebccb69",
    "syntax.py": "f57ee2c4ea36e01691d7b2913ae8aa1abca4af00",
    "tree.py": "5f8b670b492e2a84545cd71291c396754d746fbc",
    "relations.py": "bdff3033b9035e71e1a0a9898b880a678514cbab",
}
MAX_BYTES = 2_000_000


def blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def verify(root: Path) -> dict:
    if root.is_symlink():
        raise ValueError("historical checkout root must not be a symlink")
    root = root.resolve()
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    if revision != REVISION:
        raise ValueError("expected the fixed historical revision, not current HEAD")
    for folder in (root / "src", root / "src/scir"):
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("historical package path must be a real directory")
    for name, expected in BLOBS.items():
        path = root / "src/scir" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing or linked historical source: " + name)
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("historical source byte limit exceeded")
        if blob_id(raw) != expected:
            raise ValueError("historical source differs from pinned Git blob: " + name)
    return {"schema": "scir-native-baseline/1", "revision": revision,
            "verified_files": len(BLOBS), "complete": True,
            "scope": "Exact bytes of five historical source files; not current implementation equivalence or correctness."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(args.checkout), sort_keys=True))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "incomplete", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
