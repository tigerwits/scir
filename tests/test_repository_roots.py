"""A checkout root may have aliases; source links inside it still may not."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from spec import repository
from test_repository_workflow import prepare


class RepositoryRootTests(unittest.TestCase):
    def test_noncanonical_root_reports_stale_not_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            alias = root / "spec" / ".."
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                result = repository.maintenance(alias)
            self.assertEqual(result, 1, err.getvalue())
            self.assertEqual(out.getvalue(), "")
            self.assertIn("stale derived files: SPEC.md", err.getvalue())
            self.assertNotIn("incomplete", err.getvalue())
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                result = repository.maintenance(alias, write_views=True)
            self.assertEqual(result, 0, err.getvalue())
            self.assertEqual(repository.updates(repository.load(root), root), [])

    def test_missing_destination_remains_incomplete_through_root_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            (root / "docs/api.md").unlink()
            before = (root / "spec/requirements.scir").read_bytes()
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                result = repository.maintenance(root / "spec" / "..", write_views=True)
            self.assertEqual(result, 2, err.getvalue())
            self.assertEqual(out.getvalue(), "")
            self.assertEqual((root / "spec/requirements.scir").read_bytes(), before)
