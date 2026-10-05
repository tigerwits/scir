"""Root aliases are accepted; source paths may not escape their canonical root."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from spec import repository
from test_repository_workflow import prepare

class RepositoryRootTests(unittest.TestCase):
    def test_noncanonical_root_checks_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = repository.maintenance(root / "spec" / "..")
            self.assertEqual(code, 0, err.getvalue())
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_missing_manifest_is_incomplete_through_root_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            (root / "spec/index.scir").unlink()
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = repository.maintenance(root / "spec" / "..")
            self.assertEqual(code, 2, err.getvalue())
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(before, {p: p.read_bytes() for p in before})
