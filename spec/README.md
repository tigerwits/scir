# Maintained content, Markdown views

This is one optional documentation workflow. Human-facing Markdown can also be
freely authored; [the knowledge examples](../examples/knowledge/README.md) show
that arrangement. Only the explicitly marked sections below are generated.

[requirements.scir](requirements.scir) holds project requirements and their
relationships. For **query and occurrence behavior**, it also owns the exact
normative wording, API notes, and executable examples. Two Markdown sections are
rendered from those records; they are not separately maintained accounts.

```text
requirements.scir
    → SPEC.md: occurrence and query rules
    → docs/api.md: the same rules, notes, and runnable examples
```

Other topics remain an index: their obligation terms are shorthand and their
linked Markdown definitions are still authoritative. The marked query paragraphs
in [SPEC.md](../SPEC.md) remain the published contract; edit their SCIR source.
This is a repository workflow, not an addition to SCIR's runtime or format.

## Use

From an installed checkout:

```bash
python spec/check.py
python -m scir query spec/requirements.scir --pattern 'topic(?id, Queries)'
python -m scir query spec/requirements.scir --pattern 'wording(RootScope, ?text)'
python -m scir query spec/requirements.scir --pattern 'coveredBy(RootScope, ?test)'
python spec/check.py --write-views
python spec/check.py --markdown
```

The default command validates the catalog, runs its query examples, and rejects
stale generated sections without writing. `--write-views` explicitly refreshes
only the marked sections after validation and destination preflight. Everything
outside those markers is preserved. `--markdown` prints a requirement index.
None of these commands runs the linked test suite.

## Records

The existing index forms are:

```scir
requirement(NoEmptyCall, Syntax, rejects("Alice()"))
specifiedBy(NoEmptyCall, section("SPEC.md", "Surface grammar"))
coveredBy(NoEmptyCall, test("tests/test_surface.py", "SurfaceTests.test_empty_application_is_invalid_in_both_languages"))
```

Each requirement has a unique leaf ID, an area leaf, and a ground obligation.
Areas are `Core`, `Syntax`, `Patterns`, `Tree`, `Annotations`, `Transport`,
`Constraints`, and `CLI`. Payload vocabulary stays open. Each requirement needs
at least one valid source link and test link. Forward links are allowed;
duplicate IDs, duplicate links, unknown targets, and an empty catalog fail.

The migrated topic adds four forms:

| Form | Meaning |
| --- | --- |
| `topic(id, Queries)` | Select this requirement for both query views, in topic-record order. |
| `wording(id, text)` | One exact normative text leaf for each selected requirement. |
| `note(id, text)` | An optional API note for a selected requirement. |
| `queryExample(name, id, input(...), pattern, scope, paths(...))` | A named executable query example attached to a selected requirement. |

An example's `input` children are its document roots. Its pattern is a text leaf,
not a content capture. Scope is `default`, `roots`, or `all`; `default` omits the
Python scope argument. Expected paths use `path("0", "1")` with nonnegative
integer labels. A leaf `paths` means no matches. Names are unique within examples;
requirements and examples have separate ID namespaces. Examples render in source
order. The checker parses patterns and invokes `query`; it never evaluates labels
or runs Python copied from text leaves.

The two renderers are fixed project functions, not a template language. The
specification view selects wording. The API view adds notes and Python examples.
The entire selection is recomputed, so a newly added topic member or example is
noticed as well as changes to existing records. Input order is intentional.

## References and checks

A section names one exact Markdown heading outside triple-backtick fences. A test
names a direct `test_*` method of a top-level `unittest.TestCase` subclass in a
`tests/test_*.py` file. Paths are repository-relative; traversal, absolute paths,
backslashes, and symlinks fail. This is the suite's convention, not general Python
test discovery. Test files are parsed as ASTs, never imported by the checker.

A source link from a migrated requirement points to its rendered contract, not a
second editable definition. A valid test link is a declared relationship, not
proof of test execution or adequacy. Query examples check expected paths; the
independent kernel and conformance tests remain necessary.

Exit codes: **0** means checks passed (or views refreshed), **1** means invalid,
noncanonical, or stale content, and **2** means checking could not complete.
The checkout and helper are trusted project code, not an untrusted-input sandbox.
Writes are preflighted together but are not a multi-file filesystem transaction.

## Change the content, not its retelling

Find the affected IDs, inspect the wording and linked tests, then edit the source
record. Run the checks, refresh the views, inspect the diff, and run the test suite.
Do not resolve a stale-view failure by independently rewriting generated prose.
An intentional behavior change still requires review and implementation changes;
rendering does not make a new statement true.

The maintenance tests cover wording changes, newly selected records, stale views,
manual view edits, and a renamed test reference. Test expectations remain
independent rather than being generated from the same records.

The catalog and helper ship in the source distribution, not the runtime wheel.
