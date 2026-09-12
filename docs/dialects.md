# Constrained dialects

A dialect selects a subset of SCIR documents. It changes neither the content
kernel nor its syntax. `scir.constraints` provides optional acceptance checks;
it leaves structural `validate`, the CLI, and fingerprints unchanged.

## Small API

```python
from scir import parse_document, parse_pattern, validate
from scir.constraints import check, forms, vocabulary

email = (
    forms(parse_pattern("email(?sender, ?recipient, ?thing)")),
    vocabulary({"email", "Alice", "Bob", "Report"}),
)
assert check(parse_document("email(Alice, Bob, Report)"), email) == ()

other = parse_document("email(Alice, Bob, Reprot)")
validate(other)
issue, = check(other, email)
assert issue.path == (0, 2)
assert issue.rule == "vocabulary"
```

Both documents are valid SCIR; only the first conforms. A dialect is an ordered
collection of functions, not a registry or class. Applications name and version
it. Combine collections with tuple concatenation.

| Name in `scir.constraints` | Contract |
|---|---|
| `Violation(path, rule, message)` | Immutable diagnostic. Path is a snapshot-local occurrence or `None` for the whole document. Rule and message are nonempty Unicode-scalar strings. |
| `Constraint` | `Callable[[Document], Iterable[Violation]]`. |
| `check(document, constraints, *, max_violations=1000)` | Validate document shape and bounds, then collect violations in rule order. An empty tuple means conformance. |
| `forms(*patterns, scope="roots", rule="form")` | Every selected occurrence must match at least one supplied Pattern. |
| `vocabulary(symbols, *, rule="vocabulary")` | Restrict all labels, including leaves, to a copied allowlist. |

Helpers accept parsed Patterns and symbol collections, not a schema language.
Labels are exact, case-sensitive Unicode strings. `vocabulary` snapshots its
allowlist; custom rules must control their own captured state.

## Forms constrain scope, not truth

Patterns within `forms` are alternatives; separate rules passed to `check` are
conjunctive. Each match has independent captures. Repeated captures require
structural equality. A successful ground match returns `{}`, not failure.

Root scope is the default. A capture does not constrain its payload:

```python
from scir import parse_document, parse_pattern
from scir.constraints import check, forms

content = parse_document("hypothesis(H1, anything(Whatever))")
envelope = forms(parse_pattern("hypothesis(?id, ?content)"))
assert check(content, (envelope,)) == ()
strict = forms(parse_pattern("hypothesis(?id, stale(Cache))"))
assert check(content, (strict,))
```

`scope="all"` checks every occurrence, including leaves. Neither scope derives
facts or moves captured content outside its enclosing terms.

These helpers impose universal restrictions, not existence requirements. Empty
documents pass vacuously. An empty form allowlist accepts only empty documents.
Require content with a separate rule:

```python
from scir.constraints import Violation, check

def nonempty(document):
    if not document:
        yield Violation(None, "nonempty", "at least one record is required")

assert check((), (nonempty,))[0].rule == "nonempty"
```

## Open identifiers, constrained payloads

The [investigation example](../examples/dialects.py) checks these records:

```scir
hypothesis(H1, causes(stale(Cache), wrong(Report)))
observation(O1, stale(Cache))
supports(O1, H1)
```

Its local conventions are `hypothesis(id, content)`, `observation(id, content)`,
and `supports(observationID, hypothesisID)`. Four rules enforce root shapes and
presence, leaf identifiers, permitted payload forms, and unique/resolvable IDs.

A two-pass index permits forward references. Duplicate declarations never choose
a winner; references must resolve to the appropriate kind. Malformed records
receive shape diagnostics and are skipped by reference checks. Nested records
are not declarations.

Identifiers stay open: `hypothesis("new ID", stale(Cache))` is permitted.
Payload restrictions apply only to payload positions, avoiding a global allowlist
of every possible ID. Changing the support target to `H7` produces:

```text
path=(2, 1), rule=unknown-reference, message=no declaration for H7
```

The example explicitly edits the reference and rechecks. Validation never repairs
spelling, invents declarations, or mutates content. Captured payloads remain open
within the permitted forms: this is not a causal type system or proof of support.
Stricter applications can add rules without changing SCIR.

## Correlated alternatives

The example also checks separate candidate Documents against
`edits(?person, reportOf(?person))`. Alice/Alice and Carol/Carol conform; crossed
actor/owner pairs fail. Both readings can pass without resolving the pronoun.

`check` accepts Documents, not Bundles or Alternatives. Check candidates separately
or select one explicitly; do not flatten them. Conformance can inform application
policy but does not establish the intended interpretation.

```bash
python examples/dialects.py
```

## Diagnostics and failures

Diagnostics follow supplied rule order and each rule's output order. Helpers use
occurrence preorder. Duplicate rules and occurrences retain duplicate findings.
Rule order and duplication preserve mathematical acceptance, not diagnostic order
or behavior when resource limits are exceeded.

Paths must exist in this snapshot; `None` targets the document. Invalid paths,
non-Violation results, non-callable rules, and invalid helper configuration are
errors. Callback exceptions propagate. Returning `None` instead of an iterable
is an error, not an empty result.

`check` preflights up to 100,000 occurrences and depth 128 before calling rules.
Root depth is zero. `max_violations` is a positive integer: exactly that many may
be returned, but the next raises `ValueError`. No partial report is returned.
Never convert an exception or incomplete check into an empty diagnostics tuple.

## Trust and context

Rules are trusted Python code. They can fail, run forever, mutate state, or use
ordinary process privileges. Interface bounds do not bound callback time or all
allocation. Do not execute rules supplied by untrusted documents or agents.

Deterministic rules terminate and depend only on the document and fixed inputs.
Capture external registries as immutable snapshots; live clock, network, or
database reads do not meet that condition. Consumers select contracts out of band:
`dialect(Relaxed)` in content cannot weaken the required checks.

A validation record should identify the content fingerprint, contract version,
checker, and context snapshot. Rule names are diagnostic labels, not code hashes;
a content digest alone certifies no conformance. Revalidate after edits or document
combination unless a preservation law applies. See [theory](theory.md#dialects-as-subsets).
