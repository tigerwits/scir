# Guarded repository handoffs

This is a repository-tool protocol, not a change to SCIR's content format or
public package proposal schema. `spec/check.py knowledge propose` now requires
`--basis` from a fresh repository selection. The lower-level `propose_checked`
helper remains available for pure content/local-contract tests; it does not guard
linked file bytes and must not be mistaken for a complete persistence handoff.

## Read and propose

```sh
python spec/check.py knowledge select --id NamedRoles > selection.json
```

Read the selected records and their designated authoritative sources. Take the
`source_snapshot` for the ordinary `scir-change/1` request and
`input_basis.digest` for `--basis`. Do not merely replace a stale fingerprint
without reviewing changed inputs. With BASIS set to that inspected value:

```sh
python spec/check.py knowledge propose --basis "$BASIS" --change change.json
```

The command returns JSON only; it does not modify either source shard. Unknown
IDs, invalid syntax/schema/locations and unsupported placements are rejected.
Stale input/write preconditions are conflicts. Resource exhaustion and unavailable
I/O are incomplete. Errors emit no success packet. Rejection/conflict exits 1;
incomplete checks exit 2. The generic runtime CLI retains its own schema.

## Input basis

`scir-repository-basis/1` contains collection identity, the content snapshot,
record-to-source membership, and exact SHA-256 file hashes. Its digest covers a
sorted, compact UTF-8 JSON encoding with LF and the version identity included.

The file set covers both authoritative shards, all source/test/model links in
the collection, the three derived destinations, repository checker Python files,
and present contributor/ownership instructions. Limits are 2,048 files, 2 MB per
file and 32 MB total. Traversal and symlinks fail. Byte identity is intentional:
authoritative wording can change while its heading and SCIR index remain equal.

Selection checks the observed basis again before delivery. Proposals compare it
before validation and recapture it afterwards. `commit_basis` additionally covers
new source/test/model files introduced by the candidate. Missing new links fail
instead of becoming guessed references.

This is not an atomic filesystem snapshot, a signature, semantic equivalence,
proof of evidence quality, or protection against A-to-B-to-A histories. Unlinked
files, external services, Git history and the installed interpreter/package are
not all captured by this file set. A host must guard those inputs when relevant.

## Shard ownership and write plan

Existing IDs retain the authoritative shard from the input basis. New IDs need
an explicit JSON mapping through `--placements FILE`, containing exactly the new
IDs and one of `spec/native.scir` or `spec/knowledge.scir` for each. Existing IDs
cannot be moved through this option. Deletions retain the source file, possibly
empty. The final combined order is native shard followed by knowledge shard;
new records append within their assigned shard.

`scir-repository-proposal/1` returns the complete candidate, original and candidate
content fingerprints, request, placements, input/commit bases and `write_plan`.
Each changed file entry includes its path, authoritative/derived role, expected
old SHA-256, candidate SHA-256 and exact candidate text. Unchanged files are not
rewritten. Derived query sections preserve outside prose.

Assigning a new record to the earlier shard may differ from the generic runtime's
append-at-end order. `runtime_candidate_snapshot` identifies that intermediate
value; `candidate_snapshot` identifies the final explicitly partitioned value.
Both are kept instead of mislabelling one as the other.

## Host commit responsibility

Review the request, candidate, source placements and derived diff. At commit,
atomically enforce the complete `commit_basis` and the write-plan preconditions
under the host's own transaction/locking policy, with any required Git revision
or runtime pin. Checking first and writing later is not an atomic transaction.
Revalidate content and derived freshness after persistence. These tools deliberately
do not apply a sequence of in-place writes or resolve source-edit conflicts.
The temporary test replay is a fixture, not a production transaction recipe.

## Optional delivery views

`knowledge select` and `knowledge propose` also accept `--view compact` with an
explicit optional `--encoding native|notation`. The packet retains the input-basis
digest; proposals retain the commit-basis digest too. The complete file bases and
source-owned write plan remain in a retrievable, hash-bound artifact. Use
`--view artifact --expected-artifact HASH` with the same request to generate and
check that artifact. Changed inputs produce a conflict, not a fresh silent result.
The original full response remains the default. A proposal delta is not complete
context and must not be saved over an authoritative shard. Review the complete
plan before applying it. Presentation runs before the final input-basis check.
See [delivery rules and costs](../docs/workflow-tools.md) for exact boundaries.
