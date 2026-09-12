# Interpretation study

Non-normative fixtures and an evaluation protocol; [SPEC.md](../../SPEC.md) defines
structure. These studies do not extend the language.

## Corpus

[corpus.json](corpus.json) has 17 authored English fixtures and 19 candidate
documents: scope, coreference, false belief, corrections, conditions, modality,
quotation, event references, and correlated ambiguity.

```bash
python tools/study_corpus.py
```

The script checks structure, transport, alternatives, and selected comparisons.
It measures characters and depth—not tokens or translation quality. Candidates
and backtranslations are authored fixtures, not independent model outputs.
Paraphrase equivalence is stipulated, not discovered.

Known losses include tense, contrast, quantification, event identity, and calendar
anchors. For example, `chartOf(Report)` omits “one chart”; `answer(Carol)` omits
which call. The README's scope examples are explicitly schematic.

## Structural checks

```bash
python tools/check_properties.py --seed 602 --cases 1000
python tools/benchmark.py
```

Generated checks cover round trips, matching/substitution, edits, metadata erasure,
transport invariance, and constraint composition. They are finite checks, not proofs.
Benchmarks report source hashes, workload, timings, and allocations as JSON. Keep
results with the measured revision; they are not format guarantees.

## Agent evaluation

Compare original English, compressed English, SCIR, and a hybrid on held-out tasks.
Use independent translator/consumer runs, blind IDs, fixed tool budgets, and both
equal-information and equal-token comparisons. Measure scope leaks, invented
references, correction retention, answer accuracy, conformance, latency, and cost.
Audit translation fidelity separately from downstream success; report failures.

The [skill walkthrough](../agents.md#try-a-fresh-handoff) tests onboarding. Its file
and tool checks do not establish skill discovery or agent compliance. Those need
actual client runs with recorded outputs, as does any claim of better handoffs.

## Dialect-chain trials

The [runnable chain](../../examples/dialect-chain/README.md) freezes four source
statements and supplies authored representations, cumulative contracts, a small
reviewed oracle, structural projections, and a blocked target. It makes **no model
calls**. Its acceptance matrix and reconstruction checks do not show that agents
benefit from gradual constraints.

For an independent trial, freeze a held-out source, a final contract, intermediate
contracts, and the source-review rubric before translation. Compare:

| Arm | Model input |
|---|---|
| Progressive | Original source, prior draft, cumulative next contract, and diagnostics. |
| Direct | Original source and final contract. |
| Same-contract repair | Source and final contract at every revision, with diagnostics. |
| Previous-output only | Prior draft and next contract, withholding source after the first step; stress test only. |

Match total token/tool/repair budgets where possible; also report actual usage.
For an order probe, apply vocabulary then records versus records then vocabulary,
ending at the same intersection. Do not infer path independence from contract
commutativity. Stop on missing information; do not reward invented specificity.

Record prompts, model/settings, source and contract hashes, raw outputs, revisions,
violations, and tokens/latency/cost. Do not hide failed attempts. Audit source
coverage, unsupported additions, ambiguity retention, and fixed downstream
questions independently. Structural reconstruction and backtranslation are aids,
not independent semantic proofs. Several different trees may be faithful.

The fixed example's questions are: when must State stay unchanged; is payload
evaluation forbidden; what timeout is specified; which obligations share a condition?
In an agent trial, freeze expected answers and separate translator and evaluator.
Unknown wordings outside the fixture oracle require review, not an automatic zero.
The sample runner's `--stages` option inspects externally supplied stage files;
it does not run agents or score arbitrary English meaning.
