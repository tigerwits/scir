# SCIR 0.2 specification

This document specifies the 0.2 reference format and API. Implementation
0.2.1 preserves the format and tightens the boundary checks documented below.
Normative requirements concern symbolic structure, not real-world truth.

## 1. Content

Let S be the set of nonempty finite Unicode-scalar strings. No Unicode
normalization or case folding is performed. A Term is a finite ordered tree:

    Term = S × List(Term)
    Document = List(Term)

The reference Python representation is one immutable `Term(symbol, args)`
constructor, with `args: tuple[Term, ...]`; a Document is a tuple of Terms.
There are no content variables, holes, explicit references, or reserved
logical labels. Different arities of the same label are allowed. Structural
equality compares labels, child counts, and corresponding ordered children.

Root order and duplicate roots MUST be preserved. Equal subtrees at different
paths are distinct syntax occurrences. Neither their equality nor their
inequality determines real-world event identity. Physical object sharing is
an implementation detail and MUST NOT affect occurrence enumeration.

A root is explicitly presented content. It need not be a factual assertion:
it can represent a question, command, report, or hypothesis. Nested nodes
MUST NOT be promoted to roots implicitly. In particular, a root query for
`A` does not match a document whose only root is `and(A, B)`.

## 2. Surface syntax

```ebnf
document  = newlines, [term, {separator, term}, [separator]], EOF ;
separator = newline, newlines | ";", newlines ;
term      = symbol, ["(", newlines,
            [term, {newlines, ",", newlines, term}, [newlines, ","]],
            newlines, ")"] ;
symbol    = identifier | json_string ;
identifier = (ASCII_letter | "_"), {ASCII_letter | digit | "_"} ;
newlines  = {newline} ;
```

Horizontal whitespace and `#` comments extending to newline are trivia.
Inside JSON-quoted labels `#` is ordinary data. JSON string escapes are
supported; decoded empty strings and isolated surrogate code points are
invalid labels. A call head and `(` MUST be on the same logical source line;
newlines within its parentheses are allowed. There is no grouping syntax.
Trailing commas inside applications and a trailing document separator are
accepted. Empty documents are allowed; `parse` still requires exactly one
term. Complete input consumption is required. `A B` is invalid, not two roots.

`A()` and `A` parse to the same leaf; the printer emits `A`.
`"Alice"` and `Alice` parse to the same symbol. A quoted symbol MAY be a head.
Quotes do not express quotation semantics or a separate literal datatype.
For exact words as content, an application can use ordinary vocabulary such
as `text("words")`; the wrapper supplies the convention, not the lexer.
No unquoted number syntax, assignment, definitions, decorators, imports,
attribute access, control flow, evaluation, or arbitrary Python execution is
supported by this surface parser.

### Canonical print

Print a label bare exactly when it matches `identifier`; otherwise use
JSON quoting with `ensure_ascii=False`. Print nonleaf children in original
order with comma followed by one space. Leaves have no parentheses.
Print each root on one line, followed by a newline; the empty document prints
as the empty string. Comments and original whitespace are not retained.

Within the parser's supported bounds:

    parse(str(t)) = t
    parse_document(format_document(D)) = D

This is structure preservation, not restoration of original source bytes or
proof that a translation preserves English meaning.

## 3. Pattern language

Patterns are a separate datatype:

    Pattern = Var(name) | Node(symbol, List(Pattern))

They reuse content syntax with `?identifier` additionally allowed in a term
position. `?_` is an anonymous wildcard; other names capture a whole ground
subtree. Bare `_` remains a literal symbol. `"?x"` is a literal label, not a
capture. Variables cannot appear as call heads or take arguments.

`parse_pattern` returns a Pattern; `parse` and `parse_document` MUST reject
unquoted `?x` and `?_`. The reference types reject pattern children in Terms.

`match(P, t)` performs one-way matching, not symmetric unification:

