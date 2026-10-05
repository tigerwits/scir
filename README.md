# SCIR

**Symbolic content with explicit structure and small, deterministic tools.**

SCIR stores ordered symbolic trees. Use it to keep requirements, assumptions,
decisions, evidence and unresolved questions addressable without assigning them
implicit truth, types or execution. Add a consumer-owned contract when a task
needs stronger constraints. SCIR is not a theorem prover or a database.

## Start

Python 3.10 or newer is required. From an approved checkout:

```sh
python -m pip install .
python -m scir --version
```

The distribution is `symbolic-content-ir`, not the unrelated package `scir`.
The native format remains 1.0; additive profiles are opt-in.

```python
from scir import parse_document, parse_pattern, query

content = parse_document("knows(Alice, Bob)\nknows(Bob, Carol)")
pattern = parse_pattern("knows(Alice, ?person)")
hits = query(content, pattern)
assert [hit.path for hit in hits] == [(0,)]
```

Roots retain order and duplicates. Nested statements do not become root facts.
Matching is structural; a successful query does not establish the truth of a
statement. Labels have no built-in domain meaning.

## This repository uses SCIR

[spec/index.scir](spec/index.scir) lists the canonical knowledge shards explicitly.
Definitions, theory, API guides, workflows, research qualifications and skill
sources are maintained in SCIR. Only this README and the thin
[AGENTS.md](AGENTS.md) bootstrap are tracked Markdown.

```sh
python spec/check.py
python spec/check.py knowledge list
python spec/check.py knowledge search --text 'Named roles'
python spec/check.py knowledge select --id NamedRoles
python spec/check.py knowledge affected --changed PreserveCallArity
```

Selections include whole records and their declared context. A requirement links
to its owning section, not a deleted Markdown heading. Origins retain historical
commit and source hashes. Navigation links are distinct from dependency edges.
Guarded proposals return source-owned write plans; they never persist or approve
changes. The caller must enforce all commit preconditions atomically.

| Topic | Canonical source |
| --- | --- |
| Native format | [spec/format.scir](spec/format.scir) and [native requirements](spec/native.scir) |
| Profiles, dialects and theory | [spec/profiles.scir](spec/profiles.scir) |
| API and adoption guides | [docs/guides.scir](docs/guides.scir) |
| Ownership, contribution, release and verification | [spec/workflows.scir](spec/workflows.scir) |
| Research, measured results and proof boundaries | [research knowledge](docs/research/knowledge.scir) |
| Migration provenance | [migration ledger](docs/research/migration.scir) |

## Human-readable documentation and agent skills

Create a fresh disposable export outside the checkout:

```sh
python spec/check.py export --out /tmp/scir-docs
python spec/check.py export --skill scir --out /tmp/scir-skill
python spec/check.py export --skill scir-migrate --out /tmp/scir-migrate-skill
```

Exports refuse existing destinations. The complete documentation is readable as
Markdown; portable skill bundles contain their `SKILL.md` adapters, references,
scripts, canonical SCIR and license. Edit the SCIR source, not the export.
Copy an **exported bundle**, not the raw skill-source folder, into the agent's
skill directory. The Python package must be installed separately.

The sources are [the consumer skill](skills/scir/knowledge.scir) and
[the migration skill](skills/scir-migrate/knowledge.scir). A deterministic portable
example is [working_example.py](skills/scir/scripts/working_example.py).
For an actual repository handoff, run [check_self_host.py](tools/check_self_host.py).
The [consumer lifecycle](examples/consumer-lifecycle/run.py) and
[dialect chain](examples/dialect-chain/run.py) provide separate runnable examples;
[example guidance](examples/guides.scir) explains their boundaries.

## Verify and contribute

```sh
python -m unittest discover -s tests -v
python tools/check_self_host.py
```

Build and test the wheel and source distribution outside the checkout. Keep
independent expected results, negative cases and frozen historical inputs.
A declaration link is not test execution. A structural check is not a proof of
translation fidelity, and finite tests are not a general proof. The Lean model
has its own stated scope. No agent-performance advantage is claimed from this
migration; independent model trials remain a separate research task.

For sensitive security reports, do not post exploit details in public issues.
Use GitHub's private vulnerability-reporting route when enabled; otherwise open
a minimal issue requesting a private channel without disclosing sensitive detail.
The full threat model and reporting policy are in `spec/workflows.scir`.

[MIT license](LICENSE). Repository-level tooling and documentation ship with the
source distribution; the runtime wheel remains focused on the library.
