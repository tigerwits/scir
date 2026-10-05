# Working on SCIR

These instructions are for contributors. Agents using SCIR in another project
should read the [consumer skill](skills/scir/SKILL.md).

Read [SPEC.md](SPEC.md) before changing behavior. [API](docs/api.md),
[theory](docs/theory.md), and [dialects](docs/dialects.md) explain the other layers.
The optional profiles have their own [contract](docs/structured-profiles.md).

## Change workflow

Use the combined working collection in [native records](spec/native.scir) and
[profile knowledge](spec/knowledge.scir). Read [ownership](spec/OWNERSHIP.md).
Find the affected IDs, rationale, qualifications and independent test links with
`python spec/check.py knowledge select --id ID`. Use `knowledge affected` for
review dependencies. These commands do not infer truth or certify test adequacy.

The old catalog is an explicit `python spec/check.py --legacy` compatibility export.
It is not a maintained source or an intermediate validation format.
The six query/occurrence records in `spec/native.scir` own exact wording and
examples; their marked SPEC/API paragraphs are generated. Other normative rules
remain document-owned and their records are indexes. Edit the designated owner,
then run `python spec/check.py --write-views` and review the diff. Never treat an
independent prose revision or automatic rendering as a new source fact.

Run `python spec/check.py` before and after changes. It checks both source shards,
references, source/test/model links, stored query examples and direct view freshness. It
does not run the linked tests or Lean proofs. Keep independent conformance tests.
Repository `knowledge propose --basis DIGEST --change FILE` requires the inspected
selection's input-basis digest, validates local contracts and returns a source-owned
write plan. Read [handoffs](spec/HANDOFF.md); never refresh a stale guard without
reviewing changed inputs. Proposals do not persist or automatically approve changes.
For a first use or a handoff change, run `python tools/check_self_host.py` and read
[the executable self-use example](docs/self-hosting.md). It touches only a disposable
copy and verifies the original inputs; it is not a production transaction recipe.

Use `python spec/check.py knowledge diagnose --id ID --encoding notation` to inspect context
and encoding capacity. Optional `select/propose --view compact` responses retain
the basis digests; retrieve the hash-bound artifact for the complete basis and
write plan. A proposal delta is not complete context. Read the [delivery contract](docs/workflow-tools.md).

For dialect changes, read [named contracts](docs/dialect-contracts.md) and run
`python tools/check_dialects.py`. It validates the existing repository contract
through the named engine on a fixed file copy, with before/after basis checks.
Contract names and result hashes are identities, not permission or execution proof.

## Authored prose and working knowledge

Markdown is not required to be generated. Outside the two marked query sections,
write for the human reader. Put durable reasoning, dependencies, and unresolved
work in SCIR when it makes them useful to agents and tools. Keep original sources
and clarify ownership before migration; a shape check does not prove fidelity.
See [the migration skill](skills/scir-migrate/SKILL.md) and
[the authored examples](examples/knowledge/README.md). Do not expand generation
merely to make prose look synchronized.

## Code and writing

Prefer immutable values, small pure functions, and direct standard-library
algorithms. Remove wrappers that add no meaning. Comments explain invariants.
Optimize for what a reader must understand, not line count.

Lead with the task or rule. Use short sentences, concrete examples, and consistent
names. Remove repeated motivation, not qualifications that affect correctness.
SPEC presents the contract; marked query sections are maintained in SCIR. Guides
explain use; theory explains laws. The portable skill contains only operational
essentials and its own relative references.

## Verify

Install the checkout or set `PYTHONPATH=src`, then run:

```bash
python spec/check.py
python -m unittest discover -s tests -v
```

The suite executes documentation, shipped examples, the named repository check,
the disposable-copy handoff, and relocated skill references. Run individual
examples when inspecting their reports; do not repeat them as mandatory gates.
See [verification boundaries](docs/verification.md) for CI ownership.
Build the wheel and sdist; test outside the checkout. For traversal changes, run
`python tools/benchmark.py`. Preserve the golden conformance vectors; never update
expected values merely to hide a regression.

Record commands and failures. Passing fixture tests is not evidence that an agent
loads or follows the skill. Distinguish local tests, CI results, and model trials.

Follow the requested Git workflow and preserve unrelated changes. Do not publish,
create tags/releases, change visibility, force-push, or rewrite history without
explicit authorization. Keep the license and documented 1.0 contract intact.
