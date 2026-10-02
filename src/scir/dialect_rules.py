"""Profile-aware Constraint helpers; callers still select and identify the rules."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .constraints import Constraint, Violation
from .core import Document, check_symbol
from .knowledge import build_index
from . import profile as p


def structured(document: Document):
    """Convert only a completed structured/1 rejection to a diagnostic."""
    try:
        p.validate(document)
    except p.ProfileError as error:
        yield Violation(None, "structured/1", str(error))


def working(document: Document):
    """Validate working/1 without inferring domain policy or presence requirements."""
    try:
        build_index(document, collection="dialect-check")
    except p.ProfileError as error:
        yield Violation(None, "working/1", str(error))


def _names(values) -> frozenset[str]:
    if type(values) not in (tuple, list, set, frozenset) or len(values) > 256:
        raise ValueError("expected a bounded collection of at most 256 names")
    for value in values:
        check_symbol(value)
        if len(value.encode("utf-8")) > 1024:
            raise ValueError("field/kind name exceeds 1024 UTF-8 bytes")
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class FieldSet:
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()

    def __post_init__(self):
        object.__setattr__(self, "required", _names(self.required))
        object.__setattr__(self, "optional", _names(self.optional))
        if self.required & self.optional:
            raise ValueError("required and optional fields must be disjoint")


def record_fields(shapes: Mapping[str, FieldSet], *, rule: str = "record-fields") -> Constraint:
    """Closed record kinds and named fields, with open IDs and payload expressions."""
    check_symbol(rule)
    if not isinstance(shapes, Mapping) or len(shapes) > 256:
        raise ValueError("expected at most 256 record shapes")
    schema = dict(shapes)
    _names(tuple(schema))
    if any(type(value) is not FieldSet for value in schema.values()):
        raise ValueError("record shapes must contain FieldSet values")
    schema = MappingProxyType(schema)

    def constraint(document):
        index = build_index(document, collection="dialect-check")
        for number, record in enumerate(index.records.values()):
            shape = schema.get(record.kind)
            if shape is None:
                yield Violation((number, 1), rule, "record kind is not permitted: " + record.kind)
                continue
            fields = dict(record.fields)
            for key in sorted(shape.required - fields.keys(), key=lambda k: k.encode("utf-8")):
                yield Violation((number,), rule, "required field is missing: " + key)
            allowed = shape.required | shape.optional
            for offset, (key, _) in enumerate(record.fields):
                if key not in allowed:
                    yield Violation((number, len(record.term.args) - 1, offset), rule,
                                    "field is not permitted: " + key)
    return constraint


def reference_targets(field: str, kinds, *, source_kinds=None,
                      rule: str = "reference-targets") -> Constraint:
    """Check an optional single reference or plain reference tuple against kinds."""
    check_symbol(rule)
    _names((field,))
    targets = _names(kinds)
    sources = None if source_kinds is None else _names(source_kinds)

    def constraint(document):
        index = build_index(document, collection="dialect-check")
        for number, record in enumerate(index.records.values()):
            if sources is not None and record.kind not in sources:
                continue
            for offset, (key, value) in enumerate(record.fields):
                if key != field:
                    continue
                path = (number, len(record.term.args) - 1, offset, 0)
                if value.symbol == p.REF:
                    refs = (value,)
                elif value.symbol == p.TUPLE and not p.read_fields(value):
                    refs = p.read_tuple(value)
                else:
                    yield Violation(path, rule, "expected a reference or plain reference tuple")
                    continue
                for target in refs:
                    if target.symbol != p.REF:
                        yield Violation(path, rule, "tuple contains a non-reference value")
                    elif index.records[p.read_reference(target)].kind not in targets:
                        yield Violation(path, rule, "reference targets a disallowed record kind")
    return constraint
