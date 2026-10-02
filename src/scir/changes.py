"""Strict scir-change/1 requests and pure snapshot-guarded candidates."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from .core import Document, Term, check_symbol
from ._profile_native import native
from . import profile as p
from .knowledge import Index, VERSION as WORKING_VERSION, _positive, _record, build_index

VERSION = "scir-change/1"


class ChangeError(p.ProfileError):
    """A change request or its resulting collection is invalid."""


class ConflictError(ChangeError):
    """The source snapshot or requested write precondition no longer holds."""


@dataclass(frozen=True, slots=True)
class Operation:
    op: str
    id: str
    field: str | None = None
    value: Term | None = None

    def as_dict(self) -> dict:
        if self.op == "createRecord":
            return {"op": self.op, "record": str(self.value)}
        result = {"op": self.op, "id": self.id}
        if self.field is not None:
            result["field"] = self.field
        if self.value is not None:
            result["value"] = str(self.value)
        return result


@dataclass(frozen=True, slots=True)
class Request:
    collection: str
    expected_snapshot: str
    operations: tuple[Operation, ...]

    def as_dict(self) -> dict:
        return {"version": VERSION, "collection": self.collection,
                "expected_snapshot": self.expected_snapshot,
                "operations": [op.as_dict() for op in self.operations]}


def _object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ChangeError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def _constant(value: str):
    raise ChangeError("non-JSON constant: " + value)


def _term(source: str, limits: p.Limits) -> Term:
    if type(source) is not str:
        raise ChangeError("term values must be canonical native SCIR strings")
    if len(source.encode("utf-8")) > limits.bytes:
        raise p.LimitError("term byte budget exceeded")
    result = native(source, one=True, max_nodes=limits.nodes, max_depth=limits.depth)
    p.validate((result,), limits=limits)
    if str(result) != source:
        raise ChangeError("term value is not canonical native SCIR")
    return result


def read_request(source: str, *, max_bytes: int = 1_000_000,
                 max_operations: int = 1024, limits: p.Limits = p.Limits()) -> Request:
    if type(limits) is not p.Limits:
        raise ValueError("expected Limits")
    _positive(max_bytes, "max_bytes")
    _positive(max_operations, "max_operations")
    if type(source) is not str:
        raise ChangeError("request must be JSON text")
    if len(source) > max_bytes or len(source.encode("utf-8")) > max_bytes:
        raise p.LimitError("request byte budget exceeded")
    try:
        obj = json.loads(source, object_pairs_hook=_object, parse_constant=_constant)
    except RecursionError as error:
        raise p.LimitError("JSON request nesting exceeds decoder bounds") from error
    except json.JSONDecodeError as error:
        raise ChangeError("invalid JSON request") from error
    required = {"version", "collection", "expected_snapshot", "operations"}
    if type(obj) is not dict or set(obj) != required or obj["version"] != VERSION:
        raise ChangeError("expected the exact scir-change/1 envelope")
    check_symbol(obj["collection"])
    snapshot = obj["expected_snapshot"]
    if type(snapshot) is not str or not re.fullmatch(r"[0-9a-f]{64}", snapshot):
        raise ChangeError("expected a lowercase SHA-256 content fingerprint")
    if type(obj["operations"]) is not list:
        raise ChangeError("operations must be an array")
    if len(obj["operations"]) > max_operations:
        raise p.LimitError("operation budget exceeded")
    shapes = {
        "createRecord": {"op", "record"},
        "deleteRecord": {"op", "id"},
        "replacePayload": {"op", "id", "value"},
        "setField": {"op", "id", "field", "value"},
        "removeField": {"op", "id", "field"},
    }
    operations, terms = [], []
    for raw in obj["operations"]:
        if type(raw) is not dict or type(raw.get("op")) is not str:
            raise ChangeError("invalid operation object")
        op = raw["op"]
        if op not in shapes or set(raw) != shapes[op]:
            raise ChangeError("unsupported operation or operation fields")
        value = _term(raw["record" if op == "createRecord" else "value"], limits) if op in (
            "createRecord", "replacePayload", "setField") else None
        identifier = _record(value).id if op == "createRecord" else raw["id"]
        check_symbol(identifier)
        field = raw.get("field")
        if op in ("setField", "removeField"):
            check_symbol(field)
            if field in ("id", "kind", "payload"):
                raise ChangeError("record identity/kind/payload are not optional fields")
        operations.append(Operation(op, identifier, field, value))
        if value is not None:
            terms.append(value)
    p.validate(tuple(terms), limits=limits)  # Aggregate inserted content, not per-op only.
    return Request(obj["collection"], snapshot, tuple(operations))


@dataclass(frozen=True, slots=True)
class Proposal:
    collection: str
    before_snapshot: str
    candidate_snapshot: str
    document: Document
    request: Request

    def as_dict(self) -> dict:
        return {
            "version": "scir-proposal/1", "profile": WORKING_VERSION,
            "collection": self.collection, "before_snapshot": self.before_snapshot,
            "candidate_snapshot": self.candidate_snapshot,
            "request": self.request.as_dict(), "records": [str(t) for t in self.document],
            "validation": {"profile": WORKING_VERSION, "complete": True},
        }


def _propose_content(index: Index, source: str, *, limits: p.Limits = p.Limits(),
            max_records: int = 10_000, max_operations: int = 1024,
            max_request_bytes: int = 1_000_000) -> Proposal:
    """Build a validated candidate only. Hosts own atomic persistence and policy."""
    if type(index) is not Index:
        raise ValueError("expected an Index built from the current collection")
    request = read_request(source, max_bytes=max_request_bytes,
                           max_operations=max_operations, limits=limits)
    if request.collection != index.collection or request.expected_snapshot != index.snapshot:
        raise ConflictError("collection or source snapshot precondition failed")
    # Check the complete write set before rebuilding any record. Distinct slots
    # commute; a whole-record operation conflicts with every other write to its ID.
    groups, touched = {}, {}
    for operation in request.operations:
        identifier = operation.id
        slots = touched.setdefault(identifier, set())
        whole = operation.op in ("createRecord", "deleteRecord")
        slot = ("whole", "") if whole else (("payload", "") if operation.op == "replacePayload" else ("field", operation.field))
        if (whole and slots) or ("whole", "") in slots or slot in slots:
            raise ConflictError("conflicting operations for record: " + identifier)
        slots.add(slot)
        if operation.op == "createRecord":
            if identifier in index.records:
                raise ConflictError("create requires an absent record: " + identifier)
        elif identifier not in index.records:
            raise ConflictError("operation requires an existing record: " + identifier)
        if operation.op == "removeField" and operation.field not in dict(index.records[identifier].fields):
            raise ConflictError("remove requires an existing field: " + operation.field)
        groups.setdefault(identifier, []).append(operation)

    candidate = {i: r.term for i, r in index.records.items()}
    created = []
    for identifier, operations in groups.items():
        first = operations[0]
        if first.op == "createRecord":
            candidate[identifier] = first.value
            created.append(identifier)
            continue
        if first.op == "deleteRecord":
            del candidate[identifier]
            continue
        record = index.records[identifier]
        payload, values = record.payload, dict(record.fields)
        for operation in operations:
            if operation.op == "replacePayload":
                payload = operation.value
            elif operation.op == "setField":
                values[operation.field] = operation.value
            else:
                del values[operation.field]
        # Each affected record is assembled once, not once per changed field.
        candidate[identifier] = p.application("record", (Term(record.id), Term(record.kind), payload),
                                              fields=tuple(values.items()), limits=limits)
    # Preserve surviving order; append creates, including forward/cyclic references.
    order = tuple(i for i in index.records if i in candidate) + tuple(created)
    document = tuple(candidate[i] for i in order)
    final = build_index(document, collection=index.collection, limits=limits, max_records=max_records)
    result = Proposal(index.collection, index.snapshot, final.snapshot, document, request)
    return result


def propose(index: Index, source: str, *, limits: p.Limits = p.Limits(),
            max_records: int = 10_000, max_operations: int = 1024,
            max_request_bytes: int = 1_000_000,
            max_result_bytes: int = 16_000_000) -> Proposal:
    """Build a validated candidate and bound the original full response."""
    if type(index) is not Index:
        raise ValueError("expected an Index built from the current collection")
    _positive(max_result_bytes, "max_result_bytes")
    result = _propose_content(index, source, limits=limits, max_records=max_records,
                              max_operations=max_operations, max_request_bytes=max_request_bytes)
    wire = json.dumps(result.as_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(wire.encode("utf-8")) > max_result_bytes:
        raise p.LimitError("proposal packet byte budget exceeded")
    return result
