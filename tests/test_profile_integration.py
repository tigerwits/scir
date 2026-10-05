import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from scir import parse_document, format_document
from scir.notation import lower

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProfileIntegrationTests(unittest.TestCase):
    def test_authored_example_and_native_golden_are_exact(self):
        root = ROOT/'examples'/'working-profile'
        native = (root/'notes.scir').read_text(encoding='utf-8')
        expected = parse_document(native)
        self.assertEqual(format_document(expected), native)
        self.assertEqual(lower((root/'notes.scix').read_text(encoding='utf-8')), expected)
        result = subprocess.run([sys.executable, str(root/'run.py')], capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['source_written'])

    def test_evaluation_preserves_information_and_accounts_for_envelopes(self):
        study = load_tool('study_profiles')
        report, payloads = study.evaluate()
        self.assertEqual(report['records'], 20)
        self.assertEqual(report['agent_trials'], 0)
        self.assertEqual(report['tokenizer']['status'], 'unmeasured')
        self.assertEqual(len(report['representations']), 4)
        for row in report['representations']:
            self.assertEqual(row['body']['bytes'], len(payloads[row['representation']].encode()))
            self.assertGreater(row['body_and_guide']['bytes'], row['body']['bytes'])
            self.assertNotIn('o200k_base', row['body'])
        for row in report['workflows']:
            self.assertGreater(row['complete_selection_packet']['bytes'], row['selected_native_content']['bytes'])
            self.assertGreater(row['complete_candidate_proposal']['bytes'], row['change_request']['bytes'])
        self.assertEqual(report['workflows'][0]['selected_ids'], ['A1', 'D1', 'G1', 'T1'])

    def test_evaluation_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as destination:
            result = subprocess.run([sys.executable, str(ROOT/'tools'/'study_profiles.py'), '--output', destination],
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(list(Path(destination).iterdir()), [])

    def test_public_api_examples_execute(self):
        import re
        from spec import documents, repository
        source = documents.render_document(repository.load(ROOT), "docs/profiles-api.md")
        examples = re.findall(r"```python\n(.*?)\n```", source, re.S)
        self.assertEqual(len(examples), 2)
        for example in examples:
            exec(compile(example, "profiles-api.md", "exec"), {})
