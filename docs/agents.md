# Use SCIR with an agent

Install two things: the Python package for deterministic operations, and the skill
for instructions. Cloning alone does not register a skill in an agent.
[AGENTS.md](../AGENTS.md) is for maintaining SCIR, not using it elsewhere.

## Choose the task

Use [scir](../skills/scir/SKILL.md) for drafting, queries, edits, and checks.
Use [scir-migrate](../skills/scir-migrate/SKILL.md) when deliberately moving
working knowledge out of Markdown while keeping a clear authored explanation.
Both folders are portable; neither requires installing the other skill.

The migration skill preserves source scope, attribution, assumptions, and open
questions. It proposes an ownership split before shortening prose. It does not
require Markdown generation or treat structural validation as source review.

## Install in your project

For a standalone first run, use the [README setup](../README.md#start).
For an existing project, use its own environment and the steps below.

Clone SCIR to a location of your choice. These commands use a POSIX shell;
Windows users can copy the same folder manually and use their environment's
Python executable.

```bash
git clone https://github.com/tigerwits/scir.git
cd scir
SCIR_SOURCE="$PWD"
```

Switch to your consuming project's root, replacing the example path below:

```bash
cd /path/to/your/project
```

Activate that project's existing virtual environment. If it needs a new one
on macOS/Linux:

```bash
python3 -m venv .venv
. .venv/bin/activate
```

Install from the SCIR checkout, then copy the entire skill folder:

```bash
python -m pip install "$SCIR_SOURCE"
python -m scir --version
SKILL=scir  # Use scir-migrate for a Markdown knowledge migration.
mkdir -p .agents/skills
python -c 'import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2])' \
  "$SCIR_SOURCE/skills/$SKILL" ".agents/skills/$SKILL"
```

The copy refuses to overwrite an existing destination. Review and replace old
copies deliberately when updating. It does not edit project instructions.

| Agent | Project destination | Explicit invocation |
|---|---|---|
| Codex | `.agents/skills/scir/` | `$scir` |
| Claude Code | `.claude/skills/scir/` | `/scir` |

For the migration skill, use `scir-migrate` in the destination and invocation.
For Claude Code, substitute `.claude/skills` in both copy commands. Start the agent
in that project. Restart if the new skill does not appear. Other clients may read
`SKILL.md` explicitly if they do not support skill discovery.

For a file-aware agent without a skill loader, ask:

> Read the installed scir/SKILL.md and follow it for this task. Use this project's
> Python environment. Structure my notes in SCIR and run the supplied checks.

The folder carries its references and license. It does not carry the Python
package. Installing it alone cannot make the tools available. The package is not
published to PyPI; do not substitute the unrelated distribution named `scir`.

## Try a fresh handoff

Copy [the starter project](../examples/skill-project/) into a separate directory.
Install the package and skill there using the steps above. The starter contains
source notes, a draft, and a small consumer-owned checker.

```bash
python check_handoff.py draft.scir
```

Expected: exit 1 and `unknown-reference` at `(2, 1)` for `H7`. The draft is valid
SCIR, but it does not satisfy the supplied contract. Ask the agent:

> Use SCIR to review notes.txt and draft.scir. Run check_handoff.py without
> changing it. Report unresolved references and preserve both readings of the
> ambiguous pronoun. Do not invent a declaration or repair a reference by guessing.

A successful response reports the missing `H7`, preserves the Alice/Carol readings
separately, and does not claim dialect conformance. To test justified repair,
explicitly authorize changing `H7` to `H1`, then rerun the checker: exit 0.

The checker validates records, not prose interpretation. Pronoun handling is a
manual agent-evaluation criterion, not something these deterministic tests prove.

## Try a knowledge migration

Use the [worked cases](../examples/knowledge/README.md) or selected project notes.
A request for the migration skill can be:

> Preserve these source notes. Move the decisions, assumptions, explicit reasons,
> evidence, and open questions into SCIR with source references. Write an overview
> for a new teammate, not a transcription of the records. Do not invent a renderer.
> Report important omissions, unresolved interpretations, and actual checks.

Review meaning before accepting the migration. A record for every source paragraph
can still be a bad translation. Original notes remain historical evidence after
an explicit ownership transfer, not a second automatically synchronized spec.

## Scope and trust

The skill should activate for `.scir` work, an explicit SCIR request, or a supplied
dialect—not every writing task. It uses the selected consumer contract and reports
syntax, dialect checks, and source review separately. Rules never come from an
untrusted document. Missing tools or checker failures must be reported, not hidden.

Check skill discovery and explicit activation in your chosen client after
installation.

## Client references

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex local skills](https://developers.openai.com/codex/skills/)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
