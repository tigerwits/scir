"""The front door names executable current examples, not implicit dialect upgrades."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AdoptionEntrypointTests(unittest.TestCase):
    def test_readme_routes_current_profiles_and_self_use_explicitly(self):
        source = (ROOT / 'README.md').read_text(encoding='utf-8')
        for target in ('skills/scir/SKILL.md', 'skills/scir-migrate/SKILL.md',
                       'docs/self-hosting.md', 'skills/scir/scripts/working_example.py',
                       'tools/check_self_host.py', 'docs/workflow-tools.md',
                       'examples/consumer-lifecycle/README.md', 'examples/consumer-lifecycle/run.py'):
            self.assertIn(target, source)
            self.assertTrue((ROOT / target).is_file())
        self.assertIn('custom dialect', source)
        self.assertIn('standard `working/1`', source)
        self.assertIn('disposable copy', source)
