"""Delete only reviewed branch tips reachable from the default branch; dry-run by default."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=check, timeout=60)


def api(repository, suffix):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("invalid repository")
    url = "https://api.github.com/repos/" + repository + suffix
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(4_000_001)
    if len(data) > 4_000_000:
        raise ValueError("API response bound exceeded")
    return json.loads(data)


def pages(repository, collection):
    result = []
    for page in range(1, 101):
        separator = "&" if "?" in collection else "?"
        chunk = api(repository, collection + separator + f"per_page=100&page={page}")
        if type(chunk) is not list:
            raise ValueError("expected a complete paginated collection")
        result.extend(chunk)
        if len(chunk) < 100:
            return result
    raise ValueError("pagination bound exceeded")


def eligible(name, expected, actual, default, protected, open_heads, ancestor):
    if name == default or name in ("main", "master"):
        return "default-or-primary"
    if protected:
        return "protected"
    if name in open_heads:
        return "open-pull-request"
    if actual != expected:
        return "tip-changed"
    if not ancestor(expected):
        return "not-merged"
    return None


def delete_tip(root, name, expected):
    git(root, "check-ref-format", "refs/heads/" + name)
    # This is a compare-and-delete lease, never a branch update or history rewrite.
    git(root, "push", "--porcelain", "--force-with-lease=refs/heads/" + name + ":" + expected,
        "origin", ":refs/heads/" + name)


def run(root, manifest, *, apply=False):
    if set(manifest) != {"repository", "branches"} or type(manifest["branches"]) is not dict:
        raise ValueError("expected an explicit repository/branches manifest")
    repository = manifest["repository"]
    if os.environ.get("GITHUB_REPOSITORY") != repository:
        raise ValueError("run only for the explicitly named repository")
    default = api(repository, "")["default_branch"]
    git(root, "fetch", "--no-tags", "origin", "+refs/heads/*:refs/remotes/origin/*")
    main_tip = git(root, "rev-parse", "refs/remotes/origin/" + default).stdout.strip()
    branches = {b["name"]: b for b in pages(repository, "/branches")}
    open_heads = {p["head"]["ref"] for p in pages(repository, "/pulls?state=open")
                  if p["head"].get("repo") and p["head"]["repo"]["full_name"] == repository}
    def ancestor(tip):
        result = git(root, "merge-base", "--is-ancestor", tip, main_tip, check=False)
        if result.returncode not in (0, 1):
            raise ValueError("ancestry check did not complete")
        return result.returncode == 0
    report = []
    for name, expected in manifest["branches"].items():
        if type(name) is not str or type(expected) is not str or not re.fullmatch(r"[0-9a-f]{40}", expected):
            raise ValueError("manifest needs exact Git commit tips")
        git(root, "check-ref-format", "refs/heads/" + name)
        current = branches.get(name)
        if current is None:
            report.append({"branch": name, "status": "already-absent"})
            continue
        reason = eligible(name, expected, current["commit"]["sha"], default,
                          current.get("protected") is not False, open_heads, ancestor)
        if reason:
            report.append({"branch": name, "status": "preserved", "reason": reason})
            continue
        if apply:
            delete_tip(root, name, expected)
        report.append({"branch": name, "tip": expected, "status": "deleted" if apply else "would-delete"})
    return {"repository": repository, "default_tip": main_tip, "apply": apply, "branches": report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate manifest key")
            obj[key] = value
        return obj
    with args.manifest.open("rb") as stream:
        raw = stream.read(64_001)
    if len(raw) > 64_000:
        raise ValueError("manifest exceeds bound")
    manifest = json.loads(raw, object_pairs_hook=unique)
    print(json.dumps(run(Path.cwd(), manifest, apply=args.apply), indent=2))


if __name__ == "__main__":
    main()
