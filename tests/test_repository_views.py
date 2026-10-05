"""Direct current-record views, independent goldens and bounded single-pass link scans."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scir import Term, format_document, parse, parse_document
from scir.knowledge import build_index
from scir.profile import ProfileError, text, tuple_value
from spec import catalog, repository, views
from spec.projection import legacy_document
from test_native_projection import native_record
from test_repository_knowledge import fixture, record

ROOT = Path(__file__).resolve().parents[1]


class RepositoryViewTests(unittest.TestCase):
    def test_current_path_never_requires_a_legacy_catalog_or_rechecks_links(self):
        observed = []
        original = repository.declarations
        def inspect(root, path, kind):
            observed.append((path, kind))
            return original(root, path, kind)
        with patch.object(repository, "declarations", side_effect=inspect), \
                patch.object(catalog, "validate_catalog", side_effect=AssertionError("legacy detour")), \
                patch("spec.projection.legacy_document", side_effect=AssertionError("legacy projection")):
            index = repository.load(ROOT)
            self.assertEqual(repository.updates(index, ROOT), [])
            report = views.render(index)
        self.assertEqual(len(observed), len(set(observed)))
        expected = [r.id for r in index.records.values() if r.kind == "Requirement"]
        rows = [line.split("|")[1].strip() for line in report.splitlines() if line.startswith("| <code>")]
        self.assertEqual(rows, [f"<code>{i}</code>" for i in expected])
        self.assertFalse((ROOT / "spec/requirements.scir").exists())

    def test_direct_views_equal_independent_legacy_goldens_without_link_scans(self):
        old = parse_document((ROOT / "tests/fixtures/native-migration.scir").read_text(encoding="utf-8"))
        records = parse_document((ROOT / "tests/fixtures/native-migration-records.scir").read_text(encoding="utf-8"))
        index = build_index(records, collection="historical-fixture")
        for include_examples in (False, True):
            self.assertEqual(views.render_queries(index, examples=include_examples),
                             catalog.render_queries(old, examples=include_examples))
        self.assertEqual(legacy_document(index), old)

    def test_query_rules_reject_markers_duplicate_names_and_wrong_results(self):
        example = parse('example(E, input(f(A)), A, all, paths(path("0", "0")))')
        good = native_record(queryExamples=tuple_value((example,)))
        cases = [native_record(wording=text("<!-- scir:query-api:end -->")),
                 native_record(queryExamples=tuple_value((example, example))),
                 native_record(queryExamples=tuple_value((parse('example(E, input(f(A)), A, all, paths)'),)))]
        views.validate(build_index((good,), collection="test"))
        for candidate in cases:
            with self.subTest(candidate=str(candidate)), self.assertRaises(ProfileError):
                views.validate(build_index((candidate,), collection="test"))

    def test_current_requirement_report_grows_and_escapes_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            other = record("New")
            terms = (record(), Term("record", (*other.args[:2], Term("<tag>|value"), *other.args[3:])))
            index = repository.validate(terms, root)
            report = views.render(index)
            self.assertIn("All 2 requirements in 2 maintained records.", report)
            self.assertIn("&lt;tag&gt;&#124;value", report)
            self.assertEqual(sum(line.startswith("| <code>") for line in report.splitlines()), 2)
            self.assertEqual(index.document, terms)

    def test_current_cli_and_explicit_legacy_export_have_distinct_scope(self):
        from spec.check import main
        index = repository.load(ROOT)
        for args, expected in ((["--markdown"], views.render(index)),
                               (["--legacy"], format_document(legacy_document(index)))):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(args), 0)
            self.assertEqual(out.getvalue(), expected)
