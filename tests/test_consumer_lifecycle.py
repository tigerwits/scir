"""Independent consumer cases: representation is not policy or authentic evidence."""
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scir import Term, parse_document
from scir.changes import ConflictError, propose
from scir.knowledge import build_index, select
from scir.notation import lower
from scir import profile as p

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/consumer-lifecycle"
# The example is deliberately not a runtime package or dynamically loaded rule file.
spec = importlib.util.spec_from_file_location("lifecycle_policy_fixture", EXAMPLE / "policy.py")
POLICY = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = POLICY
spec.loader.exec_module(POLICY)


def request(index, *operations):
    return json.dumps({"version": "scir-change/1", "collection": index.collection,
                       "expected_snapshot": index.snapshot, "operations": list(operations)})


def field(identifier, name, value):
    return {"op": "setField", "id": identifier, "field": name, "value": value}


def ready(index):
    return request(index, field("T", "decision", '"scir.ref"(D2)'),
                   field("T", "dependsOn", '"scir.tuple"("scir.ref"(D2), "scir.ref"(R))'),
                   field("T", "status", "ready"))


class ConsumerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.raw = (EXAMPLE / "notes.scir").read_bytes()
        self.index = build_index(parse_document(self.raw.decode()), collection="fixture")
        d1 = "5c328c9539d7659cd4402276c04d1453a3294d5ce6efea8e093f26dd0a69d813"
        d2 = "134bd2902f8286076d40ee0368cc7c829f4f6228b84615dd8ec952eade1f2184"
        self.trusted = POLICY.TrustedInputs(frozenset((d1, d2)), {
            "testReceipt": POLICY.Receipt(d2, "test", POLICY.STAGING, "passed"),
            "deliveryReceipt": POLICY.Receipt(d2, "delivery", POLICY.STAGING, "completed")})

    def candidate(self, *operations):
        value = propose(self.index, request(self.index, *operations))
        return build_index(value.document, collection=self.index.collection)

    def test_permitted_ready_and_completed_candidates_keep_unrelated_records(self):
        POLICY.check(self.index, self.trusted)
        proposed = POLICY.propose_checked(self.index, ready(self.index), self.trusted)
        index = build_index(proposed.document, collection="fixture")
        POLICY.check(index, self.trusted)
        finish = request(index, field("T", "status", "completed"),
                         field("T", "evidence", '"scir.tuple"("scir.ref"(Etest), "scir.ref"(Edelivery))'))
        final = POLICY.propose_checked(index, finish, self.trusted)
        self.assertEqual(dict(build_index(final.document, collection="fixture").records["T"].fields)["status"], Term("completed"))
        self.assertEqual(final.document[:5], self.index.document[:5])
        self.assertEqual(final.document[-1], self.index.document[-1])
        with self.assertRaises(ConflictError):
            POLICY.propose_checked(index, ready(self.index), self.trusted)
        self.assertEqual((EXAMPLE / "notes.scir").read_bytes(), self.raw)

    def test_generic_validity_does_not_accept_swapped_roles_lost_scope_or_dependencies(self):
        cases = [
            {"op": "replacePayload", "id": "T", "value": 'send(doc, "scir.kw"(from(bob), to(alice)))'},
            {"op": "removeField", "id": "T", "field": "scope"},
            field("T", "scope", '"scir.tuple"(environment(production))'),
            field("T", "dependsOn", '"scir.tuple"'),
            field("T", "status", "ready"),
            field("D2", "reason", '"scir.text"("changed approved decision")'),
        ]
        for operation in cases:
            candidate = self.candidate(operation)  # Generic working/1 accepts the shape.
            with self.subTest(operation=operation), self.assertRaises(p.ProfileError):
                POLICY.check(candidate, self.trusted)

    def test_recovery_original_key_and_order_are_consumer_rules(self):
        for value in (
            'when(ambiguous(submission), require(before(lookup(newKey), retry(originalKey))))',
            'when(ambiguous(submission), require(before(retry(originalKey), lookup(originalKey))))',
        ):
            candidate = self.candidate({"op": "replacePayload", "id": "R", "value": value})
            with self.assertRaisesRegex(POLICY.PolicyError, "recovery"):
                POLICY.check(candidate, self.trusted)

    def test_represented_evidence_cannot_fabricate_a_trusted_receipt(self):
        ready_index = build_index(propose(self.index, ready(self.index)).document, collection="fixture")
        POLICY.check(ready_index, self.trusted)
        with self.assertRaises(POLICY.PolicyError):
            POLICY.check(ready_index, POLICY.TrustedInputs(frozenset(), self.trusted.receipts))
        with self.assertRaises(POLICY.PolicyError):
            POLICY.check(ready_index, POLICY.TrustedInputs(self.trusted.approved_decisions, {}))
        for changed in (replace(self.trusted.receipts["testReceipt"], outcome="failed"),
                        replace(self.trusted.receipts["testReceipt"], decision_snapshot="0" * 64),
                        replace(self.trusted.receipts["testReceipt"], scope=Term("production"))):
            receipts = dict(self.trusted.receipts, testReceipt=changed)
            with self.assertRaises(POLICY.PolicyError):
                POLICY.check(ready_index, POLICY.TrustedInputs(self.trusted.approved_decisions, receipts))
        fake = request(ready_index, field("Etest", "receipt", "inventedReceipt"))
        with self.assertRaises(POLICY.PolicyError):
            POLICY.propose_checked(ready_index, fake, self.trusted)
        unsupported = request(ready_index, field("T", "status", "completed"))
        with self.assertRaisesRegex(POLICY.PolicyError, "delivery receipt"):
            POLICY.propose_checked(ready_index, unsupported, self.trusted)

    def test_effective_state_reports_competing_cycles_scope_and_unapproved(self):
        cases = [
            ('record(A, Decision, p, status: approved, scope: (environment(staging),))\n'
             'record(B, Decision, p, status: approved, scope: (environment(staging),), supersedes: (&A,))', "resolved", ("B",)),
            ('record(A, Decision, p, status: approved, scope: (environment(staging),))\n'
             'record(B, Decision, p, status: proposed, scope: (environment(staging),), supersedes: (&A,))', "unapproved", ("B",)),
            ('record(A, Decision, p, status: approved, scope: (environment(staging),))\n'
             'record(B, Decision, p, status: approved, scope: (environment(staging),), supersedes: (&A,))\n'
             'record(C, Decision, p, status: approved, scope: (environment(staging),), supersedes: (&A,))', "competing", ("B", "C")),
            ('record(A, Decision, p, status: approved, scope: (environment(staging),), supersedes: (&B,))\n'
             'record(B, Decision, p, status: approved, scope: (environment(staging),), supersedes: (&A,))', "cycle", ("A", "B")),
            ('record(A, Decision, p, status: approved, scope: (environment(staging),))\n'
             'record(B, Decision, p, status: approved, scope: (environment(production),), supersedes: (&A,))', "scope-mismatch", ("A", "B")),
        ]
        for source, status, ids in cases:
            index = build_index(lower(source), collection="history")
            with self.subTest(status=status):
                self.assertEqual(POLICY.effective(index, "A"), POLICY.Resolution(status, ids))
                self.assertEqual(index.document, lower(source))
        self.assertEqual(select(self.index, ("D1",)).selected_ids, ("D1",))
        self.assertEqual(POLICY.effective(self.index, "D1"), POLICY.Resolution("resolved", ("D2",)))

    def test_resolution_and_policy_bounds_are_explicit(self):
        with self.assertRaises(POLICY.PolicyError):
            POLICY.effective(self.index, "Unknown")
        with self.assertRaises(POLICY.PolicyError):
            POLICY.effective(self.index, "N")
        many = build_index(tuple(Term("record", (Term("N" + str(i)), Term("Note"), Term("p")))
                                 for i in range(257)), collection="large")
        for call in (lambda: POLICY.effective(many, "N0"), lambda: POLICY.check(many, self.trusted)):
            with self.assertRaises(p.LimitError):
                call()
        receipts = dict(self.trusted.receipts)
        detached = POLICY.TrustedInputs(self.trusted.approved_decisions, receipts)
        receipts.clear()
        self.assertEqual(len(detached.receipts), 2)
        with self.assertRaises(TypeError):
            detached.receipts["new"] = None

    def test_relocated_example_runs_without_writes_or_external_services(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "consumer"
            shutil.copytree(EXAMPLE, target)
            before = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
            for flags in ((), ("-O",)):
                result = subprocess.run([sys.executable, *flags, str(target / "run.py")], cwd=temp,
                                        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                        capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["resolved_id"], "D2")
                self.assertEqual(report["final_status"], "completed")
                self.assertEqual(report["rejected"], ["stale-decision-link", "unsupported-completion", "stale-snapshot"])
                self.assertEqual(report["service_calls"], 0)
                self.assertEqual(report["agent_trials"], 0)
                self.assertFalse(report["source_written"])
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()})
