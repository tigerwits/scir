"""Measure the example in a fresh process, without polluting other test imports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = r'''
from dataclasses import replace
import json
from unittest.mock import patch
from scir import Term, parse_document
from scir.dialects import evaluate
from scir.profile import application, text
import dialect, policy, run
original = parse_document((run.HERE / 'notes.scir').read_text(encoding='utf-8'))
context = dialect.context_from(run.trusted_fixture(), 'cost-fixture')
contract = dialect.contract()
rows = []
for size in (len(original), 200):
    document = original + tuple(application('record', (Term(f'Extra{i}'), Term('Note'), text('inert')))
                                for i in range(size - len(original)))
    with patch.object(dialect, 'build_index', wraps=dialect.build_index) as builds:
        result = evaluate(document, contract, context, collection=run.COLLECTION)
        rows.append({'size': size, 'builds': builds.call_count, 'outcome': result.outcome})
    revoked = replace(context, document=())
    if evaluate(document, contract, revoked, collection=run.COLLECTION).outcome != 'rejected':
        raise AssertionError('stale trust was reused')
    if result.matches(document, contract, revoked, collection=run.COLLECTION):
        raise AssertionError('old validation followed a changed context')
with patch.object(policy, 'check', side_effect=AssertionError('must not run')) as check:
    result = evaluate(original + (original[0],), contract, context, collection=run.COLLECTION)
    if result.outcome != 'rejected' or check.called:
        raise AssertionError('invalid working content reached policy')
print(json.dumps(rows))
'''


class ConsumerCostTests(unittest.TestCase):
    def test_one_index_per_evaluation_without_repeating_policy_helpers(self):
        result = subprocess.run([sys.executable, '-B', '-c', PROGRAM],
            cwd=ROOT / 'examples/consumer-lifecycle',
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual([r['size'] for r in rows], [7, 200])
        self.assertEqual([r['builds'] for r in rows], [1, 1])
        self.assertEqual([r['outcome'] for r in rows], ['accepted', 'accepted'])
