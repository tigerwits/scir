"""Structural matching, occurrence, and assertion."""

from __future__ import annotations

from .ast import Atom, Call, Expr, Variable
from .tree import walk

Bindings = dict[str, Expr]


def match(pattern: Expr, subject: Expr) -> Bindings | None:
    """Top-level structural match. Returns bindings, or None on failure."""
    bindings: Bindings = {}
    if _unify(pattern, subject, bindings):
        return bindings
    return None


def occurs(pattern: Expr, subject: Expr) -> list[Bindings]:
    """Bindings for every subtree of `subject` that matches `pattern`."""
    results: list[Bindings] = []
    for node in walk(subject):
        bindings = match(pattern, node)
        if bindings is not None:
            results.append(bindings)
    return results


def asserted_nodes(expr: Expr) -> list[Expr]:
    """Nodes treated as top-level assertions of `expr`.

    The root is always included. Conjunction arguments are included
    recursively. Descent does not enter `not`, `or`, `if`, or ordinary calls.
    """
    nodes: list[Expr] = []

    def collect(node: Expr) -> None:
        nodes.append(node)
        if isinstance(node, Call) and node.head == "and":
            for arg in node.args:
                collect(arg)

    collect(expr)
    return nodes


def asserted(pattern: Expr, subject: Expr) -> list[Bindings]:
    """Bindings for asserted nodes of `subject` that match `pattern`."""
    results: list[Bindings] = []
    for node in asserted_nodes(subject):
        bindings = match(pattern, node)
        if bindings is not None:
            results.append(bindings)
    return results


def query(
    subject: Expr,
    pattern: Expr,
    *,
    recursive: bool = True,
) -> list[Bindings]:
    """Match `pattern` against `subject`.

    `recursive=True` is subtree matching (`occurs`).
    `recursive=False` is top-level matching only.
    """
    if recursive:
        return occurs(pattern, subject)
    bindings = match(pattern, subject)
    return [] if bindings is None else [bindings]


def _unify(pattern: Expr, subject: Expr, bindings: Bindings) -> bool:
    if isinstance(pattern, Variable):
        bound = bindings.get(pattern.name)
        if bound is None:
            bindings[pattern.name] = subject
            return True
        return bound == subject
    if isinstance(pattern, Atom):
        return isinstance(subject, Atom) and pattern.name == subject.name
    if isinstance(pattern, Call):
        if not isinstance(subject, Call):
            return False
        if pattern.head != subject.head:
            return False
        if len(pattern.args) != len(subject.args):
            return False
        for p_arg, s_arg in zip(pattern.args, subject.args):
            if not _unify(p_arg, s_arg, bindings):
                return False
        return True
    return False
