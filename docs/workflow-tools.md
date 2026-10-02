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

## Optional delivery views

Use `scir.delivery.selection(index, identifiers, ...)` for complete selected
records. Use `scir.delivery.proposal(index, request, ...)` for a labelled change
summary and its complete candidate artifact. Both return an immutable `Delivery`
with two UTF-8 JSON strings: `packet` and `artifact`. They write no file or cache.
The caller can retain the artifact in an approved store or generate it again.
There is no implicit network lookup or persistence layer.

Both APIs accept these keyword arguments:

| Argument | Default and purpose |
| --- | --- |
| `encoding` | `"native"`; or explicitly `"notation"` |
| `guards` | `()`; an immutable tuple of unique host name/value string pairs |
| `limits` | `profile.Limits()`; complete selected/candidate content bounds |
| `max_records` | `10000`; the record bound |
| `max_packet_bytes` | `16000000`; the complete packet bound |
| `max_artifact_bytes` | `16000000`; the complete artifact bound |
| `notation_limits` | `notation.Limits()`; used only for explicit notation delivery |

The proposal API also accepts `max_operations=1024` and
`max_request_bytes=1000000`, as in the original change API. Host guards have a
128-pair and 64,000 UTF-8 name/value byte bound. A guard is opaque host input:
SCIR does not check its authenticity or use it to authorize an operation.

`scir-delivery/1` packets retain collection, profile, encoding, source/candidate
fingerprints and host guards. In this schema, `native` means format 1.0 and
`notation` means notation/1 with operators disabled. Selected records retain every field and reference,
including scope, status and evidence. A full record is never replaced by a short
summary. Detailed inclusion reasons are in the `scir-delivery-artifact/1` artifact.
It contains the full original response and the same host guards. The packet gives
its exact SHA-256 and byte count. Hashes identify bytes; they are not signatures.

Proposal packets contain changed/new records and explicit deleted IDs. They state
`content_scope: "changed-records"` and `context_complete: false`. They are not
standalone working collections: an unchanged prerequisite can be outside the
delta. All changes are checked against the original snapshot and the full
candidate is validated before a response is returned. The full candidate and
request remain in the artifact. An empty delta is possible for a valid no-op.

The complete artifact must fit its own bound even when only the packet will be
sent. No successful packet promises an artifact that failed construction. Native
and notation output are checked through their actual readers. Failure does not
change the encoding or remove context. Existing `select()` and `propose()` retain
their original response schema, full response bound and default behavior.

```python
import json
from scir.delivery import selection
from scir.knowledge import build_index
from scir.notation import lower

index = build_index(lower('record(A, Note, t"Retain the scope.")'), collection="example")
result = selection(index, ("A",), encoding="notation")
packet = json.loads(result.packet)
assert lower(packet["content"]) == index.document
assert result.checked_artifact(packet["artifact"]["sha256"]) == result.artifact
```

`checked_artifact(expected_sha256)` requires a lowercase 64-digit SHA-256.
A mismatch is a conflict. Callers must verify this value when retrieving a stored
artifact or generating it again. Changing content, collection or host guards can
change the artifact identity. Do not bypass a mismatch by replacing the hash.

### CLI views

The runtime `knowledge select` and `knowledge propose` commands accept
`--view full|compact|artifact`. The default is `full` and remains unchanged.
`--encoding native|notation` requires an explicit compact or artifact view.
An artifact view requires `--expected-artifact HASH`; other views forbid it.
`--max-output-bytes` bounds stdout; `--max-artifact-bytes` separately bounds the
constructed artifact. Every failure leaves stdout empty and uses the existing
rejection, conflict or incomplete-processing diagnostic on stderr.

```sh
python -m scir knowledge select examples/working-profile/notes.scir --collection example --id T1 --view compact --encoding notation
# HASH is artifact.sha256 from the inspected packet. Use the same source and IDs.
python -m scir knowledge select examples/working-profile/notes.scir --collection example --id T1 --view artifact --expected-artifact "$HASH"
```

The repository `spec/check.py knowledge select/propose` commands expose the same
view choice. They retain their stronger input-basis guards. Compact packets carry
`guards.input_basis`; proposals also carry `guards.commit_basis`. The full basis,
record-to-source membership and source-owned write plan remain in the artifact.
The adapter checks the observed input basis again after presentation. Repository
commands retain their 16 MB response/artifact bounds; runtime budget flags do not
apply there. Read [the handoff contract](../spec/HANDOFF.md) before persistence.

## Complete cost accounting

`python tools/study_delivery.py --output .build/delivery-study` measures public
synthetic independent, modular and fully linked collections. It checks selected
content and full candidates, and retains each exact response with its hash.
The report includes the original response, compact packet, complete artifact and
packet-plus-artifact byte costs. It has no tokenizer or model calls.

A compact packet can be larger for a small selection. Requesting both packet and
artifact can cost more than the original full response. Measure actual fetches,
requests and host metadata before making an efficiency claim. These examples do
not establish agent performance or make an audit fetch free.
