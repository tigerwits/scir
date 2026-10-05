"""Both repository scripts resolve their own helpers outside the checkout cwd."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import scir

ROOT = Path(__file__).resolve().parents[1]


class RepositoryScriptImportsTests(unittest.TestCase):
    def test_standalone_scripts_work_without_checkout_on_pythonpath(self):
        paths = ("spec/native.scir", "spec/knowledge.scir", "spec/index.scir", "spec/format.scir")
        before = {name: (ROOT / name).read_bytes() for name in paths}
        env = dict(os.environ, PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent),
                   PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as tmp:
            for filename, args in (("check.py", ()), ("repository.py", ("check",))):
                result = subprocess.run([sys.executable, "-B", str(ROOT / "spec" / filename), *args],
                                        cwd=tmp, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("repository records", result.stdout)
        self.assertEqual(before, {name: (ROOT / name).read_bytes() for name in paths})
