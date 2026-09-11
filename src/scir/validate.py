"""Structural validation. No real-world or ontological checks."""

from __future__ import annotations

import re

from .ast import Atom, Call, Expr, Variable
from .tree import walk

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

# head -> (min_arity, max_arity); None max means unbounded.
RESERVED_ARITY: dict[str, tuple[int, int | None]] = {
    "not": (1, 1),
    "and": (2, None),
    "or": (2, None),
    "if": (2, 2),
}


class ValidationError(ValueError):
    pass


def validate(expr: Expr) -> None:
    """Raise ValidationError if `expr` violates structural invariants."""
    for node in walk(expr):
        if isinstance(node, Atom):
            _check_ident(node.name, "atom")
        elif isinstance(node, Variable):
            _check_ident(node.name, "variable")
        elif isinstance(node, Call):
            _check_ident(node.head, "call head")
            if not isinstance(node.args, tuple):
                raise ValidationError("call arguments must be a tuple")
            arity = RESERVED_ARITY.get(node.head)
            if arity is not None:
                lo, hi = arity
                n = len(node.args)
                if n < lo or (hi is not None and n > hi):
                    expected = str(lo) if hi == lo else (f"{lo}+" if hi is None else f"{lo}..{hi}")
                    raise ValidationError(
                        f"reserved operator {node.head!r} expects arity {expected}, got {n}"
                    )
        else:
            raise ValidationError(f"unknown node type {type(node)!r}")


def _check_ident(name: str, kind: str) -> None:
    if not name or not IDENT_RE.match(name):
        raise ValidationError(f"malformed {kind} name {name!r}")
