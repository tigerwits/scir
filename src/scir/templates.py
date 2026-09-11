"""Experimental API-only acyclic macros. Definitions do not assert content."""
from __future__ import annotations

from dataclasses import dataclass
from .core import Document, Term, check_symbol, validate
from .patterns import IDENT, Node, Pattern, instantiate, variables


@dataclass(frozen=True, slots=True)
class Definition:
    parameters: tuple[str, ...]
    body: Pattern

    def __post_init__(self):
        if type(self.parameters) is not tuple or any(type(p) is not str or not IDENT.fullmatch(p) or p == "_" for p in self.parameters):
            raise ValueError("parameters must be identifier names, excluding '_'")
        if len(set(self.parameters)) != len(self.parameters):
            raise ValueError("duplicate parameter")
        if variables(self.body) - set(self.parameters):
            raise ValueError("undeclared metavariable or wildcard in definition")


def expand(document: Document, definitions: dict[str, Definition], *, max_steps=100_000) -> Document:
    validate(document)
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps must be positive")
    if type(definitions) is not dict or len(definitions) > 128:
        raise ValueError("at most 128 named definitions are supported")
    dependencies = {}
    for name, definition in definitions.items():
        check_symbol(name)
        if type(definition) is not Definition:
            raise ValueError("expected a Definition")
        pending, used = [definition.body], set()
        while pending:
            p = pending.pop()
            if isinstance(p, Node):
                if p.symbol in definitions:
                    used.add(p.symbol)
                pending.extend(p.args)
        dependencies[name] = used
    done = set()
    while len(done) < len(dependencies):
        ready = {n for n, deps in dependencies.items() if n not in done and deps <= done}
        if not ready:
            raise ValueError("recursive definitions are not allowed")
        done.update(ready)
    remaining = max_steps

    def go(term, depth=0):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 128:
            raise ValueError("macro expansion resource limit exceeded")
        args = tuple(go(a, depth + 1) for a in term.args)
        if term.symbol not in definitions:
            return Term(term.symbol, args)
        definition = definitions[term.symbol]
        if len(args) != len(definition.parameters):
            raise ValueError(f"macro {term.symbol!r} arity mismatch")
        body = instantiate(definition.body, dict(zip(definition.parameters, args)))
        return go(body, depth + 1)

    return tuple(go(t) for t in document)
