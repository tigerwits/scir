"""Independent projection expectations and an exact initial migration witness."""
import hashlib
from pathlib import Path
import unittest

from scir import Term, format_document, parse_document
from scir.knowledge import build_index, select
from scir.profile import ProfileError, text, tuple_value
from spec.projection import legacy_document
from spec.check import render_queries
from test_repository_knowledge import record

ROOT = Path(__file__).resolve().parents[1]


def native_record(**fields):
    values = dict(area=Term("Core"), ownership=Term("record"), projection=Term("native"),
                  topic=Term("Queries"), viewOrder=Term("0"), wording=text("Keep the enclosing scope."))
    values.update(fields)
    return record(**values)


class NativeProjectionTests(unittest.TestCase):
    def test_migration_preserves_fixed_legacy_bytes_and_both_query_views(self):
        index = build_index(parse_document((ROOT / "spec/native.scir").read_text(encoding="utf-8")), collection="scir-repository")
        old = (ROOT / "spec/requirements.scir").read_bytes().replace(b"\r\n", b"\n")
        # Historical migration witness only; behavioral goldens remain independent.
        blob = hashlib.sha1(b"blob " + str(len(old)).encode() + b"\0" + old).hexdigest()
        self.assertEqual(blob, "64a65d662ff9fd5ce193bab4e448289b0e87c3e2")
        projected = legacy_document(index)
        self.assertEqual(format_document(projected).encode(), old)
        self.assertEqual(len(index.records), 30)
        self.assertEqual(select(index, ("RootScope",)).selected_ids, ("RootScope",))
        for examples in (False, True):
            self.assertEqual(render_queries(projected, examples=examples),
                             render_queries(parse_document(old.decode()), examples=examples))

    def test_small_projection_has_independent_literal_expectations(self):
        index = build_index((native_record(),), collection="scir-repository")
        expected = ('requirement(R, Core, preserve)\n'
                    'specifiedBy(R, section("docs/rules.md", Rules))\n'
                    'coveredBy(R, test("tests/test_rule.py", "RuleTests.test_rule"))\n'
                    'topic(R, Queries)\nwording(R, "Keep the enclosing scope.")\n')
        self.assertEqual(format_document(legacy_document(index)), expected)

    def test_noncanonical_ambiguous_and_incomplete_projection_metadata_fails(self):
        for item in (native_record(viewOrder=Term("01")), native_record(viewOrder=Term("1")),
                     native_record(ownership=Term("index")), native_record(wording=text("")),
                     native_record(projection=Term("other")), native_record(queryExamples=tuple_value((Term("bad"),)))):
            with self.subTest(item=str(item)), self.assertRaises(ValueError):
                legacy_document(build_index((item,), collection="test"))
        other = native_record()
        other = Term("record", (Term("S"), *other.args[1:]))
        with self.assertRaises(ProfileError):
            legacy_document(build_index((native_record(), other), collection="test"))

