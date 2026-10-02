"""Delivery preserves content/guards and costs; a delta is never full context."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scir import Term, digest, format_document, parse_document
from scir import delivery, profile as p
from scir.changes import ConflictError, propose
from scir.knowledge import build_index, select
from scir.notation import Limits as NotationLimits, lower


def request(index, *operations):
    return json.dumps({"version": "scir-change/1", "collection": index.collection,
                       "expected_snapshot": index.snapshot, "operations": list(operations)})


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.document = lower('record(A, Assumption, t"unknown", status: unverified)\n'
                              'record(T, Task, send(doc, from: alice, to: bob), dependsOn: (&A,), '
                              'scope: (environment(staging),), evidence: (&A,), status: blocked)\n'
                              'record(U, Note, t"unrelated")')
        self.index = build_index(self.document, collection="example")

    def test_whole_selection_in_both_encodings_and_exact_artifact_binding(self):
        for encoding in ("native", "notation"):
            result = delivery.selection(self.index, ("T",), encoding=encoding, guards=(("basis", "abc"),))
            packet, artifact = json.loads(result.packet), json.loads(result.artifact)
            decoder = parse_document if encoding == "native" else lower
            self.assertEqual(decoder(packet["content"]), self.document[:2])
            self.assertEqual(packet["source_snapshot"], self.index.snapshot)
            self.assertEqual(packet["guards"], {"basis": "abc"})
            self.assertEqual(artifact["value"], select(self.index, ("T",)).as_dict())
            self.assertEqual(artifact["guards"], packet["guards"])
            self.assertEqual(packet["artifact"]["bytes"], len(result.artifact.encode()))
            self.assertEqual(packet["artifact"]["sha256"], hashlib.sha256(result.artifact.encode()).hexdigest())
            self.assertEqual(result.checked_artifact(packet["artifact"]["sha256"]), result.artifact)
            changed_guard = delivery.selection(self.index, ("T",), encoding=encoding, guards=(("basis", "def"),))
            with self.assertRaises(ConflictError):
                changed_guard.checked_artifact(packet["artifact"]["sha256"])
        self.assertEqual(self.index.document, self.document)

    def test_compact_budget_is_separate_but_full_artifact_must_fit(self):
        source = tuple(Term("record", (Term("R" + str(i)), Term("Note"), Term("p"))) for i in range(100))
        index = build_index(source, collection="x")
        ids = tuple(index.records)
        result = delivery.selection(index, ids)
        packet_bytes, artifact_bytes = len(result.packet.encode()), len(result.artifact.encode())
        legacy_bytes = len((json.dumps(select(index, ids).as_dict(), ensure_ascii=False,
                                      separators=(",", ":")) + "\n").encode())
        self.assertLess(packet_bytes, legacy_bytes)
        with self.assertRaises(p.LimitError):
            select(index, ids, limits=p.Limits(bytes=packet_bytes))
        self.assertEqual(delivery.selection(index, ids, max_packet_bytes=packet_bytes), result)
        for options in ({"max_packet_bytes": packet_bytes - 1}, {"max_artifact_bytes": artifact_bytes - 1}):
            with self.subTest(options=options), self.assertRaises(p.LimitError):
                delivery.selection(index, ids, **options)
        self.assertGreater(packet_bytes + artifact_bytes, legacy_bytes)  # A fetch is not free.

    def test_delta_matches_full_candidate_and_retains_deleted_ids(self):
        change = request(self.index,
                         {"op": "setField", "id": "T", "field": "status", "value": "ready"},
                         {"op": "deleteRecord", "id": "U"},
                         {"op": "createRecord", "record": 'record(New, Note, p)'})
        full = propose(self.index, change)
        result = delivery.proposal(self.index, change, encoding="notation")
        packet, artifact = json.loads(result.packet), json.loads(result.artifact)
        self.assertEqual(artifact["value"], full.as_dict())
        self.assertEqual(packet["deleted_ids"], ["U"])
        self.assertEqual(packet["content_scope"], "changed-records")
        self.assertFalse(packet["context_complete"])
        delta = lower(packet["content"])
        self.assertEqual(tuple(t.args[0].symbol for t in delta), ("T", "New"))
        self.assertEqual((self.document[0],) + delta, full.document)
        self.assertEqual(packet["candidate_snapshot"], digest(full.document))
        self.assertEqual(packet["before_snapshot"], self.index.snapshot)
        no_op = delivery.proposal(self.index, request(self.index))
        self.assertEqual(json.loads(no_op.packet)["content"], "")
        self.assertEqual(self.index.document, self.document)

    def test_proposals_keep_full_validation_and_legacy_response_unchanged(self):
        invalid = request(self.index, {"op": "deleteRecord", "id": "A"})
        with self.assertRaises(p.ProfileError):
            delivery.proposal(self.index, invalid)
        valid = request(self.index, {"op": "replacePayload", "id": "U", "value": "q"})
        full = propose(self.index, valid)
        result = delivery.proposal(self.index, valid)
        self.assertEqual(json.loads(result.artifact)["value"], full.as_dict())
        with self.assertRaises(ConflictError):
            delivery.proposal(build_index(full.document, collection="example"), valid)
        n = len(result.artifact.encode())
        with self.assertRaises(p.LimitError):
            delivery.proposal(self.index, valid, max_artifact_bytes=n - 1)

    def test_bad_guards_capacity_and_unknown_ids_fail_explicitly(self):
        for options in ({"guards": (("basis", "a"), ("basis", "b"))}, {"guards": []},
                        {"guards": (("basis", False),)}, {"encoding": "guess"},
                        {"max_packet_bytes": True}, {"notation_limits": None}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                delivery.selection(self.index, ("T",), **options)
        with self.assertRaises(p.LimitError):
            delivery.selection(self.index, ("T",), encoding="notation", notation_limits=NotationLimits(source_bytes=1))
        with self.assertRaises(p.ProfileError):
            delivery.selection(self.index, ("Missing",))

    def test_actual_cli_delivers_hash_checked_artifact_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "notes.scir"
            source.write_text(format_document(self.document), encoding="utf-8")
            original = source.read_bytes()
            args = [sys.executable, "-m", "scir", "knowledge", "select", str(source),
                    "--collection", "example", "--id", "T"]
            def run(*flags):
                return subprocess.run(args + list(flags), capture_output=True, timeout=15)
            compact = run("--view", "compact", "--encoding", "notation")
            self.assertEqual(compact.returncode, 0, compact.stderr)
            packet = json.loads(compact.stdout)
            sha = packet["artifact"]["sha256"]
            artifact = run("--view", "artifact", "--encoding", "notation", "--expected-artifact", sha)
            self.assertEqual(artifact.returncode, 0, artifact.stderr)
            self.assertEqual(hashlib.sha256(artifact.stdout).hexdigest(), sha)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(json.loads(run().stdout), select(self.index, ("T",)).as_dict())
            for flags in (("--view", "artifact"), ("--encoding", "notation")):
                bad = run(*flags)
                self.assertEqual(bad.returncode, 1)
                self.assertEqual(bad.stdout, b"")
            source.write_bytes(original.replace(b"unrelated", b"changed"))
            stale = run("--view", "artifact", "--expected-artifact", sha)
            self.assertEqual(stale.returncode, 1)
            self.assertEqual(stale.stdout, b"")
            self.assertEqual(json.loads(stale.stderr)["error"], "conflict")

    def test_guard_and_native_reader_budgets_are_explicit(self):
        for guards in (tuple((str(i), "x") for i in range(129)), (("x", "é" * 32_000),)):
            with self.assertRaises(p.LimitError):
                delivery.selection(self.index, ("T",), guards=guards)
        large = build_index((p.application("record", (Term("A"), Term("Note"),
                                                       p.text("x" * 2_000_000))),), collection="large")
        with self.assertRaises(p.LimitError):
            delivery.selection(large, ("A",))
        with self.assertRaises(ValueError):
            delivery.selection(self.index, ("T",)).checked_artifact("not-a-hash")

    def test_actual_proposal_cli_keeps_candidate_artifact_and_stale_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, change = root / "notes.scir", root / "change.json"
            source.write_text(format_document(self.document), encoding="utf-8")
            update = request(self.index, {"op": "setField", "id": "T", "field": "reason",
                                          "value": str(p.text("é\nreviewed"))})
            change.write_text(update, encoding="utf-8")
            args = [sys.executable, "-m", "scir", "knowledge", "propose", str(source),
                    "--collection", "example", "--change", str(change)]
            def run(*flags):
                return subprocess.run(args + list(flags), capture_output=True, timeout=15)
            compact = run("--view", "compact")
            self.assertEqual(compact.returncode, 0, compact.stderr)
            packet = json.loads(compact.stdout)
            self.assertFalse(packet["context_complete"])
            artifact = run("--view", "artifact", "--expected-artifact", packet["artifact"]["sha256"])
            self.assertEqual(artifact.returncode, 0, artifact.stderr)
            self.assertEqual(json.loads(artifact.stdout)["value"], propose(self.index, update).as_dict())
            self.assertEqual(hashlib.sha256(artifact.stdout).hexdigest(), packet["artifact"]["sha256"])
            self.assertEqual(json.loads(run().stdout), propose(self.index, update).as_dict())
            source.write_bytes(source.read_bytes().replace(b"unrelated", b"updated"))
            stale = run("--view", "compact")
            self.assertEqual(stale.returncode, 1)
            self.assertEqual(stale.stdout, b"")
            self.assertEqual(json.loads(stale.stderr)["error"], "conflict")
