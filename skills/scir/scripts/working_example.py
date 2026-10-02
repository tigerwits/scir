#!/usr/bin/env python3
"""Run an in-memory working/1 fixture with the already approved SCIR package."""
from __future__ import annotations

import json
from scir import digest, format_document
from scir.changes import ConflictError, propose
from scir.knowledge import affected, build_index, select
from scir.notation import lower, pretty

SOURCE = '''record(A1, Assumption, idempotent(handler), status: unverified)
record(D1, Decision, use(outbox), dependsOn: (&A1,), scope: (environment(staging),), status: proposed)
record(T1, Task, implement(worker), dependsOn: (&D1,), status: blocked)
record(N1, Note, t"Unrelated fixture note.")
'''


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> dict:
    document = lower(SOURCE)
    original = format_document(document)
    require(lower(pretty(document)) == document, "notation changed content")
    index = build_index(document, collection="working-example")
    packet = select(index, ("T1",))
    require(packet.selected_ids == ("A1", "D1", "T1"), "missing required context")
    require(packet.document == document[:3], "record qualifications changed")
    require(affected(index, ("A1",)) == ("A1", "D1", "T1"), "wrong dependency direction")
    request = {"version": "scir-change/1", "collection": index.collection,
               "expected_snapshot": packet.source_snapshot,
               "operations": [{"op": "setField", "id": "T1", "field": "reason",
                               "value": '"scir.text"("Fixture-only reviewed note.")'}]}
    candidate = propose(index, json.dumps(request))
    require(candidate.document[0:2] == document[0:2] and candidate.document[3] == document[3],
            "unrelated records changed")
    updated = build_index(candidate.document, collection=index.collection)
    try:
        propose(updated, json.dumps(request))
    except ConflictError:
        stale_rejected = True
    else:
        raise AssertionError("stale request was accepted")
    require(format_document(document) == original and digest(document) == index.snapshot,
            "source mutated")
    return {"example": "working/1", "selected_ids": list(packet.selected_ids),
            "scope_retained": True, "stale_rejected": stale_rejected,
            "source_written": False, "agent_trials": 0,
            "before_snapshot": index.snapshot, "candidate_snapshot": candidate.candidate_snapshot}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