* A labelled pattern node matches equal label and arity, then ordered children.
* A capture binds the corresponding whole Term. Repeated captures require
  structural equality, not object identity or semantic equivalence.
* The wildcard matches without creating a binding.
* Success returns a finite name-to-Term map. Failure returns None. An empty
  map is successful ground matching and MUST NOT be treated as failure.

`instantiate(P, env)` simultaneously replaces captures by ground terms.
Missing bindings and wildcards are errors; unused environment entries are
ignored. There are no binders and consequently no variable-capture operation.

## 4. Occurrences, queries, editing

A Path is a nonempty tuple `(root_index, child_index, ...)` of nonnegative
integers. Boolean values do not count as integers for paths. Paths are valid
only in a particular document snapshot.

`walk(D)` yields `(path, term)` for every occurrence in root-order, depth-first
preorder. `at(D, p)` returns a term or raises ValueError for an invalid path.

`query(D, P, scope="roots")` matches roots only. Explicit `scope="all"`
visits every occurrence. A Hit includes `path`, `term`, and `bindings`.
No query scope denotes logical consequence. The default is deliberately not
recursive. Results remain ordered and duplicate occurrences are retained.

`replace_at(D, p, t)` replaces exactly one occurrence, retaining all unrelated
occurrences. It does not rewrite inside the replacement or update annotations.
`diff(A, B)` compares positional roots/children. Equal terms are skipped;
equal head/arity recurses; otherwise it reports the changed frontier. Missing
roots are represented by None. It is not a minimum-edit or semantic diff.

## 5. Fingerprints

`digest(D)` is lower-case SHA-256 hex of:

    UTF8("scir:0.2:document\n") || UTF8(format_document(D))

The prefix is part of the format. No metadata enters the fingerprint.
This is a content fingerprint, not a unique document-instance identifier,
event ID, or mathematical guarantee against collisions. Python `hash()`
is deliberately NOT specified as a persistent wire identifier.

## 6. Relational transport

`encode(D)` emits the exact key set:

    version: "scir-relations/0.2"
    nodes: [[id, symbol], ...]
    args: [[parent_id, position, child_id], ...]
    roots: [[position, node_id], ...]

Every occurrence, INCLUDING every leaf, has a node row. Encoding uses
preorder IDs starting at zero, without deduplication. Array row order is
not semantic; the explicit positions determine order.

The decoder MUST validate unique nonnegative integer IDs, valid labels,
existing edge endpoints, unique contiguous positions beginning at zero,
unique root nodes, zero incoming edges for roots, exactly one incoming edge
for nonroots, and reachability of every node from the roots. Cycles, sharing,
orphan nodes, duplicate rows/positions, unknown keys and unsupported versions
are rejected. This is a forest transport, not an arbitrary DAG transport.

For successful reference encoding:

    decode(encode(D)) = D

Renaming node IDs bijectively and permuting row order preserves decoding.
`encode(decode(R))` canonicalizes occurrence numbering and row order; it need
not equal the original arbitrary row serialization.

## 7. Annotations and ambiguity

`Annotation(snapshot, path, key, value_json)` is outside content. The snapshot
is `digest(D)`. `annotate` validates a path and copies JSON metadata into a
canonical immutable string: sorted keys, no extra whitespace, finite JSON
numbers, Unicode scalar strings. Annotation keys are nonempty Unicode-scalar
strings. Metadata dictionaries MUST have string keys: integer/Boolean keys
are rejected, never coerced. Lists and tuples encode as JSON arrays; other
non-JSON Python objects are rejected with ValueError. `Bundle(D, annotations)` validates each
target against D and rejects stale fingerprints and invalid paths.

    erase(Bundle(D, M)) = D

This is only content projection: evidence, confidence and source attribution
are intentionally lost on erasure. It is not an epistemic equivalence.
No automatic annotation relocation across edits is performed.

