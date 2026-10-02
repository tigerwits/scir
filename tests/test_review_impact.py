import unittest
from scir import Term
from scir import profile as p
from scir.knowledge import build_index, select, affected


def rec(i, **fields):
    return p.application("record", (Term(i), Term("Note"), Term("p")), fields=tuple(fields.items()))


def refs(*ids):
    return p.tuple_value(tuple(p.reference(i) for i in ids))


class ReviewImpactTests(unittest.TestCase):
    def test_only_declared_dependencies_propagate_review(self):
        doc = (rec("A"), rec("Citation", evidence=refs("A")),
               rec("C", dependsOn=refs("A", "A")), rec("D", dependsOn=refs("C")),
               rec("Supersession", supersedes=refs("A")))
        index = build_index(doc, collection="x")
        self.assertEqual(affected(index, ("A",)), ("A", "C", "D"))
        self.assertEqual(affected(index, ("D",)), ("D",))
        self.assertEqual(select(index, ("Citation",)).selected_ids, ("A", "Citation"))
        self.assertEqual(index.dependents["A"], ("C",))
        self.assertEqual(index.document, doc)

    def test_cycles_idempotence_and_empty_requests(self):
        index = build_index((rec("A", dependsOn=refs("B")), rec("B", dependsOn=refs("A"))), collection="x")
        result = affected(index, ("B",))
        self.assertEqual(result, ("A", "B"))
        self.assertEqual(affected(index, result), result)
        self.assertEqual(affected(index, ()), ())

    def test_unknown_requested_and_output_limits(self):
        index = build_index((rec("A"), rec("B", dependsOn=refs("A"))), collection="x")
        for ids in (("missing",), ["A"], (False,)):
            with self.assertRaises(ValueError):
                affected(index, ids)
        for kw in ({"max_records": 1}, {"max_bytes": 2}):
            with self.assertRaises(p.LimitError):
                affected(index, ("A",), **kw)
        with self.assertRaises(p.LimitError):
            select(index, ("B", "B", "B"), max_records=2)
        with self.assertRaises(ValueError):
            affected(index, ("A",), max_bytes=True)
