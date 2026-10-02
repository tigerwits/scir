# Named dialect contracts

This additive Python API composes acceptance checks over the unchanged SCIR
Document. It does not add syntax, a checker registry, a schema compiler, or an
execution engine. Existing `scir.constraints` rules and APIs remain supported.
A failed dialect check leaves generic SCIR content intact.

## Contract and execution

`scir.dialects.Rule(name, version, implementation, run, requires=())` names a
trusted callback. `run(document, context)` returns an iterable of existing
`Violation` records. `implementation` is a lowercase SHA-256 declared by the host.
It must identify the approved checker artifact, dependencies, and captured
configuration. This API does not inspect code, verify the hash, or authenticate
the host. Diagnostic rule labels do not substitute for implementation identity.
Use `from_constraint(name, version, implementation, constraint, requires=())` to
adapt an existing document-local constraint. Exceptions are not empty diagnostics.

`Dialect(name, version, rules)` has an immutable ordered tuple of unique rules.
Every prerequisite must appear earlier. Missing, cyclic, forward, self, or duplicate
prerequisites fail during construction. At most 256 rules are permitted. Names
and versions have a 1,024-byte UTF-8 bound; the JSON descriptor has a 256,000-byte
bound. An empty plan imposes no constraints and can accept an empty document.
Its `as_dict()` returns an inert descriptor; its `fingerprint` hashes canonical
JSON for that descriptor. There is intentionally no executable manifest loader.

`compose(name, version, *parents, rules=())` takes the ordered union of parent
rules, followed by new rules. A shared parent rule runs once. Its name, version,
implementation, prerequisite list and in-process callable must agree. A local
rule cannot override an inherited name. Incompatible parent orders fail rather
than silently reordering checks. Reuse the same Rule binding across parent plans.
This is conservative identity checking, not semantic equivalence of Python code.
Composition is conjunction for fixed pure total rules, not a satisfiability test
or a translator between different representations.

`Context(name, revision, document=())` contains separately supplied immutable data.
It accepts generic SCIR, not only working records. Its fingerprint binds the name,
revision and exact data digest. A context revision can distinguish A-B-A histories
only if the host actually supplies a monotonic revision. Context data is not trusted
because of any label it contains. The host must obtain it from an approved source.
Captured mutable state, live I/O and a live clock are outside reproducible checking.

## Validation result

`evaluate(document, dialect, context, *, collection, max_violations=1000,
max_bytes=1000000, limits=profile.Limits())` returns an immutable `Evaluation`.
The collection is explicit. Both input documents are measured before any callback.
The result binds the content digest, complete dialect descriptor, context identity,
and ordered per-rule Steps. Context data is not copied into the result.

Each step is `passed`, `rejected`, `blocked`, or `incomplete`. A failed prerequisite
blocks only its dependents. Independent checks still run. Each blocked step names
its direct blockers. A callback must finish before its diagnostics are accepted.
A callback exception discards that callback's partial findings and marks the step
incomplete. Invalid diagnostics/paths are incomplete, not rejection of the content.
Errors expose a category, not arbitrary exception text. Interrupt and process-exit
exceptions propagate. A trusted callback can still hang or use process privileges;
this API is not a sandbox, time limit or memory isolation mechanism.

Overall `outcome` is `incomplete` if any executed check cannot complete, otherwise
`rejected` if any check fails, otherwise `accepted`. `conforms` is true only for
accepted results. `complete` says the prescribed evaluation reached a conclusive
accept/reject result, not that blocked checks ran. `all_executed` and the step list
make that distinction explicit. Aggregate diagnostic/output exhaustion raises
`LimitError` without a partial receipt; input/configuration errors also raise.
No exception may be translated into acceptance by a calling adapter.

`Evaluation.as_dict()` returns a detached JSON-compatible record.
`matches(document, dialect, context, collection=...)` compares all bound input
identities. It does not re-execute checks or verify a signature. Public Python
objects and JSON receipts can be fabricated. Retain the exact package/runtime
build, host input basis and actual execution provenance where audit requires them.
The descriptor alone cannot prove that a callback matches its declared code hash.

## Handoffs and acceptance

A receipt applies to its whole checked document. Extraction, selection, edits and
concatenation require new evaluation unless a consumer establishes a preservation
law. Even reference-closed selection may omit records required by another rule.
An A-B-A content history restores its content digest; use host revision guards
when every intervening change matters. No receipt authorizes an action or a write.

For proposals, first construct the generic candidate with `scir.changes.propose`.
Evaluate the complete candidate under the required Dialect and fixed Context.
Do not promote a rejected or incomplete result to a checked candidate. Keep both
the generic source snapshot and external context/input-basis guard at the host's
atomic commit boundary. This API does not supply persistent commit semantics.
