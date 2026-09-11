"""Deterministic tree operations over immutable SCIR expressions."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from .ast import Atom, Call, Expr, Variable


def walk(expr: Expr) -> Iterator[Expr]:
    """Preorder walk of every node in the expression tree."""
    yield expr
    if isinstance(expr, Call):
        for arg in expr.args:
            yield from walk(arg)


def find_symbol(expr: Expr, name: str) -> list[Expr]:
    """Atoms, variables, and calls whose name/head equals `name`."""
    found: list[Expr] = []
    for node in walk(expr):
        if isinstance(node, Atom) and node.name == name:
            found.append(node)
        elif isinstance(node, Variable) and node.name == name:
            found.append(node)
        elif isinstance(node, Call) and node.head == name:
            found.append(node)
    return found


def filter_subtrees(expr: Expr, predicate: Callable[[Expr], bool]) -> list[Expr]:
    """Every subtree for which `predicate` is true, in preorder."""
    return [node for node in walk(expr) if predicate(node)]


def replace(expr: Expr, target: Expr, replacement: Expr) -> Expr:
    """Replace every subtree structurally equal to `target`.

    Matching nodes are replaced whole; the replacement is not itself walked
    for further substitution in this pass.
    """
    if expr == target:
        return replacement
    if isinstance(expr, Call):
        return Call(
            expr.head,
            tuple(replace(arg, target, replacement) for arg in expr.args),
        )
    return expr
