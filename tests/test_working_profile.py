import unittest
from scir import Term, parse, digest
from scir import profile as p
from scir.knowledge import build_index


def record(identifier, payload=None, **fields):
    return p.application("record", (Term(identifier), Term("Note"), payload or Term("ok")),
                         fields=tuple(fields.items()))


class WorkingProfileTests(unittest.TestCase):
    def test_forward_references_cycles_and_immutable_indexes(self):
        doc = (record("A", dependsOn=p.tuple_value((p.reference("B"),))),
               record("B", p.reference("A")))
        index = build_index(doc, collection="project")
        self.assertEqual(index.snapshot, digest(doc))
        self.assertEqual(index.references["A"], ("B",))
        self.assertEqual(index.references["B"], ("A",))
        self.assertEqual(index.dependents["B"], ("A",))
        with self.assertRaises(TypeError):
            index.records["C"] = index.records["A"]
        self.assertEqual(index.document, doc)

    def test_text_symbols_and_field_names_are_not_references(self):
        value = p.application("explain", (p.text("scir.ref"), Term("B")),
                              fields=(("scir.ref", p.text("&C")),))
        index = build_index((record("A", value),), collection="project")
        self.assertEqual(index.references["A"], ())
        self.assertEqual(index.records["A"].fields, ())

    def test_references_in_extension_fields_are_checked(self):
        with self.assertRaises(p.ProfileError):
            build_index((record("A", custom=p.reference("missing")),), collection="x")
        doc = (record("A", custom=p.reference("B")), record("B"))
        self.assertEqual(build_index(doc, collection="x").references["A"], ("B",))

    def test_invalid_shapes_and_identity(self):
        cases = ((record("A"), record("A")), (Term("A"),),
                 (parse('record(A, f(K), x)'),),
                 (record("A", status=p.text("verified")),),
                 (record("A", dependsOn=Term("B")),),
                 (record("A", dependsOn=p.tuple_value((Term("B"),))),),
                 (record("A", scope=p.tuple_value(fields=(("x", Term("a")),))),),
                 (record("A", id=Term("B")),))
        for doc in cases:
            with self.subTest(doc=doc), self.assertRaises(p.ProfileError):
                build_index(doc, collection="x")
        for collection in ("", None, "\ud800"):
            with self.assertRaises(ValueError):
                build_index((), collection=collection)

    def test_open_kinds_and_contradictory_payloads_remain_data(self):
        doc = (record("A", Term("p"), status=Term("verified")), record("B", parse('not(p)')))
        index = build_index(doc, collection="x")
        self.assertEqual(index.document, doc)
        self.assertEqual(len(index.records), 2)

    def test_record_and_content_bounds(self):
        doc = (record("A"), record("B"))
        with self.assertRaises(p.LimitError):
            build_index(doc, collection="x", max_records=1)
        with self.assertRaises(ValueError):
            build_index(doc, collection="x", max_records=True)
        with self.assertRaises(p.LimitError):
            build_index(doc, collection="x", limits=p.Limits(nodes=4))
