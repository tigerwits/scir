"""Conservative kernel-only normalization."""

from __future__ import annotations

from .ast import Call, Expr


def normalize(expr: Expr) -> Expr:
    """Apply reserved `not`/`and`/`or` rewrites bottom-up.

    Ordinary symbols are not rewritten.
    """
    if not isinstance(expr, Call):
        return expr
    args = tuple(normalize(arg) for arg in expr.args)
    node = Call(expr.head, args)
    if node.head == "not" and len(node.args) == 1:
        inner = node.args[0]
        if isinstance(inner, Call) and inner.head == "not" and len(inner.args) == 1:
            return inner.args[0]
        return node
    if node.head in ("and", "or"):
        return _flatten(node.head, node.args)
    return node


def _flatten(head: str, args: tuple[Expr, ...]) -> Call:
    flat: list[Expr] = []
    for arg in args:
        if isinstance(arg, Call) and arg.head == head:
            flat.extend(arg.args)
        else:
            flat.append(arg)
    return Call(head, tuple(flat))
