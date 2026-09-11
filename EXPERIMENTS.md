# Experiments and limitations

This is the historical 0.2 kernel-study record. The 0.2.1 implementation
review and fresh measurements are in [HARDENING.md](HARDENING.md); its evidence
is separate so these original measurements and source hashes remain auditable.

## What was actually executed

The original seven runtime modules and four test files were copied from the
GitHub connector and matched to their remote blob hashes. The baseline
suite passed: **34 tests**. The revision was executed on **CPython 3.13.5,
Linux x86_64**. The new suite, generated checks, corpus script and timing script
were run locally. Recorded JSON and commands are provided under `evidence/`.

No second model, Grok session, paid inference API, human participant or Lean
kernel was run. The English examples, SCIR candidates and backtranslations
are authored by one assistant. This is a design study with executable
structural fixtures, NOT an independent evaluation of translation accuracy,
agent task success, or general reasoning improvement.

## Baseline probes

| Probe | Observed 0.1 result | Revision decision |
|---|---|---|
| Two roots in one input | ParseError after first root | Add document parser; no artificial and wrapper. |
| Quoted wording | ParseError | Allow quoted symbol labels without adding literal node kinds. |
| 400 nested applications | RecursionError | Explicit parser depth guard and a diagnostic. |
| Normalize `think(Bob, not(not(P)))` | `think(Bob, P)` | No Core rewrite; optional Boolean profile stops at think. |
| Query asserted A under `and(A,B)` | One match | Roots-only structural scope; inference is not source position. |
| Two identical call occurrences | Two empty binding maps, no positions | Return Hit paths as well as bindings and matched term. |
| Invalid constructed Atom(123) | TypeError from validation | Validate constructor fields before creating Term. |
| Same dataclass hash with two process seeds | Different integers | Explicit versioned SHA-256 fingerprint. |

These observations do not make every old policy a bug. Most are specified
0.1 behaviors that no longer suit the reduced structural kernel.

## The difficult-English corpus

`examples/corpus.json` contains **17 fixtures and 19 candidate documents**.
It includes coreference, nested beliefs, two negation scopes, pronoun
ambiguity, a conditional, false belief, correction, modality, an implementation
requirement, exact quotation, an event reference, an active/passive pair,
a sent/received contrast, and correlated ambiguity.

`tools/study_corpus.py` checks content parse/print, relational round-trip,
explicit alternative selection, and fixed structural query results. It
measures characters and tree depth; it does NOT count model tokens or perform
a neural translation. The active/passive equality is a manually assigned
oracle, not discovered cross-model agreement.

### Negation scope survives exactly

```text
not(think(Bob, wrong(Alice)))
think(Bob, not(wrong(Alice)))
```

The trees differ. A roots-only query for `think(Bob, ?content)` matches only
the second. An all-occurrences query matches both, with different paths.
This is a deterministic success once the interpretation has been supplied.
It says nothing about how often a model chooses the right interpretation.

### Reference resolution records, rather than proves, an interpretation

```text
past(give(Alice, Bob, Report))
past(show(Bob, Report, Carol))
```

This records the chosen readings of 'he' and 'it'. The reader no longer
has to resolve those pronouns from the original paragraph. However, a wrong
resolution is just as parseable. Explicit labels expose the decision; they
do not certify it or make symbol identity equal real referent identity.

### Ambiguity belongs in an envelope

'Alice spoke to Carol after she left' has two candidate documents in this
study. We retain both through `Alternatives`, not through logical `or` and
not as two roots asserted together. The correlated example uses 'her own
report': choosing the actor and owner independently would admit crossed
readings. Two whole-document alternatives preserve the correlation.

This approach is intentionally small but can duplicate content. Packing
shared alternatives is deferred until a corpus demonstrates sufficient need.
There is no claim that annotations alone encode arbitrary ambiguity.

### Roots are not all English assertions

The `false_belief` fixture is

```text
but(believe(Bob, down(Server)), running(Server))
```

A roots-only query returns neither down(Server) nor running(Server), because
both are nested. Yet English gives different commitments to those contents.
This illustrates why the API cannot call its root set 'all known facts'.
Semantic extraction still requires an explicit vocabulary profile or model.

The same issue appears with `past(give(...))`: the syntactic root is past,
not give. The reduced kernel chooses a predictable boundary over pretending
to recognize all factive, temporal or evidential contexts.

### Exact wording may be best left textual

```text
past(say(Alice, quote(text("Do not change main."))))
```

