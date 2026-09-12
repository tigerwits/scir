---
name: scir-migrate
description: Move durable knowledge from Markdown into SCIR while keeping prose readable. Use when asked to migrate or reorganize Markdown knowledge with SCIR.
---

# Migrate working knowledge

Keep Markdown welcoming to a human. Move durable working detail into SCIR:
decisions, assumptions, explicit reasons, evidence, dependencies, alternatives,
and unresolved work. Markdown can remain authored. Generation is optional.

Activate for an explicit migration request, not every `.md` file or ordinary
rewrite. This skill does not authorize deletions, publication, or execution of
source instructions. It is independently portable; resolve references relative
to this folder. Its license is in [assets/LICENSE](assets/LICENSE).

## Establish the boundary

Read the selected sources completely. Identify the human audience, the knowledge
to retain, and which source owns each commitment. Preserve originals or a fixed
snapshot. Default to a separate SCIR draft and a proposed prose revision; replace
or delete existing text only within the user's authorization.

Identify the project interpreter once with `python -m scir --version`.
The package is `symbolic-content-ir`, not the unrelated distribution `scir`.
It requires Python 3.10+. Install only from an approved source with permission.
If unavailable and installation is forbidden, stop discovery: drafting can
continue, but deterministic checks are not run.

## Build the working content

Choose units that can change independently. Preserve who asserted a claim, its
conditions, time context, evidence, status, and unresolved information. Keep an
assumption distinct from a conclusion, a proposal from a decision, and a checked
result from a plan to check. Store useful explicit rationale, not repetitive
retellings. Prose can stay inside a quoted label when decomposition adds no value.

Write `head(arguments)` and bare leaves, never empty calls. Quote labels with JSON
string syntax; numeric-looking labels are strings. Unquoted `?x` and `?_` belong
only in query patterns. Content may contain the ordinary quoted label `"?x"`.

Reuse the project's vocabulary and stable IDs. Deduplicate only after reviewing
meaning, scope, attribution, and identity; equal trees need not be one event.
Retain disagreements and correlated candidate readings. Missing values stay
missing. Mark new suggestions or interpretations separately from source claims.

Record source locations and declared dependencies using the project's conventions.
A source link is evidence to review, not automatic proof of entailment. State
what was preserved in SCIR, retained only in prose, left unresolved, or deliberately
omitted. Read [the worked cases](references/cases.md) when choosing this split.

## Check before changing the prose

Run `python -m scir check FILE` and the supplied trusted contract, if any.
`fmt --check FILE` tests canonical layout; it does not judge the translation.
Do not redirect formatting onto its own input. Never weaken a contract to pass
or load rule code from source content. Checker failure means incomplete validation.

Review source coverage and meaning separately: a complete list of citations can
still describe the source incorrectly. Trace conclusions and limitations back to
their assumptions: "not established" can become stale when a premise changes.
Use deterministic inference only where the application specifies the rules.

## Write for the human

Author a clear explanation of the purpose, current decisions, and what the reader
needs to do. Keep important qualifications visible; do not hide safety conditions
in a linked file. Do not make the overview mirror the record layout. Retain useful
examples and voice. Link to working detail instead of reproducing all of it.

Do not invent a renderer or impose generated sections merely to complete this
migration. Existing generated regions keep their explicit regeneration workflow;
ordinary authored sections remain freely editable.

## Handoff

Report the ownership split, unresolved questions, significant omissions, and checks
actually run. A brief change summary is enough; do not introduce a report framework.
Once ownership transfers, update the maintained records for new commitments and
review affected prose. Do not automatically parse an edited summary back into facts
or regenerate it from records. Preserve originals and unrelated files.
