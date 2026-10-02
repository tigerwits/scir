import itertools
import json
import unittest
from scir import Term, parse
from scir import profile as p
from scir.knowledge import build_index, select


def rec(i, payload=Term("p"), **fields):
    return p.application("record", (Term(i), Term("Hypothesis"), payload), fields=tuple(fields.items()))


class WorkingSelectionTests(unittest.TestCase):
    def test_scope_evidence_payload_and_extensions_are_retained(self):
        doc = (rec("Guard", parse('environment(staging)')),
               rec("Evidence", p.text("unconfirmed")), rec("Other"),
               rec("Task", parse('not(delivered(doc))'),
                   scope=p.tuple_value((p.reference("Guard"),)),
                   evidence=p.tuple_value((p.reference("Evidence"),)),
                   reason=p.text("Does not establish delivery"),
                   custom=p.reference("Payload")),
               rec("Payload", p.reference("Guard")))
        index = build_index(doc, collection="example")
        packet = select(index, ("Task",))
        self.assertEqual(packet.selected_ids, ("Guard", "Evidence", "Task", "Payload"))
        self.assertEqual(packet.document, (doc[0], doc[1], doc[3], doc[4]))
        self.assertEqual(packet.source_snapshot, index.snapshot)
        self.assertEqual(packet.profile, "working/1")
        self.assertTrue(packet.complete)
        self.assertEqual(packet.reasons[2], ("Task", "requested", None))
        self.assertIn("Hypothesis", packet.as_dict()["records"][2])

    def test_cycles_empty_requests_duplicates_and_order(self):
        doc = (rec("B", p.reference("A")), rec("A", p.reference("B")), rec("C"))
        index = build_index(doc, collection="x")
        result = select(index, ("A", "A"))
        self.assertEqual(result.requested_ids, ("A",))
        self.assertEqual(result.selected_ids, ("B", "A"))
        self.assertEqual(select(index, result.selected_ids).document, result.document)
        self.assertEqual(select(index, ()).document, ())

    def test_unknown_ids_and_incomplete_budgets_fail(self):
        index = build_index((rec("A", p.reference("B")), rec("B")), collection="x")
        for ids in (("missing",), (1,), ["A"]):
            with self.assertRaises(ValueError):
                select(index, ids)
        with self.assertRaises(p.LimitError):
            select(index, ("A",), max_records=1)
        with self.assertRaises(p.LimitError):
            select(index, ("A",), limits=p.Limits(nodes=1))
        packet = select(index, ("A",))
        size = len((json.dumps(packet.as_dict(), ensure_ascii=False, separators=(",", ":"))+"\n").encode())
        self.assertEqual(select(index, ("A",), limits=p.Limits(bytes=size)), packet)
        with self.assertRaises(p.LimitError):
            select(index, ("A",), limits=p.Limits(bytes=size-1))

    def test_exhaustive_small_graph_closure_matches_fixed_point_oracle(self):
        ids = ("A", "B", "C")
        edges = tuple(itertools.product(ids, repeat=2))
        for mask in range(1 << len(edges)):
            graph = {i: [b for k, (a,b) in enumerate(edges) if a == i and mask & (1 << k)] for i in ids}
            doc = tuple(rec(i, p.tuple_value(tuple(p.reference(t) for t in graph[i]))) for i in ids)
            index = build_index(doc, collection="x")
            for seed in ids:
                expected = {seed}
                while True:
                    after = expected | {t for s in expected for t in graph[s]}
                    if after == expected:
                        break
                    expected = after
                packet = select(index, (seed,))
                self.assertEqual(set(packet.selected_ids), expected)
