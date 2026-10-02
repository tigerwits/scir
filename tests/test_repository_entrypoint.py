"""Real maintenance entrypoint checks against the complete repository."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from spec.repository import SOURCES, load
from spec import handoff

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, str(ROOT / "spec/check.py"), *args],
                          cwd=ROOT, capture_output=True, timeout=30)


class RepositoryEntrypointTests(unittest.TestCase):
    def test_default_and_selected_context_share_the_full_source_snapshot(self):
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"54 repository records", result.stdout)
        result = run("knowledge", "select", "--id", "NamedRoles")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["source_snapshot"], load(ROOT).snapshot)
        self.assertEqual(packet["repository_contract"], "scir-repository/1")
        self.assertTrue(packet["complete"])
        self.assertIn("ModelProofBoundary", packet["selected_ids"])
        self.assertIn("SPEC.md", packet["input_basis"]["files"])
        result = run("knowledge", "select", "--id", "MissingRecord")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(json.loads(result.stderr)["status"], "rejected")

    def test_checked_proposal_and_stale_rejection_do_not_write_source(self):
        before = {name:(ROOT / name).read_bytes() for name in SOURCES}
        index = load(ROOT)
        basis = handoff.capture(ROOT, index, SOURCES).fingerprint
        request = {"version":"scir-change/1", "collection":index.collection,
                   "expected_snapshot":index.snapshot, "operations":[
                       {"op":"setField", "id":"NamedRoles", "field":"reason", "value":"reviewed"}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            result = run("knowledge", "propose", "--basis", basis, "--change", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            proposal = json.loads(result.stdout)
            self.assertEqual(proposal["before_snapshot"], index.snapshot)
            self.assertNotEqual(proposal["candidate_snapshot"], index.snapshot)
            self.assertEqual(len(proposal["records"]), 54)
            self.assertEqual([w["path"] for w in proposal["write_plan"]], ["spec/knowledge.scir"])
            request["expected_snapshot"] = "0" * 64
            path.write_text(json.dumps(request), encoding="utf-8")
            result = run("knowledge", "propose", "--basis", basis, "--change", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
        self.assertEqual(before, {name:(ROOT / name).read_bytes() for name in SOURCES})
