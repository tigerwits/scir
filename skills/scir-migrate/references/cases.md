# Choose what belongs underneath

The examples use local vocabulary, not a required schema. The SCIR retains working
detail; the human prose is deliberately written rather than rendered.

## Architecture: a proposal is not a decision

Source: EventStore uses an append-only log. Replay assumes deterministic handlers.
Checkpoint recovery is proposed under that assumption, not approved. Compaction
policy remains undecided.

```scir
record(D1, Decision, use(EventStore, AppendOnlyLog))
record(A1, Assumption, deterministic(Handlers))
record(P1, Proposal, unapproved(checkpointRecovery))
dependsOn(P1, A1)
record(Q1, Question, compactionPolicy(EventStore))
```

Human overview:

> The event history is our recovery foundation. Checkpoint recovery is still a
> proposal, and compaction policy is open. The working record preserves the
> handler assumption that the proposal relies on.

A review query can find `dependsOn(?proposal, A1)` without asking a model to reread
the overview. It does not determine whether the assumption is true.

## Research: preserve disagreement

Source: Mina attributes the regression to connection reuse. Arun suspects load.
Trace17 records reuse of an expired connection but does not settle the cause.

```scir
hypothesis(H1, Mina, causes(connectionReuse, Regression))
hypothesis(H2, Arun, causes(Load, Regression))
observation(O1, Trace17, reused(expired(Connection)))
unresolved(cause(Regression))
```

Human overview:

> The cause is still open. An expired connection was reused, but that observation
> does not yet distinguish connection reuse from load as the explanation.

Do not compress this to `causes(connectionReuse, Regression)`. The shorter record
would discard attribution and uncertainty. Compactness is less duplicated meaning,
not fewer symbols at any cost.

## A rationale may remain language

```scir
question(Q1, reconnectReads, "Must clients observe their earlier writes after reconnecting?")
dependsOn(StorageDecision, Q1)
```

The prose question already communicates its nuance. Its identity and relation to
a pending decision are what need structure. `StorageDecision` must resolve under
a reference-checking project contract; the fragment alone makes no such claim.

## Source ownership and review

Start with the selected Markdown as the authority. Prepare a scoped SCIR proposal
with citations to a preserved snapshot. Review conditions, numbers, units, negation,
status, and identity before transferring ownership of particular commitments.

After that transfer, source notes are historical evidence, the designated SCIR
records own the working detail, and human prose explains the relevant part.
Authored prose can contribute new decisions too; reconcile those intentionally.
Do not resolve disagreements by whichever file has the latest timestamp.

An authored overview can be edited for tone or structure without changing SCIR.
A content change may call for a targeted prose review; it does not imply that prose
must be regenerated. References and hashes can flag review needs, not certify
arbitrary summaries as faithful.

When a requested contraction would discard an exception or unresolved question,
retain it in the working content and make the omission explicit. Preserve original
files until the owner accepts the migration; a passing shape check is not enough.
