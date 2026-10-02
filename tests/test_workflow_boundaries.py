"""Small counterexamples for content, lifecycle policy and delivery capacity."""
import json
import unittest

from scir import Term, format_document, parse_document
from scir.changes import ConflictError, propose
from scir.knowledge import affected, build_index, select
from scir.notation import pretty
from scir import profile as p


def record(identifier, **fields):
    return p.application("record", (Term(identifier), Term("Note"), p.text("unchanged")),
                         fields=tuple(fields.items()))


def refs(*identifiers):
    return p.tuple_value(tuple(p.reference(i) for i in identifiers))


def request(index, value):
    return json.dumps({"version": "scir-change/1", "collection": index.collection,
                       "expected_snapshot": index.snapshot, "operations": [
                           {"op": "setField", "id": "A", "field": "status", "value": value}]})


class WorkflowBoundaryTests(unittest.TestCase):
    def test_supersession_is_outgoing_context_not_automatic_current_state(self):
        document = (record("Old"), record("New", supersedes=refs("Old")),
                    record("Alternative", supersedes=refs("Old")),
                    record("Task", dependsOn=refs("Old")))
        index = build_index(document, collection="history")
        self.assertEqual(select(index, ("Old",)).selected_ids, ("Old",))
        self.assertEqual(select(index, ("New",)).selected_ids, ("Old", "New"))
        self.assertEqual(affected(index, ("Old",)), ("Old", "Task"))
        self.assertEqual(index.document, document)  # No competitor chosen or record deleted.
        cyclic = build_index((record("A", supersedes=refs("B")),
                              record("B", supersedes=refs("A"))), collection="history")
        self.assertEqual(select(cyclic, ("A",)).selected_ids, ("A", "B"))

    def test_content_guard_accepts_restored_content_not_intervening_history(self):
        original = build_index((record("A", status=Term("draft")),), collection="history")
        old_request = request(original, "proposed")
        changed = build_index(propose(original, request(original, "reviewed")).document,
                              collection=original.collection)
        with self.assertRaises(ConflictError):
            propose(changed, old_request)
        restored = build_index(propose(changed, request(changed, "draft")).document,
                               collection=original.collection)
        self.assertEqual(restored.snapshot, original.snapshot)
        self.assertEqual(restored.document, original.document)
        reused = propose(restored, old_request)
        self.assertEqual(reused.before_snapshot, original.snapshot)
        candidate = build_index(reused.document, collection="history")
        self.assertEqual(dict(candidate.records["A"].fields)["status"], Term("proposed"))
        self.assertEqual(dict(original.records["A"].fields)["status"], Term("draft"))

    def test_select_native_before_notation_and_keep_capacity_failure_explicit(self):
        # The native input fits. Its complete notation spelling exceeds the default
        # 64,000-byte cap; each independent record is small enough to deliver.
        records = tuple(p.application("record", (Term("R" + str(i)), Term("Note"), p.text("x" * 9000)))
                        for i in range(8))
        native = format_document(records)
        self.assertEqual(parse_document(native), records)
        index = build_index(records, collection="capacity")
        with self.assertRaises(p.LimitError):
            pretty(records)
        packet = select(index, ("R0",))
        self.assertEqual(packet.document, records[:1])
        self.assertIn('t"', pretty(packet.document))
        linked = tuple(p.application("record", (Term("R" + str(i)), Term("Note"), p.text("x" * 9000)),
                                    fields=(("dependsOn", refs("R" + str(i - 1))),) if i else ())
                       for i in range(8))
        required = select(build_index(linked, collection="capacity"), ("R7",))
        self.assertEqual(required.document, linked)
        with self.assertRaises(p.LimitError):
            pretty(required.document)  # Never drop a prerequisite to make it fit.
