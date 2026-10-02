"""Immutable, collection-local working/1 indexes. No inference or persistence."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from .core import Document, Term, check_symbol, digest
from . import profile as p

VERSION = "working/1"


def _positive(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(name + " must be a positive integer")


def _leaf(term: Term, role: str) -> str:
    if term.args or term.symbol in p.RESERVED:
        raise p.ProfileError(role + " must be an ordinary symbol leaf")
    return term.symbol


def _plain_tuple(term: Term, role: str) -> tuple[Term, ...]:
    args, fields = p._split(term)
    if term.symbol != p.TUPLE or fields:
        raise p.ProfileError(role + " must be a positional tuple")
    return args


def _references(term: Term) -> tuple[str, ...]:
    """Traverse validated expressions, never literal payload/field labels."""
    pending, found = [term], {}
    while pending:
        t = pending.pop()
        if t.symbol == p.REF:
            found.setdefault(t.args[0].symbol, None)
        elif t.symbol != p.TEXT:
            args, fields = p._split(t)
            pending.extend(v for _, v in reversed(fields))
            pending.extend(reversed(args))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Record:
    id: str
    kind: str
    payload: Term
    fields: tuple[tuple[str, Term], ...]
    term: Term


@dataclass(frozen=True, slots=True)
class Index:
    collection: str
    document: Document
    snapshot: str
    records: Mapping[str, Record]
    references: Mapping[str, tuple[str, ...]]
    dependents: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        # Detach maps from the builder; no mutable mapping escapes.
        for name in ("records", "references", "dependents"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


def _record(term: Term) -> Record:
    args, fields = p._split(term)
    if term.symbol != "record" or len(args) != 3:
        raise p.ProfileError("working roots must be record(ID, Kind, Payload)")
    identifier, kind = _leaf(args[0], "ID"), _leaf(args[1], "kind")
    for key, value in fields:
        if key in ("id", "kind", "payload"):
            raise p.ProfileError("reserved record slot cannot be a named field: " + key)
        if key == "status":
            _leaf(value, "status")
        elif key in ("dependsOn", "supersedes", "scope", "evidence"):
            items = _plain_tuple(value, key)
            if key in ("dependsOn", "supersedes") and any(t.symbol != p.REF for t in items):
                raise p.ProfileError(key + " must contain explicit references")
    return Record(identifier, kind, args[2], fields, term)


def build_index(document: Document, *, collection: str,
                limits: p.Limits = p.Limits(), max_records: int = 10_000) -> Index:
    check_symbol(collection)
    _positive(max_records, "max_records")
    p.validate(document, limits=limits)
    if len(collection.encode("utf-8")) > limits.bytes or len(document) > max_records:
        raise p.LimitError("collection/record budget exceeded")
    records, references, reverse = {}, {}, {}
    for term in document:
        record = _record(term)
        if record.id in records:
            raise p.ProfileError("duplicate record ID: " + record.id)
        records[record.id] = record
        references[record.id] = _references(term)
        reverse[record.id] = []
    for identifier, record in records.items():
        for target in references[identifier]:
            if target not in records:
                raise p.ProfileError("unresolved local reference: " + target)
        fields = dict(record.fields)
        if "dependsOn" in fields:
            targets = dict.fromkeys(t.args[0].symbol for t in fields["dependsOn"].args)
            for target in targets:
                reverse[target].append(identifier)
    return Index(collection, document, digest(document), records, references,
                 {key: tuple(value) for key, value in reverse.items()})


def _ids(index: Index, identifiers: tuple[str, ...], maximum: int) -> tuple[str, ...]:
    if type(index) is not Index or type(identifiers) is not tuple:
        raise ValueError("expected an Index and an immutable ID tuple")
    _positive(maximum, "max_records")
    if len(identifiers) > maximum:
        raise p.LimitError("requested ID budget exceeded")
    unique = {}
    for identifier in identifiers:
        check_symbol(identifier)
        if identifier not in index.records:
            raise p.ProfileError("unknown record ID: " + identifier)
        unique.setdefault(identifier, None)
    return tuple(unique)


@dataclass(frozen=True, slots=True)
class Selection:
    collection: str
    source_snapshot: str
    requested_ids: tuple[str, ...]
    selected_ids: tuple[str, ...]
    document: Document
    reasons: tuple[tuple[str, str, str | None], ...]
    profile: str = VERSION
    complete: bool = True

    def as_dict(self) -> dict:
        return {
            "profile": self.profile, "collection": self.collection,
            "source_snapshot": self.source_snapshot,
            "requested_ids": list(self.requested_ids), "selected_ids": list(self.selected_ids),
            "records": [str(t) for t in self.document], "complete": self.complete,
            "reasons": [{"id": i, "kind": k, "via": v} for i, k, v in self.reasons],
        }


def select(index: Index, identifiers: tuple[str, ...], *,
           max_records: int = 10_000, limits: p.Limits = p.Limits()) -> Selection:
    """Return whole records closed over every declared local reference."""
    from collections import deque
    import json
    seeds = _ids(index, identifiers, max_records)
    _positive(max_records, "max_records")
    reasons = {i: ("requested", None) for i in seeds}
    queue = deque(seeds)
    while queue:
        if len(reasons) > max_records:
            raise p.LimitError("selection record budget exceeded")
        identifier = queue.popleft()
        for target in index.references[identifier]:
            if target not in reasons:
                reasons[target] = ("reference", identifier)
                queue.append(target)
    selected = tuple(i for i in index.records if i in reasons)
    document = tuple(index.records[i].term for i in selected)
    p.validate(document, limits=limits)
    result = Selection(index.collection, index.snapshot, seeds, selected, document,
                       tuple((i, *reasons[i]) for i in selected))
    # Envelope costs, not just payload bytes, count against the output budget.
    wire = json.dumps(result.as_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(wire.encode("utf-8")) > limits.bytes:
        raise p.LimitError("selection packet byte budget exceeded")
    return result


def affected(index: Index, changed: tuple[str, ...], *,
             max_records: int = 10_000, max_bytes: int = 16_000_000) -> tuple[str, ...]:
    """Review candidates along reverse dependsOn edges; not a truth judgment."""
    from collections import deque
    import json
    seeds = _ids(index, changed, max_records)
    _positive(max_bytes, "max_bytes")
    seen, queue = set(seeds), deque(seeds)
    while queue:
        if len(seen) > max_records:
            raise p.LimitError("review record budget exceeded")
        for dependent in index.dependents[queue.popleft()]:
            if dependent not in seen:
                seen.add(dependent)
                queue.append(dependent)
    result = tuple(i for i in index.records if i in seen)
    wire = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(wire.encode("utf-8")) > max_bytes:
        raise p.LimitError("review output byte budget exceeded")
    return result
