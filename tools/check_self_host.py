#!/usr/bin/env python3
"""Exercise real repository handoffs on an isolated copy, never the input checkout."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

import scir

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root=ROOT):
    root = Path(root).resolve()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
    observations = []

    def invoke(checkout, *args, expected=0, json_output=True):
        result = subprocess.run([sys.executable, str(checkout / "spec/check.py"), *args],
                                cwd=checkout, env=env, capture_output=True, timeout=30)
        observations.append({"args": list(args), "exit": result.returncode,
                             "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr)})
        require(result.returncode == expected, result.stderr.decode("utf-8", "replace"))
        if expected:
            require(result.stdout == b"", "failure emitted success output")
        return json.loads(result.stderr if expected else result.stdout) if json_output else None

    initial = invoke(root, "knowledge", "select", "--id", "NamedRoles")
    hashes = initial["input_basis"]["files"]
    with tempfile.TemporaryDirectory(prefix="scir-self-host-") as temp:
        scratch = Path(temp) / "checkout"
        shutil.copytree(root, scratch, ignore=shutil.ignore_patterns(
            ".git", ".build", "build", "dist", "__pycache__", "*.egg-info", ".venv"))
        packet = invoke(scratch, "knowledge", "select", "--id", "NamedRoles")
        require(packet["input_basis"] == initial["input_basis"], "copy changed the maintenance basis")
        require({"NamedRoles", "TupleArity", "ModelProofBoundary"} <= set(packet["selected_ids"]),
                "selected context omitted a governing rule or limitation")
        request = {"version": "scir-change/1", "collection": packet["collection"],
                   "expected_snapshot": packet["source_snapshot"], "operations": [
                       {"op": "setField", "id": "NamedRoles", "field": "reason",
                        "value": '"scir.text"("Self-host fixture; not an adopted design change.")'}]}
        request_path = Path(temp) / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        proposal = invoke(scratch, "knowledge", "propose", "--basis", packet["input_basis"]["digest"],
                          "--change", str(request_path))
        require(proposal["source_written"] is False, "proposal claims persistence")
        require([entry["path"] for entry in proposal["write_plan"]] == ["spec/knowledge.scir"],
                "narrow update crossed its source ownership")
        # Change authoritative prose without changing its heading or SCIR record.
        authority = scratch / "docs/structured-profiles.md"
        authority.write_bytes(authority.read_bytes() + b"\n<!-- isolated self-host fixture -->\n")
        failure = invoke(scratch, "knowledge", "propose", "--basis", packet["input_basis"]["digest"],
                         "--change", str(request_path), expected=1)
        require(failure["status"] == "conflict", "authoritative change did not invalidate the basis")
        fresh = invoke(scratch, "knowledge", "select", "--id", "NamedRoles")
        require(fresh["source_snapshot"] == packet["source_snapshot"], "fixture changed SCIR content")
        require(fresh["input_basis"]["digest"] != packet["input_basis"]["digest"], "file basis unchanged")
        # The test knows the exact hypothetical prose change; a real agent must review it.
        candidate = invoke(scratch, "knowledge", "propose", "--basis", fresh["input_basis"]["digest"],
                           "--change", str(request_path))
        for name, expected_hash in candidate["commit_basis"]["files"].items():
            require(fingerprint(scratch / name) == expected_hash, "commit basis changed in fixture")
        for entry in candidate["write_plan"]:
            name = PurePosixPath(entry["path"])
            require(not name.is_absolute() and ".." not in name.parts, "invalid fixture destination")
            path = scratch / name
            require(not path.is_symlink() and fingerprint(path) == entry["expected_sha256"],
                    "write precondition changed")
            raw = entry["content"].encode("utf-8")
            require(hashlib.sha256(raw).hexdigest() == entry["sha256"], "candidate bytes changed")
        # Sequential replay is safe only in this exclusively owned disposable copy.
        for entry in candidate["write_plan"]:
            (scratch / entry["path"]).write_bytes(entry["content"].encode("utf-8"))
        invoke(scratch, json_output=False)
        final = invoke(scratch, "knowledge", "select", "--id", "NamedRoles")
        require(final["source_snapshot"] == candidate["candidate_snapshot"], "replay differs from candidate")
    require(all(fingerprint(root / name) == value for name, value in hashes.items()),
            "original maintenance inputs changed")
    return {"example": "scir-self-host/1", "complete": True, "source_written": False,
            "scratch_replay": True, "agent_trials": 0, "observations": observations,
            "input_basis": initial["input_basis"]["digest"],
            "scope": "Deterministic real-repository scenario; temporary replay is not a storage transaction."}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
