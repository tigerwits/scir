"""Operation-count checks, not machine-dependent latency gates."""
import itertools
import json
import unittest
from unittest.mock import patch
from scir import Term, digest
from scir.changes import propose, ConflictError
from scir.knowledge import build_index
from scir import profile as p


def request(index, operations):
    return json.dumps({"version":"scir-change/1", "collection":index.collection,
                      "expected_snapshot":index.snapshot, "operations":operations})


class ChangeBatchCostTests(unittest.TestCase):
    def test_many_field_changes_scan_large_payload_only_a_constant_number_of_times(self):
        payload = Term("payload", (Term("x"),) * 10000)
        record = p.application("record", (Term("A"), Term("Note"), payload))
        index = build_index((record,), collection="cost")
        operations = [{"op":"setField", "id":"A", "field":f"field{i}", "value":"ready"} for i in range(100)]
        measure, visits = p.measure, []
        def counted(document, **kwargs):
            result = measure(document, **kwargs)
            visits.append(result.nodes)
            return result
        with patch("scir.profile.measure", side_effect=counted):
            result = propose(index, request(index, operations))
        self.assertLess(sum(visits), 40000)
        self.assertIs(build_index(result.document, collection="cost").records["A"].payload, payload)
        self.assertEqual(digest(index.document), index.snapshot)

    def test_distinct_slot_order_does_not_change_candidate(self):
        record = p.application("record", (Term("A"), Term("Note"), Term("old")), fields=(("remove", Term("x")),))
        index = build_index((record,), collection="order")
        operations = [{"op":"setField", "id":"A", "field":"status", "value":"ready"},
                      {"op":"removeField", "id":"A", "field":"remove"},
                      {"op":"replacePayload", "id":"A", "value":"new"}]
        expected = p.application("record", (Term("A"), Term("Note"), Term("new")), fields=(("status", Term("ready")),))
        for order in itertools.permutations(operations):
            self.assertEqual(propose(index, request(index, list(order))).document, (expected,))

    def test_conflicts_fail_before_record_construction_and_final_validation_remains(self):
        index = build_index((Term("record", (Term("A"), Term("Note"), Term("x"))),), collection="x")
        operation = {"op":"setField", "id":"A", "field":"status", "value":"ready"}
        with patch("scir.profile.application", side_effect=AssertionError("rebuilt before preflight")):
            with self.assertRaises(ConflictError):
                propose(index, request(index, [operation, operation]))
        with self.assertRaises(p.ProfileError):
            propose(index, request(index, [{**operation, "value":"bad(shape)"}]))
