"""Actual repository subprocess responses, not synthesized scenario outcomes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import scir
from spec import repository
from test_repository_handoff import fixture, request

ROOT = Path(__file__).resolve().parents[1]


class RepositoryCliReviewTests(unittest.TestCase):
    def invoke(self, root, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
        return subprocess.run([sys.executable, str(root / "spec/check.py"), "knowledge", *args],
                              cwd=root, env=env, capture_output=True, timeout=20)

    def prepare(self, root):
        index = fixture(root)
        for path in (ROOT / "spec").glob("*.py"):
            shutil.copyfile(path, root / "spec" / path.name)
        result = self.invoke(root, "select", "--id", "D")
        self.assertEqual(result.returncode, 0, result.stderr)
        return index, json.loads(result.stdout)["input_basis"]["digest"]

    def test_subprocess_failure_matrix_and_no_source_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, basis = self.prepare(root)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            cases = [("f(", 1, "rejected"),
                     ("f(" * 130 + "a" + ")" * 130, 2, "incomplete"),
                     ('section("docs/missing.md", Policy)', 1, "rejected")]
            change = root / "change.json"
            for value, code, status in cases:
                field = "source" if value.startswith("section") else "reason"
                change.write_text(request(index, [{"op":"setField", "id":"D", "field":field, "value":value}]), encoding="utf-8")
                result = self.invoke(root, "propose", "--basis", basis, "--change", str(change))
                self.assertEqual((result.returncode, result.stdout), (code, b""), result.stderr)
                diagnostic = json.loads(result.stderr)
                self.assertEqual((diagnostic["status"], diagnostic["complete"]), (status, code == 1))
            result = self.invoke(root, "propose", "--basis", basis, "--change", str(root / "absent.json"))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stderr)["status"], "incomplete")
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_subprocess_rejects_old_basis_after_authoritative_body_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, basis = self.prepare(root)
            change = root / "change.json"
            change.write_text(request(index, [{"op":"setField", "id":"D", "field":"reason", "value":"reviewed"}]), encoding="utf-8")
            (root / "docs/contract.md").write_bytes(b"# Policy\nDelivery is forbidden.\n")
            result = self.invoke(root, "propose", "--basis", basis, "--change", str(change))
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual(json.loads(result.stderr)["status"], "conflict")
            fresh = self.invoke(root, "select", "--id", "D")
            new_basis = json.loads(fresh.stdout)["input_basis"]["digest"]
            self.assertNotEqual(new_basis, basis)
            result = self.invoke(root, "propose", "--basis", new_basis, "--change", str(change))
            self.assertEqual(result.returncode, 0, result.stderr)
            proposal = json.loads(result.stdout)
            self.assertFalse(proposal["source_written"])
            self.assertEqual([w["path"] for w in proposal["write_plan"]], ["spec/knowledge.scir"])

    def test_invalid_candidate_link_shape_is_rejected_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, basis = self.prepare(root)
            change = root / "change.json"
            change.write_text(request(index, [{"op":"removeField", "id":"D", "field":"source"}]), encoding="utf-8")
            result = self.invoke(root, "propose", "--basis", basis, "--change", str(change))
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual(json.loads(result.stderr)["status"], "rejected")
