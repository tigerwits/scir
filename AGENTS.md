# Working on SCIR

These instructions are for contributors. Agents using SCIR in another project
should read the [consumer skill](skills/scir/SKILL.md).

Read [SPEC.md](SPEC.md) before changing behavior. [API](docs/api.md),
[theory](docs/theory.md), and [dialects](docs/dialects.md) explain the other layers.

## Change workflow

Use [the SCIR content](spec/requirements.scir) to find affected IDs, wording,
examples, and test links. [The maintenance guide](spec/README.md) defines ownership.
Query/occurrence paragraphs in SPEC and the API guide are generated: edit their
SCIR records, then run `python spec/check.py --write-views`. Review the resulting
diff. Never independently edit those views or silently treat a prose revision as
a new source fact. Other topics are still authored in their linked Markdown.

Run `python spec/check.py` before and after changes. It checks links, stored query
examples, and view freshness; it does not run the referenced tests or establish
that changed wording is correct. Keep the independent conformance tests.

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
python tools/check_properties.py
python tools/study_corpus.py
python examples/dialects.py
python examples/knowledge/run.py
python examples/dialect-chain/run.py
```

Tests execute documentation, shipped examples, and relocated skill references.
Build the wheel and sdist; test outside the checkout. For traversal changes, run
`python tools/benchmark.py`. Preserve the golden conformance vectors; never update
expected values merely to hide a regression.

Record commands and failures. Passing fixture tests is not evidence that an agent
loads or follows the skill. Distinguish local tests, CI results, and model trials.

Follow the requested Git workflow and preserve unrelated changes. Do not publish,
create tags/releases, change visibility, force-push, or rewrite history without
explicit authorization. Keep the license and documented 1.0 contract intact.
