"""Named adapter for the existing consumer policy; not a generic manifest loader."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import scir
from scir import Term
from scir.changes import ConflictError, propose
from scir.constraints import Violation
from scir.dialects import Context, Dialect, Rule, compose, evaluate, from_constraint
from scir.dialect_rules import FieldSet, record_fields, reference_targets, structured, working
from scir.knowledge import build_index

import policy


def context_from(trusted: policy.TrustedInputs, revision: str) -> Context:
    """The host supplies verified inputs; candidate records never call this function."""
    approvals = tuple(Term("approval", (Term(value),)) for value in sorted(trusted.approved_decisions))
    receipts = tuple(Term("receipt", (Term(key), Term(value.decision_snapshot),
                                      Term(value.operation), value.scope, Term(value.outcome)))
                     for key, value in sorted(trusted.receipts.items()))
    return Context("consumer-lifecycle-trust/1", revision, approvals + receipts)


def _trusted(context: Context) -> policy.TrustedInputs:
    if context.name != "consumer-lifecycle-trust/1":
        raise ValueError("unexpected consumer context")
    approvals, receipts = set(), {}
    for term in context.document:
        if term.symbol == "approval" and len(term.args) == 1 and not term.args[0].args:
            if term.args[0].symbol in approvals:
                raise ValueError("duplicate approval input")
            approvals.add(term.args[0].symbol)
        elif term.symbol == "receipt" and len(term.args) == 5:
            key, snapshot, operation, scope, outcome = term.args
            if any(t.args for t in (key, snapshot, operation, outcome)) or key.symbol in receipts:
                raise ValueError("invalid or duplicate receipt input")
            receipts[key.symbol] = policy.Receipt(snapshot.symbol, operation.symbol, scope, outcome.symbol)
        else:
            raise ValueError("invalid host input shape")
    return policy.TrustedInputs(frozenset(approvals), receipts)


def implementation_identity() -> str:
    """Local build identity, not a signature. Host attestation remains separate."""
    here = Path(__file__).resolve().parent
    package = Path(scir.__file__).resolve().parent
    # These files include the engine, adapters, helper configuration and domain rules.
    files = {"consumer/" + name: here / name for name in ("dialect.py", "policy.py")}
    files.update(("scir/" + path.name, path) for path in package.glob("*.py"))
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def contract() -> Dialect:
    identity = implementation_identity()
    base = Dialect("working-profile", "1", (
        from_constraint("structured", "1", identity, structured),
        from_constraint("working", "1", identity, working, requires=("structured",)),
    ))
    schema = {kind: FieldSet(optional=fields) for kind, fields in policy.FIELDS.items()}

    def domain(document, context):
        trusted = _trusted(context)  # Host input errors must be incomplete, not policy rejection.
        try:
            policy.check(build_index(document, collection="consumer-check"), trusted)
        except policy.PolicyError as error:
            yield Violation(None, "consumer-policy", str(error))

    return compose("consumer-lifecycle", "1", base, rules=(
        from_constraint("fields", "1", identity, record_fields(schema), requires=("working",)),
        from_constraint("decision-targets", "1", identity,
                        reference_targets("decision", {"Decision"}, source_kinds={"Task"}), requires=("working",)),
        from_constraint("evidence-targets", "1", identity,
                        reference_targets("evidence", {"Evidence"}, source_kinds={"Task"}), requires=("working",)),
        Rule("policy", "1", identity, domain, ("fields", "decision-targets", "evidence-targets")),
    ))


def propose_checked(index, request: str, dialect: Dialect, context: Context, *, expected_context: str):
    """Return only a conforming complete candidate and its bound validation result."""
    if context.fingerprint != expected_context:
        raise ConflictError("consumer context changed; review fresh authority and receipt inputs")
    candidate = propose(index, request)
    result = evaluate(candidate.document, dialect, context, collection=index.collection)
    if result.outcome == "incomplete":
        raise RuntimeError("consumer dialect validation did not complete")
    if not result.conforms:
        raise policy.PolicyError("consumer dialect rejected the candidate")
    return candidate, result
