# Migration with the optional 1.1 profiles

Use this reference only when the project explicitly adopts `structured/1`,
`notation/1` or `working/1`. Existing native dialects are not obsolete. Do not
change an installed skill cache or redirect a service-owned knowledge store to
local files. A local SCIR draft or test fixture is not accepted service state.

## Choose ownership before notation

Maintain one owner: authored Markdown (possibly with native SCIR fences), authored
`.scix`, or canonical `.scir`. Do not keep two editable translations. Preserve a
revision-exact baseline and an explicit mapping from source units to records.
A generated payload is a view, not a second source. Do not concatenate unrelated
fences without an explicit collection contract; their surrounding scope matters.

A fence selects neither a profile nor permissions. A host that only recognizes
native `scir` fences does not suddenly support `scix`; preserve its pinned parser
and test new profiles in a separately approved environment. Never relabel a fence
to bypass a validator. Use the owning skill validator as well as SCIR checks.

## Represent independently changing units

Keep positional arguments for stable signatures and names for ambiguous roles.
`f(a,b)` differs from `f((a,b))`; tuples retain nesting and multiplicity. Named
fields follow positional arguments, have unique keys, and canonicalize key order.
`t"..."` is literal text; quoted symbols still denote symbols. `&ID` is an explicit
reference; ordinary repeated words do not create links. An `@let` abbreviation
substitutes a ground value, not a persistent record or callable function.

Use `record(ID,Kind,Payload,...)` for an explicitly selected working collection.
Status is an authored state, not approval. Preserve assumptions, conditions,
provenance, uncertainty, and absent information. Link prerequisites explicitly;
selection closes over references, whereas review impact follows `dependsOn` only.

This complete in-memory example is fixture data, not a claim about a project:

```python
from scir.notation import lower
from scir.knowledge import build_index, select
source = '''record(Boundary, Rule, forbid(directStoreAccess))
record(Recovery, Procedure, when(ambiguous(submission), lookup(originalKey)),
       dependsOn: (&Boundary,), scope: (authorizedServiceOnly,),
       reason: t"A retry must not conceal an unknown result.")
'''
document = lower(source)
index = build_index(document, collection="migration-fixture")
packet = select(index, ("Recovery",))
assert packet.selected_ids == ("Boundary", "Recovery")
assert packet.document == document
```

## Check the migration and the workflow separately

Check syntax, the explicitly selected profile, canonical transport, and the
project's stronger contract. Review source coverage against independently stated
obligations: order, alternatives, original keys, authorization and qualifications
must not be lost. A hash detects a changed baseline, not a faithful interpretation.
Retain exact independent trees for difficult cases; do not regenerate expected
results from the candidate being graded.

Measure the complete source, guide, selection and update request/response. Include
retained prose and routing context; report both cold and already-known guide costs.
Saving body tokens is not proof of lower end-to-end cost or better agent behavior.
Keep authoring fixtures, deterministic executions and independent agent trials
separate. Publish no skill or installed-cache claim from source tests alone.

## Handoff safely

Native `check` checks only syntax. `knowledge check/select/propose` consume native
working records, not implicit notation or Markdown. Explicitly lower `.scix` to a
separate output when needed. Guard a change with its collection and whole source
snapshot; proposed values must be canonical native term strings.

A generic proposal guards SCIR content, not linked files, live services or Git
history. Use a host-specific input-basis guard when authoritative material is
external. Preserve source ownership in the host's write plan and revalidate all
inputs at its atomic commit boundary. Do not apply compiled changes back through
aliases or multiple source shards by guessing. Report stale input as conflict,
invalid content as rejection, and resource/I/O failure as incomplete. Do not retry
by merely replacing the fingerprint without reviewing the changed context.