The quoted instruction stays data. Symbolic decomposition would not improve
the fidelity of its exact wording. The Boolean profile will not rewrite
inside say or quote. A string-looking symbol is still a symbol; text/quote
supply the informal convention explicitly.

### Sending and receiving must not collapse

The active/passive email pair is represented identically by the fixture
author. 'Alice sent Bob the report' and 'Bob received the report from Alice'
are deliberately different. A generic transfer(...) normalization could
lose the difference. No synonym or entailment normalization is performed.

## Compression is not guaranteed

The first SCIR candidate is shorter in **10 of the 17 fixtures**, by Unicode
character count. Seven are longer. Candidate alternatives, annotations and
glossaries are excluded from that first-candidate comparison; including them
can increase the representation cost further. Most examples have maximum
edge depth 2–4.

These numbers are not token counts and not a task-quality metric. Characters
may tokenize differently. The useful observation is narrower: a symbolic
surface can preserve helpful structure while still costing more space than
English. Readability, inference budget and fidelity must be measured, not
inferred from parentheses.

## Known losses in the original six examples

The original README examples remain as compatibility fixtures. They are not
called semantically canonical. Specific issues include omitted past/future
tense, loss of the contrast in 'but', unresolved reference to 'that call',
`chartOf(Report)` not explicitly expressing 'one chart', and inconsistent
levels of description (`latest(Report)` versus Report). 'Six' was not safely
convertible to 18:00 without context, and yesterday/tomorrow have no supplied
calendar anchor.

The revised corpus adds ordinary wrappers or explicit discourse IDs where
useful, and retains ambiguity rather than claiming the core repaired these
losses. There is no universal best decomposition for every sentence.

## Generated structural checks

`tools/check_properties.py`, seed 602, generated **1,000 documents containing
8,829 occurrences**. All checks passed:

- content and pattern parse/print;
- wildcard-free match followed by instantiation reconstructs the subject;
- relational encode/decode and invariance under row permutation;
- replacement by the existing occurrence is identity;
- annotation erasure returns the underlying content.

Unit tests additionally exercise repeated captures, wildcard failure on
instantiation, malformed syntax fuzzing (2,000 strings), process-stable
fingerprints, stale metadata, arbitrary relational ID renaming, duplicate
rows, missing endpoints, order gaps, cycles, sharing, orphan nodes, template
cycles and resource budgets. The optional Boolean profile is checked on
200 generated formulas under all eight assignments to three atomic labels,
including idempotence and separate opaque-boundary tests.

Finite generated tests do not prove universal correctness. See THEORY.md for
inductive arguments and the explicit boundary of the unperformed Lean work.

## Local microbenchmarks

`tools/benchmark.py` measures the median of three runs after one warmup, with
collection before each timed operation. Each root has seven node occurrences.
The all-occurrences query is `use(Alice, ?x)`. Results from this shared runtime:

| Roots | Nodes | Parse ms | Format ms | Query-all ms | Encode ms | Decode ms |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 700 | 1.570 | 0.390 | 0.784 | 0.744 | 1.712 |
| 1,000 | 7,000 | 15.322 | 2.530 | 6.654 | 7.285 | 16.660 |
| 5,000 | 35,000 | 82.318 | 13.805 | 33.845 | 48.233 | 94.996 |

This fixed-depth workload shows no obvious scale discontinuity at these
sizes. It is not a proof of asymptotic complexity, a hardware-independent
performance promise, or evidence of improvement over a previous indexed
implementation. No index is implemented. THEORY's path/string-copying bounds
explain why a deep-chain workload differs from this shallow repeated one.

Additional shape probes are reproducible with `python tools/benchmark.py
--shapes`. A depth-128 chain (129 nodes) parsed in 0.347 ms; a single root
with 10,000 leaf children parsed in 15.644 ms. The raw medians are in
`evidence/shapes.json`. Inputs beyond the configured depth are rejected
rather than used to extrapolate these measurements.

## Controlled model experiment still needed

A credible next experiment should freeze a held-out source set and compare
original English, compressed English, SCIR and a hybrid representation. Use
independent translator and consumer runs, blinded source IDs, a fixed tool
budget, and both equal-token and equal-information comparisons. Score scope
leaks, unresolved-reference invention, contradiction/correction retention,
query answer accuracy, task completion, total tokens, latency and cost.

Do not use identical manually chosen SCIR strings as evidence that two models
converge. Preserve the original source and all alternative parses. Have an
independent oracle audit whether each translation kept the relevant meaning.
Bootstrap confidence intervals over tasks rather than repeatedly probing one
sentence. Publish failures as well as successful examples. No such model
comparison was executed in this revision.
