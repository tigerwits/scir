import json
import unittest
from scir import Term, parse, digest
from scir import profile as p
from scir.knowledge import build_index
from scir.changes import propose, ConflictError


def rec(i, payload=Term("p"), **fields):
    return p.application("record", (Term(i), Term("Note"), payload), fields=tuple(fields.items()))


def request(index, *operations, **overrides):
    obj = {"version": "scir-change/1", "collection": index.collection,
           "expected_snapshot": index.snapshot, "operations": list(operations)}
    obj.update(overrides)
    return json.dumps(obj)


class GuardedChangeTests(unittest.TestCase):
    def setUp(self):
        self.doc = (rec("A", reason=p.text("keep")), rec("B", status=Term("blocked")))
        self.index = build_index(self.doc, collection="project")

    def test_narrow_change_noop_and_unrelated_records(self):
        op = {"op": "setField", "id": "B", "field": "status", "value": "ready"}
        result = propose(self.index, request(self.index, op))
        self.assertIs(result.document[0], self.doc[0])
        self.assertEqual(result.document[1], rec("B", status=Term("ready")))
        self.assertEqual(self.index.document, self.doc)
        self.assertEqual(result.candidate_snapshot, digest(result.document))
        self.assertEqual(result.before_snapshot, self.index.snapshot)
        self.assertEqual(propose(self.index, request(self.index)).document, self.doc)
        same = {**op, "value": "blocked"}
        self.assertEqual(propose(self.index, request(self.index, same)).candidate_snapshot, self.index.snapshot)

    def test_snapshot_guard_includes_unrelated_inputs_and_collection(self):
        wire = request(self.index, {"op": "setField", "id": "B", "field": "status", "value": "ready"})
        changed = build_index((rec("A", Term("changed")), self.doc[1]), collection="project")
        for index in (changed, build_index(self.doc, collection="elsewhere"),
                      build_index(tuple(reversed(self.doc)), collection="project")):
            with self.assertRaises(ConflictError):
                propose(index, wire)
        # Reordering changes the conservative snapshot but a fresh request still targets by ID.
        reordered = build_index(tuple(reversed(self.doc)), collection="project")
        updated = propose(reordered, request(reordered, {"op": "replacePayload", "id": "A", "value": "new"}))
        self.assertEqual(updated.document[1].args[0], Term("A"))

    def test_create_forward_cycle_and_append_order(self):
        a = rec("C", p.reference("D"))
        b = rec("D", p.reference("C"))
        result = propose(self.index, request(self.index,
            {"op": "createRecord", "record": str(a)}, {"op": "createRecord", "record": str(b)}))
        self.assertEqual(result.document, self.doc + (a, b))

    def test_delete_validates_entire_candidate(self):
        doc = (rec("A"), rec("B", p.reference("A")))
        index = build_index(doc, collection="x")
        delete = {"op": "deleteRecord", "id": "A"}
        with self.assertRaises(p.ProfileError):
            propose(index, request(index, delete))
        result = propose(index, request(index, delete, {"op": "replacePayload", "id": "B", "value": "p"}))
        self.assertEqual(result.document, (rec("B"),))
        self.assertEqual(index.document, doc)

    def test_conflicting_writes_and_missing_fields_fail_without_partial_result(self):
        field = {"op": "setField", "id": "A", "field": "status", "value": "ready"}
        cases = ((field, field),
                 (field, {"op": "deleteRecord", "id": "A"}),
                 ({"op": "deleteRecord", "id": "A"}, field),
                 ({"op": "createRecord", "record": str(rec("A"))},),
                 ({"op": "removeField", "id": "A", "field": "absent"},),
                 ({"op": "deleteRecord", "id": "missing"},),
                 ({"op": "createRecord", "record": str(rec("C"))},
                  {"op": "setField", "id": "C", "field": "status", "value": "ready"}))
        for operations in cases:
            with self.subTest(operations=operations), self.assertRaises(ConflictError):
                propose(self.index, request(self.index, *operations))
            self.assertEqual(self.index.document, self.doc)

    def test_multiple_different_slots_and_remove_field(self):
        result = propose(self.index, request(self.index,
            {"op": "replacePayload", "id": "A", "value": "not(p)"},
            {"op": "removeField", "id": "A", "field": "reason"},
            {"op": "setField", "id": "A", "field": "status", "value": "proposed"}))
        self.assertEqual(result.document[0], rec("A", parse('not(p)'), status=Term("proposed")))
        self.assertIs(result.document[1], self.doc[1])

    def test_invalid_final_roles_and_resource_bounds(self):
        with self.assertRaises(p.ProfileError):
            propose(self.index, request(self.index,
                {"op": "setField", "id": "B", "field": "status", "value": str(p.text("ready"))}))
        wire = request(self.index, {"op": "createRecord", "record": str(rec("C"))})
        for options in ({"max_records": 2}, {"max_request_bytes": 1}, {"max_result_bytes": 1},
                        {"limits": p.Limits(nodes=4)}):
            with self.subTest(options=options), self.assertRaises(p.LimitError):
                propose(self.index, wire, **options)
        result = propose(self.index, request(self.index))
        size = len((json.dumps(result.as_dict(), ensure_ascii=False, separators=(",", ":"))+"\n").encode())
        self.assertEqual(propose(self.index, request(self.index), max_result_bytes=size), result)
        with self.assertRaises(p.LimitError):
            propose(self.index, request(self.index), max_result_bytes=size-1)
