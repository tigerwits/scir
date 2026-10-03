"""Named validation around real consumer candidates, with independent negative cases."""
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
from unittest.mock import patch

import scir
from scir import Term, parse_document
from scir.changes import ConflictError, propose
from scir.constraints import Violation
from scir.dialects import Rule, compose, evaluate
from scir.knowledge import build_index, select
from scir import profile as p

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/consumer-lifecycle'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {name: module}):
        spec.loader.exec_module(module)
    return module


POLICY = load('policy', EXAMPLE / 'policy.py')
with patch.dict(sys.modules, {'policy': POLICY}):
    ADAPTER = load('dialect_fixture', EXAMPLE / 'dialect.py')
    RUN = load('run_fixture', EXAMPLE / 'run.py')


class DialectHandoffTests(unittest.TestCase):
    def setUp(self):
        self.document = parse_document((EXAMPLE / 'notes.scir').read_text())
        self.index = build_index(self.document, collection=RUN.COLLECTION)
        self.trusted = RUN.trusted_fixture()
        self.context = ADAPTER.context_from(self.trusted, 'revision-1')
        self.contract = ADAPTER.contract()

    def result(self, document, context=None, dialect=None):
        return evaluate(document, dialect or self.contract, context or self.context,
                        collection=self.index.collection)

    def test_named_plan_and_original_policy_agree_on_permitted_and_forbidden_changes(self):
        self.assertTrue(self.result(self.document).conforms)
        accepted, receipt = ADAPTER.propose_checked(self.index, RUN.request(self.index, RUN.ready_operations()),
            self.contract, self.context, expected_context=self.context.fingerprint)
        POLICY.check(build_index(accepted.document, collection=self.index.collection), self.trusted)
        self.assertTrue(receipt.conforms)
        cases = [
            {'op': 'setField', 'id': 'T', 'field': 'status', 'value': 'ready'},
            {'op': 'replacePayload', 'id': 'T', 'value': 'send(doc, "scir.kw"(from(bob), to(alice)))'},
            {'op': 'removeField', 'id': 'T', 'field': 'scope'},
            {'op': 'setField', 'id': 'T', 'field': 'dependsOn', 'value': '"scir.tuple"'},
            {'op': 'setField', 'id': 'D2', 'field': 'reason', 'value': '"scir.text"("unapproved change")'},
            {'op': 'replacePayload', 'id': 'R', 'value': 'retry(newKey)'},
            {'op': 'setField', 'id': 'T', 'field': 'decision', 'value': '"scir.ref"(N)'},
        ]
        for operation in cases:
            candidate = propose(self.index, RUN.request(self.index, [operation]))
            with self.subTest(operation=operation):
                with self.assertRaises(p.ProfileError):
                    POLICY.check(build_index(candidate.document, collection=self.index.collection), self.trusted)
                self.assertEqual(self.result(candidate.document).outcome, 'rejected')

    def test_invalid_working_content_does_not_execute_consumer_policy(self):
        bad = self.document + (self.document[0],)
        with patch.object(POLICY, 'check', side_effect=AssertionError('must not run')) as callback:
            result = self.result(bad)
        callback.assert_not_called()
        self.assertEqual([s.status for s in result.steps], ['passed', 'rejected', 'blocked', 'blocked', 'blocked', 'blocked'])
        self.assertEqual(result.outcome, 'rejected')

    def test_bad_external_context_is_incomplete_not_content_rejection(self):
        for context in (replace(self.context, name='other'),
                        replace(self.context, document=(Term('unknown'),)),
                        replace(self.context, document=self.context.document + (self.context.document[0],))):
            self.assertEqual(self.result(self.document, context).outcome, 'incomplete')
            with self.assertRaises(RuntimeError):
                ADAPTER.propose_checked(self.index, RUN.request(self.index, []), self.contract, context,
                                        expected_context=context.fingerprint)

    def test_changed_external_revision_and_revoked_evidence_cannot_reuse_result(self):
        prepared, receipt = ADAPTER.propose_checked(self.index, RUN.request(self.index, RUN.ready_operations()),
            self.contract, self.context, expected_context=self.context.fingerprint)
        later = replace(self.context, revision='revision-2')
        with self.assertRaises(ConflictError):
            ADAPTER.propose_checked(self.index, RUN.request(self.index, []), self.contract, later,
                                    expected_context=self.context.fingerprint)
        self.assertFalse(receipt.matches(prepared.document, self.contract, later, collection=self.index.collection))
        revoked = ADAPTER.context_from(POLICY.TrustedInputs(self.trusted.approved_decisions, {}), 'revision-2')
        self.assertEqual(self.result(prepared.document, revoked).outcome, 'rejected')

    def test_reference_closed_selection_may_fail_a_stronger_dialect(self):
        def inventory(document, context):
            if not any(t.args[0] == Term('N') for t in document):
                yield Violation(None, 'inventory', 'consumer requires its independent note')
        strict = compose('inventory-consumer', '1', self.contract, rules=(
            Rule('inventory', '1', 'c'*64, inventory, ('working',)),))
        original = self.result(self.document, dialect=strict)
        self.assertTrue(original.conforms)
        packet = select(self.index, ('D1',))
        self.assertEqual(packet.selected_ids, ('D1',))
        self.assertFalse(original.matches(packet.document, strict, self.context, collection=self.index.collection))
        self.assertEqual(self.result(packet.document, dialect=strict).outcome, 'rejected')

    def test_canonical_context_roundtrip_copies_fixed_receipt_inputs(self):
        self.assertEqual(ADAPTER._trusted(self.context), self.trusted)
        self.assertEqual(parse_document(scir.format_document(self.context.document)), self.context.document)
        with self.assertRaises(TypeError):
            POLICY.FIELDS['Note'] = frozenset()
        self.assertIsInstance(POLICY.FIELDS['Note'], frozenset)

    def test_relocated_named_runner_reports_real_results_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'example'
            shutil.copytree(EXAMPLE, target)
            before = {path.name: path.read_bytes() for path in target.iterdir() if path.is_file()}
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                       PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
            for flags in ((), ('-O',)):
                result = subprocess.run([sys.executable, *flags, str(target/'dialect_run.py')],
                    cwd=temp, env=env, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual([report[n]['outcome'] for n in ('initial','rejected','candidate','selected','incomplete')],
                                 ['accepted','rejected','accepted','accepted','incomplete'])
                self.assertTrue(report['context_conflict'])
                self.assertFalse(report['source_written'])
                self.assertEqual(report['service_calls'], 0)
                self.assertEqual(report['agent_trials'], 0)
            self.assertEqual(before, {path.name:path.read_bytes() for path in target.iterdir() if path.is_file()})

    def test_repository_uses_named_validation_on_its_fixed_input_basis(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
        result = subprocess.run([sys.executable, str(ROOT/'tools/check_dialects.py')],
                                cwd=ROOT, env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report['source_written'])
        validation = report['validation']
        self.assertEqual(validation['outcome'], 'accepted')
        self.assertEqual(validation['context']['revision'], report['input_basis']['digest'])
        self.assertEqual([s['rule'] for s in validation['steps']], ['structured','working','repository'])
        self.assertTrue(validation['all_executed'])
