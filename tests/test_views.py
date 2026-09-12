"""A maintained content source, checked examples, and non-authoritative views."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from scir import format_document, parse, parse_document, replace_at
from scir.relations import decode, encode

ROOT = Path(__file__).resolve().parents[1]
TOOLS = runpy.run_path(str(ROOT / "spec/check.py"))
CHECK, UPDATES, RENDER, MAIN = (TOOLS[k] for k in
                              ("validate_catalog", "view_updates", "render_queries", "main"))
SOURCE = '''requirement(R, Tree, defaults(query, roots))
specifiedBy(R, section("SPEC.md", "Contract"))
coveredBy(R, test("tests/test_sample.py", "Sample.test_query"))
topic(R, Queries)
wording(R, "Queries default to matching roots.")
note(R, "A match is not a fact.")
queryExample(Default, R, input(think(Bob, use(Alice, Data))), "use(Alice, ?data)", default, paths)
'''


class ContentViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for directory in ("spec", "docs", "tests"):
            (self.root / directory).mkdir()
        self.catalog = self.root / "spec/requirements.scir"
        self.catalog.write_bytes(format_document(parse_document(SOURCE)).encode())
        self.spec = self.root / "SPEC.md"
        self.api = self.root / "docs/api.md"
        for path, key in ((self.spec, "query-spec"), (self.api, "query-api")):
            path.write_bytes((f"# Contract\n\nKEEP café\n<!-- scir:{key}:start -->\nold\n"
                              f"<!-- scir:{key}:end -->\nKEEP suffix\n").encode())
        (self.root / "tests/test_sample.py").write_text(
            'import unittest\nraise AssertionError("must not import tests")\n'
            'class Sample(unittest.TestCase):\n    def test_query(self):\n        pass\n')
        self.document = parse_document(SOURCE)

    def rules(self, source):
        return {v.rule for v in CHECK(parse_document(source), self.root)}

    def run_cli(self, *args):
        out, err = StringIO(), StringIO()
        with patch.dict(MAIN.__globals__, ROOT=self.root), redirect_stdout(out), redirect_stderr(err):
            code = MAIN(list(args))
        return code, out.getvalue(), err.getvalue()

    def apply(self, document=None):
        for path, data in UPDATES(self.document if document is None else document, self.root):
            path.write_bytes(data)

    def test_repository_views_are_fresh(self):
        document = parse_document((ROOT / "spec/requirements.scir").read_text())
        self.assertEqual(CHECK(document), ())
        self.assertEqual(UPDATES(document), [])

    def test_initial_migration_preserves_the_existing_normative_contract(self):
        # Independent pre-migration text, not an expectation derived from records.
        expected = '''A path is a nonempty sequence `(root_index, child_index, ...)` of nonnegative
integers. Python Booleans are not indices. Paths are local to a document snapshot.
Walking enumerates every occurrence in root-order, depth-first preorder.
Queries default to matching roots. Explicit `scope="all"` matches every
occurrence. Results include path, matched term, and bindings, in traversal order,
including duplicate occurrences. Neither scope computes logical consequences.'''
        doc = parse_document((ROOT / "spec/requirements.scir").read_text())
        wording = RENDER(doc, examples=False).split("\n", 1)[1]
        self.assertEqual(" ".join(wording.split()), " ".join(expected.split()))

    def test_default_check_rejects_stale_views_without_writing(self):
        before = self.spec.read_bytes(), self.api.read_bytes()
        code, _, errors = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("stale view: SPEC.md", errors)
        self.assertIn("stale view: docs/api.md", errors)
        self.assertEqual(before, (self.spec.read_bytes(), self.api.read_bytes()))

    def test_root_alias_keeps_stale_diagnostics_relative(self):
        alias = self.root.with_name(self.root.name + "-alias")
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("directory symlinks unavailable")
        self.addCleanup(alias.unlink)
        out, err = StringIO(), StringIO()
        with patch.dict(MAIN.__globals__, ROOT=alias), redirect_stdout(out), redirect_stderr(err):
            code = MAIN([])
        self.assertEqual(code, 1, err.getvalue())
        self.assertIn("stale view: SPEC.md", err.getvalue())
        self.assertIn("stale view: docs/api.md", err.getvalue())
        self.assertNotIn(str(alias), err.getvalue())

    def test_explicit_write_preserves_other_sections_and_is_idempotent(self):
        code, out, errors = self.run_cli("--write-views")
        self.assertEqual(code, 0, errors)
        self.assertIn("Refreshed 2", out)
        for path in (self.spec, self.api):
            self.assertTrue(path.read_bytes().startswith("# Contract\n\nKEEP café\n".encode()))
            self.assertTrue(path.read_bytes().endswith(b"KEEP suffix\n"))
        before = self.spec.read_bytes(), self.api.read_bytes()
        self.assertEqual(self.run_cli()[0], 0)
        self.assertIn("Refreshed 0", self.run_cli("--write-views")[1])
        self.assertEqual(before, (self.spec.read_bytes(), self.api.read_bytes()))

    def test_wording_change_requires_source_update_and_refresh(self):
        self.apply()
        revised = replace_at(self.document, (4, 1), parse('"Revised wording for review."'))
        self.assertEqual(CHECK(revised, self.root), ())
        self.catalog.write_bytes(format_document(revised).encode("utf-8"))
        self.assertEqual(self.run_cli()[0], 1)
        self.assertEqual(self.run_cli("--write-views")[0], 0)
        self.assertEqual(self.run_cli()[0], 0)
        for path in (self.spec, self.api):
            self.assertIn("Revised wording for review.", path.read_text())
        self.assertNotIn("Revised wording", format_document(self.document))

    def test_new_topic_member_is_selected_without_editing_the_renderer(self):
        self.apply()
        extra = SOURCE.replace("(R,", "(Added,").replace("queryExample(Default, R,", "queryExample(New, Added,")
        extra = extra.replace('"Queries default to matching roots."', '"New selected content."')
        doc = parse_document(SOURCE + extra)
        self.assertEqual(CHECK(doc, self.root), ())
        self.assertEqual(len(UPDATES(doc, self.root)), 2)
        self.apply(doc)
        for path in (self.spec, self.api):
            self.assertIn("New selected content.", path.read_text())

    def test_new_example_invalidates_only_the_api_view(self):
        self.apply()
        extra = 'queryExample(Nested, R, input(f(A)), A, all, paths(path("0", "0")))\n'
        doc = parse_document(SOURCE + extra)
        self.assertEqual(CHECK(doc, self.root), ())
        self.assertEqual([p for p, _ in UPDATES(doc, self.root)], [self.api])

    def test_unselected_requirement_does_not_change_query_views(self):
        self.apply()
        extra = "\n".join(SOURCE.splitlines()[:3]).replace("(R,", "(Unselected,")
        doc = parse_document(SOURCE + extra)
        self.assertEqual(CHECK(doc, self.root), ())
        self.assertEqual(UPDATES(doc, self.root), [])

    def test_manual_view_edit_is_not_a_source_change(self):
        self.apply()
        original = self.catalog.read_bytes()
        self.spec.write_bytes(self.spec.read_bytes().replace(b"Queries default", b"Queries do not default"))
        self.assertEqual(self.run_cli()[0], 1)
        self.assertEqual(self.catalog.read_bytes(), original)
        self.assertEqual(self.run_cli("--write-views")[0], 0)
        self.assertNotIn("do not default", self.spec.read_text())

    def test_missing_later_marker_prevents_all_writes(self):
        self.api.write_text("# API\nmissing markers\n")
        before = self.spec.read_bytes(), self.api.read_bytes()
        code, _, errors = self.run_cli("--write-views")
        self.assertEqual(code, 2)
        self.assertIn("marker pair", errors)
        self.assertEqual(before, (self.spec.read_bytes(), self.api.read_bytes()))

    def test_duplicate_reversed_or_inline_markers_fail(self):
        begin = "<!-- scir:query-spec:start -->"
        end = "<!-- scir:query-spec:end -->"
        for text in (begin + "\n" + begin + "\n" + end, end + "\n" + begin + "\n",
                     "inline" + begin + "\n" + end, begin + "x\n" + end,
                     begin + "\n" + end + "suffix"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                TOOLS["replace_view"](text, "query-spec", "new\n")

    def test_render_destinations_cannot_be_symlinks(self):
        self.api.unlink()
        try:
            self.api.symlink_to(self.spec)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            UPDATES(self.document, self.root)

    def test_custom_catalog_cannot_write_project_views(self):
        path = self.root / "other.scir"
        path.write_bytes(format_document(parse_document(SOURCE)).encode("utf-8"))
        before = self.spec.read_bytes()
        self.assertEqual(self.run_cli(str(path), "--write-views")[0], 2)
        self.assertEqual(self.spec.read_bytes(), before)

    def test_invalid_source_prevents_view_writes(self):
        self.catalog.write_text(SOURCE.replace('default, paths)', 'default, paths(path("0")))'))
        before = self.spec.read_bytes(), self.api.read_bytes()
        self.assertEqual(self.run_cli("--write-views")[0], 1)
        self.assertEqual(before, (self.spec.read_bytes(), self.api.read_bytes()))

    def test_migrated_fields_require_ownership_and_unique_values(self):
        for kind in ("topic", "wording", "note"):
            with self.subTest(kind=kind):
                line = next(s for s in SOURCE.splitlines() if s.startswith(kind + "("))
                self.assertIn("duplicate-content", self.rules(SOURCE + line))
                self.assertIn("content-reference", self.rules(SOURCE.replace(line, line.replace("(R,", "(Unknown,"))))
        without_topic = "\n".join(s for s in SOURCE.splitlines() if not s.startswith("topic("))
        self.assertIn("missing-content", self.rules(without_topic))
        without_wording = "\n".join(s for s in SOURCE.splitlines() if not s.startswith("wording("))
        self.assertIn("missing-content", self.rules(without_wording))

    def test_malformed_extension_forms_are_diagnostics(self):
        for value in ("wording(R)", "topic(R)", "queryExample(E)", "note(R, A, B)"):
            self.assertIn("form", self.rules(SOURCE + value))

    def test_unknown_topics_or_composite_text_fail(self):
        for old, new in (("topic(R, Queries)", "topic(R, Other)"),
                         ('"Queries default to matching roots."', "words(Queries)"),
                         ('"A match is not a fact."', "note(Text)")):
            self.assertIn("content-field", self.rules(SOURCE.replace(old, new)))
        self.assertIn("content-field", self.rules(SOURCE.replace(
            '"A match is not a fact."', '"<!-- scir:query-spec:end -->"')))

    def test_examples_need_unique_names_and_migrated_owners(self):
        example = SOURCE.splitlines()[-1]
        self.assertIn("example-id", self.rules(SOURCE + example))
        self.assertIn("example-id", self.rules(SOURCE.replace("queryExample(Default,", "queryExample(id(Default),")))
        self.assertIn("content-reference", self.rules(SOURCE.replace("queryExample(Default, R,", "queryExample(Default, Unknown,")))
        unselected = "\n".join(s for s in SOURCE.splitlines() if not s.startswith(("topic(", "wording(", "note(")))
        self.assertIn("content-reference", self.rules(unselected))

    def test_example_pattern_scope_and_paths_are_checked(self):
        for old, new in (("default, paths)", "other, paths)"),
                         ("default, paths)", 'all, paths(path("0", "1")))'),
                         ("default, paths)", 'all, paths(path("-1")))'),
                         ("default, paths)", 'all, paths(path("00")))'),
                         ("default, paths)", 'all, paths(path("0.0")))'),
                         ("default, paths)", "all, paths(path))"),
                         ('"use(Alice, ?data)"', '"use("'),
                         ("input(think", "source(think")):
            with self.subTest(new=new):
                changed = SOURCE.replace(old, new)
                rules = self.rules(changed)
                if new == 'all, paths(path("0", "1")))':
                    self.assertEqual(rules, set())
                else:
                    self.assertIn("query-example", rules)

    def test_wrong_expected_paths_are_not_silently_recomputed(self):
        bad = SOURCE.replace("default, paths)", 'all, paths(path("0")))')
        issues = CHECK(parse_document(bad), self.root)
        self.assertTrue(any(v.rule == "query-example" and "got [(0, 1)]" in v.message for v in issues))

    def test_example_data_is_not_python(self):
        data = 'queryExample(Symbol, R, input(__import__(os)), "__import__(?x)", roots, paths(path("0")))'
        self.assertEqual(self.rules(SOURCE + data), set())

    def test_rendered_examples_execute_and_default_really_omits_scope(self):
        text = RENDER(self.document, examples=True)
        self.assertIn("hits = query(content, pattern)\n", text)
        code = text.split("```python\n")[1].split("```")[0]
        exec(compile(code, "<generated query example>", "exec"), {})
        self.assertNotIn("A match is not a fact", RENDER(self.document, examples=False))

    def test_views_are_deterministic_after_transport(self):
        for examples in (False, True):
            self.assertEqual(RENDER(self.document, examples=examples),
                             RENDER(decode(encode(self.document)), examples=examples))

    def test_topic_membership_controls_order_and_removal(self):
        other = SOURCE.replace("(R,", "(Added,").replace("queryExample(Default, R,", "queryExample(New, Added,")
        other = other.replace('"Queries default to matching roots."', '"Second wording."')
        doc = parse_document(SOURCE + other)
        self.assertLess(RENDER(doc, examples=False).index("Queries default"),
                        RENDER(doc, examples=False).index("Second wording"))
        self.apply(doc)
        self.assertEqual(len(UPDATES(self.document, self.root)), 2)

    def test_view_markers_do_not_silently_normalize_newlines(self):
        original = self.spec.read_bytes().replace(b"\n", b"\r\n")
        self.spec.write_bytes(original)
        code, _, _ = self.run_cli("--write-views")
        self.assertEqual(code, 2)
        self.assertEqual(self.spec.read_bytes(), original)

    def test_api_only_note_change_does_not_rewrite_the_specification(self):
        self.apply()
        doc = replace_at(self.document, (5, 1), parse('"A revised usage note."'))
        self.assertEqual(CHECK(doc, self.root), ())
        self.assertEqual([p for p, _ in UPDATES(doc, self.root)], [self.api])

    def test_hostile_example_name_cannot_break_the_generated_code_fence(self):
        doc = replace_at(self.document, (6, 0), parse('"<tag>\\n```python"'))
        text = RENDER(doc, examples=True)
        self.assertIn("&lt;tag&gt;", text)
        self.assertEqual(text.count("\n```python\n"), 1)
        self.assertEqual(len([line for line in text.splitlines() if line.startswith("```")]), 2)

    def test_removed_topic_is_not_silently_an_empty_view(self):
        doc = parse_document("\n".join(SOURCE.splitlines()[:3]))
        self.assertEqual(CHECK(doc, self.root), ())
        with self.assertRaises(ValueError):
            UPDATES(doc, self.root)


if __name__ == "__main__":
    unittest.main()
