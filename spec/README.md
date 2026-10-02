# Repository knowledge and derived views

The repository maintains one `scir-repository` working collection in two explicit
canonical record shards. Read [ownership](OWNERSHIP.md) before changing content.

```text
native.scir + knowledge.scir
    -> validated working/1 collection
    -> whole-context selection, dependency review, guarded candidates
    -> requirements.scir (derived native compatibility catalog)
        -> SPEC.md: marked occurrence/query paragraphs
        -> docs/api.md: marked rules, notes and executable examples
```

`native.scir` preserves the original 30 requirement IDs, obligation terms,
source/test links, six exact query wording records and three query examples.
`knowledge.scir` covers the added profiles, decisions, limitations and open work.
Only the explicitly marked query material is generated into Markdown. The other
specification sections and human explanations remain authored; there is no
blanket Markdown migration or documentation template language.

## Check, select and review

From the installed project interpreter:

```sh
python spec/check.py
python spec/check.py --markdown
python spec/check.py knowledge select --id NamedRoles
python spec/check.py knowledge select --id RootScope
python spec/check.py knowledge affected --changed PreserveCallArity
```

Selection starts from known IDs and follows all explicit references, returning
whole records with their source snapshot and context. It does not discover
unwritten dependencies or infer facts. Review candidates follow only reverse
`dependsOn` relationships. A source link is not evidence of a successful run.

Read the [handoff contract](HANDOFF.md) before proposing a change. Requests retain
`scir-change/1` and the full combined content snapshot; the repository CLI also
requires `--basis` with the inspected selection's `input_basis.digest`:

```sh
python spec/check.py knowledge propose --basis "$BASIS" --change change.json
```

The additional guard covers exact linked source/test/model bytes, shard ownership
and repository-tool inputs. The repository wrapper checks local links and query
projection, returning a full candidate and explicit per-shard write plan without
writing source. New records require explicit source placements. The host still
owns authorization and an atomic commit of all preconditions and planned files.

## Refresh only the derived material

After an explicitly reviewed source-record edit:

```sh
python spec/check.py --write-views
python spec/check.py
python -m unittest discover -s tests -v
```

Default checking fails on stale outputs without writing. Refresh preflights all
three destinations, preserves Markdown outside the markers and leaves both
source shards untouched. These are not atomic multi-file filesystem writes.
Inspect the diff and run independent tests; rendering never makes a claim true.

The native dialect still supports direct inspection of the derived catalog:

```sh
python -m scir query spec/requirements.scir --pattern 'topic(?id, Queries)'
python -m scir query spec/requirements.scir --pattern 'wording(RootScope, ?text)'
python -m scir query spec/requirements.scir --pattern 'coveredBy(RootScope, ?test)'
```

The existing `validate_catalog`, query example and renderer functions remain
available through `check.py` compatibility exports. Their reusable implementation
lives in `catalog.py`, below both CLI and repository orchestration. They are not
another authored account of the project.

## What checks establish

Static checks resolve one exact Markdown heading outside triple-backtick fences,
a direct test method in a top-level `unittest.TestCase` subclass, or a simple Lean
theorem declaration. File paths are repository-relative, bounded and cannot use
traversal or symlinks. No linked test or proof is executed by location checking.
Query examples call only the public SCIR query API with authored expected paths.

A payload with a valid citation may still be wrong. Separate source review,
independent test execution, model checking and agent trials from bookkeeping.
Exit 0 means the requested checks completed; 1 means rejection or stale content;
2 means checking could not complete. New selection/proposal errors emit no partial
success. The catalog and maintenance tools ship in the source distribution,
not the runtime wheel.
