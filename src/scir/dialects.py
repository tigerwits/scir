"""Named, dependency-ordered acceptance contracts. No content-driven code loading."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Callable, Iterable

from .core import Document, check_symbol, digest
from .constraints import Constraint, Violation
from .tree import at
from . import profile as p

VERSION = "scir-dialect/1"
RESULT_VERSION = "scir-dialect-result/1"
MAX_RULES = 256
MAX_DESCRIPTOR_BYTES = 256_000
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _name(value: str) -> None:
    check_symbol(value)
    if len(value.encode("utf-8")) > 1024:
        raise ValueError("dialect identifier exceeds 1024 UTF-8 bytes")


def _positive(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(name + " must be a positive integer")


def _wire(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Context:
    """Host-supplied fixed data and revision. Content cannot confer its trust."""
    name: str
    revision: str
    document: Document = ()

    def __post_init__(self) -> None:
        _name(self.name)
        _name(self.revision)
        p.measure(self.document)

    def as_dict(self) -> dict:
        return {"name": self.name, "revision": self.revision,
                "content_snapshot": digest(self.document)}

    @property
    def fingerprint(self) -> str:
        return _hash(_wire(self.as_dict()))


Check = Callable[[Document, Context], Iterable[Violation]]


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    version: str
    implementation: str
    run: Check
    requires: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _name(self.name)
        _name(self.version)
        if type(self.implementation) is not str or not _HASH.fullmatch(self.implementation):
            raise ValueError("implementation must be a declared lowercase SHA-256")
        if not callable(self.run) or type(self.requires) is not tuple:
            raise ValueError("rule needs a callable and immutable prerequisite names")
        if len(self.requires) > MAX_RULES or len(set(self.requires)) != len(self.requires):
            raise ValueError("duplicate or excessive prerequisites")
        for name in self.requires:
            _name(name)
        if self.name in self.requires:
            raise ValueError("rule cannot require itself")

    def as_dict(self) -> dict:
        return {"name": self.name, "version": self.version,
                "implementation": self.implementation, "requires": list(self.requires)}


def from_constraint(name: str, version: str, implementation: str,
                    constraint: Constraint, *, requires: tuple[str, ...] = ()) -> Rule:
    """Adapt an existing document-local constraint; do not reinterpret its errors."""
    if not callable(constraint):
        raise ValueError("expected a trusted constraint")

    def run(document, context):
        return constraint(document)

    return Rule(name, version, implementation, run, requires)


@dataclass(frozen=True, slots=True)
class Dialect:
    name: str
    version: str
    rules: tuple[Rule, ...]

    def __post_init__(self) -> None:
        _name(self.name)
        _name(self.version)
        if type(self.rules) is not tuple or len(self.rules) > MAX_RULES:
            raise ValueError("dialect needs an immutable tuple of at most 256 rules")
        prior = set()
        for rule in self.rules:
            if type(rule) is not Rule or rule.name in prior:
                raise ValueError("dialect rules must have unique names")
            if not set(rule.requires) <= prior:
                raise ValueError("prerequisites must be declared before " + rule.name)
            prior.add(rule.name)
        if len(_wire(self.as_dict()).encode("utf-8")) > MAX_DESCRIPTOR_BYTES:
            raise p.LimitError("dialect descriptor budget exceeded")

    def as_dict(self) -> dict:
        return {"schema": VERSION, "name": self.name, "version": self.version,
                "rules": [r.as_dict() for r in self.rules]}

    @property
    def fingerprint(self) -> str:
        return _hash(_wire(self.as_dict()))


def compose(name: str, version: str, *parents: Dialect,
            rules: tuple[Rule, ...] = ()) -> Dialect:
    """Ordered union, with no inherited rule removal, reorder or rebinding."""
    if len(parents) > MAX_RULES or type(rules) is not tuple:
        raise ValueError("invalid parent/rule collection")
    inherited = {}
    for parent in parents:
        if type(parent) is not Dialect:
            raise ValueError("expected Dialect parents")
        for rule in parent.rules:
            old = inherited.get(rule.name)
            if old is not None and (old.as_dict() != rule.as_dict() or old.run is not rule.run):
                raise ValueError("inherited checker was rebound: " + rule.name)
            inherited.setdefault(rule.name, rule)
            if len(inherited) > MAX_RULES:
                raise p.LimitError("composed rule budget exceeded")
    positions = {key: i for i, key in enumerate(inherited)}
    for parent in parents:
        order = [positions[r.name] for r in parent.rules]
        if order != sorted(order):
            raise ValueError("incompatible parent rule order")
    return Dialect(name, version, tuple(inherited.values()) + rules)


@dataclass(frozen=True, slots=True)
class Step:
    rule: str
    status: str
    violations: tuple[Violation, ...] = ()
    blocked_by: tuple[str, ...] = ()
    error: str | None = None

    def as_dict(self) -> dict:
        return {"rule": self.rule, "status": self.status,
                "violations": [{"path": list(v.path) if v.path is not None else None,
                                "rule": v.rule, "message": v.message} for v in self.violations],
                "blocked_by": list(self.blocked_by), "error": self.error}


@dataclass(frozen=True, slots=True)
class Evaluation:
    collection: str
    content_snapshot: str
    dialect_json: str
    context_json: str
    steps: tuple[Step, ...]

    @property
    def outcome(self) -> str:
        if any(s.status == "incomplete" for s in self.steps):
            return "incomplete"
        return "rejected" if any(s.status != "passed" for s in self.steps) else "accepted"

    @property
    def conforms(self) -> bool:
        return self.outcome == "accepted"

    def as_dict(self) -> dict:
        return {"schema": RESULT_VERSION, "collection": self.collection,
                "content_snapshot": self.content_snapshot,
                "dialect": json.loads(self.dialect_json), "dialect_digest": _hash(self.dialect_json),
                "context": json.loads(self.context_json), "context_digest": _hash(self.context_json),
                "outcome": self.outcome, "complete": self.outcome != "incomplete",
                "all_executed": all(s.status in ("passed", "rejected") for s in self.steps),
                "steps": [s.as_dict() for s in self.steps]}

    def matches(self, document: Document, dialect: Dialect, context: Context, *, collection: str) -> bool:
        """Identity comparison only. It does not authenticate this result or the host."""
        p.measure(document)
        if type(dialect) is not Dialect or type(context) is not Context:
            raise ValueError("expected a Dialect and Context")
        _name(collection)
        return (self.collection == collection and self.content_snapshot == digest(document)
                and self.dialect_json == _wire(dialect.as_dict())
                and self.context_json == _wire(context.as_dict()))


class _InvalidDiagnostic(Exception):
    pass


class _OutputLimit(Exception):
    pass


def evaluate(document: Document, dialect: Dialect, context: Context, *, collection: str,
             max_violations: int = 1000, max_bytes: int = 1_000_000,
             limits: p.Limits = p.Limits()) -> Evaluation:
    """Evaluate trusted callbacks, skipping only checks with unpassed prerequisites.

