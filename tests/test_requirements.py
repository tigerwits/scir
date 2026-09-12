"""The project's SCIR index: valid links, explicit gaps, no code execution."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import runpy
import tempfile
import unittest

from scir import format_document, parse, parse_document, parse_pattern, query, replace_at
from scir.relations import decode, encode

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "spec/requirements.scir"
TOOLS = runpy.run_path(str(ROOT / "spec/check.py"))
CHECK, RENDER, MAIN = (TOOLS[name] for name in ("validate_catalog", "render", "main"))
SOURCE = '''requirement(R, CLI, preserves(Input))
specifiedBy(R, section("SPEC.md", "Contract"))
coveredBy(R, test("tests/test_sample.py", "Sample.test_behavior"))
'''
TEST_SOURCE = '''import unittest
raise RuntimeError("catalog validation must not import this module")
class Sample(unittest.TestCase):
    def test_behavior(self):
        pass
'''


class RequirementCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tests").mkdir()
        (self.root / "SPEC.md").write_text("# Specification\n\n## Contract\nBehavior.\n", encoding="utf-8")
        (self.root / "tests/test_sample.py").write_text(TEST_SOURCE, encoding="utf-8")

    def issues(self, source=SOURCE):
        return CHECK(parse_document(source), self.root)

    def rules(self, source):
        return {issue.rule for issue in self.issues(source)}

    def test_repository_catalog_is_canonical_and_resolves(self):
        text = CATALOG.read_text(encoding="utf-8")
        document = parse_document(text)
        self.assertEqual(format_document(document), text)
        self.assertEqual(CHECK(document), ())
        cli = query(document, parse_pattern("requirement(?id, CLI, ?obligation)"))
        self.assertIn("CanonicalOutput", [str(h.bindings["id"]) for h in cli])

    def test_reference_check_does_not_execute_tests(self):
        self.assertEqual(self.issues(), ())

    def test_empty_or_links_only_catalog_fails(self):
        self.assertIn("nonempty", self.rules(""))
        self.assertIn("nonempty", self.rules("\n".join(SOURCE.splitlines()[1:])))

    def test_malformed_records_do_not_crash_other_rules(self):
        for text in ("requirement(R)", "coveredBy(R, wrong(A))", "unrelated(A)"):
            with self.subTest(text=text):
                self.assertIn("form", self.rules(SOURCE + text))

    def test_identifiers_are_leaves_and_areas_are_declared(self):
        self.assertIn("identifier", self.rules(SOURCE.replace("(R,", "(f(R),")))
        for area in ("Other", "CLI(A)"):
            self.assertIn("area", self.rules(SOURCE.replace(", CLI,", f", {area},")))
        self.assertEqual(self.issues(SOURCE.replace("(R,", '("new ID",')), ())

    def test_reference_location_arguments_must_be_leaves(self):
        self.assertIn("location", self.rules(SOURCE.replace('"Contract"', 'f(Contract)')))
        self.assertIn("location", self.rules(SOURCE.replace('"tests/test_sample.py"', 'file(A)')))

    def test_forward_links_are_valid(self):
        lines = SOURCE.splitlines()
        self.assertEqual(self.issues("\n".join(lines[1:] + lines[:1])), ())

    def test_unknown_and_ambiguous_requirement_references_fail(self):
        self.assertIn("reference", self.rules(SOURCE.replace("coveredBy(R,", "coveredBy(Missing,")))
        issues = self.issues(SOURCE + "requirement(R, CLI, other)\n")
        self.assertIn("duplicate-id", {v.rule for v in issues})
        self.assertTrue(any("ambiguous" in v.message for v in issues))

    def test_duplicate_links_fail_but_multiple_tests_are_allowed(self):
        self.assertIn("duplicate-link", self.rules(SOURCE + SOURCE.splitlines()[2]))
        p = self.root / "tests/test_sample.py"
        p.write_text(TEST_SOURCE + "    def test_other(self):\n        pass\n", encoding="utf-8")
        self.assertEqual(self.issues(SOURCE + 'coveredBy(R, test("tests/test_sample.py", "Sample.test_other"))'), ())

    def test_missing_source_and_coverage_are_visible(self):
        self.assertIn("source", self.rules("\n".join(line for line in SOURCE.splitlines() if not line.startswith("specifiedBy"))))
        self.assertIn("coverage", self.rules("\n".join(line for line in SOURCE.splitlines() if not line.startswith("coveredBy"))))

    def test_nested_records_do_not_declare_requirements(self):
        wrapped = SOURCE.replace("requirement(R, CLI, preserves(Input))", "quote(requirement(R, CLI, preserves(Input)))")
        self.assertIn("reference", self.rules(wrapped))

    def test_missing_section_is_not_resolved_by_a_fenced_heading(self):
        p = self.root / "SPEC.md"
        p.write_text('# Specification\n```text\n## Contract\n```\n', encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE))

    def test_missing_or_ambiguous_sections_fail(self):
        self.assertIn("location", self.rules(SOURCE.replace('"Contract"', '"Missing"')))
        (self.root / "SPEC.md").write_text("# Contract\n# Contract\n", encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE))

    def test_test_location_is_a_direct_unittest_method(self):
        for name in ("Sample.missing", "Other.test_behavior", "test_behavior"):
            self.assertIn("location", self.rules(SOURCE.replace("Sample.test_behavior", name)))
        p = self.root / "tests/test_sample.py"
        p.write_text(TEST_SOURCE.replace("unittest.TestCase", "object"), encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE))
        p.write_text(TEST_SOURCE.replace("def test_behavior", "async def test_behavior"), encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE))

    def test_duplicate_or_invalid_test_source_is_rejected(self):
        p = self.root / "tests/test_sample.py"
        p.write_text(TEST_SOURCE + "    def test_behavior(self):\n        pass\n", encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE))
        p.write_text("invalid python (", encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE))

    def test_paths_must_stay_in_checkout_and_in_test_files(self):
        for path in ("/tmp/other.py", "../outside.py", "tests/../sample.py", "tests//test_sample.py",
                     "C:/test_sample.py", "tests\\test_sample.py", "missing.py", "SPEC.md"):
            with self.subTest(path=path):
                import json
                self.assertIn("location", self.rules(SOURCE.replace('"tests/test_sample.py"', json.dumps(path))))
        (self.root / "other.py").write_text(TEST_SOURCE, encoding="utf-8")
        self.assertIn("location", self.rules(SOURCE.replace("tests/test_sample.py", "other.py")))

    def test_symlink_reference_is_rejected(self):
        link = self.root / "alias.md"
        try:
            link.symlink_to(self.root / "SPEC.md")
        except OSError:
            self.skipTest("symlinks unavailable on this platform")
        self.assertIn("location", self.rules(SOURCE.replace("SPEC.md", "alias.md")))

    def test_renamed_test_requires_an_explicit_catalog_edit(self):
        document = parse_document(SOURCE)
        self.assertEqual(CHECK(document, self.root), ())
        test_file = self.root / "tests/test_sample.py"
        test_file.write_text(TEST_SOURCE.replace("test_behavior", "test_renamed"), encoding="utf-8")
        self.assertTrue(CHECK(document, self.root))
        updated = replace_at(document, (2, 1, 1), parse('"Sample.test_renamed"'))
        self.assertEqual(CHECK(updated, self.root), ())
        self.assertEqual(document, parse_document(SOURCE))
        self.assertEqual(updated[:2], document[:2])

    def test_transport_preserves_validation_and_query_order(self):
        doc = parse_document(SOURCE)
        self.assertEqual(CHECK(decode(encode(doc)), self.root), CHECK(doc, self.root))
        self.assertEqual(CHECK(doc, self.root), CHECK(tuple(reversed(doc)), self.root))

    def test_renderer_is_deterministic_and_escapes_cells(self):
        doc = parse_document(SOURCE)
        before = format_document(doc)
        view = RENDER(doc)
        self.assertEqual(view, RENDER(decode(encode(doc))))
        self.assertIn("Declared links, not proof", view)
        self.assertIn("Sample.test_behavior", view)
        escaped = replace_at(doc, (0, 2), parse('"<tag>|value"'))
        self.assertIn("&lt;tag&gt;&#124;value", RENDER(escaped))
        self.assertEqual(format_document(doc), before)

    def test_command_checks_and_renders_without_writing(self):
        before = CATALOG.read_bytes()
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = MAIN(["--markdown"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("# Project requirement index", out.getvalue())
        self.assertEqual(CATALOG.read_bytes(), before)

    def test_command_separates_rejection_from_incomplete_check(self):
        file = self.root / "input.scir"
        for source, expected in (("unknown(A)\n", 1), ("A()", 2)):
            file.write_text(source, encoding="utf-8")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(MAIN([str(file)]), expected)
            self.assertEqual(file.read_text(encoding="utf-8"), source)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(MAIN([str(self.root / "missing.scir")]), 2)

    def test_command_rejects_crlf_catalog(self):
        file = self.root / "input.scir"
        file.write_bytes(CATALOG.read_bytes().replace(b"\n", b"\r\n"))
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(MAIN([str(file)]), 1)

    def test_command_rejects_noncanonical_catalog(self):
        file = self.root / "input.scir"
        file.write_text(CATALOG.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(MAIN([str(file)]), 1)


if __name__ == "__main__":
    unittest.main()
