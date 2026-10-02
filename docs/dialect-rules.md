# Profile-aware dialect helpers

`scir.dialect_rules` supplies ordinary `Constraint` functions. Use them directly
with `scir.constraints.check` or adapt them into a named plan with
`scir.dialects.from_constraint`. They do not select themselves from document labels.
The caller's checker identity must include the helper implementation and its
captured schema configuration. No configuration is fetched from candidate content.

## Profile adapters

`structured(document)` yields one whole-document violation for a completed
structured/1 rejection. `working(document)` does the same for working/1, including
record shapes, duplicate IDs and unresolved references. Resource exhaustion and
unexpected exceptions still propagate; named evaluation reports them as incomplete.
The adapter's internal collection name has no domain meaning or external authority.
Empty working collections pass unless a separate rule requires their presence.

Place structured validation first. Make working validation require it. Make
record-specific rules require the working rule. Prerequisites control execution;
combining old low-level constraints without these gates retains the old behavior.

## Record fields

`FieldSet(required=(), optional=())` takes bounded collections of field names and
copies them to immutable sets. Required and optional names must be disjoint.
`record_fields(shapes, rule="record-fields")` copies a mapping from allowed record
kinds to FieldSet values. The mapping can have at most 256 kinds, and each field
collection at most 256 names of at most 1,024 UTF-8 bytes. Unknown kinds or fields
and absent required fields produce occurrence-bound diagnostics. IDs and payload
expressions remain open. No global symbol allowlist is imposed on literal prose.
An empty schema permits only an empty collection; presence is a separate rule.

## Reference targets

`reference_targets(field, kinds, source_kinds=None, rule="reference-targets")`
checks an optional named field. It must be one explicit reference or a positional
tuple of explicit references. Every target must have a permitted kind. Missing
fields are ignored; use FieldSet for required presence. Tuple order and duplicates
are not rewritten, and an empty tuple passes. A named tuple is not a reference list.
The optional source-kind filter limits the records inspected, not the whole dialect.
All allowlists are copied. Similar words and literal text are not references.

Each record helper validates working/1 before using its index. A caller that omits
profile prerequisites can therefore receive a profile exception rather than a
normal diagnostic. Do not translate that exception into acceptance. These helpers
check shape and reference kinds, not approval, source fidelity or evidence truth.
Conditional status requirements remain small consumer-owned rules; the library
is not a general schema interpreter or a replacement for a domain checker.
