# Working knowledge, readable explanations

The overview is for a person arriving at the project. The SCIR holds the working
detail an agent needs to continue it: assumptions, reasons, evidence, rejected
proposals, and open questions. Neither has to be a mechanical copy of the other.

Each case contains three authored artifacts:

```text
source.md       frozen source notes, with sentence anchors
knowledge.scir  reviewed structural interpretation and dependencies
overview.md     a short explanation written for a human
```

The overviews are **not generated**. There is no renderer or byte-equality test
for them. They may reorganize or omit working detail without dropping that detail
from the maintained knowledge. Significant new commitments need reconciliation,
not an automatic overwrite in either direction.

## Three cases

| Case | Human explanation | What remains in SCIR |
| --- | --- | --- |
| [Event-store recovery](architecture/overview.md) | Recovery direction and outstanding decisions. | A determinism assumption, precise obligations, an unapproved proposal, and its dependencies. |
| [Checkout incident](investigation/overview.md) | The cause remains unresolved; restart needs approval. | Attributed observations and hypotheses, insufficient evidence, an earlier proposal, and its withdrawal. |
| [Order argument](mathematics/overview.md) | Why the maximum is c, without claiming strict inequality. | Domain, premises, conclusions, their limitation, and review dependencies. |

These are authored fixtures, not recorded agent trials. Local role and payload
meanings are stated in the source notes; none becomes SCIR Core vocabulary.

## Query the detail you need

From an installed checkout:

```bash
python examples/knowledge/run.py
python -m scir query examples/knowledge/architecture/knowledge.scir --pattern 'record(?id, Assumption, ?content)'
python -m scir query examples/knowledge/investigation/knowledge.scir --pattern 'record(?id, Hypothesis, ?content)'
python examples/knowledge/run.py --case mathematics --changed A2
```

The last command returns review candidates `A2`, `C1`, `C2`, and `L1`: both
conclusions and the limitation depend on that premise. Strengthening `b <= c`
to `b < c` would establish `a < c`, so the old limitation also needs review.
The helper changes no files and makes no truth judgment. An incomplete
dependency graph can miss relevant work; reachability only follows declared links.

The explicit rule is: a changed record needs review; if X depends on a record
needing review, X needs review too. The helper computes the least fixed point of
that rule, even with cycles, and returns IDs in document order. This is a small
example of deterministic reasoning **under a declared rule**, not built-in
logical inference by `query` or a proof checker for the mathematical argument.

## The local migration contract

Four root forms are sufficient here:

```scir
snapshot("source-byte SHA-256")
record(P1, Proposal, unapproved(recover(checkpointThenSuffix)))
source(P1, S4)
dependsOn(P1, A1)
```

That fragment illustrates forms, not a complete conforming document. The supplied
checker requires one exact SHA-256 for `source.md`, unique leaf record IDs, known
role leaves, valid source anchors and dependency references, and no duplicate
links. Forward references are accepted. Payloads stay open.

`source.md` uses explicit `S1: ...` lines; this is an example convention, not a
Markdown parser. Every marked sentence needs a link, and every record needs at
least one source link. One sentence may support several records. These are
**bookkeeping checks**: they cannot establish that a cited sentence supports a
particular translation. A wrong conclusion with a valid citation can still pass.
Read the source and proposed interpretation together.

Dependencies are authored review relationships. Equal labels elsewhere are not
automatically references, and cycles are allowed. Their closure is temporary
query output, not another maintained copy of the knowledge.

After changing the source, the old byte hash fails. Review the affected records
before updating that hash. Rehashing alone establishes neither fidelity nor a
completed migration. After handoff, the original source remains historical;
it must not silently override subsequently approved knowledge changes.

The runner checks canonical SCIR and the local contract. Exit **0** means those
checks completed, **1** means rejection, and **2** means checking could not
complete. Authored overviews and domain truth are outside its acceptance claim.
It never installs packages, imports source-provided rules, executes payloads,
rewrites prose, or changes source notes.

## Try a maintenance change

In a scratch copy, remove `A2` from the mathematical records: the `dependsOn`
reference fails. Keep the record but revise its premise: references may still
pass, while the conclusions need mathematical review. Editing the overview alone
does not alter the premises or generate a false fidelity certificate.

For real projects, use the [migration skill](../../skills/scir-migrate/SKILL.md).
Keep your own vocabulary and acceptance policy; this four-form dialect is an
example, not a mandatory knowledge schema.
