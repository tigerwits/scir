"""Trusted policy for this example only; no rule code is loaded from records."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from scir import Term, digest, parse
from scir.changes import propose
from scir.knowledge import Index, build_index
from scir import profile as p

STAGING = parse('"scir.tuple"(environment(staging))')
ACTION = parse('send(doc, "scir.kw"(from(alice), to(bob)))')
RECOVERY = parse('when(ambiguous(submission), require(before(lookup(originalKey), retry(originalKey))))')
MAX_RECORDS = 256


class PolicyError(p.ProfileError):
    """This consumer rejects a structurally valid commitment."""


def require(value, message):
    if not value:
        raise PolicyError(message)


def references(value):
    require(not p.read_fields(value), "expected a plain reference tuple")
    return tuple(p.read_reference(t) for t in p.read_tuple(value))


@dataclass(frozen=True, slots=True)
class Receipt:
    decision_snapshot: str
    operation: str
    scope: Term
    outcome: str


@dataclass(frozen=True, slots=True)
class TrustedInputs:
    """Already verified external inputs. Records cannot construct this trust boundary."""
    approved_decisions: frozenset[str]
    receipts: Mapping[str, Receipt]

    def __post_init__(self):
        object.__setattr__(self, "approved_decisions", frozenset(self.approved_decisions))
        object.__setattr__(self, "receipts", MappingProxyType(dict(self.receipts)))


@dataclass(frozen=True, slots=True)
class Resolution:
    status: str
    ids: tuple[str, ...]


def effective(index: Index, identifier: str, *, scope: Term = STAGING) -> Resolution:
    """Resolve declared same-scope lineage. This result is not approval to act."""
    if len(index.records) > MAX_RECORDS:
        raise p.LimitError("consumer record budget exceeded")
    require(identifier in index.records and index.records[identifier].kind == "Decision", "unknown decision")
    successors = {i: [] for i, r in index.records.items() if r.kind == "Decision"}
    for child in successors:
        field = dict(index.records[child].fields).get("supersedes")
        for parent in references(field) if field is not None else ():
            require(parent in successors, "replacement target must be a decision")
            if child not in successors[parent]:
                successors[parent].append(child)
    seen, queue = {identifier}, deque((identifier,))
    while queue:
        for child in successors[queue.popleft()]:
            if child not in seen:
                seen.add(child)
                queue.append(child)
    ordered = tuple(i for i in index.records if i in seen)
    if any(dict(index.records[i].fields).get("scope") != scope for i in ordered):
        return Resolution("scope-mismatch", ordered)
    # Kahn's algorithm avoids unbounded recursion and detects any reachable cycle.
    indegree = dict.fromkeys(ordered, 0)
    for parent in ordered:
        for child in successors[parent]:
            indegree[child] += 1
    queue = deque(i for i in ordered if indegree[i] == 0)
    visited = 0
    while queue:
        visited += 1
        for child in successors[queue.popleft()]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(ordered):
        return Resolution("cycle", ordered)
    terminal = tuple(i for i in ordered if not successors[i])
    if len(terminal) != 1:
        return Resolution("competing", terminal)
    status = dict(index.records[terminal[0]].fields).get("status")
    return Resolution("resolved" if status == Term("approved") else "unapproved", terminal)


def check(index: Index, trusted: TrustedInputs) -> None:
    """Check the whole candidate. Completion needs trusted external receipts."""
    if len(index.records) > MAX_RECORDS:
        raise p.LimitError("consumer record budget exceeded")
    allowed = {
        "Decision": {"status", "scope", "supersedes", "reason"},
        "Recovery": {"scope", "reason"},
        "Evidence": {"scope", "subject", "receipt", "operation", "outcome", "reason"},
        "Task": {"scope", "status", "decision", "recovery", "dependsOn", "evidence", "reason"},
        "Note": {"reason"},
    }
    for record in index.records.values():
        fields = dict(record.fields)
        require(record.kind in allowed and set(fields) <= allowed[record.kind], "unknown consumer kind or field")
        if record.kind != "Note":
            require(fields.get("scope") == STAGING, "staging scope is required")
        if record.kind == "Decision":
            require(record.payload == ACTION, "decision action or roles changed")
            require(fields.get("status") in (Term("proposed"), Term("approved")), "invalid decision status")
            if fields["status"] == Term("approved"):
                require(digest((record.term,)) in trusted.approved_decisions, "approval is not backed by trusted input")
            if "supersedes" in fields:
                require(all(index.records[i].kind == "Decision" for i in references(fields["supersedes"])),
                        "replacement target must be a decision")
        elif record.kind == "Recovery":
            require(record.payload == RECOVERY, "recovery key, condition or order changed")
        elif record.kind == "Evidence":
            require({"subject", "receipt", "operation", "outcome"} <= fields.keys(), "incomplete evidence claim")
            subject = p.read_reference(fields["subject"])
            require(index.records[subject].kind == "Decision", "evidence subject is not a decision")
            require(all(not fields[k].args for k in ("receipt", "operation", "outcome")), "evidence coordinates must be leaves")
        elif record.kind == "Task":
            require(record.payload == ACTION, "task action or roles changed")
            require({"decision", "recovery", "dependsOn", "status"} <= fields.keys(), "task prerequisites are missing")
            decision, recovery = (p.read_reference(fields[k]) for k in ("decision", "recovery"))
            require(index.records[decision].kind == "Decision" and index.records[recovery].kind == "Recovery", "wrong prerequisite kinds")
            dependencies = references(fields["dependsOn"])
            require(len(dependencies) == 2 and set(dependencies) == {decision, recovery}, "declared dependencies do not match prerequisites")
            status = fields["status"]
            require(status in (Term("blocked"), Term("ready"), Term("completed")), "invalid task status")
            if status == Term("blocked"):
                continue
            resolved = effective(index, decision)
            require(resolved == Resolution("resolved", (decision,)), "task decision is stale or unresolved")
            fingerprint = digest((index.records[decision].term,))
            require(fingerprint in trusted.approved_decisions, "task has no trusted approval")
            require("evidence" in fields, "task needs execution evidence")
            observed = set()
            for identifier in references(fields["evidence"]):
                evidence = index.records[identifier]
                require(evidence.kind == "Evidence", "task evidence must reference evidence records")
                values = dict(evidence.fields)
                require({"subject", "receipt", "operation", "outcome", "scope"} <= values.keys(), "incomplete evidence claim")
                require(p.read_reference(values["subject"]) == decision, "evidence refers to another decision")
                key = values["receipt"].symbol
                actual = trusted.receipts.get(key)
                claimed = Receipt(fingerprint, values["operation"].symbol, values["scope"], values["outcome"].symbol)
                require(actual == claimed, "evidence does not match a trusted receipt")
                observed.add((actual.operation, actual.outcome))
            require(("test", "passed") in observed, "ready task needs a passing test receipt")
            if status == Term("completed"):
                require(("delivery", "completed") in observed, "completed task needs a delivery receipt")


def propose_checked(index: Index, request: str, trusted: TrustedInputs):
    """Return a pure proposal only after complete profile and consumer checks."""
    candidate = propose(index, request)
    check(build_index(candidate.document, collection=index.collection), trusted)
    return candidate
