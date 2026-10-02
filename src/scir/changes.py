"""Strict scir-change/1 requests and pure snapshot-guarded candidates."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from .core import Document, Term, check_symbol
from .syntax import parse
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
    result = parse(source, max_nodes=limits.nodes, max_depth=limits.depth)
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
    except (json.JSONDecodeError, RecursionError) as error:
        raise ChangeError("invalid or excessively nested JSON request") from error
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