A callback error yields incomplete, never empty successful diagnostics. Exceptions
from interrupt/exit requests propagate. Callbacks are not sandboxed or time-bounded.
"""
    if type(dialect) is not Dialect or type(context) is not Context:
        raise ValueError("expected a Dialect and Context")
    _name(collection)
    _positive(max_violations, "max_violations")
    _positive(max_bytes, "max_bytes")
    p.measure(document, limits=limits)
    p.measure(context.document, limits=limits)
    declaration, basis = _wire(dialect.as_dict()), _wire(context.as_dict())
    snapshot = digest(document)
    if len(declaration.encode("utf-8")) + len(basis.encode("utf-8")) > max_bytes:
        raise p.LimitError("validation metadata budget exceeded")
    steps, states, count, charged = [], {}, 0, 0
    for rule in dialect.rules:
        blockers = tuple(r for r in rule.requires if states[r] != "passed")
        if blockers:
            step = Step(rule.name, "blocked", blocked_by=blockers)
        else:
            violations = []
            try:
                for violation in rule.run(document, context):
                    if type(violation) is not Violation:
                        raise _InvalidDiagnostic("expected Violation")
                    if violation.path is not None:
                        try:
                            at(document, violation.path)
                        except (ValueError, IndexError, TypeError) as error:
                            raise _InvalidDiagnostic("invalid occurrence") from error
                    count += 1
                    charged += len(_wire({"path": violation.path, "rule": violation.rule,
                                          "message": violation.message}).encode("utf-8"))
                    if count > max_violations or charged > max_bytes:
                        raise _OutputLimit()
                    violations.append(violation)
                step = Step(rule.name, "rejected" if violations else "passed", tuple(violations))
            except _OutputLimit as error:
                raise p.LimitError("validation diagnostic/output budget exceeded") from error
            except Exception as error:
                # Discard partial diagnostics from a callback that did not finish.
                category = ("invalid-diagnostic" if isinstance(error, _InvalidDiagnostic)
                            else "resource-limit" if isinstance(error, p.LimitError)
                            else "callback-error")
                step = Step(rule.name, "incomplete", error=category)
        steps.append(step)
        states[rule.name] = step.status
    result = Evaluation(collection, snapshot, declaration, basis, tuple(steps))
    if len(_wire(result.as_dict()).encode("utf-8")) > max_bytes:
        raise p.LimitError("validation result byte budget exceeded")
    return result
