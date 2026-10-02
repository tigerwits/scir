#!/usr/bin/env python3
"""Run hypothetical lifecycle changes with fixed test-double approvals and receipts."""
from pathlib import Path
import json

from scir import parse_document, format_document
from scir.changes import ConflictError
from scir.knowledge import build_index, select
from scir.delivery import selection
from policy import Receipt, TrustedInputs, PolicyError, STAGING, check, effective, propose_checked

HERE = Path(__file__).resolve().parent
COLLECTION = "consumer-lifecycle-fixture"
# These are independent fixture coordinates, not hashes approved from a candidate.
D1 = "5c328c9539d7659cd4402276c04d1453a3294d5ce6efea8e093f26dd0a69d813"
D2 = "134bd2902f8286076d40ee0368cc7c829f4f6228b84615dd8ec952eade1f2184"


def trusted_fixture():
    """Test doubles only. Real hosts must authenticate these inputs independently."""
    return TrustedInputs(frozenset((D1, D2)), {
        "testReceipt": Receipt(D2, "test", STAGING, "passed"),
        "deliveryReceipt": Receipt(D2, "delivery", STAGING, "completed"),
    })


def request(index, operations):
    return json.dumps({"version": "scir-change/1", "collection": index.collection,
                       "expected_snapshot": index.snapshot, "operations": operations})


def ready_operations():
    return [{"op": "setField", "id": "T", "field": "decision", "value": '"scir.ref"(D2)'},
            {"op": "setField", "id": "T", "field": "dependsOn",
             "value": '"scir.tuple"("scir.ref"(D2), "scir.ref"(R))'},
            {"op": "setField", "id": "T", "field": "status", "value": "ready"}]


def run():
    path = HERE / "notes.scir"
    raw = path.read_bytes()
    document = parse_document(raw.decode("utf-8"))
    index = build_index(document, collection=COLLECTION)
    trusted = trusted_fixture()
    check(index, trusted)
    resolution = effective(index, "D1")
    if resolution.status != "resolved" or resolution.ids != ("D2",):
        raise AssertionError("expected one reviewed replacement")
    rejected = []
    unsafe = request(index, [{"op": "setField", "id": "T", "field": "status", "value": "ready"}])
    try:
        propose_checked(index, unsafe, trusted)
    except PolicyError:
        rejected.append("stale-decision-link")
    else:
        raise AssertionError("a historical prerequisite became current implicitly")
    update = request(index, ready_operations())
    prepared = propose_checked(index, update, trusted)
    ready = build_index(prepared.document, collection=COLLECTION)
    try:
        propose_checked(ready, request(ready, [{"op": "setField", "id": "T", "field": "status", "value": "completed"}]), trusted)
    except PolicyError:
        rejected.append("unsupported-completion")
    else:
        raise AssertionError("completion was accepted without a delivery receipt")
    finish = request(ready, [{"op": "setField", "id": "T", "field": "status", "value": "completed"},
                             {"op": "setField", "id": "T", "field": "evidence",
                              "value": '"scir.tuple"("scir.ref"(Etest), "scir.ref"(Edelivery))'}])
    completed = propose_checked(ready, finish, trusted)
    final = build_index(completed.document, collection=COLLECTION)
    try:
        propose_checked(final, update, trusted)
    except ConflictError:
        rejected.append("stale-snapshot")
    else:
        raise AssertionError("stale input was accepted")
    delivered = selection(final, ("T",), encoding="notation", guards=(("host_revision", "fixture-only"),))
    packet = json.loads(delivered.packet)
    if json.loads(delivered.checked_artifact(packet["artifact"]["sha256"]))["value"] != select(final, ("T",)).as_dict():
        raise AssertionError("delivery changed the complete selected context")
    if path.read_bytes() != raw or format_document(index.document).encode("utf-8") != raw:
        raise AssertionError("source was changed")
    return {"example": "consumer-lifecycle/1", "resolved_id": "D2", "final_status": "completed",
            "rejected": rejected, "source_written": False, "service_calls": 0, "agent_trials": 0,
            "trust": "fixed test doubles, not authenticated live receipts",
            "packet_bytes": len(delivered.packet.encode("utf-8")),
            "artifact_bytes": len(delivered.artifact.encode("utf-8"))}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