`Alternatives(options)` is a distinct, unresolved envelope of at least two
candidate Documents. Its options are NOT roots of one Document and are NOT
logical disjuncts. `choose(i)` explicitly selects an option by index. No
metadata-erasure operation chooses a candidate. Local holes, packed choices,
correlation variables and ambiguity surface syntax are deferred.

## 8. Explicit templates and profiles

The optional API-only template layer accepts named
`Definition(parameters, body_pattern)` values. Parameters are unique
capture names, excluding `_`; every body capture must be declared. Definition
bodies may reference other declared names only in an acyclic dependency graph.
Names denote macros of one specified arity. Known macro calls in ALL bodies
are arity-checked, including unused definitions. Definitions emit no roots.

`expand(D, definitions)` first expands arguments, substitutes them into a
matching definition body, and expands that body. The visitor performs these
operations together rather than allocating an unbounded intermediate term. Unknown names stay ordinary.
Parameter substitution does not replace bare symbols of the same spelling.
Nullary definitions are aliases for terms, NOT event references. Expansion
can duplicate occurrences and MUST NOT promise shared event identity.

The optional `boolean_normalize` profile interprets only `not` (arity 1),
`and`/`or` (arity >=2), and `if` (arity 2), in regions reached solely through
those heads. It validates arity, removes double negation and flattens same-head
`and`/`or` without reordering. It stops at EVERY other head. This is an opt-in
derived view, not core normalization or a translation of general English
conditionals. No symbol names are reserved by Core.

## 9. Implementation limits and errors

The mathematical model contains all finite trees. The small reference parser
supports at most 2,000,000 source characters, 100,000 nodes (across the whole
document) and depth 128 (root depth zero). Node/depth limits may be lowered;
node limits may be raised explicitly. Depth cannot be raised above 128.
`ParseError` contains an index plus one-based line and column.

The reference encoder rejects forests exceeding 100,000 occurrences or depth
128; the decoder defaults to those bounds. Templates allow at most 128
definitions and default to 100,000 steps with a depth guard of 128. A step is
a definition-body occurrence inspected during dependency checking, or one
expansion-visitor call. Substituted arguments count again at every occurrence.
One shared budget covers preflight and expansion; unused bodies also count.
Depth includes macro expansion frames. These checks precede substitution
allocation; a previously sufficient custom budget may need increasing.

Lexing is lazy with one-token lookahead. Successful parsing still consumes the
complete source; failures need not scan the rest of the file. When an input has
several errors, the first reported diagnostic may therefore differ from 0.2.0.

Metadata is limited to 100,000 value occurrences (including dictionary keys),
depth 128, and 2,000,000 canonical JSON characters. Empty containers count as
values, root depth is zero, and tuple arrays retain the existing conversion.
Cyclic containers, invalid Unicode, unsupported objects, and excess sizes
raise ValueError. Raw Annotation payloads are also size/depth checked by Bundle.
`erase` accepts a Bundle only, never an unresolved Alternatives envelope.

The CLI reads at most 16,000,001 characters, rejecting input beyond 16,000,000
before JSON parsing. The smaller SCIR source cap still applies to content.
Duplicate JSON object keys are rejected on relational decode instead of
silently keeping the final value. A decoder rejects a second incoming edge
as soon as seen rather than accumulating an arbitrarily large invalid table.
These are bounded reference interfaces, NOT a Python sandbox or universal
resource guarantee for all programmatically constructed objects.

Normal Python construction can create deeper trees. Recursive value equality,
printing and substitution are not promised stack-safe outside the supported
bounds. Constructor validation assumes normal frozen-dataclass use, not
hostile mutation through Python reflection.

## 10. Compatibility

0.2 removes Atom, Call, content Variable, `asserted`, `occurs`, implicit
normalization and the old query result shape. Use `Term`, `parse_pattern`,
`parse_document`, explicit query scope and Hit paths. The tests specifying
0.1 distinctions are intentionally replaced, not silently reinterpreted.
There is no semantic synonym mapping and no proof that a parsed document is
an accurate representation of its natural-language source.
