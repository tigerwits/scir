# Bounded workflow tools

These optional tools use the existing `working/1` index. They do not change native
format 1.0, decide which claims are true, or write source files. The old `select`
and `propose` responses and their bounds remain unchanged.

## Selection diagnostics

Use `scir.diagnostics.diagnose(index, identifiers, *, encoding="native",
limits=profile.Limits(), max_records=10000, max_output_bytes=16000000,
notation_limits=notation.Limits())` to return a caller-owned JSON-compatible report.
`identifiers` is an immutable ID tuple, as for `select`. Select `native` or
`notation` explicitly. No filename or content chooses an encoding.

```sh
python -m scir knowledge diagnose examples/working-profile/notes.scir --collection example --id T1 --encoding notation
```

The report identifies its `scir-selection-diagnostics/1` schema, collection,
source snapshot and seeds. It contains these measurements:

| Field | Meaning |
| --- | --- |
| `total` | Whole-collection record count, canonical UTF-8 bytes, nodes and depth |
| `selected` | The same counts for complete reference-closed records, plus edge counts |
| `legacy_packet_bytes` | Exact bytes of the original compact-JSON `select` response, including its final LF |
| `encoding_check` | Requested content spelling, its complete status, and its byte count or failure reason |
| `reasons` | The first discovered reference path, as in `select`, not every path |

Canonical bytes include one LF per root. JSON byte counts use Unicode directly,
compact separators and a final LF. They are not token counts. Both encodings use
the same complete records and check that their corresponding reader accepts the
complete spelling. A Python-built native document can exceed the source-reader
limit even when its profile size is valid. No tokenizer or graph-analysis dependency is installed.

Each distinct source-target pair counts once in `reference_edges`, even when it
occurs more than once or has several roles. `dependency_edges` counts the subset
explicitly declared in `dependsOn`. `other_reference_edges` is the difference.
A pair used for both citation and dependence belongs to the dependency subset;
these counts do not remove either declaration from the record. Counts refer to
outgoing edges of selected records, whose targets are in the selected closure.

The report does not contain delivered records. Its `content_delivered` is false.
`complete: true` means the diagnostic operation completed. An encoding check can
still have `complete: false`, `bytes: null` and an explicit limit reason. This is
not a zero-cost successful delivery. Unknown IDs, invalid arguments, or exhausted
analysis/report bounds fail without a partial report. CLI rejection exits 1;
incomplete processing exits 2. A completed capacity diagnostic exits 0 even if its
requested encoding cannot carry the content; inspect `encoding_check.complete`.

The content limit applies separately to the selected and whole collection during
measurement. The output limit applies to the diagnostic JSON. A caller must use
an approved larger limit explicitly if a valid index exceeds that analysis budget.

```python
from scir.knowledge import build_index
from scir.notation import lower
from scir.diagnostics import diagnose

index = build_index(lower('record(A, Note, p)\nrecord(B, Task, work, dependsOn: (&A,))'),
                    collection="example")
report = diagnose(index, ("B",), encoding="notation")
assert report["selected_ids"] == ["A", "B"]
assert report["selected"]["dependency_edges"] == 1
assert report["content_delivered"] is False
```

Diagnostics do not find a minimal explanation or prove semantic completeness.
A chain can require the whole collection. Use measured size and declared paths to
review the authoring structure; do not delete necessary links to improve a score.
The index stays immutable. Each call computes a fresh report without a cache.
