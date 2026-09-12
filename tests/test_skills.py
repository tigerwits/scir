"""Portable skill files and consumer setup; these tests do not run an LLM."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

import scir

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "scir"
SKILLS = (SKILL, ROOT / "skills" / "scir-migrate")
STARTER = ROOT / "examples" / "skill-project"
FENCE = re.compile(r"^```([\w-]*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")


def run_python(directory, *args):
    # Use this test's package, whether installed from a wheel or loaded from src.
    env = dict(os.environ, PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
    return subprocess.run([sys.executable, *args], cwd=directory, env=env,
                          capture_output=True, text=True, timeout=20)


class SkillTests(unittest.TestCase):
    def test_frontmatter_and_portable_license(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                source = (skill / "SKILL.md").read_text(encoding="utf-8")
                _, header, body = source.split("---\n", 2)
                fields = dict(line.split(": ", 1) for line in header.splitlines())
                self.assertEqual(set(fields), {"name", "description"})
                self.assertEqual(fields["name"], skill.name)
                self.assertRegex(fields["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                self.assertLessEqual(len(fields["name"]), 64)
                self.assertTrue(30 <= len(fields["description"]) <= 160)
                self.assertIn("Use when", fields["description"])
                self.assertEqual((skill / "assets/LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes())
                self.assertLess(len(body.splitlines()), 500)

    def test_references_travel_with_the_skill(self):
        for skill in SKILLS:
            for path in skill.rglob("*.md"):
                for link in LINK.findall(FENCE.sub("", path.read_text(encoding="utf-8"))):
                    parts = urlsplit(link)
                    with self.subTest(skill=skill.name, path=path.name, link=link):
                        self.assertFalse(parts.scheme or parts.netloc, "the skill must work offline")
                        target = (path.parent / unquote(parts.path)).resolve()
                        self.assertTrue(target.is_relative_to(skill))
                        self.assertTrue(target.is_file())

    def test_reference_examples_after_relocation(self):
        for skill in SKILLS:
            with tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                for client in (".agents", ".claude"):
                    copied = project / client / "skills" / skill.name
                    shutil.copytree(skill, copied)
                    for path in copied.rglob("*.md"):
                        for language, source in FENCE.findall(path.read_text(encoding="utf-8")):
                            if language == "python":
                                result = run_python(project, "-c", source)
                                self.assertEqual(result.returncode, 0, result.stderr)
                            elif language == "scir":
                                scir.parse_document(source)
                    result = run_python(project, "-m", "scir", "--version")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("1.0", result.stdout)

    def test_install_copy_refuses_overwrite(self):
        for skill in SKILLS:
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / ".agents/skills" / skill.name
                shutil.copytree(skill, target)
                marker = target / "local-note.txt"
                marker.write_text("keep", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    shutil.copytree(skill, target)
                self.assertEqual(marker.read_text(), "keep")

    def test_starter_blocks_unknown_reference_then_accepts_explicit_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "consumer"
            shutil.copytree(STARTER, project)
            before = {p.name: p.read_bytes() for p in project.iterdir() if p.is_file()}
            result = run_python(project, "check_handoff.py", "draft.scir")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("(2, 1): unknown-reference: no declaration for H7", result.stdout)
            self.assertEqual(before, {p.name: p.read_bytes() for p in project.iterdir() if p.is_file()})
            fixed = before["draft.scir"].decode().replace("supports(O1, H7)", "supports(O1, H1)")
            (project / "repaired.scir").write_text(fixed, encoding="utf-8")
            result = run_python(project, "check_handoff.py", "repaired.scir")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("conforms", result.stdout)

    def test_starter_rejects_bad_shapes_duplicate_ids_and_wrong_reference_kind(self):
        cases = (
            ("", "nonempty"),
            ("arbitrary(A)", "form"),
            ("hypothesis(H1, P)\nhypothesis(H1, Q)", "duplicate-id"),
            ("hypothesis(f(H1), P)", "identifier"),
            ("hypothesis(H1, P)\nsupports(H1, H1)", "reference-kind"),
            ("observation(O1, P)\nhypothesis(H1, Q)\nsupports(O1, f(H1))", "identifier"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "consumer"
            shutil.copytree(STARTER, project)
            for source, rule in cases:
                with self.subTest(rule=rule):
                    (project / "case.scir").write_text(source, encoding="utf-8")
                    result = run_python(project, "check_handoff.py", "case.scir")
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(rule, result.stdout)

    def test_starter_allows_forward_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "consumer"
            shutil.copytree(STARTER, project)
            (project / "case.scir").write_text(
                "supports(O1, H1)\nhypothesis(H1, P)\nobservation(O1, Q)", encoding="utf-8")
            result = run_python(project, "check_handoff.py", "case.scir")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_starter_parse_and_file_errors_are_not_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "consumer"
            shutil.copytree(STARTER, project)
            (project / "broken.scir").write_text("f(", encoding="utf-8")
            for filename in ("broken.scir", "missing.scir"):
                result = run_python(project, "check_handoff.py", filename)
                self.assertEqual(result.returncode, 2)
                self.assertIn("check failed:", result.stderr)
                self.assertNotIn("conforms", result.stdout)

    def test_starter_needs_installed_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "consumer"
            shutil.copytree(STARTER, project)
            # Disable site-packages and PYTHONPATH to model a missing dependency.
            result = subprocess.run(
                [sys.executable, "-I", "-S", "check_handoff.py", "draft.scir"],
                cwd=project, capture_output=True, text=True, timeout=20,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No module named 'scir'", result.stderr)
            self.assertNotIn("conforms", result.stdout)


if __name__ == "__main__":
    unittest.main()
