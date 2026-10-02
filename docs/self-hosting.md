# SCIR as a consumer of SCIR

Use an approved installed checkout (Python 3.10+) and read the contributor
instructions in [AGENTS.md](../AGENTS.md). This example needs no private skill,
external service, credential, network lookup or new runtime feature.

## Two runnable entry points

For a new consuming project, the portable skill ships a bounded in-memory example:

```sh
python skills/scir/scripts/working_example.py
```

It lowers named roles, tuples, text and references; selects a task with its
assumption, proposed decision and staging scope; follows review dependencies;
proposes one field change; and rejects the same request against changed content.
The records are explicitly hypothetical. The script writes no source or store.
It remains runnable after copying the skill to another project.

For work on SCIR itself:

```sh
python spec/check.py
python tools/check_self_host.py
```

The second command uses real repository records through the actual CLI. It copies
the checkout to a disposable directory, captures NamedRoles and its required
context, prepares a source-owned change, changes authoritative prose without
changing the SCIR snapshot, checks stale-basis rejection, obtains fresh context,
and replays a valid write plan only in the temporary copy. The final real checker
must pass and its content fingerprint must equal the proposed candidate. Original
maintenance inputs are hash-checked before and after. A temporary fixture replay
is not a concurrent persistence implementation or an approved design change.

## Maintain one owner

The source is `spec/native.scir` plus `spec/knowledge.scir`. The compatibility
catalog and marked Markdown sections are derived. Other normative sections stay
document-owned. Read [ownership](../spec/OWNERSHIP.md) and the
[handoff contract](../spec/HANDOFF.md); do not edit a generated retelling.

A selection's `source_snapshot` belongs in the change JSON. Its
`input_basis.digest` is the separate repository `--basis` guard. Generic working
collections do not hash linked authoritative files automatically. Inspect changed
inputs before retrying; do not refresh fingerprints to bypass a conflict.

## Verification and limits

`test_adoption_examples.py` runs these paths in the ordinary suite. A separate CI
job builds a wheel and source distribution, installs the wheel, repeats the
consumer and repository scenarios from the extracted source distribution outside
the checkout, and retains their reports plus the tested source and distributions.
The reports count actual subprocess output bytes, not LLM framing or reasoning
quality. Existing conformance, portability, packaging and proof gates still apply.

This demonstrates deterministic usage and relocation. It does not show that a
provider activates a skill, that an independent agent follows it, that migration
is semantically faithful, or that the format improves task success. Those require
separate trials. A host must still enforce the complete commit basis atomically
when applying a reviewed plan to shared persistent state.
