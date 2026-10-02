# Repository knowledge ownership

Repository tooling uses `working/1` under a local `scir-repository/1` contract.
It adds no runtime vocabulary. The collection is loaded explicitly, in order,
from `native.scir` and `knowledge.scir`. These are canonical authoritative record
shards with globally unique IDs, not language imports or separate namespaces.

## One owner for each statement

| Material | Maintained owner | Other representations |
| --- | --- | --- |
| Native query/occurrence wording | Six record-owned entries in `native.scir` | Derived legacy catalog and two marked Markdown views |
| Other native rules | Linked SPEC/API/dialect sections | Native working records index obligations and independent tests |
| New 1.1 rules | Profile contract and API sections | `knowledge.scir` indexes rules, rationale and checks |
| Adoption decisions and limitations | Linked specification/result section | Attributed summaries, not independently editable normative definitions |
| Test expectations | Independent test methods | Links express intended coverage, not execution or adequacy |
| Proof models | Lean source and declared scope | Declaration links do not establish elaboration or Python correctness |
| Measurements | Identified runs and artifacts | Reported success is not automatic approval or truth |

`requirements.scir` is now a DERIVED compatibility catalog, not an authoring
source. Its initial migration preserves all 127 roots and every byte. Existing
query paragraphs and examples remain unchanged. The fixed legacy renderers still
consume that dialect. Do not edit the compatibility catalog or marked Markdown
sections independently; edit their record owner and explicitly refresh views.
Other Markdown remains authored and authoritative where a record says `index`.

## Record contract

Every record has an ID, kind, area, source section and ownership. Kinds are
Requirement, Decision, Limitation and Question. Requirements carry a nonempty
`tests` tuple. Decisions/questions carry an authored status. Optional `models`
contains Lean declaration links. Unknown local fields and kinds fail. All
explicit references resolve within the combined collection, including across
shards. Repeated labels are not references.

`ownership: index` means the payload is an index/summary of the linked section.
`ownership: record` is restricted to projected query records. Their `wording`
and optional `apiNote` are exact text. `topic: Queries` and contiguous unique
`viewOrder` labels define presentation order. `queryExamples` contains
`example(name, input(...), pattern, scope, paths(...))` values. The legacy checker
executes these query examples against the public query API, never code from text.
`projection: native` marks the subset exported to the compatibility catalog.

Source/test/model paths are resolved statically with byte limits and no traversal
or symlinks. Heading and theorem recognition follow this repository's documented
simple source conventions; they are not full Markdown or Lean elaborators.
Test source is parsed as AST, never imported by link checking. A declaration's
existence cannot establish source fidelity, test execution or test adequacy.

## Maintenance boundary

The default `python spec/check.py` validates both record shards, their combined
references, source/test/model locations, legacy projection, stored query examples
and all derived views. It does not execute linked tests or check Lean proofs.
`--write-views` preflights every destination and refreshes only the legacy catalog
and two marked query views. It does not write either authoritative shard. Writes
are explicit but not a multi-file filesystem transaction.

`python spec/check.py knowledge select --id NamedRoles` returns whole records,
including declared rationale, dependency and proof-scope links. `affected` follows
reverse `dependsOn`, not every citation. Repository `propose --change REQUEST`
adds the stronger local contract and derived-view preflight to the pure runtime
candidate checker; generic `scir knowledge propose` checks only `working/1`.
Neither proposal command writes source or assigns approval.

The combined content snapshot covers both SCIR shards, not the bytes of linked
Markdown, tests, proof files, or Git history. A host persists with an atomic
revision precondition and checks its broader checkout basis where relevant.
Candidate output is the entire combined collection; a host preserves shard
membership or explicitly reviews its repartition. It must not save the whole
combined candidate into one shard while leaving duplicates in another.

Compact notation is a delivery/authoring option, not a second maintained copy.
No source rewrite guesses whether to edit an alias definition or one occurrence.
The external grill remains independent and version-pinned; its historical
experiments and evidence must not be retargeted to make current checks pass.

## Shared checks and historical evidence

`locations.py` is the single static path/heading/test/model resolver for both
catalog representations. It inspects LF, CRLF and CR source without rewriting
bytes. Its 2 MB per-file inspection bound also applies to legacy catalog links;
exhaustion is an incomplete check, never proof that a location is absent. The
legacy entrypoint and ordered diagnostics remain available as compatibility
adapters; their independent conformance expectations are not generated from the
working records.

The former current-source hash assertion now lives in the explicit historical
[baseline checker](../tools/check_native_baseline.py) and its separate CI job.
It checks the five recorded native files at commit `3ceeb1e`, not current HEAD.
Historical exact-byte identity and present-day behavioral compatibility are
different obligations. Current format, digest, transport, query, scope and
negative-control tests remain mandatory; source reformatting is not itself a
format break. This cleanup changes no runtime code or conformance vector.
Historical reports still describe the actual revisions they measured.

Keep independently constructed expected results even when they resemble runtime
code. Remove duplicated implementations only after replacement checks exist.
The private grill is an additional challenge, not a required private dependency
of this repository's test suite. Finite scenarios, model proofs and actual agent
trials remain distinct evidence categories.
