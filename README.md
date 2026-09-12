# SCIR — Symbolic Content IR

**Markdown is the surface. SCIR is the volume.**

SCIR is a symbolic content IR for agents and software. Maintain decisions,
requirements, assumptions, and open questions as structured content. Query it,
constrain it, and revise it directly. Use Markdown to explain the part needed
by the current reader, rather than maintaining a new account of the project
at every handoff.

The kernel keeps composition explicit and vocabulary open. Project contracts
can impose stronger rules without replacing the representation.

## Write for humans; keep the working detail

Markdown can be authored: a clear introduction, a design story, a short handoff.
It need not be generated or reproduce every record. SCIR keeps the underlying
assumptions, reasons, evidence, dependencies, and unresolved questions available
for the next person, agent, or program.

```scir
record(A1, Assumption, deterministic(Handlers))
record(P1, Proposal, unapproved(checkpointRecovery))
dependsOn(P1, A1)
```

An overview can explain why checkpoint recovery is being considered. An agent can
query what the proposal depends on. A dependency checker can identify it for
review when the handler assumption changes. Those are different uses of the same
working content, not a requirement to turn all prose into templates.

[Three complete examples](examples/knowledge/README.md) pair architecture,
incident investigation, and a mathematical argument with **authored human
overviews**. The [migration skill](skills/scir-migrate/SKILL.md) teaches how to
make this split without losing source commitments.

This repository also uses optional [deterministic views](spec/README.md) for
query rules that must be repeated exactly in its specification and API guide.
`python spec/check.py` checks their freshness. Generation is a local choice,
not the definition of using SCIR.

## Explicit composition

“Bob thinks Alice did not delete the file.”

```scir
think(Bob, not(delete(Alice, File)))
```

“Bob does not think Alice deleted the file.”

```scir
not(think(Bob, delete(Alice, File)))
```

These examples isolate negation scope, omitting tense. An author or model chooses
the interpretation; SCIR preserves its structure for tools to inspect.

## Kernel

```text
Term     = (symbol, ordered tuple of Terms)
Document = ordered tuple of Terms
```

One content constructor. Root order and duplicates matter. Labels such as `think`
and `not` have no built-in semantics. A dialect restricts accepted documents
without changing the representation.

## Start

Requires Python 3.10+ with no third-party runtime dependencies. Install from
source in a fresh directory.

**macOS / Linux**

```bash
git clone https://github.com/tigerwits/scir.git
cd scir
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m scir --version
python examples/knowledge/run.py
```

**Windows PowerShell**

```powershell
git clone https://github.com/tigerwits/scir.git
cd scir
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m scir --version
.\.venv\Scripts\python.exe examples/knowledge/run.py
```

The Windows commands do not require changing PowerShell execution policy.
The demo checks three knowledge artifacts and reports records that need review
after an example change. It leaves source notes and human overviews unchanged.
See the [worked cases](examples/knowledge/README.md) for expected results.
Installing from source may download build dependencies.

The distribution is `symbolic-content-ir`; the import and command are `scir`.
Download a wheel or source archive from the
[v1.0.0 release](https://github.com/tigerwits/scir/releases/tag/v1.0.0).
It is **not published to PyPI**. Do not install the unrelated distribution `scir`.

**Using an agent?** Install the [portable SCIR skill](skills/scir/SKILL.md) with the
[setup guide](docs/agents.md). It teaches drafting, queries, edits, and dialect
checks in your project. The package supplies the tools; the skill supplies instructions.

## Query and edit

```python
from scir import parse, parse_document, parse_pattern, query, replace_at

content = parse_document("think(Bob, use(Alice, SalesData))")
pattern = parse_pattern("use(Alice, ?data)")

assert query(content, pattern) == []  # Roots only.
hit = query(content, pattern, scope="all")[0]
assert hit.path == (0, 1)
assert str(hit.bindings["data"]) == "SalesData"

changed = replace_at(content, hit.path, parse("use(Alice, Report)"))
assert str(changed[0]) == "think(Bob, use(Alice, Report))"
```

`?data` is a pattern capture, not an unresolved entity. Finding `use(...)` inside
a belief does not establish that it happened. Queries make no model calls.

## Constrain a dialect

```python
from scir import parse_document, parse_pattern
from scir.constraints import check, forms, vocabulary

rules = (
    forms(parse_pattern("email(?sender, ?recipient, ?thing)")),
    vocabulary({"email", "Alice", "Bob", "Report"}),
)
assert check(parse_document("email(Alice, Bob, Report)"), rules) == ()
issue, = check(parse_document("email(Alice, Bob, Reprot)"), rules)
assert issue.path == (0, 2)
```

Both documents parse; only the first conforms. Rules are trusted application code,
not code loaded from content. See [dialects](docs/dialects.md) for open identifiers,
reference checks, composition, and failure handling. The [dialect chain](examples/dialect-chain/README.md)
keeps a source fixed while adding vocabulary, record, and reference constraints.
It also shows when a stricter contract must be blocked rather than filled by guessing.

## CLI

```bash
python -m scir check examples/query.scir
python -m scir fmt --check examples/query.scir
python -m scir query examples/query.scir --pattern 'use(Alice, ?data)' --scope all
python -m scir encode examples/document.scir | python -m scir decode
```

Output goes to stdout, errors to stderr. Commands never rewrite input files.
`fmt --check` returns 0 for canonical input, 1 for differences, and 2 for errors.
The CLI checks structure, not project constraints.

## Further reading

[Worked examples](docs/examples.md) cover incident investigation, corrections,
conditional requirements, and correlated ambiguity. The [API guide](docs/api.md)
also covers annotations, alternatives, and relational transport.

[Specification](SPEC.md) · [Theory](docs/theory.md) · [Agent setup](docs/agents.md) ·
[Research](docs/research/README.md) · [Changelog](CHANGELOG.md) · [Contributing](AGENTS.md) ·
[Releasing](docs/releasing.md) · [Security](SECURITY.md)

Format **1.0**; implementation **1.0.0**.
[Compatibility](SPEC.md#versioning-and-compatibility) covers the documented API
and format. Structural correctness does not establish truth, translation fidelity,
or improved agent performance. Licensed under [MIT](LICENSE).
