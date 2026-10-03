# Optional profiles: Python and CLI API

Package 1.1 adds these interfaces; native format 1.0 and all previously documented
APIs remain unchanged. The [profile contract](structured-profiles.md) owns semantic
rules. A generic native document is not automatically a structured or working
profile. Use the project interpreter and select the intended interface explicitly.

## Structured values

`scir.profile` exports `VERSION = "structured/1"`, `TUPLE`, `TEXT`, `REF`, `KW`,
`RESERVED`, `ProfileError`, `LimitError`, immutable `Limits` and `Size`, and:

| Function | Result |
| --- | --- |
| `text(value: str)` / `read_text(term)` | Tagged exact text / decoded string, including empty text |
| `reference(identifier: str)` / `read_reference(term)` | Tagged local reference / literal ID |
| `tuple_value(items=(), *, fields=(), limits=Limits())` | Tagged tuple; no implicit flattening |
| `application(head, positional=(), *, fields=(), limits=Limits())` | Ordinary symbol-headed term with optional named roles |
| `read_tuple(term)` | Tuple's positional components only |
| `read_arguments(term)` | Ordinary application's positional components only |
| `read_fields(term)` | Immutable `(name, value)` pairs in canonical order |
| `validate(document, *, limits=Limits())` | `Size` or explicit error; never repairs content |
| `measure(document, *, limits=Limits())` | Exact native canonical bytes and occurrence counts |

Inputs `items`, `positional`, and `fields` are tuples; every field is a `(str, Term)`
pair. Duplicate keys fail, including equal duplicates. Readers validate their
inputs. Text and reference constructors validate payload scalar strings; profile
or workflow boundaries enforce aggregate resource bounds. Do not pass unbounded
Python-built objects directly to native recursive printing before validation.

`Limits(nodes=100000, depth=128, bytes=16000000)` requires strict integers, not
Booleans. Nodes/bytes are positive, depth is 0..128. `Size(nodes, depth, bytes)`
counts every occurrence and one LF per document root; empty documents measure zero.
Tags consume real native nodes, depth, and bytes. Physical sharing saves no budget.
These are bounded interfaces, not a sandbox against reflected/mutated Python values.

```python
from scir import Term, parse
from scir.profile import application, text, tuple_value, reference

send = application("send", (Term("doc"),),
                   fields=(("to", Term("bob")), ("from", Term("alice"))))
assert send == parse('send(doc, "scir.kw"(from(alice), to(bob)))')
assert tuple_value((Term("a"),)) != Term("a")
assert text("A1") != reference("A1")
```

## Notation

`scir.notation` exports `VERSION = "notation/1"` and:

```text
lower(source, *, operators=None, limits=Limits()) -> Document
pretty(document, *, operators=None, limits=Limits()) -> str
environment_digest(operators=None) -> str
```

`operators` is exactly `None` or `"arithmetic/1"`. The environment digest identifies
the resolved fixed table plus notation/profile versions; it is separate from the
native content digest. No document can load code, an operator pack, or a URL.

Notation `Limits(source_bytes=64000, tokens=16000, nodes=8000, depth=64,
expanded_bytes=256000, declarations=128)` uses positive integers, with depth at
most 64. `.content()` returns the corresponding structured-content limits.
Limits cover unused declarations, aggregate expansion and each shared occurrence.
The native parser's independent bounds still apply to the final reparse.

`lower` checks native format/parse roundtrip. `pretty` emits explicit, checked
prefix spelling, not necessarily infix notation. It never invents abbreviations,
recovers comments, or edits authored source; failure emits no truncated spelling.
Aliases are erased and each separately processed document starts with fresh bindings.

```python
from scir.notation import lower
from scir import parse_document

assert lower("send(doc, to: bob, from: alice)") == parse_document(
    'send(doc, "scir.kw"(from(alice), to(bob)))')
assert lower("a + b", operators="arithmetic/1") == lower("plus(a,b)")
assert lower("f(a,b)") != lower("f((a,b))")
```

## Working records

```text
build_index(document, *, collection, limits=profile.Limits(), max_records=10000)
    -> Index
select(index, identifiers, *, max_records=10000, limits=profile.Limits())
    -> Selection
affected(index, changed, *, max_records=10000, max_bytes=16000000)
    -> tuple[str, ...]
```

`identifiers`/`changed` are immutable ID tuples. Duplicates are collapsed in first
request order, but count toward input bounds. Empty tuples are valid in Python.
The CLI requires at least one explicit seed. Collection identity is a nonempty
host-supplied Unicode-scalar string, not inferred from a filename.

Index construction validates the entire collection. Use `build_index`; `Index`
and `Record` are returned snapshots, not unchecked alternative construction APIs.
Do not mutate native Terms by reflection or manufacture inconsistent Index maps.

Result fields:

- `Record(id, kind, payload, fields, term)` preserves the original term.
- `Index(collection, document, snapshot, records, references, dependents)` has
  detached read-only mappings; reference/dependent lists are immutable tuples.
- `Selection(collection, source_snapshot, requested_ids, selected_ids, document,
  reasons, profile="working/1", complete=True)` contains whole original records.
  A reason is `(id, "requested"|"reference", via_id_or_none)`. The first discovered
  path is reported, not every possible path. `.as_dict()` returns a caller-owned
  JSON-compatible mapping with canonical native record strings.

