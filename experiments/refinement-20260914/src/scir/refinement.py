"""Opt-in cumulative validation plans; ordinary SCIR data, not kernel semantics.

A caller explicitly selects validation(NAME, stage(ID, parents(...), rules(...)),
...) and supplies trusted, deterministic checker bindings. Stage inheritance is
conjunction, never override. No imports, evaluation, rewriting, or proof checking
are inferred from content labels. The registry is trusted Python, not a sandbox.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .core import Document, Term, check_symbol, digest
from .constraints import Constraint, Violation, check


@dataclass(frozen=True)
class Checker:
    run: Constraint
    requires: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not callable(self.run) or type(self.requires) is not tuple:
            raise ValueError("a checker needs a callable and a tuple of prerequisite names")
        for name in self.requires:
            check_symbol(name)
        if len(set(self.requires)) != len(self.requires):
            raise ValueError("duplicate checker prerequisite")


@dataclass(frozen=True)
class Stage:
    name: str
    checks: tuple[tuple[str, Checker], ...]


@dataclass(frozen=True)
class Profile:
    name: str
    fingerprint: str
    stages: tuple[Stage, ...]

    def stage(self, name: str) -> Stage:
        for stage in self.stages:
            if stage.name == name:
                return stage
        raise ValueError(f"unknown stage {name!r}")


@dataclass(frozen=True)
class Evaluation:
    profile: str
    stage: str
    input_fingerprint: str
    scheduled: tuple[str, ...]
    executed: tuple[str, ...]
    violations: tuple[Violation, ...]

    @property
    def conforms(self) -> bool:
        return not self.violations and self.executed == self.scheduled


def _leaf(term: Term) -> str:
    if term.args:
        raise ValueError("expected a leaf identifier")
    return term.symbol


def _names(term: Term, head: str) -> tuple[str, ...]:
    if term.symbol != head:
        raise ValueError(f"expected {head} group")
    names = tuple(_leaf(child) for child in term.args)
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate identifier in {head}")
    return names


def compile_profile(document: Document, name: str,
                    registry: Mapping[str, Checker]) -> Profile:
    """Compile a bounded stage DAG. Unselected symbolic roots stay inert.

All stages of the selected profile must resolve, even if not evaluated. Ordered
parent union preserves each parent's prerequisite order and evaluates inherited
checker names once. An incompatible ordered union is rejected rather than reordered.
The fingerprint covers selected plan data, NOT the Python checker implementation.
"""
    check(document, ())
    check_symbol(name)
    matches = [t for t in document if t.symbol == "validation" and t.args
               and not t.args[0].args and t.args[0].symbol == name]
    if len(matches) != 1:
        raise ValueError("select exactly one named validation profile")
    root = matches[0]
    if not 1 <= len(root.args) - 1 <= 128:
        raise ValueError("a profile must declare 1..128 stages")
    declarations = {}
    for term in root.args[1:]:
        if term.symbol != "stage" or len(term.args) != 3:
            raise ValueError("expected stage(ID, parents(...), rules(...))")
        stage = _leaf(term.args[0])
        if stage in declarations:
            raise ValueError(f"duplicate stage {stage!r}")
        declarations[stage] = (_names(term.args[1], "parents"),
                               _names(term.args[2], "rules"))
    bindings = dict(registry)
    for parents, rules in declarations.values():
        for parent in parents:
            if parent not in declarations:
                raise ValueError(f"unknown parent stage {parent!r}")
        for rule in rules:
            if rule not in bindings or type(bindings[rule]) is not Checker:
                raise ValueError(f"unknown checker {rule!r}")
    pending, compiled, total = dict(declarations), {}, 0
    while pending:
        ready = [s for s, (parents, _) in pending.items()
                 if all(p in compiled for p in parents)]
        if not ready:
            raise ValueError("cyclic stage inheritance")
        for stage in ready:
            parents, local = pending.pop(stage)
            names = dict.fromkeys(r for p in parents for r, _ in compiled[p].checks)
            names.update(dict.fromkeys(local))
            total += len(names)
            if total > 8192:
                raise ValueError("profile exceeds 8192 compiled checker occurrences")
            seen = set()
            for rule in names:
                missing = set(bindings[rule].requires) - seen
                if missing:
                    raise ValueError(f"{stage}: {rule} missing prior checks {sorted(missing)}")
                seen.add(rule)
            candidate = Stage(stage, tuple((r, bindings[r]) for r in names))
            for parent in parents:
                require_extension(compiled[parent], candidate)
            compiled[stage] = candidate
    return Profile(name, digest((root,)), tuple(compiled[s] for s in declarations))


def evaluate(document: Document, profile: Profile, stage: str, *,
             max_violations: int = 1000) -> Evaluation:
    """Stop on a failed check; exceptions and exhausted budgets never conform.

Diagnostics retain paths into the unchanged input. A result lists checks actually
completed; later checks are NOT claimed to have run. Checkers must be pure and
stable for the caller's pinned input/environment. Conformance is not truth.
"""
    selected = profile.stage(stage)
    executed = []

    def sequential(subject):
        for name, checker in selected.checks:
            failed = False
            for violation in checker.run(subject):
                failed = True
                yield violation
            executed.append(name)
            if failed:
                return

    issues = check(document, (sequential,), max_violations=max_violations)
    return Evaluation(profile.fingerprint, stage, digest(document),
                      tuple(n for n, _ in selected.checks), tuple(executed), issues)


def require_extension(before: Stage, after: Stage) -> None:
    """Reject removed, reordered or rebound checks in an in-process refinement.

Callable identity is a conservative guard, NOT semantic equivalence. Stable,
side-effect-free checker behavior is still a caller obligation. Cross-process
replay must also pin code and environment; a profile digest alone is insufficient.
"""
    positions = {name: (i, checker) for i, (name, checker) in enumerate(after.checks)}
    last = -1
    for name, checker in before.checks:
        i, replacement = positions.get(name, (-1, None))
        if (i <= last or replacement is None or replacement.run is not checker.run
                or replacement.requires != checker.requires):
            raise ValueError(f"refinement removed, reordered or rebound {name!r}")
        last = i
