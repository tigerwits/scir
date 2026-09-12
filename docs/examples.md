# Worked examples

Run the checked workflows after installing the package:

```bash
python examples/workflows.py
python examples/dialects.py
```

Each example defines local vocabulary. The library checks structure, not whether
the English interpretation is faithful. The [agent setup](agents.md) includes a
separate-project exercise with a deliberately invalid reference.

## Working knowledge and authored prose

[Architecture, investigation, and mathematics](../examples/knowledge/README.md)
show a different use: SCIR retains working detail while a human-friendly overview
is written independently. Their read-only checker validates source bookkeeping
and follows declared dependencies. It does not generate the overview or certify
its meaning.

```bash
python examples/knowledge/run.py
python examples/knowledge/run.py --case mathematics --changed A2
```

The second command flags premise `A2`, conclusions `C1` and `C2`, and limitation
`L1` for review. It follows declared dependencies without deciding whether those
statements are true. The examples also retain a withdrawn proposal and unresolved
competing hypotheses.

## Incident investigation

**Source:** Monitor reports a Checkout timeout while contacting Database. Alice
suspects stale pooled connections; Bob suspects overload. Trace17 records reuse
of expired Connection7. Trace18 is cited against overload. Restart needs OnCall approval.

[incident.scir](../examples/incident.scir):

```scir
reported(Monitor, timeout(Checkout, Database))
suspects(Alice, causes(stale(ConnectionPool), timeout(Checkout, Database)))
suspects(Bob, causes(overload(Database), timeout(Checkout, Database)))
recorded(Trace17, reuse(Checkout, expired(Connection7)))
contradicts(Trace18, overload(Database))
requires(restart(Checkout), approval(OnCall))
```

Conventions: `reported(source, content)`, `suspects(person, explanation)`,
`causes(cause, effect)`, `contradicts(evidence, content)`, and
`requires(action, prerequisite)`. Trace labels are references; SCIR does not fetch them.

The workflow joins root-level hypotheses and contradiction records by exact
`cause` equality, returning `Bob / Trace18`. This records a challenge to Bob's
explanation—not proof that Bob is wrong or Alice right. The timeout has zero
root matches and three nested occurrences, not necessarily three real events.
The restart requirement grants no permission to restart anything.

## Corrected handoff

**Source:** Alice's R1 reports Database unavailable. R2 corrects R1: ConnectionPool
is exhausted. On parse failure, ParseTask must preserve Payload, return Error,
and leave State unchanged. It must not evaluate symbols; its TestSuite must pass.

[handoff.scir](../examples/handoff.scir):

```scir
report(R1, Alice, unavailable(Database))
correction(R2, Alice, R1, exhausted(ConnectionPool))
requires(ParseTask, on(failure(ParseDocument), all(preserve(Payload), return(Error), unchanged(State))))
forbids(ParseTask, evaluate(Symbols))
requires(ParseTask, pass(TestSuite))
```

Conventions: `report(id, author, content)`,
`correction(id, author, previousReport, replacementContent)`,
`requires(task, obligation)`, and `forbids(task, action)`.
`on(condition, obligations)` and `all(...)` organize requirements; they execute nothing.

The workflow joins R2 to R1 by ID, retaining both records. It neither promotes
either payload to a fact nor applies a “latest report wins” rule. It captures the
whole conditional obligation: `unchanged(State)` is not an unconditional guarantee.

An explicit edit replaces `TestSuite` with `RegressionSuite` at `(4, 1, 0)`.
Earlier roots remain unchanged. An old annotation fails against the new snapshot,
even when its path still exists. Transport reconstructs the edited document exactly.

## Correlated ambiguity

**Source:** “She edits her own report.” Context permits Alice or Carol as “she.”

```scir
edits(Alice, reportOf(Alice))
```

```scir
edits(Carol, reportOf(Carol))
```

Store these as separate candidate Documents in `Alternatives`. The local
`reportOf(person)` convention shares the actor. The repeated-capture pattern
`edits(?person, reportOf(?person))` matches both and rejects crossed pairs.

That is structural consistency, not pronoun resolution. `choose(1)` explicitly
selects Carol's reading without certifying it. Treating Alternatives as a Document
or erasing it as metadata fails. Candidate lists need not exhaust all readings.

## Dialect checks

The [dialect guide](dialects.md) adds fixed vocabulary, open identifiers, payload
forms, unique declarations, and forward-reference checks. A document may parse
but fail that contract; diagnostics identify the offending occurrences.

## Handoff checklist

Keep the source, local vocabulary, and enclosing scope with query results. Preserve
unresolved readings. Treat requirements as records, not authorization. After an
edit, recheck the contract and review metadata before attaching it anew.

[API](api.md) explains the operations. [Research](research/README.md) separates
these structural checks from an evaluation of actual agent handoffs.
