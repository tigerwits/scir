#!/usr/bin/env python3
"""Run the named contract with fixed test doubles, without changing any source."""
from dataclasses import replace
import json

from scir import Term, parse_document
from scir.changes import ConflictError, propose
from scir.dialects import evaluate
from scir.knowledge import build_index, select

from dialect import context_from, contract, propose_checked
from run import HERE, COLLECTION, trusted_fixture, request, ready_operations
from policy import PolicyError


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    path = HERE / "notes.scir"
    raw = path.read_bytes()
    index = build_index(parse_document(raw.decode("utf-8")), collection=COLLECTION)
    context = context_from(trusted_fixture(), "fixture-revision-1")
    dialect = contract()
    initial = evaluate(index.document, dialect, context, collection=COLLECTION)
    require(initial.conforms, "original fixture does not conform")
    unsafe = propose(index, request(index, [{"op": "setField", "id": "T", "field": "status", "value": "ready"}]))
    rejected = evaluate(unsafe.document, dialect, context, collection=COLLECTION)
    require(rejected.outcome == "rejected", "domain policy was not checked")
    prepared, receipt = propose_checked(index, request(index, ready_operations()), dialect, context,
                                        expected_context=context.fingerprint)
    require(receipt.matches(prepared.document, dialect, context, collection=COLLECTION), "candidate receipt mismatch")
    require(not initial.matches(prepared.document, dialect, context, collection=COLLECTION), "old receipt followed an edit")
    packet = select(build_index(prepared.document, collection=COLLECTION), ("D1",))
    require(not receipt.matches(packet.document, dialect, context, collection=COLLECTION), "whole receipt followed extraction")
    selected_receipt = evaluate(packet.document, dialect, context, collection=COLLECTION)
    require(selected_receipt.conforms, "rechecked historical decision does not conform")
    invalid_host = replace(context, document=(Term("inventedAuthority"),))
    incomplete = evaluate(index.document, dialect, invalid_host, collection=COLLECTION)
    require(incomplete.outcome == "incomplete", "bad host input became content approval/rejection")
    new_context = replace(context, revision="fixture-revision-2")
    try:
        propose_checked(index, request(index, ready_operations()), dialect, new_context,
                        expected_context=context.fingerprint)
    except ConflictError:
        context_conflict = True
    else:
        raise AssertionError("stale external context was ignored")
    require(path.read_bytes() == raw, "source changed")
    return {"example": "named-consumer-dialect/1", "initial": initial.as_dict(),
            "rejected": rejected.as_dict(), "candidate": receipt.as_dict(),
            "selected": selected_receipt.as_dict(), "incomplete": incomplete.as_dict(),
            "context_conflict": context_conflict, "source_written": False,
            "service_calls": 0, "agent_trials": 0,
            "trust": "fixed input fixtures and local build hashes, not authenticated live execution"}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
