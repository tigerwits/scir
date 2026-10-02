"""Consumer portability and real self-use, not provider activation or agent quality."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import scir

ROOT = Path(__file__).resolve().parents[1]


def run(cwd, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env=env,
                          capture_output=True, timeout=60)


class AdoptionExampleTests(unittest.TestCase):
    def test_portable_working_example_works_after_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "unrelated-project/.agents/skills/scir"
            shutil.copytree(ROOT / "skills/scir", target)
            before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            for flags in ((), ("-O",)):
                result = run(tmp, *flags, target / "scripts/working_example.py")
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["selected_ids"], ["A1", "D1", "T1"])
                self.assertTrue(report["stale_rejected"])
                self.assertFalse(report["source_written"])
                self.assertEqual(report["agent_trials"], 0)
            self.assertEqual(before, {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()})

    def test_repository_self_hosting_uses_actual_subprocesses_and_scratch_only(self):
        result = run(ROOT, ROOT / "tools/check_self_host.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["complete"])
        self.assertFalse(report["source_written"])
        self.assertTrue(report["scratch_replay"])
        self.assertEqual(report["agent_trials"], 0)
        self.assertEqual([item["exit"] for item in report["observations"]], [0, 0, 0, 1, 0, 0, 0, 0])

    def test_migration_routes_to_current_profile_rules(self):
        source = (ROOT / "skills/scir-migrate/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/working.md", source)
        guide = (ROOT / "skills/scir-migrate/references/working.md").read_text(encoding="utf-8")
        for term in ("t\"...\"", "working/1", "input-basis", "service", "incomplete"):
            self.assertIn(term, guide)
        self.assertIn("check_self_host.py", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
