"""The repository uses working records without weakening legacy conformance."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from scir import digest, format_document
from spec import repository
from test_repository_knowledge import fixture, record
from test_native_projection import native_record


def prepare(root):
    fixture(root)
    for name, key in (("SPEC.md", "query-spec"), ("docs/api.md", "query-api")):
        (root / name).write_text(f"# Public\n\nOutside stays.\n<!-- scir:{key}:start -->\nstale\n<!-- scir:{key}:end -->\nTail stays.\n", encoding="utf-8", newline="\n")
    (root / "spec/native.scir").write_text(format_document((native_record(),)), encoding="utf-8", newline="\n")
    (root / "spec/knowledge.scir").write_text("", encoding="utf-8", newline="\n")
    (root / "spec/requirements.scir").write_text("old\n", encoding="utf-8", newline="\n")


def request(index, operations):
    return json.dumps({"version":"scir-change/1", "collection":index.collection,
                       "expected_snapshot":index.snapshot, "operations":operations})


class RepositoryWorkflowTests(unittest.TestCase):
    def test_refresh_is_explicit_idempotent_and_preserves_source_and_outer_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            sources = {name:(root / name).read_bytes() for name in repository.SOURCES}
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(repository.maintenance(root), 1)
                self.assertEqual((root / "spec/requirements.scir").read_text(), "old\n")
                self.assertEqual(repository.maintenance(root, write_views=True), 0)
                self.assertEqual(repository.maintenance(root), 0)
            self.assertEqual(repository.updates(repository.load(root), root), [])
            for name, raw in sources.items():
                self.assertEqual((root / name).read_bytes(), raw)
            for name in ("SPEC.md", "docs/api.md"):
                self.assertTrue((root / name).read_text().startswith("# Public\n\nOutside stays.\n"))
                self.assertTrue((root / name).read_text().endswith("Tail stays.\n"))

    def test_late_preflight_failure_prevents_all_derived_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            (root / "docs/api.md").write_text("missing markers", encoding="utf-8", newline="\n")
            before = {p:p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(repository.maintenance(root, write_views=True), 2)
            self.assertEqual(before, {p:p.read_bytes() for p in before})

    def test_repository_candidate_rejects_links_accepted_by_generic_working_profile(self):
        from scir.changes import propose
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            index = repository.load(root)
            bad = request(index, [{"op":"setField", "id":"R", "field":"source",
                                   "value":'section("docs/missing.md", Rules)'}])
            self.assertNotEqual(propose(index, bad).candidate_snapshot, index.snapshot)
            with self.assertRaises(ValueError):
                repository.propose_checked(index, bad, root)
            self.assertEqual(index.snapshot, digest(index.document))

    def test_cross_shard_context_changes_invalidate_old_proposals(self):
        from scir.changes import ConflictError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            (root / "spec/knowledge.scir").write_text(format_document((record("P"),)), encoding="utf-8", newline="\n")
            index = repository.load(root)
            old_request = request(index, [{"op":"setField", "id":"R", "field":"reason", "value":"reviewed"}])
            intervening = repository.propose_checked(index, request(index, [
                {"op":"setField", "id":"P", "field":"reason", "value":"changed"}]), root)
            new_index = repository.validate(intervening.document, root)
            with self.assertRaises(ConflictError):
                repository.propose_checked(new_index, old_request, root)
            self.assertEqual(tuple(index.records), ("R", "P"))
