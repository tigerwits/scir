# SCIR format 1.0

This is the normative structural contract. “MUST” and “MUST NOT” state format
requirements. The reference Python API is described separately in
[docs/api.md](docs/api.md). Neither document assigns truth conditions to vocabulary.

The marked query/occurrence paragraphs below are generated from
[the maintained SCIR records](spec/requirements.scir). Edit those records, then
run `python spec/check.py --write-views`. Other sections are maintained here.

## Content

Let S be the nonempty finite strings of Unicode scalar values.

```text
Term     = S × List(Term)
Document = List(Term)
```

Terms are finite ordered trees. Labels may occur at any arity, including zero.
No label is reserved for logic, types, execution, or real-world identity.
Structural equality compares labels, arity, and corresponding children.
Unicode normalization and case folding MUST NOT be performed.

A document MUST preserve root order and duplicate roots. Roots are presented
content, not necessarily facts. Nested occurrences MUST NOT be promoted to
roots implicitly. Equal values at different paths remain different syntax
occurrences; physical sharing MUST NOT change occurrence enumeration.

## Surface grammar

```ebnf
document   = newlines, [term, {separator, term}, [separator]], EOF ;
separator  = newline, newlines | ";", newlines ;
term       = symbol, ["(", newlines, term,
             {newlines, ",", newlines, term}, [newlines, ","], newlines, ")"] ;
symbol     = identifier | json_string ;
identifier = (ASCII_letter | "_"), {ASCII_letter | digit | "_"} ;
newlines   = {newline} ;
```

Space, tab, carriage return, and form feed are horizontal trivia. `#` starts
a comment through the next LF; the LF remains a separator. Inside quoted
labels, `#` is data. An application head and its opening parenthesis MUST be
on the same source line. There is no grouping syntax.

Leaves are written without parentheses: `A` is valid, `A()` is invalid.
Trailing commas are allowed inside nonempty applications. Blank lines, empty
documents, and a single trailing separator are allowed. `A B` and `A;;B` are
invalid. Successful parsing MUST consume the complete input.

Quoted labels use JSON string syntax. Their decoded values MUST belong to S;
empty labels and isolated surrogate code points are invalid. Quoting only
escapes a label: `"Alice"` and `Alice` are the same leaf. A quoted label may be
an application head. Number-like labels require quotes and have no arithmetic
semantics. Imports, assignment, decorators, definitions, attribute access,
control flow, and arbitrary Python execution are not part of the language.

## Canonical form

A label matching `identifier` MUST print bare. Other labels MUST use JSON
quoting with Unicode scalar characters left unescaped except JSON-required
escapes: quote, backslash, and control characters. Use the short JSON escapes
for backspace, tab, LF, form feed, and CR; use lowercase `\u00xx` for the other
characters below U+0020. Do not escape `/` or other scalar values.

Leaves print as labels. Nonleaves print as `head(child, child)` with one space
after every comma and no other whitespace. A document prints each root followed
by one LF; the empty document prints as an empty string. Comments are not content.
Within the applicable size and depth bounds:

```text
parse(str(t)) = t
parse_document(format_document(D)) = D
```

These laws preserve tree structure, not the original source bytes.

## Patterns and substitution

Patterns are separate from ground content:

```text
Pattern = Var(name) | Node(symbol, List(Pattern))
```

They use the same grammar with `?identifier` additionally allowed in a term
position. `?_` is an anonymous wildcard; every other name captures a whole
subtree. Bare `_` and quoted `"?x"` are ordinary labels. Captures cannot be
heads or have arguments. Content parsers MUST reject unquoted captures.

Matching is one-way, against a ground Term. A labelled node matches equal
label and arity, then corresponding children. A capture binds its name to the
subject subtree; later occurrences require structural equality. A wildcard
matches without binding. Failure returns no match, distinct from a successful
empty binding map. No symmetric unification, inference, or backtracking occurs.

Instantiation simultaneously replaces captures with ground Terms. Missing
bindings and wildcards are errors; unused bindings are ignored. There are no
binders or implicit substitutions into symbol labels.

## Occurrences and operations

<!-- scir:query-spec:start -->
<!-- Maintained in spec/requirements.scir; refresh with python spec/check.py --write-views. -->

A path is a nonempty sequence `(root_index, child_index, ...)` of nonnegative integers. Python Booleans are not indices. Paths are local to a document snapshot.

Walking enumerates every occurrence in root-order, depth-first preorder.

Queries default to matching roots.

Explicit `scope="all"` matches every occurrence.

Results include path, matched term, and bindings, in traversal order, including duplicate occurrences.

Neither scope computes logical consequences.
<!-- scir:query-spec:end -->

A targeted replacement changes one valid occurrence and retains unrelated
occurrences. It neither traverses the inserted replacement nor relocates metadata.
A positional diff descends while corresponding labels and arities agree; otherwise
it reports that changed frontier. Missing roots are represented separately from
terms. It is not minimum-edit alignment or a semantic comparison.

## Fingerprint

The document digest is lowercase hexadecimal SHA-256 of:

```text
UTF8("scir:1.0:document\n") || UTF8(format_document(D))
```

The prefix is normative. Metadata is excluded. The digest is not a document-instance
ID, event ID, or mathematical proof of equality. Python `hash()` is not a wire ID.

