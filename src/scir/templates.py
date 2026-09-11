"""Experimental API-only acyclic macros. Definitions do not assert content."""
from __future__ import annotations

from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from .core import Document, Term, check_symbol, validate
from .patterns import IDENT, Bindings, Node, Pattern, Var, variables


@dataclass(frozen=True, slots=True)
class Definition:
    parameters: tuple[str, ...]
    body: Pattern

    def __post_init__(self) -> None:
        if type(self.parameters) is not tuple:
            raise ValueError("parameters must be a tuple")
        if any(type(p) is not str or not IDENT.fullmatch(p) or p == "_" for p in self.parameters):
            raise ValueError("parameters must be identifier names, excluding '_'")
        if len(set(self.parameters)) != len(self.parameters):
            raise ValueError("duplicate parameter")
        if variables(self.body) - set(self.parameters):
            raise ValueError("undeclared metavariable or wildcard in definition")


def expand(document: Document, definitions: dict[str, Definition], *, max_steps: int = 100_000) -> Document:
    """Bound definition checking and substitution before building expanded trees."""
    validate(document)
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps must be positive")
    if type(definitions) is not dict or len(definitions) > 128:
        raise ValueError("at most 128 named definitions are supported")
    for name, definition in definitions.items():
        check_symbol(name)
        if type(definition) is not Definition:
            raise ValueError("expected a Definition")
    remaining = max_steps

    def charge(depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 128:
            raise ValueError("macro expansion resource limit exceeded")

    dependencies = {}
    for name, definition in definitions.items():
        pending, used = [(definition.body, 0)], set()
        while pending:
            p, depth = pending.pop()
            charge(depth)
            if isinstance(p, Node):
                if p.symbol in definitions:
                    if len(p.args) != len(definitions[p.symbol].parameters):
                        raise ValueError(f"macro {p.symbol!r} arity mismatch")
                    used.add(p.symbol)
                if len(p.args) > remaining - len(pending):
                    raise ValueError("macro expansion resource limit exceeded")
                pending.extend((a, depth + 1) for a in p.args)
        dependencies[name] = used
    try:
        TopologicalSorter(dependencies).prepare()
    except CycleError as e:
        raise ValueError("recursive definitions are not allowed") from e

    def go(term: Term | Pattern, bindings: Bindings, depth: int = 0) -> Term:
        charge(depth)
        if isinstance(term, Var):
            # Actual arguments are already macro-free. Count each copied occurrence.
            return go(bindings[term.name], {}, depth)
        args = tuple(go(a, bindings, depth + 1) for a in term.args)
        if term.symbol not in definitions:
            return Term(term.symbol, args)
        definition = definitions[term.symbol]
        if len(args) != len(definition.parameters):
            raise ValueError(f"macro {term.symbol!r} arity mismatch")
        return go(definition.body, dict(zip(definition.parameters, args)), depth + 1)

    return tuple(go(t, {}) for t in document)
