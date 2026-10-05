"""Source-basis and shard ownership regressions on independent fixtures."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scir import Term, format_document, parse_document, digest
from scir import profile as p
from scir.changes import ConflictError
from spec import repository, handoff


def fixture(root):
    for name in ("spec", "docs", "tests"):
        (root / name).mkdir(exist_ok=True)
    (root / "spec/index.scir").write_text('collection("scir-repository", shard("spec/native.scir"), shard("spec/knowledge.scir"))\n', encoding="utf-8", newline="\n")
    (root / "docs/contract.md").write_bytes(b"# Policy\nDelivery is allowed.\n")
    (root / "tests/test_sample.py").write_bytes(b"import unittest\nclass Sample(unittest.TestCase):\n    def test_case(self): pass\n")
    for name, key in (("SPEC.md", "query-spec"), ("docs/api.md", "query-api")):
        (root / name).write_bytes(f"# Contract\nOutside stays.\n<!-- scir:{key}:start -->\nstale\n<!-- scir:{key}:end -->\nTail stays.\n".encode())
    native = p.application("record", (Term("R"), Term("Requirement"), Term("rule")), fields=(
        ("area", Term("Tree")), ("ownership", Term("record")), ("projection", Term("native")),
        ("source", Term("section", (Term("SPEC.md"), Term("Contract")))),
        ("tests", p.tuple_value((Term("test", (Term("tests/test_sample.py"), Term("Sample.test_case"))),))),
        ("topic", Term("Queries")), ("viewOrder", Term("0")), ("wording", p.text("Queries default to matching roots."))))
    decision = p.application("record", (Term("D"), Term("Decision"), Term("permit")), fields=(
        ("area", Term("Workflow")), ("ownership", Term("index")), ("status", Term("adopted")),
        ("source", Term("section", (Term("docs/contract.md"), Term("Policy"))))))
    (root / "spec/native.scir").write_bytes(format_document((native,)).encode())
    (root / "spec/knowledge.scir").write_bytes(format_document((decision,)).encode())
    (root / "spec/requirements.scir").write_bytes(b"old\n")
    with contextlib.redirect_stdout(io.StringIO()):
        if repository.maintenance(root) != 0:
            raise AssertionError("fixture refresh failed")
    return repository.load(root)


def request(index, operations):
    return json.dumps({"version":"scir-change/1", "collection":index.collection,
                       "expected_snapshot":index.snapshot, "operations":operations})


class RepositoryHandoffTests(unittest.TestCase):
    def test_authoritative_body_and_test_changes_invalidate_same_content_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            source = request(index, [{"op":"setField", "id":"D", "field":"reason", "value":"reviewed"}])
            for name in ("docs/contract.md", "tests/test_sample.py"):
                before = handoff.capture(root, index, repository.sources(root))
                path = root / name
                original = path.read_bytes()
                path.write_bytes(original.replace(b"allowed", b"forbidden") if name.endswith(".md") else original + b"# changed evidence\n")
                self.assertEqual(repository.load(root).snapshot, index.snapshot)
                with self.assertRaises(ConflictError):
                    repository.propose_handoff(index, source, before.fingerprint, root)
                path.write_bytes(original)

    def test_plan_keeps_existing_shards_and_replays_exact_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            basis = handoff.capture(root, index, repository.sources(root))
            before = {name:(root / name).read_bytes() for name in repository.sources(root)}
            source = request(index, [{"op":"setField", "id":"R", "field":"wording", "value":str(p.text("Reviewed query wording."))}])
            result = repository.propose_handoff(index, source, basis.fingerprint, root)
            self.assertEqual({w["path"] for w in result["write_plan"]}, {"spec/native.scir", *handoff.DERIVED})
            self.assertEqual(before, {name:(root / name).read_bytes() for name in before})
            for item in result["write_plan"]:
                path = root / item["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["expected_sha256"])
                path.write_bytes(item["content"].encode())  # Replay only in this temporary fixture.
            reloaded = repository.load(root)
            self.assertEqual(reloaded.snapshot, result["candidate_snapshot"])
            self.assertEqual(repository.updates(reloaded, root), [])
            self.assertEqual((root / "spec/knowledge.scir").read_bytes(), before["spec/knowledge.scir"])

    def test_create_placement_is_explicit_and_existing_ids_cannot_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            basis = handoff.capture(root, index, repository.sources(root))
            old = index.records["D"].term
            created = Term("record", (Term("E"), *old.args[1:]))
            source = request(index, [{"op":"createRecord", "record":str(created)}])
            with self.assertRaises(p.ProfileError):
                repository.propose_handoff(index, source, basis.fingerprint, root)
            result = repository.propose_handoff(index, source, basis.fingerprint, root, placements={"E":"spec/native.scir"})
            terms = tuple(parse_document(t)[0] for t in result["records"])
            self.assertEqual(tuple(t.args[0].symbol for t in terms), ("R", "E", "D"))
            self.assertEqual(digest(terms), result["candidate_snapshot"])
            self.assertNotEqual(result["runtime_candidate_snapshot"], result["candidate_snapshot"])
            with self.assertRaises(p.ProfileError):
                repository.propose_handoff(index, source, basis.fingerprint, root,
                    placements={"E":"spec/native.scir", "D":"spec/native.scir"})

    def test_observed_input_change_during_validation_yields_no_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            basis = handoff.capture(root, index, repository.sources(root))
            original = repository.validate
            def changing(document, checkout):
                result = original(document, checkout)
                (root / "docs/contract.md").write_bytes(b"# Policy\nDifferent body.\n")
                return result
            with patch.object(repository, "validate", side_effect=changing), self.assertRaises(ConflictError):
                repository.propose_handoff(index, request(index, []), basis.fingerprint, root)

    def test_unreadable_candidate_shard_is_not_a_successful_write_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            old = index.records["D"].term
            large = Term("record", old.args[:2] + (p.text("x" * 1_300_000),) + old.args[3:])
            source_path = root / "spec/knowledge.scir"
            source_path.write_bytes(format_document((large,)).encode())
            index = repository.load(root)
            basis = handoff.capture(root, index, repository.sources(root))
            change = request(index, [{"op": "setField", "id": "D", "field": "reason",
                                      "value": str(p.text("y" * 800_000))}])
            from scir.changes import propose
            self.assertTrue(propose(index, change).document)  # Generic profile accepts the candidate.
            before = source_path.read_bytes()
            with self.assertRaisesRegex(p.LimitError, "candidate repository source"):
                repository.propose_handoff(index, change, basis.fingerprint, root)
            self.assertEqual(source_path.read_bytes(), before)
