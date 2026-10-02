"""Opt-in structured/1 values encoded as unchanged SCIR 1.0 Terms."""
from __future__ import annotations

from dataclasses import dataclass
from .core import Document, Term, check_symbol, format_symbol, validate as validate_core

VERSION = "structured/1"
TUPLE, TEXT, REF, KW = "scir.tuple", "scir.text", "scir.ref", "scir.kw"
RESERVED = frozenset((TUPLE, TEXT, REF, KW))


class ProfileError(ValueError):
    """Content is well-formed SCIR but does not meet this profile."""


class LimitError(ValueError):
    """A complete result could not be constructed within caller bounds."""


@dataclass(frozen=True, slots=True)
class Limits:
    nodes: int = 100_000
    depth: int = 128
    bytes: int = 16_000_000

    def __post_init__(self) -> None:
        if any(type(n) is not int or n < 1 for n in (self.nodes, self.bytes)):
            raise ValueError("node and byte limits must be positive integers")
        if type(self.depth) is not int or not 0 <= self.depth <= 128:
            raise ValueError("depth must be an integer in 0..128")


@dataclass(frozen=True, slots=True)
class Size:
    nodes: int
    depth: int
    bytes: int


def measure(document: Document, *, limits: Limits = Limits()) -> Size:
    """Count occurrences and exact canonical UTF-8 bytes before serialization."""
    validate_core(document)
    if type(limits) is not Limits:
        raise ValueError("expected Limits")
    if len(document) > limits.nodes:
        raise LimitError("node budget exceeded")
    pending = [(t, 0) for t in reversed(document)]
    count, depth, size = 0, 0, len(document)  # One LF per root.
    while pending:
        t, d = pending.pop()
        if type(t) is not Term or type(t.args) is not tuple:
            raise ProfileError("expected an immutable ground Term")
        check_symbol(t.symbol)
        if len(t.symbol) > limits.bytes:
            raise LimitError("byte budget exceeded")
        count += 1
        depth = max(depth, d)
        size += len(format_symbol(t.symbol).encode("utf-8")) + 2 * len(t.args)
        if d > limits.depth or count + len(pending) + len(t.args) > limits.nodes:
            raise LimitError("tree budget exceeded")
        if size > limits.bytes:
            raise LimitError("byte budget exceeded")
        pending.extend((a, d + 1) for a in reversed(t.args))
    if size > limits.bytes:
        raise LimitError("byte budget exceeded")
    return Size(count, depth, size)


def validate(document: Document, *, limits: Limits = Limits()) -> Size:
    size = measure(document, limits=limits)
    pending = list(reversed(document))
    while pending:
        t = pending.pop()
        if t.symbol in (TEXT, REF):
            if (t.symbol == REF and len(t.args) != 1) or len(t.args) > 1:
                raise ProfileError("invalid text/reference arity")
            if t.args and t.args[0].args:
                raise ProfileError("text/reference payload must be a symbol leaf")
            # Payload labels are literal, not recursively interpreted as tags.
        elif t.symbol == KW:
            raise ProfileError("keyword container is not an expression")
        else:
            positional, fields = _split(t)
            pending.extend(reversed(positional))
            pending.extend(value for _, value in reversed(fields))
    return size


def text(value: str) -> Term:
    if type(value) is not str:
        raise ValueError("text requires a string")
    return Term(TEXT, (Term(value),)) if value else Term(TEXT)


def read_text(term: Term) -> str:
    validate((term,))
    if term.symbol != TEXT:
        raise ProfileError("expected text")
    return term.args[0].symbol if term.args else ""


def reference(identifier: str) -> Term:
    return Term(REF, (Term(identifier),))


def read_reference(term: Term) -> str:
    validate((term,))
    if term.symbol != REF:
        raise ProfileError("expected reference")
    return term.args[0].symbol


def _split(term: Term) -> tuple[tuple[Term, ...], tuple[tuple[str, Term], ...]]:
    """Read this node only; callers validate recursively at the public boundary."""
    args = term.args
    if not args or args[-1].symbol != KW:
        return args, ()
    entries = args[-1].args
    if not entries or any(len(e.args) != 1 for e in entries):
        raise ProfileError("keyword entries must be nonempty unary fields")
    keys = [e.symbol.encode("utf-8") for e in entries]
    if any(a >= b for a, b in zip(keys, keys[1:])):
        raise ProfileError("keyword keys must be unique and in UTF-8 order")
    return args[:-1], tuple((e.symbol, e.args[0]) for e in entries)


def read_fields(term: Term) -> tuple[tuple[str, Term], ...]:
    """Return immutable named entries, not an implicit positional signature."""
    validate((term,))
    return () if term.symbol in (TEXT, REF) else _split(term)[1]


def read_arguments(term: Term) -> tuple[Term, ...]:
    validate((term,))
    if term.symbol in RESERVED:
        raise ProfileError("expected an ordinary application")
    return _split(term)[0]


def _compose(head: str, positional: tuple[Term, ...],
             fields: tuple[tuple[str, Term], ...], limits: Limits) -> Term:
    if type(fields) is not tuple:
        raise ValueError("fields must be an immutable tuple of pairs")
    names, values, entries = set(), [], []
    for item in fields:
        if type(item) is not tuple or len(item) != 2:
            raise ValueError("each field must be a (name, value) tuple")
        key, value = item
        check_symbol(key)
        if key in names:
            raise ProfileError("duplicate keyword: " + key)
        names.add(key)
        values.append(value)
        entries.append(Term(key, (value,)))
    # Reject unattached keyword containers even in the last positional slot.
    validate_core(positional)
    validate(positional + tuple(values), limits=limits)
    entries.sort(key=lambda e: e.symbol.encode("utf-8"))
    children = positional + ((Term(KW, tuple(entries)),) if entries else ())
    result = Term(head, children)
    validate((result,), limits=limits)
    return result


def application(head: str, positional: tuple[Term, ...] = (), *,
                fields: tuple[tuple[str, Term], ...] = (),
                limits: Limits = Limits()) -> Term:
    check_symbol(head)
    if head in RESERVED:
        raise ProfileError("use the tagged-value constructor, not an ordinary head")
    return _compose(head, positional, fields, limits)


def tuple_value(items: tuple[Term, ...] = (), *,
                fields: tuple[tuple[str, Term], ...] = (),
                limits: Limits = Limits()) -> Term:
    return _compose(TUPLE, items, fields, limits)


def read_tuple(term: Term) -> tuple[Term, ...]:
    """Read positional components; read_fields returns named components separately."""
    validate((term,))
    if term.symbol != TUPLE:
        raise ProfileError("expected tuple")
    return _split(term)[0]