## Relational transport

The JSON object MUST have exactly these keys and shapes:

```text
version: "scir-relations/1.0"
nodes:   [[id, symbol], ...]
args:    [[parent_id, position, child_id], ...]
roots:   [[position, node_id], ...]
```

Every occurrence, including each leaf, has a node row. The encoder assigns
preorder IDs starting at zero, without deduplication. Explicit positions, not
row order, determine child and root order.

The decoder MUST reject duplicate IDs, invalid labels, unknown endpoints,
noninteger or negative IDs/positions, duplicate or noncontiguous positions,
duplicate roots, unsupported versions, unknown keys, cycles, sharing, and
unreachable nodes. Roots have no incoming edges; every other occurrence has
exactly one. All positions begin at zero without gaps. JSON object keys MUST
be unique at the JSON-reading boundary.

```text
decode(encode(D)) = D
```

Permuting rows or bijectively renaming IDs preserves decoding. Re-encoding a
valid transport chooses canonical preorder IDs and row order, not its original bytes.

## Annotations and alternatives

Annotations are external records `(snapshot, path, key, value_json)`.
`snapshot` is the document digest; `key` is a nonempty Unicode-scalar string.
The reference Bundle validates targets and rejects stale fingerprints or invalid
paths. It MUST NOT automatically relocate metadata after an edit.

Metadata accepts finite JSON scalars, string-keyed objects, and list/tuple arrays.
It is copied to immutable canonical JSON: sorted keys, no extra whitespace,
Unicode scalar strings, finite numbers. Non-string object keys MUST be rejected,
not coerced. A raw annotation payload is accepted only if already canonical.
This Python metadata encoding is not a separate cross-language fingerprint standard.

```text
erase(Bundle(D, annotations)) = D
```

Erasure preserves content only; it loses evidence and provenance. It accepts
Bundles, not unresolved interpretations.

Alternatives hold at least two whole candidate Documents. Candidates MUST NOT
be combined as roots or treated as logical disjunction by the kernel. Selecting
one is an explicit indexed operation. The candidate set need not be exhaustive;
selection alone does not establish correctness. No surface ambiguity or hole
syntax is defined.

## Application constraints

A dialect selects admissible Documents without altering the Term algebra, content
grammar, canonical bytes, fingerprint, or relational envelope. Generic validity
MUST NOT imply conformance to an application dialect. Consumers choose their
required constraints; no document label automatically selects or bypasses them.
Constraints MUST NOT silently rewrite content or promote nested occurrences.

The optional Python constraint API is specified in [docs/dialects.md](docs/dialects.md).
It is not a new wire format, reserved vocabulary, or truth definition. It leaves
structural `validate` and the CLI's structural `check` unchanged. A failed or
incomplete constraint check MUST NOT be reported as conforming.

## Reference implementation bounds

The algebra contains all finite trees. The reference implementation applies:

| Boundary | Limit |
|---|---|
| Source parser | 2,000,000 characters; 100,000 occurrences; depth 128. |
| Relational encoder/decoder | 100,000 occurrences; depth 128. |
| Each annotation JSON payload | 100,000 values including keys; depth 128; 2,000,000 canonical JSON characters. |
| CLI input read | 16,000,000 characters before parsing; the smaller source cap still applies. |

Root depth is zero. Parser and decoder accept explicit positive integer node
budgets; depth budgets may be lowered but not raised above 128. The encoder's
bounds are fixed. Empty metadata containers count as values. Cyclic metadata,
invalid Unicode, unsupported objects, and exceeded bounds raise validation errors.
Raw annotation payloads receive the same checks through Bundle.

`ParseError` carries a zero-based character index and one-based line and column.
Other invalid boundary inputs raise `ValueError`. First diagnostics on multiply
malformed inputs are unspecified. CLI processing errors return 2; formatting
check differences return 1; success returns 0.

These are bounded reference interfaces, not a sandbox. Direct Python construction
can exceed parser bounds; recursive equality, printing, and instantiation are
not promised stack-safe for such trees. Constructor validation assumes ordinary
immutable use, not hostile mutation by reflection. `validate(D)` checks the ground
Document shape, not truth, source fidelity, or a complete resource audit.

## Versioning and compatibility

The package version is `1.0.0`; the format identifier is `1.0`.

Within format 1.0, the content grammar, canonical UTF-8 representation, digest
domain, and relational envelope have the behavior specified here. Equivalent
valid content MUST keep the same canonical bytes and fingerprint. A change to
those rules requires a new format identifier; a decoder rejects unsupported
identifiers rather than guessing their meaning.

Within package 1.x, the documented API in [docs/api.md](docs/api.md), its return
record fields, and the documented CLI behavior are the compatibility surface.
Compatible additions may use a minor release; bug fixes may use a patch release.
Breaking documented behavior requires a major release. Names not documented as
public, private helpers, incidental exception wording, and benchmark timings
are not compatibility promises. Rejection diagnostics may change, but documented
exception types and CLI exit codes remain part of the contract.

The [conformance vectors](docs/conformance.json) fix representative canonical
strings, document digests, and occurrence tables. They supplement this specification;
they are not exhaustive and do not certify an English-to-SCIR translation.
Version 1.0 makes a structural/API commitment, not a claim of proven agent benefit
or general production suitability for every workload.
