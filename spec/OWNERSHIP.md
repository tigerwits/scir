# Repository knowledge ownership

The repository uses `working/1` with a local `scir-repository/1` contract. It adds
no runtime vocabulary. `native.scir` and `knowledge.scir`, in that order, form one
canonical collection with globally unique IDs. They are not language imports.

## One owner for each statement

| Material | Maintained owner | Other representations |
| --- | --- | --- |
| Native query/occurrence wording | Six record-owned entries in `native.scir` | Two marked Markdown views |
| Other native rules | Linked specification sections | Working records index obligations and tests |
| New rules, decisions and limitations | Linked contract/result sections | Records index rationale and checks |
| Test expectations | Independent test methods | Coverage links are declarations, not execution |
| Proof models | Lean source and stated scope | A declaration link does not establish elaboration |
| Measurements | Identified runs and artifacts | Reported success is not approval or truth |

`views.py` renders directly from the working records. The old catalog is available
only through the explicit `--legacy` export. It is not an intermediate validation
format or another authoring source. Its initial migration inputs are frozen test
fixtures; their byte witness does not freeze current requirements.

## Record contract

Each record has an ID, kind, area, source section and ownership. Kinds are
Requirement, Decision, Limitation and Question. Requirements need a nonempty
`tests` tuple. Decisions and questions need an authored status. Optional `models`
links Lean declarations. Unknown local fields/kinds fail. All explicit references
resolve within the combined collection, including across shards.

`ownership: index` identifies a summary of a document-owned definition.
`ownership: record` is limited to query requirements. Their exact `wording` and
optional `apiNote` are text. `topic: Queries` and contiguous unique `viewOrder`
labels define the two views. `queryExamples` contains uniquely named
`example(name, input(...), pattern, scope, paths(...))` values. The checker runs
only the public query operation with independent expected paths, never source code
from a record. `projection: native` also marks the optional legacy-export subset.

Location checks inspect bounded static source without importing test modules.
They reject traversal and symlinks. The same file/kind is scanned once within a
validation call. Declarations do not establish source fidelity, test execution,
coverage adequacy, or successful proof elaboration.

## Maintenance boundary

`python spec/check.py` validates both shards, references, locations, stored query
examples and both direct views. It does not run linked tests or Lean proofs.
`--markdown` reports all current requirements. `--write-views` preflights both
Markdown destinations and rewrites only their marked regions. It does not write
records and is not an atomic multi-file transaction.

Selection preserves whole records and their declared context. `affected` follows
reverse `dependsOn`. Proposals require the inspected content snapshot and separate
`--basis` file digest. Read [HANDOFF.md](HANDOFF.md). The file basis covers source
shards, declared authoritative files, tests, model sources, derived targets and
repository checker inputs. Candidate plans retain source ownership, validate
native readability and size, and require placements for new IDs. Neither default
nor compact output changes this obligation.

The host must atomically enforce the commit basis and complete write plan. Do not
save a combined candidate into one shard while leaving duplicate records elsewhere.
Hashes do not cover unlinked information, Git history or A-to-B-to-A changes.
A conflict requires review of changed inputs, not merely a refreshed digest.
No proposal assigns approval or performs a live service operation.

Authored notation and canonical source are distinct ownership choices. Do not
infer whether a content edit should change an alias definition or one occurrence.
The private grill is independent and version-pinned, not a required dependency
of this public repository. Its original measurements retain their subject pins.

## Shared checks and historical evidence

`locations.py` resolves paths/headings/test/model declarations for both the current
contract and explicit legacy validator. LF, CRLF and CR are inspected without
rewriting stored bytes. Its 2 MB per-file limit also applies to legacy links;
exhaustion is incomplete, not a report that a location is absent.

The [historical baseline checker](../tools/check_native_baseline.py) checks five
native files at `3ceeb1e`, not current HEAD. Historical byte identity and current
behavioral compatibility are different obligations. Keep current format, digest,
transport, scope and negative tests. Reformatting source is not itself a format
break. Remove duplicate implementations only after replacement checks exist.

Links, deterministic scenarios, model proofs and independent agent trials remain
different evidence categories. Passing all layers does not establish truth.
