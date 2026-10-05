# Repository knowledge and direct views

One `scir-repository` collection is maintained in two explicit canonical record
shards. Read [ownership](OWNERSHIP.md) before changing content.

```text
native.scir + knowledge.scir
    -> validated working/1 collection and repository contract
    -> complete requirement index, selection, review and guarded proposals
    -> two directly rendered query sections in SPEC.md and docs/api.md
```

`views.py` reads the owning records. It checks query order, wording, example IDs
and independent expected query paths. Location checks inspect each declared
file/kind once per validation. They do not import tests or elaborate Lean.
No legacy catalog is required to validate, select or render current knowledge.

## Check, select and review

```sh
python spec/check.py
python spec/check.py --markdown
python spec/check.py knowledge select --id NamedRoles
python spec/check.py knowledge affected --changed PreserveCallArity
```

The Markdown index includes every Requirement in both shards, not just the native
subset. Selection returns whole records and closes declared references. Review
follows reverse `dependsOn`, not every citation. These operations do not discover
unwritten dependencies or establish truth, execution, approval or coverage.

For proposals, follow the [handoff contract](HANDOFF.md). Supply the inspected
selection's `input_basis.digest` as `--basis`, and its content snapshot in the
`scir-change/1` request. The adapter checks linked input bytes, source ownership,
query examples and derived destinations before returning a per-file plan.
It writes no source. New record IDs require explicit placements. A host must
atomically enforce all commit preconditions and planned writes.

## Refresh only the derived material

After reviewing an authoritative record change:

```sh
python spec/check.py --write-views
python spec/check.py
```

This preflights both Markdown destinations, preserves bytes outside their markers,
and leaves both source shards untouched. It is not a multi-file transaction.
Rendering synchronizes text; it never makes a claim true. Other prose remains
authored, and only the six designated query records own exact normative wording.

## Explicit compatibility export

Consumers of the old native catalog can request a separate view:

```sh
python spec/check.py --legacy > /tmp/scir-legacy.scir
python -m scir query /tmp/scir-legacy.scir --pattern 'topic(?id, Queries)'
```

Choose a fresh output path and never redirect onto a source. The export contains
only the records explicitly marked `projection: native`. `projection.py` and the
old validator in `catalog.py` are transitional compatibility adapters. Supplying
an explicit catalog file to `check.py` retains the legacy inspection behavior;
this is not the normal repository workflow. Do not author or commit a second
catalog. The old `check.py` function re-exports remain for existing consumers.

The initial catalog and its record source are frozen under `tests/fixtures/`.
Their migration witness must not constrain future changes to the living records.
Independent exact query tests and marker/ownership checks remain mandatory.

## What checks establish

Static links identify a Markdown heading outside triple-backtick fences, a direct
method of a top-level `unittest.TestCase`, or a simple Lean theorem declaration.
These are bounded source conventions, not full Markdown or Lean elaboration.
Paths cannot traverse out of the repository or use symlinks. A declaration's
existence is not evidence of fidelity, execution or test adequacy.

Exit 0 means the requested checks completed, 1 means rejection or stale content,
and 2 means checking could not complete. Failed selection/proposals emit no
partial success. Repository tools ship in the sdist, not the runtime wheel.
