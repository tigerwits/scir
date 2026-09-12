"""Optional acceptance rules over SCIR documents, never another content language."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .core import Document, Path, check_symbol, validate
from .patterns import Node, Pattern, Var, match
from .tree import at, walk


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path | None
    rule: str
    message: str

    def __post_init__(self) -> None:
        if self.path is not None and (
            type(self.path) is not tuple or not self.path
            or any(type(i) is not int or i < 0 for i in self.path)
        ):
            raise ValueError("violation path must be None or a nonempty tuple of nonnegative integers")
        check_symbol(self.rule)
        check_symbol(self.message)


Constraint = Callable[[Document], Iterable[Violation]]


def check(document: Document, constraints: Iterable[Constraint], *,
          max_violations: int = 1000) -> tuple[Violation, ...]:
    """Collect violations in rule order. An incomplete check raises, never passes."""
    validate(document)
    if type(max_violations) is not int or max_violations < 1:
        raise ValueError("max_violations must be a positive integer")
    # Iterators charge occurrences without buffering a wide root/child sequence.
    pending, count = [iter(document)], 0
    while pending:
        term = next(pending[-1], None)
        if term is None:
            pending.pop()
            continue
        count += 1
        if count > 100_000 or len(pending) > 129:
            raise ValueError("constraint input exceeds 100,000 occurrences or depth 128")
        if term.args:
            pending.append(iter(term.args))
    violations = []
    for constraint in constraints:
        if not callable(constraint):
            raise ValueError("a constraint must be callable")
        for violation in constraint(document):
            if type(violation) is not Violation:
                raise ValueError("a constraint must yield Violation records")
            if violation.path is not None:
                at(document, violation.path)
            if len(violations) == max_violations:
                raise ValueError("constraint diagnostic limit exceeded; check incomplete")
            violations.append(violation)
    return tuple(violations)


def forms(*patterns: Pattern, scope: str = "roots", rule: str = "form") -> Constraint:
    """Each selected occurrence must match at least one permitted pattern."""
    if any(type(p) not in (Node, Var) for p in patterns):
        raise ValueError("forms expects patterns, not source strings or ground Terms")
    if scope not in ("roots", "all"):
        raise ValueError("scope must be 'roots' or 'all'")
    check_symbol(rule)

    def constraint(document: Document) -> Iterable[Violation]:
        validate(document)
        nodes = walk(document) if scope == "all" else (((i,), t) for i, t in enumerate(document))
        for path, term in nodes:
            if not any(match(pattern, term) is not None for pattern in patterns):
                yield Violation(path, rule, "no permitted form matches this occurrence")

    return constraint


def vocabulary(symbols: Iterable[str], *, rule: str = "vocabulary") -> Constraint:
    """Restrict every label, including leaves, to a copied allowlist."""
    if isinstance(symbols, (str, bytes)):
        raise ValueError("vocabulary expects a collection of symbols, not one string")
    allowed = frozenset(symbols)
    for symbol in allowed:
        check_symbol(symbol)
    check_symbol(rule)

    def constraint(document: Document) -> Iterable[Violation]:
        for path, term in walk(document):
            if term.symbol not in allowed:
                yield Violation(path, rule, f"symbol {term.symbol!r} is not permitted")

    return constraint
