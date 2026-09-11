"""One-way matching and simultaneous substitution; data cannot contain holes."""
from __future__ import annotations

from dataclasses import dataclass
from .core import IDENT, Term, check_symbol, format_symbol


@dataclass(frozen=True, slots=True)
class Var:
    name: str

    def __post_init__(self) -> None:
        if type(self.name) is not str or not IDENT.fullmatch(self.name):
            raise ValueError("invalid metavariable name")

    def __str__(self) -> str:
        return "?" + self.name


@dataclass(frozen=True, slots=True)
class Node:
    symbol: str
    args: tuple[Pattern, ...] = ()

    def __str__(self) -> str:
        head = format_symbol(self.symbol)
        return head if not self.args else head + "(" + ", ".join(map(str, self.args)) + ")"

    def __post_init__(self) -> None:
        check_symbol(self.symbol)
        if type(self.args) is not tuple or any(type(a) not in (Node, Var) for a in self.args):
            raise ValueError("pattern arguments must be Nodes or Vars")


Pattern = Node | Var
Bindings = dict[str, Term]


def match(pattern: Pattern, subject: Term) -> Bindings | None:
    if type(pattern) not in (Node, Var) or type(subject) is not Term:
        raise ValueError("match expects a pattern and a ground Term")
    bindings: Bindings = {}
    pending = [(pattern, subject)]
    while pending:
        p, t = pending.pop()
        if isinstance(p, Var):
            if p.name == "_":
                continue
            if p.name in bindings and bindings[p.name] != t:
                return None
            bindings[p.name] = t
        else:
            if p.symbol != t.symbol or len(p.args) != len(t.args):
                return None
            pending.extend(zip(reversed(p.args), reversed(t.args)))
    return bindings


def instantiate(pattern: Pattern, bindings: Bindings) -> Term:
    """Simultaneous substitution; missing captures/wildcards are errors."""
    if isinstance(pattern, Var):
        if pattern.name == "_" or pattern.name not in bindings:
            raise ValueError(f"no substitution for {pattern}")
        value = bindings[pattern.name]
        if type(value) is not Term:
            raise ValueError("substitutions must be ground Terms")
        return value
    if type(pattern) is not Node:
        raise ValueError("expected a pattern")
    return Term(pattern.symbol, tuple(instantiate(a, bindings) for a in pattern.args))


def variables(pattern: Pattern) -> set[str]:
    if type(pattern) not in (Node, Var):
        raise ValueError("expected a pattern")
    pending, found = [pattern], set()
    while pending:
        p = pending.pop()
        if isinstance(p, Var):
            found.add(p.name)
        else:
            pending.extend(p.args)
    return found
