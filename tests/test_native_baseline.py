"""Historical-byte checks have their own subject; current behavior has conformance tests."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_baseline", ROOT / "tools/check_native_baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True, timeout=10).stdout.strip()


def fixture(root):
    git(root, "init", "-q")
    package = root / "src/scir"
    package.mkdir(parents=True)
    raw = b"# Historical fixture only.\n"
    for name in baseline.BLOBS:
        (package / name).write_bytes(raw)
    git(root, "add", ".")
    git(root, "-c", "user.name=SCIR fixture", "-c", "user.email=scir@example.invalid", "commit", "-qm", "baseline fixture")
    return git(root, "rev-parse", "HEAD"), {name: baseline.blob_id(raw) for name in baseline.BLOBS}


class NativeBaselineTests(unittest.TestCase):
    def test_fixed_manifest_is_historical_not_current_package(self):
        self.assertEqual(baseline.REVISION, "3ceeb1ea9ae2c0f52a1568a1f7b611469384571c")
        self.assertEqual(set(baseline.BLOBS), {"core.py", "syntax.py", "patterns.py", "tree.py", "relations.py"})
        self.assertTrue(all(len(value) == 40 for value in baseline.BLOBS.values()))
        self.assertEqual(baseline.blob_id(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_exact_fixture_and_changed_missing_or_overbound_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            revision, files = fixture(root)
            with patch.object(baseline, "REVISION", revision), patch.object(baseline, "BLOBS", files):
                self.assertEqual(baseline.verify(root)["verified_files"], 5)
                path = root / "src/scir/core.py"
                raw = path.read_bytes()
                path.write_bytes(b"changed\n")
                with self.assertRaisesRegex(ValueError, "differs from pinned"):
                    baseline.verify(root)
                path.unlink()
                with self.assertRaisesRegex(ValueError, "missing or linked"):
                    baseline.verify(root)
                path.write_bytes(raw)
                with patch.object(baseline, "MAX_BYTES", 1), self.assertRaisesRegex(ValueError, "byte limit"):
                    baseline.verify(root)
                self.assertTrue(baseline.verify(root)["complete"])

    def test_same_source_at_different_revision_is_not_the_fixed_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            revision, files = fixture(root)
            git(root, "-c", "user.name=SCIR fixture", "-c", "user.email=scir@example.invalid", "commit", "--allow-empty", "-qm", "another revision")
            with patch.object(baseline, "REVISION", revision), patch.object(baseline, "BLOBS", files):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    result = baseline.main([str(root)])
                self.assertEqual(result, 2)
                self.assertEqual(out.getvalue(), "")
                self.assertIn("fixed historical revision", err.getvalue())
