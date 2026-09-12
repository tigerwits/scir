"""Application-owned dialects and reviewed mappings for one fixed source.

Nothing here is a SCIR operator or a general English-equivalence checker.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
import re

from scir import Document, Term, parse, parse_pattern, query
from scir.constraints import Constraint, Violation, check
from scir.core import Path
from scir.patterns import match

CASE = "parser-requirements/1"
SOURCE_SHA256 = "c04efd69c0c30c0157c1bd07c6bcec574802871d315eeb0732a6bac2ebac18d8"
NAMES = ("generic", "vocabulary", "records", "references", "concrete-timeout")
FILES = tuple(f"{i:02d}-{name}.scir" for i, name in enumerate(NAMES[:4]))

# An authored oracle, independent of the editable stage files. It is not an NL parser.
COMMITMENTS = tuple(map(parse, (
    "requires(Parser, on(failure(Parse), return(Error)))",
    "requires(Parser, on(failure(Parse), unchanged(State)))",
    "forbids(Parser, evaluate(Payload))",
    "unspecified(timeoutPolicy(Parser))",
)))
DRAFT = tuple(map(parse, (
    "must(Parser, when(parseFails, return(Error)))",
    "must(Parser, when(parseFails, leaveUnchanged(State)))",
    "mustNot(Parser, evaluate(Payload))",
    "unspecified(timeoutPolicy(Parser))",
)))
TRANSLATIONS = dict(zip(DRAFT, COMMITMENTS))
STATEMENTS = {
    "requires": parse_pattern("requires(?owner, on(?condition, ?effect))"),
    "forbids": parse_pattern("forbids(?owner, evaluate(?payload))"),
    "unspecified": parse_pattern("unspecified(timeoutPolicy(?owner))"),
    "timeout": parse_pattern("timeout(?owner, ?duration)"),
}
DECLARATION = parse_pattern("condition(?id, failure(?operation))")


def statements(document: Document) -> Iterator[tuple[Path, Term]]:
    """Visit statement positions only; a declaration does not assert its condition."""
    for i, root in enumerate(document):
        if root.symbol == "condition":
            continue
        if root.symbol == "record" and len(root.args) == 2:
            yield (i, 1), root.args[1]
        else:
            yield (i,), root


def leaf_call(term: Term, heads: tuple[str, ...]) -> bool:
    return term.symbol in heads and len(term.args) == 1 and not term.args[0].args


def shapes(document: Document) -> Iterable[Violation]:
    """Fixed operation shapes, but open leaf identifiers in their stated positions."""
    for i, root in enumerate(document):
        if root.symbol == "condition":
            bindings = match(DECLARATION, root)
            if bindings is None or any(t.args for t in bindings.values()):
                yield Violation((i,), "shape", "expected condition(leafID, failure(leafOperation))")
        elif root.symbol == "record":
            if len(root.args) != 2 or root.args[0].args:
                yield Violation((i,), "shape", "expected record(leafID, statement)")

    for path, term in statements(document):
        pattern = STATEMENTS.get(term.symbol)
        bindings = None if pattern is None else match(pattern, term)
        if bindings is None:
            yield Violation(path, "shape", "expected requires, forbids, unspecified, or timeout statement")
            continue
        if term.symbol == "requires":
            if bindings["owner"].args:
                yield Violation(path + (0,), "shape", "component ID must be a leaf")
            if not leaf_call(bindings["condition"], ("failure", "ref")):
                yield Violation(path + (1, 0), "shape", "expected failure(leafOperation) or ref(leafID)")
            if not leaf_call(bindings["effect"], ("return", "unchanged")):
                yield Violation(path + (1, 1), "shape", "expected return(leafValue) or unchanged(leafState)")
        elif any(t.args for t in bindings.values()):
            yield Violation(path, "shape", "component, payload, and duration values must be leaves")


def named_records(document: Document) -> Iterable[Violation]:
    if not any(t.symbol == "record" and len(t.args) == 2 for t in document):
        yield Violation(None, "record-required", "at least one named record is required")
    for i, term in enumerate(document):
        if term.symbol not in ("record", "condition"):
            yield Violation((i,), "record-required", "wrap the statement in record(ID, statement)")


def declarations(document: Document) -> Iterator[tuple[Path, Term]]:
    for i, term in enumerate(document):
        if term.symbol in ("record", "condition") and len(term.args) == 2 and not term.args[0].args:
            yield (i,), term


def unique_ids(document: Document) -> Iterable[Violation]:
    seen = set()
    for path, term in declarations(document):
        name = term.args[0].symbol
        if name in seen:
            yield Violation(path + (0,), "unique-id", f"duplicate declaration {name}")
        seen.add(name)


def conditional_statements(document: Document) -> Iterator[tuple[Path, Term]]:
    for path, term in statements(document):
        if match(STATEMENTS["requires"], term) is not None:
            yield path, term


def reference_conditions(document: Document) -> Iterable[Violation]:
    for path, term in conditional_statements(document):
        if not leaf_call(term.args[1].args[0], ("ref",)):
            yield Violation(path + (1, 0), "reference-required", "conditional obligations must use ref(conditionID)")


def valid_references(document: Document) -> Iterable[Violation]:
    index = {}
    for _, term in declarations(document):
        name = term.args[0].symbol
        index[name] = None if name in index else term
    used = set()
    for path, term in conditional_statements(document):
        condition = term.args[1].args[0]
        if not leaf_call(condition, ("ref",)):
            continue  # The earlier shape rule diagnoses malformed structures.
        name = condition.args[0].symbol
        target = index.get(name)
        if name not in index:
            yield Violation(path + (1, 0, 0), "unknown-reference", f"no declaration for {name}")
        elif target is None:
            yield Violation(path + (1, 0, 0), "ambiguous-reference", f"duplicate declarations for {name}")
        elif target.symbol != "condition":
            yield Violation(path + (1, 0, 0), "reference-kind", f"{name} is not a condition")
        else:
            used.add(name)
    for path, term in declarations(document):
        if term.symbol == "condition" and term.args[0].symbol not in used:
            yield Violation(path, "unused-condition", "unused declaration cannot be silently discarded by projection")


def concrete_timeout(document: Document) -> Iterable[Violation]:
    durations = []
    for path, term in statements(document):
        if term == COMMITMENTS[3]:
            yield Violation(path, "timeout-unspecified", "target contract requires a concrete Parser timeout")
        bindings = match(STATEMENTS["timeout"], term)
        if bindings is not None and bindings["owner"] == Term("Parser"):
            durations.append(bindings["duration"])
            value = bindings["duration"]
            if value.args or not re.fullmatch(r"[1-9][0-9]*(?:ms|s|m)", value.symbol):
                yield Violation(path + (1,), "timeout-value", "expected a positive duration such as the label \"30s\"")
    if len(durations) != 1:
        yield Violation(None, "timeout-required", "exactly one concrete Parser timeout is required")


# Earlier contracts permit later representations. Later rules only restrict them.
ADDITIONS: tuple[tuple[Constraint, ...], ...] = (
    (), (shapes,), (named_records, unique_ids),
    (reference_conditions, valid_references), (concrete_timeout,),
)
CONTRACTS = tuple(tuple(rule for group in ADDITIONS[:i + 1] for rule in group)
                  for i in range(len(ADDITIONS)))


def require(document: Document, rules: tuple[Constraint, ...]) -> None:
    issues = check(document, rules)
    if issues:
        raise ValueError("; ".join(f"{v.path}: {v.rule}: {v.message}" for v in issues))


def translate_draft(document: Document) -> Document:
    """Apply four explicitly reviewed whole-statement mappings, not synonym inference."""
    try:
        return tuple(TRANSLATIONS[t] for t in document)
    except KeyError as e:
        raise ValueError(f"no reviewed draft mapping for {e.args[0]}") from e


def unrecord(document: Document) -> Document:
    require(document, CONTRACTS[2])
    return tuple(t if t.symbol == "condition" else t.args[1] for t in document)


def inline_statement(term: Term, index: dict[str, Term]) -> Term:
    if match(STATEMENTS["requires"], term) is not None:
        owner, clause = term.args
        condition, effect = clause.args
        if leaf_call(condition, ("ref",)):
            return Term("requires", (owner, Term("on", (index[condition.args[0].symbol], effect))))
    return term


def condition_index(document: Document) -> dict[str, Term]:
    return {t.args[0].symbol: t.args[1] for _, t in declarations(document) if t.symbol == "condition"}


def inline_conditions(document: Document) -> Document:
    """Partial projection: validated definitions only, no expansion below arbitrary heads."""
    require(document, CONTRACTS[3])
    index = condition_index(document)
    return tuple(Term("record", (t.args[0], inline_statement(t.args[1], index)))
                 for t in document if t.symbol == "record")


def source_review(document: Document, *, generic: bool = False) -> dict:
    """Compare to the fixed authored oracle; never claim general semantic equivalence."""
    if generic:
        claims = translate_draft(document)
    else:
        require(document, (shapes, unique_ids, valid_references))
        index = condition_index(document)
        claims = tuple(inline_statement(t, index) for _, t in statements(document))
    expected, actual = Counter(COMMITMENTS), Counter(claims)
    return {
        "status": "matches-authored-oracle" if actual == expected else "differs-from-authored-oracle",
        "commitments": {f"S{i + 1}": actual[t] == expected[t] for i, t in enumerate(COMMITMENTS)},
        "missing": [str(t) for t in (expected - actual).elements()],
        "unexpected": [str(t) for t in (actual - expected).elements()],
        "questions": {
            "state_unchanged_when": [str(h.bindings["guard"]) for h in query(
                claims, parse_pattern("requires(Parser, on(?guard, unchanged(State)))"))],
            "payload_evaluation_forbidden": bool(query(claims, parse_pattern("forbids(Parser, evaluate(Payload))"))),
            "timeout_unspecified": bool(query(claims, parse_pattern("unspecified(timeoutPolicy(Parser))"))),
            "timeout_values": [str(h.bindings["value"]) for h in query(claims, parse_pattern("timeout(Parser, ?value)"))],
            "parse_failure_effects": [str(h.bindings["effect"]) for h in query(
                claims, parse_pattern("requires(Parser, on(failure(Parse), ?effect))"))],
        },
    }
