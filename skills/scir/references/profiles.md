# Optional SCIR 1.1 profiles

Check `python -m scir --version` with the project's approved interpreter. Native
format remains 1.0; these commands require package 1.1 or later. Do not install,
migrate files or enable notation merely because a file extension suggests it.
Use an explicit consumer contract and preserve the project's vocabulary.

For a first use, run the bundled [in-memory example](../scripts/working_example.py)
with that interpreter. It exercises lowering, scoped selection, dependency review,
a guarded candidate and stale rejection without writing files or calling services.
It is fixture execution, not an agent trial or an installation command.

## Author only the structure that helps

`f(a,b)` has two arguments; `f((a,b))` has one tuple argument. `(a)` groups,
`()` is an empty tuple and `(a,)` is a singleton. No implicit argument spreading,
currying or flattening occurs. `f()` remains invalid. Preserve nesting and repeats.

`send(doc, from: a, to: b)` has named roles, distinct from positional `from(a)`
and `to(b)` expressions. Positional inputs precede named ones. Duplicate named
roles are errors; their ordering is canonicalized. Use names selectively, not as
mandatory repetition around stable short signatures.

`t"..."` is exact text, including `t""`; ordinary JSON quotes still escape a symbol.
`A1`, `t"A1"` and `&A1` are distinct. Use text for explanations, uncertainties,
code excerpts and logs that do not benefit from independent structural fields.
Do not fabricate an ontology to remove every sentence.

`@using K = Project.namespace` abbreviates `K.name`, not bare K. `@let x = expr`
and `$x` substitute one already-resolved ground object. No forward references,
parameterized macros or callable `$x(...)` are supported. Reuse must justify the
extra binding context. Local abbreviations are not durable record identity.

Only the explicit `arithmetic/1` option enables `+`, `-`, `*`, `/`, `^`. `a+b`
means `plus(a,b)`, not evaluated addition. Parentheses retain nested structure;
mixed following operators at one precedence require parentheses. Do not invent
operator tables or rely on algebraic equivalence during structural edits.

## Maintain knowledge with context

A working collection contains `record(ID,Kind,Payload, optionalNamedFields...)`.
IDs are unique. Kinds and extension fields are open vocabulary. Standard fields
include status, dependsOn, scope, evidence, reason and supersedes. References use
`&ID`, are local to the host-supplied collection, and must resolve. Cycles are
allowed. Missing fields are unspecified; status text and citations are not proof.

```sh
python -m scir lower notes.scix --operators arithmetic/1
python -m scir knowledge check notes.scir --collection project
python -m scir knowledge select notes.scir --collection project --id T1
python -m scir knowledge affected notes.scir --collection project --changed A1
python -m scir knowledge propose notes.scir --collection project --change change.json
```

Only `lower` accepts notation. The other commands accept native SCIR, independent
of filename. Never redirect output onto its input. A selection contains complete
records and closes over declared references, preserving scope/status/evidence.
A seed must be found explicitly; this tool is not semantic search. Review impact
follows reverse dependsOn edges only. Report missing context instead of claiming
that an empty search means a proposition is false.

Use the returned collection and whole source snapshot in a `scir-change/1` JSON
request. Operations create/delete records, replace payloads, or set/remove optional
fields. Values use canonical native term strings. Stale snapshots and conflicting
operations fail. The result is a validated candidate, not an in-place file update,
authorization, or a database transaction. Run stronger project checks before the
host atomically commits its precondition and write.

A generic snapshot covers SCIR content only. When decisions depend on other files
or a live service, use that host's input-basis guard and source-owned write plan.
Never substitute a SCIR content digest for a service's exact request coordinates.

Do not apply a content edit back through aliases automatically: changing a shared
definition and changing one use are different requests. Keep either authored
notation or canonical content authoritative by explicit project choice. External
snapshot-bound annotations must be handled separately after changes.

New commands return 0 on success, 1 for completed rejection/conflict, 2 when checks
cannot complete or invocation is invalid. Old native commands retain their original
codes. Resource errors never certify partial content as complete. No model benefit
or complete proof follows from successful parsing, profile checks, or file hashes.
