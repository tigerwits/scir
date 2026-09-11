# Working on SCIR

Read SPEC.md before changing parser or API behavior. Core content has exactly
one recursive constructor: Term(symbol, ordered tuple of Terms). A Document
is an ordered tuple. Do not insert types, graph references, logical inference,
query captures or confidence into that content representation.

## Use the interface

```python
from scir import parse_document, parse_pattern, query
content = parse_document("think(Bob, wrong(Chart))")
pattern = parse_pattern("wrong(?thing)")
query(content, pattern)                # []: roots only
query(content, pattern, scope="all")   # occurrence, not a factual assertion
```

Use `?x` only in patterns. Do not represent unresolved content by query
variables. Store unresolved candidate documents in Alternatives; do not
flatten candidates into roots. Keep original text and provenance when the
interpretation is uncertain. Names and argument roles remain an agreed
vocabulary, not a kernel-certified meaning.

Occurrence paths are valid only for one snapshot. Bind annotations to the
fingerprint. Do not silently remap annotations after edits. Do not infer real
event identity from equal trees, different paths, or physical object sharing.

Logical normalization is opt-in and stops at ordinary heads. Template
expansion is an explicit API, not execution of Python or SCIR symbols.
Do not introduce broad rewrites under belief, quotation or source evidence.

Run before a change is considered ready:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python tools/check_properties.py
python tools/study_corpus.py
```

Benchmark changes affecting allocation/traversal with tools/benchmark.py.
Record exact commands, versions, seeds and failures. Do not label authored
English fixtures an independent model evaluation. No unexecuted Lean file
counts as a checked proof. Changes belong on a branch and in a reviewable PR;
do not merge without authorization.