Selection uses every explicit local reference. Reverse review impact uses only
`dependsOn`. Reference and dependency cycles terminate. No text matching, semantic
search, truth inference, supersession deletion or authorization is performed.
Required context is complete only with respect to authored references.

Selection's `limits.bytes` includes its complete compact-JSON packet plus final LF,
not just its content. `affected` bounds its returned compact JSON array plus LF;
a host adding metadata must additionally bound its full response. Limit failures
raise `LimitError`, never return a partially complete result.

Indexes and packets are snapshot-local. Their content fingerprints ignore comments
and formatting and do not detect an A-to-B-to-A history. They are not signatures or
proof that the collection name belongs to a particular remote service.

## Change proposals

`scir.changes.VERSION = "scir-change/1"` identifies the exact JSON request schema.

```text
read_request(source, *, max_bytes=1000000, max_operations=1024,
             limits=profile.Limits()) -> Request
propose(index, source, *, limits=profile.Limits(), max_records=10000,
        max_operations=1024, max_request_bytes=1000000,
        max_result_bytes=16000000) -> Proposal
```

`source` is JSON text, not a path or executable expression. `Request`/`Operation`
are immutable results; `.as_dict()` returns caller-owned transport data. Passing
term strings in notation syntax, or noncanonical native strings, is an error.
Unknown envelope/operation fields, duplicate JSON keys and non-JSON numeric constants
fail. Term count/size limits also apply across all inserted terms in the request.

An empty operation list is a guarded no-op. No two operations may write the same
payload/field. Creation/deletion conflicts with every other operation on that ID.
Distinct fields of one record can change together. `setField` cannot change the
fixed ID, kind or payload slots. Deleting a referenced record is allowed only when
the batch also repairs/removes references, leaving a valid final collection.

`Proposal(collection, before_snapshot, candidate_snapshot, document, request)` is
returned only after whole-candidate `working/1` validation. `.as_dict()` includes
version `scir-proposal/1`, profile identity, canonical candidate records and a
complete validation marker. That marker certifies only this profile check, not a
stronger project policy. Run additional consumer constraints before persistence.

The full source snapshot and collection must match. The original Index/document
remain unchanged on both success and failure. No file is written. To persist a
candidate, the host must atomically enforce the precondition at commit. Checking
first and writing later is not a transaction. Selective read sets, persistent
history, source edits through aliases and automatic conflict resolution are absent.

## CLI

```sh
python -m scir lower notes.scix --operators arithmetic/1
python -m scir knowledge check notes.scir --collection project
python -m scir knowledge select notes.scir --collection project --id T1
python -m scir knowledge affected notes.scir --collection project --changed A1
python -m scir knowledge propose notes.scir --collection project --change change.json
```

Only `lower` consumes notation. Knowledge commands consume native SCIR, even when
a path ends in `.scix`. An absent path or `-` means stdin; document and change
request cannot both consume stdin. `--max-records` (default 10000) applies to the
source collection and result; `--max-output-bytes` (default 16000000) bounds the
complete knowledge response. Values must be positive integers. Native parsing
retains its independent source/node/depth limits. Change JSON is bounded to 1 MB.

New commands return 0 for success, 1 for completed rejection/conflict, and 2 for
incomplete checks (resource exhaustion, unavailable files, recursion failure).
Failures write JSON diagnostics only to stderr and no partial success to stdout.
Argparse usage failures also return 2. The adapter maps native 1.0 parser budget
failures to incomplete results, with regression tests for that boundary.
Existing native commands retain their original exit codes and outputs.

All command output uses UTF-8 and LF, independently of terminal encoding/platform.
Commands do not overwrite files, choose a lower-trust profile from input, or install
a package. Never redirect output onto the input file. Review candidate content and
preserve ownership of authored notation versus maintained canonical content.

## Diagnostics and optional delivery

The additive `scir.diagnostics` and `scir.delivery` modules provide bounded cost
reports and optional response views. See [the workflow API](workflow-tools.md)
for exact arguments, wire schemas, reader checks and byte limits. The original
`Selection`, `Proposal`, `select()` and `propose()` response contracts stay intact.
New results are output values, not unchecked constructors for accepted state.

The runtime and repository CLIs retain full responses by default. Explicit compact
views retain whole selected records; proposal views are labelled deltas. Full
audit/candidate data remains in a hash-bound artifact. Later retrieval costs count,
and a small packet does not authorize a source write.

The [consumer lifecycle example](../examples/consumer-lifecycle/README.md) shows
trusted policy, evidence requirements and explicit replacement resolution. Those
rules belong to that example, not the generic library. A status label, represented
receipt or successful generic parse cannot authenticate execution or approval.

## Named acceptance contracts

`scir.dialects` composes named trusted rules and returns content-, collection-,
contract- and context-bound results. See [the contract](dialect-contracts.md) and
[profile-aware helpers](dialect-rules.md). Existing profile exceptions, knowledge
commands and default response shapes are unchanged. Dialect code is selected by
the host, never loaded from a document or a command-line module string.
