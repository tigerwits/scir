import json
import unittest
from scir import profile as p
from scir.changes import read_request, ChangeError


def wire(operations=(), **changes):
    value = {"version": "scir-change/1", "collection": "x",
             "expected_snapshot": "0" * 64, "operations": list(operations)}
    value.update(changes)
    return json.dumps(value)


class ChangeRequestTests(unittest.TestCase):
    def test_roundtrip_all_operation_shapes(self):
        operations = (
            {"op": "createRecord", "record": "record(A, Note, p)"},
            {"op": "replacePayload", "id": "B", "value": "not(p)"},
            {"op": "setField", "id": "B", "field": "status", "value": "ready"},
            {"op": "removeField", "id": "C", "field": "reason"},
            {"op": "deleteRecord", "id": "C"},
        )
        parsed = read_request(wire(operations))
        self.assertEqual(parsed.operations[0].id, "A")
        self.assertEqual(parsed.as_dict(), json.loads(wire(operations)))
        self.assertEqual(read_request(json.dumps(parsed.as_dict())), parsed)
        self.assertEqual(read_request(wire()).operations, ())

    def test_json_shape_duplicate_and_unknown_fields_fail(self):
        bad = ('{"version":1,"version":2}', '[]', '{', '[NaN]',
               wire(version="scir-change/2"), wire(expected_snapshot="a"),
               wire(extra=True), wire().replace('"operations": []', '"operations": {}'), wire(collection=""),
               wire(operations=[{"op": "execute", "code": "x"}]),
               wire(operations=[{"op": ["deleteRecord"], "id": "A"}]))
        for source in bad:
            with self.subTest(source=source), self.assertRaises(ValueError):
                read_request(source)
        nested = wire([{"op": "deleteRecord", "id": "A"}]).replace('"id": "A"', '"id":"A","id":"B"')
        with self.assertRaises(ChangeError):
            read_request(nested)

    def test_canonical_terms_and_reserved_slots(self):
        for value in (True, "f(a,b)", " p", "p\n", "t\"text\"", '"scir.ref"', 'a;b'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_request(wire([{"op": "replacePayload", "id": "A", "value": value}]))
        for field in ("id", "kind", "payload", ""):
            with self.assertRaises(ValueError):
                read_request(wire([{"op": "setField", "id": "A", "field": field, "value": "x"}]))

    def test_aggregate_and_input_limits(self):
        operations = [{"op": "replacePayload", "id": "A", "value": "f(a)"}] * 2
        with self.assertRaises(p.LimitError):
            read_request(wire(operations), max_operations=1)
        with self.assertRaises(p.LimitError):
            read_request(wire(operations), limits=p.Limits(nodes=3))
        with self.assertRaises(p.LimitError):
            read_request(wire(), max_bytes=1)
        for option in ({"max_operations": True}, {"max_bytes": 0}):
            with self.assertRaises(ValueError):
                read_request(wire(), **option)
