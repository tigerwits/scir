"""Deletion policy and real Git compare-and-delete leases on temporary repositories."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

PATH = Path(__file__).with_name("prune_merged_branches.py")
spec = importlib.util.spec_from_file_location("prune", PATH)
prune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prune)


class BranchCleanupTests(unittest.TestCase):
    def test_policy_preserves_primary_protected_open_changed_and_unmerged(self):
        def decision(name="topic", actual="a", default="main", protected=False, heads=(), merged=True):
            return prune.eligible(name, "a", actual, default, protected, set(heads), lambda _: merged)
        self.assertIsNone(decision())
        self.assertEqual(decision(name="main"), "default-or-primary")
        self.assertEqual(decision(name="custom", default="custom"), "default-or-primary")
        self.assertEqual(decision(protected=True), "protected")
        self.assertEqual(decision(heads=("topic",)), "open-pull-request")
        self.assertEqual(decision(actual="new"), "tip-changed")
        self.assertEqual(decision(merged=False), "not-merged")

    def test_actual_lease_deletes_exact_tip_and_preserves_a_raced_tip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, work = root / "remote.git", root / "work"
            prune.git(root, "init", "--bare", str(remote))
            prune.git(root, "init", str(work))
            prune.git(work, "config", "user.name", "Fixture")
            prune.git(work, "config", "user.email", "fixture@example.invalid")
            prune.git(work, "commit", "--allow-empty", "-m", "base")
            old = prune.git(work, "rev-parse", "HEAD").stdout.strip()
            prune.git(work, "remote", "add", "origin", str(remote))
            prune.git(work, "push", "origin", "HEAD:refs/heads/merged", "HEAD:refs/heads/raced")
            prune.delete_tip(work, "merged", old)
            self.assertEqual(prune.git(work, "ls-remote", "--heads", "origin", "merged").stdout, "")
            prune.git(work, "commit", "--allow-empty", "-m", "new")
            new = prune.git(work, "rev-parse", "HEAD").stdout.strip()
            prune.git(work, "push", "origin", "HEAD:refs/heads/raced")
            with self.assertRaises(subprocess.CalledProcessError):
                prune.delete_tip(work, "raced", old)
            self.assertIn(new, prune.git(work, "ls-remote", "--heads", "origin", "raced").stdout)
