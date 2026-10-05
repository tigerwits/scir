"""Actual repository views retain complete basis and source-owned plan artifacts."""
import hashlib
import io
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scir.notation import lower
from spec import repository, handoff, delivery
from test_repository_handoff import fixture, request

ROOT = Path(__file__).resolve().parents[1]


class RepositoryDeliveryTests(unittest.TestCase):
    def test_cli_selection_and_artifact_reject_changed_authoritative_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = fixture(root)
            for source in (ROOT / "spec").glob("*.py"):
                shutil.copyfile(source, root / "spec" / source.name)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            args = [sys.executable, str(root / "spec/check.py"), "knowledge", "select", "--id", "D"]
            def run(*flags):
                return subprocess.run(args + list(flags), cwd=root, env=env, capture_output=True, timeout=15)
            full = run()
            compact = run("--view", "compact", "--encoding", "notation")
            self.assertEqual(full.returncode, 0, full.stderr)
            self.assertEqual(compact.returncode, 0, compact.stderr)
            original, packet = json.loads(full.stdout), json.loads(compact.stdout)
            self.assertEqual(lower(packet["content"]), (index.records["D"].term,))
            self.assertEqual(packet["guards"]["input_basis"], original["input_basis"]["digest"])
            artifact = run("--view", "artifact", "--expected-artifact", packet["artifact"]["sha256"])
            self.assertEqual(artifact.returncode, 0, artifact.stderr)
            self.assertEqual(hashlib.sha256(artifact.stdout).hexdigest(), packet["artifact"]["sha256"])
            self.assertEqual(json.loads(artifact.stdout)["value"], original)
            authority = root / "docs/contract.md"
            authority.write_bytes(b"# Policy\nDelivery is forbidden.\n")
            self.assertEqual(repository.load(root).snapshot, index.snapshot)
            stale = run("--view", "artifact", "--expected-artifact", packet["artifact"]["sha256"])
            self.assertEqual(stale.returncode, 1)
            self.assertEqual(stale.stdout, b"")
            self.assertEqual(json.loads(stale.stderr)["status"], "conflict")
            wrong = run("--encoding", "notation")
            self.assertEqual(wrong.returncode, 1)
            self.assertEqual(wrong.stdout, b"")

    def test_cli_proposal_retains_commit_basis_and_complete_write_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = fixture(root)
            for source in (ROOT / "spec").glob("*.py"):
                shutil.copyfile(source, root / "spec" / source.name)
            basis = handoff.capture(root, index, repository.sources(root))
            change = root / "request.json"
            change.write_text(request(index, [{"op": "setField", "id": "D", "field": "reason",
                                              "value": '"scir.text"("reviewed fixture")'}]), encoding="utf-8")
            before = {name: (root / name).read_bytes() for name in repository.sources(root)}
            args = [sys.executable, str(root / "spec/check.py"), "knowledge", "propose",
                    "--change", str(change), "--basis", basis.fingerprint]
            def run(*flags):
                return subprocess.run(args + list(flags), cwd=root,
                                      env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                      capture_output=True, timeout=15)
            compact = run("--view", "compact")
            self.assertEqual(compact.returncode, 0, compact.stderr)
            packet = json.loads(compact.stdout)
            self.assertFalse(packet["context_complete"])
            self.assertFalse(packet["source_written"])
            self.assertEqual(packet["guards"], {"input_basis": basis.fingerprint, "commit_basis": basis.fingerprint})
            artifact = run("--view", "artifact", "--expected-artifact", packet["artifact"]["sha256"])
            self.assertEqual(artifact.returncode, 0, artifact.stderr)
            full = json.loads(run().stdout)
            self.assertEqual(json.loads(artifact.stdout)["value"], full)
            self.assertEqual([entry["path"] for entry in full["write_plan"]], ["spec/knowledge.scir"])
            self.assertEqual(hashlib.sha256(artifact.stdout).hexdigest(), packet["artifact"]["sha256"])
            self.assertEqual(before, {name: (root / name).read_bytes() for name in repository.sources(root)})

    def test_delivery_is_inside_the_repository_recapture_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            original = delivery.present
            def changed(index, result, **kwargs):
                value = original(index, result, **kwargs)
                (root / "docs/contract.md").write_bytes(b"# Policy\nChanged during presentation.\n")
                return value
            out, err = io.StringIO(), io.StringIO()
            loader = repository.load
            with patch.object(repository, "ROOT", root), patch.object(repository, "load", lambda: loader(root)), \
                    patch.object(delivery, "present", side_effect=changed), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = repository.main(["select", "--id", "D", "--view", "compact"])
            self.assertEqual(code, 1)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(json.loads(err.getvalue())["status"], "conflict")

    def test_native_capacity_failure_remains_incomplete_at_presentation(self):
        from scir import digest, Term
        from scir import profile as p
        from scir.knowledge import build_index
        document = (p.application("record", (Term("A"), Term("Note"), p.text("x" * 2_000_000))),)
        index = build_index((), collection="x")
        result = {"collection": "x", "repository_contract": "scir-repository/2",
                  "input_basis": {"digest": "a"}, "commit_basis": {"digest": "b"},
                  "before_snapshot": index.snapshot, "candidate_snapshot": digest(document),
                  "records": [str(document[0])], "complete": True, "validation": {}}
        with self.assertRaises(p.LimitError):
            delivery.present(index, result, kind="proposal")
