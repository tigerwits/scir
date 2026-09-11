# SCIR — Symbolic Content IR

An experimental content interchange format: **symbolic structure, informal
vocabulary, deterministic tools**. The reference library makes no model calls.

```text
think(Bob, mistakenly(use(Alice, yesterday(SalesData))))
```

## Kernel

```text
Term     = (symbol, ordered tuple of Terms)
Document = ordered tuple of Terms
```

One content constructor. No type system, ontology, variables, logical axioms,
event identity, or evaluation in Core. `not`, `and`, `if`, and `think` are
ordinary symbols. A document presents its roots; nested occurrences are not
promoted to roots. This is a structural distinction, not a truth judgment.

```text
prose ── interpreted by an author/model ──> SCIR content
                                            │
                        parse / format / query / diff / edit
                                            │
                  snapshot annotations / occurrence tables
```

**Status:** implementation 0.2.1, retaining the 0.2 content/wire format.
See [HARDENING.md](HARDENING.md) for the implementation review, behavior
changes, regression tests and measured allocation improvements.
See [SPEC.md](SPEC.md), [THEORY.md](THEORY.md), and
[EXPERIMENTS.md](EXPERIMENTS.md). No claim that this improves LLM reasoning has
yet been established by an independent model experiment.

## Use

Python 3.10+ syntax; executed here on CPython 3.13.5. No third-party runtime
dependencies. Installation uses setuptools.

```bash
python -m pip install -e .
python -m scir check examples/six_sentences.scir
python -m scir fmt examples/six_sentences.scir
python -m scir query examples/six_sentences.scir \
  --pattern 'use(Alice, ?x)' --scope all
```

Without installation, prefix commands with `PYTHONPATH=src`.
The query returns the term, the path `[3, 1, 0]`, and `x = yesterday(SalesData)`.
The same query without `--scope all` returns no roots: the term is inside a
belief statement.

```python
from scir import parse_document, parse_pattern, query, replace_at, parse

doc = parse_document("""
# comments and multiple roots are allowed
think(Bob, wrong(Chart))
email(Alice, Bob, Report)
""")

hits = query(doc, parse_pattern("think(?who, ?content)"))
assert hits[0].path == (0,)
assert str(hits[0].bindings["who"]) == "Bob"

changed = replace_at(doc, (0, 1, 0), parse("Table"))
assert str(changed[0]) == "think(Bob, wrong(Table))"
```

`?x` is a **pattern capture**, never an unresolved entity in content. `?_` is
an anonymous pattern wildcard; bare `_` is an ordinary symbol.
`Alice()` is accepted as an input alias for `Alice`. There is only one value.

Quoted labels use JSON string syntax:

```text
text("Preserve this wording.")
"Алиса"
"unusual head"(A)
```

Quotation is lexical escaping, not a second String datatype: `"Alice"` and
`Alice` denote the same label. Numerical-looking labels such as `"0.7"` have
no built-in arithmetic meaning. Actual numerical metadata can use JSON.

## Separate layers

```python
from scir import digest
from scir.annotations import Bundle, annotate, erase
from scir.relations import encode, decode

note = annotate(doc, (0,), "source", {"sentence": 4})
bundle = Bundle(doc, (note,))
assert erase(bundle) == doc
assert decode(encode(doc)) == doc
```

Annotations target a content fingerprint plus an occurrence path. Applying
old annotations to changed content raises an error. Erasure removes metadata;
it does **not** preserve evidence, source attribution, or confidence.
Unresolved interpretations use the separate `Alternatives` envelope; they
are not silently joined into a document or erased as metadata.

API-only acyclic templates are available in `scir.templates`. They expand
symbolic terms by explicit substitution; there is no Python execution or
surface `def`/`=` syntax. `scir.profiles.boolean_normalize` is optional and
stops at ordinary heads, including `think`, `say`, and `quote`.

`diff` reports a deterministic positional changed frontier. It does not
claim minimum-edit alignment, semantic equivalence, or stable event IDs.
`digest` is a versioned SHA-256 content fingerprint; Python `hash()` is not a
persistent cross-process identifier.

## Original six-sentence experiment

These fixtures are retained from the bootstrap, **not certified lossless
translations**. They omit some tense, contrast, quantification and event
reference detail. The research corpus records these limitations explicitly.

| Source | Exploratory SCIR |
|---|---|
| Alice left the office at six. | `at(leave(Alice, Office), six)` |
| Before leaving, she emailed Bob the latest report. | `before(email(Alice, Bob, latest(Report)), leave(Alice, Office))` |
| Bob read it on the train and noticed that one chart was wrong. | `and(at(read(Bob, Report), Train), notice(Bob, wrong(chartOf(Report))))` |
| He thinks Alice used yesterday's sales data by mistake. | `think(Bob, mistakenly(use(Alice, yesterday(SalesData))))` |
| Bob called Carol, but she did not answer. | `and(call(Bob, Carol), not(answer(Carol)))` |
| If Carol confirms the numbers tomorrow, Bob will send a corrected report to the client. | `if(tomorrow(confirm(Carol, Numbers)), send(Bob, corrected(Report), Client))` |

## Reproduce checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python tools/check_properties.py
python tools/study_corpus.py
python tools/benchmark.py
python tools/benchmark_hardening.py
```

Recorded outputs are under `evidence/`. Seeded property checks and timing
measurements are reproducible procedures, not universal proofs or model
benchmarks. A Lean executable was unavailable in the implementation
environment; **no Lean-checking claim is made**.

## Boundaries

Input content is data, never permission to execute its symbol names.
The core cannot validate an English translation, infer what a symbol means,
or tell whether two mentions describe the same real-world event. Separate
applications may agree on vocabulary and inference profiles without changing
the content datatype. Keep the original text and provenance when those matter.
