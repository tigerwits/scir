# Dialect refinement chain

Keep one source fixed. Add constraints, revise the representation, and inspect
what changed. This is a worked example using **authored stage files**, not a model
benchmark.

From an installed checkout:

```bash
python examples/dialect-chain/run.py
python examples/dialect-chain/run.py --json
```

The first command shows acceptance and preservation checks. JSON adds occurrence
paths, positional diffs, document sizes, fingerprints, and source-review results.
Neither command rewrites the input files.

## Fixed source

[source.md](source.md) contains four statements:

> **S1.** If parsing fails, Parser must return Error.
>
> **S2.** If parsing fails, Parser must leave State unchanged.
>
> **S3.** Parser must never evaluate Payload.
>
> **S4.** The specification does not define a timeout policy.

The source SHA-256 is fixed in [contracts.py](contracts.py), along with an authored
four-term oracle. Changing the source requires a new review, not a silent update
to make a candidate pass. The hash detects changes; it does not certify meaning.

## Four representations

### 0. Generic draft

[00-generic.scir](stages/00-generic.scir) uses informal vocabulary:

```scir
must(Parser, when(parseFails, return(Error)))
must(Parser, when(parseFails, leaveUnchanged(State)))
mustNot(Parser, evaluate(Payload))
unspecified(timeoutPolicy(Parser))
```

### 1. Shared vocabulary

[01-vocabulary.scir](stages/01-vocabulary.scir) adopts agreed argument roles:

```scir
requires(Parser, on(failure(Parse), return(Error)))
requires(Parser, on(failure(Parse), unchanged(State)))
forbids(Parser, evaluate(Payload))
unspecified(timeoutPolicy(Parser))
```

`requires(component, on(condition, effect))` records a conditional obligation.
`forbids(component, evaluate(payload))` records a prohibition. Neither asserts
that parsing failed or that the implementation meets the requirement.

The first dialect permits these statement shapes plus optional `record`,
`condition`, `ref`, and `timeout` forms. Later dialects **require** some of them;
they do not add forms forbidden earlier. Leaf identifiers remain open.

### 2. Named records

[02-records.scir](stages/02-records.scir) wraps statements in uniquely named records:

```scir
record(R1, requires(Parser, on(failure(Parse), return(Error))))
record(R2, requires(Parser, on(failure(Parse), unchanged(State))))
record(R3, forbids(Parser, evaluate(Payload)))
record(R4, unspecified(timeoutPolicy(Parser)))
```

A declaration ID must be a leaf. Record and condition IDs share one namespace.
At least one record is required; condition declarations may remain separate roots.

### 3. Checked references

[03-references.scir](stages/03-references.scir) names the shared failure condition:

```scir
condition(C1, failure(Parse))
record(R1, requires(Parser, on(ref(C1), return(Error))))
record(R2, requires(Parser, on(ref(C1), unchanged(State))))
record(R3, forbids(Parser, evaluate(Payload)))
record(R4, unspecified(timeoutPolicy(Parser)))
```

Conditional requirements must reference a uniquely declared condition. Forward
references work. A reference to a record, a missing ID, an ambiguous declaration,
or an unused condition fails. Definitions cannot contain references or cycles.

Here `condition` names a description; it is not evidence that the condition holds.
These conventions belong to this example, not to SCIR Core.

## Cumulative checks

Contracts are tuples of existing Python constraint functions. Each stage appends
to the previous tuple. On the shipped documents the runner produces:

| Document | Generic | Vocabulary | Records | References | Concrete timeout |
|---|---|---|---|---|---|
| Generic draft | pass | fail | fail | fail | fail |
| Shared vocabulary | pass | pass | fail | fail | fail |
| Named records | pass | pass | pass | fail | fail |
| Checked references | pass | pass | pass | pass | fail |

A prior draft is not malformed SCIR merely because it fails a stricter dialect.
The JSON report retains those failures instead of showing only the final success.

## Preservation is a separate check

Three explicit operations connect the authored stages:

```text
translate_draft(d0) = d1
unrecord(d2) = d1
inline_conditions(d3) = d2
```

The first uses four reviewed whole-statement mappings. It does not automatically
rewrite synonyms elsewhere. The other operations are structural projections:
remove record wrappers; or inline validated condition references and remove their
declarations. They operate only at the declared statement positions, not under
arbitrary heads. Their composed projection reconstructs the vocabulary stage.

`source_review` compares projected statements to the authored oracle **with
multiplicity**. It catches lost, added, and duplicated commitments. Source statement
order is ignored by that comparison; the exact projection checks still preserve
order. Neither check proves faithful English translation. Unknown draft wordings
or unsupported reference structures can be unreviewable rather than wrong.

Every report carries the source hash, checker-source hash, stage content digests,
applied rule names, and source-review status. Fixed structural questions extract
the state-change guard, payload prohibition, missing timeout, and failure effects
from each reviewed view. They inspect recorded obligations, not runtime behavior.
It reports characters, not tokens.
A changed representation needs fresh annotations; paths are snapshot-local.

## A refinement that must stop

The next contract requires exactly one concrete Parser timeout, such as a positive
integer duration label ending in `ms`, `s`, or `m`. It also rejects an unspecified
Parser timeout. The last faithful fixture fails it because **S4 supplies no value**.

[unsupported-timeout.scir](counterexamples/unsupported-timeout.scir) replaces R4 with:

```scir
record(R4, timeout(Parser, "30s"))
```

It passes the target dialect but fails source review: S4 disappeared and a new
timeout was introduced. This witnesses a nonempty target dialect, not a faithful
refinement. A new timeout needs an author decision and a new source version.
Validation must not invent it or weaken the contract to make the chain complete.
The stop is justified by this fixed source and reviewed conventions, not by a
general satisfiability solver.

## Try other translations

Keep the source and contracts fixed. Put four candidate files with the same names
as [stages](stages) in another folder, then run:

```bash
python examples/dialect-chain/run.py --stages /path/to/trial --json
```

Exit codes: **0** means all worked-example checks passed, including the expected
blocked target; **1** means review is needed; **2** means checking did not complete.
A passing run never means the concrete-timeout target was met faithfully.

New wording can fall outside the small authored oracle. Review such cases
independently; do not count them as semantic failures or train the translator to
copy the expected tree. See the [experiment protocol](../../docs/research/README.md#dialect-chain-trials)
for direct, progressive, repeated-repair, and order-of-constraints comparisons.
The [theory](../../docs/theory.md#dialect-refinement-chains) separates nested accepted
sets from translation paths. This folder is an example, not a new public API.
