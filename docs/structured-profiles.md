# Additive profiles and working knowledge

Status: approved implementation contract for package 1.1.0. Core format remains
1.0. This document specifies optional behavior; it does not reinterpret generic
SCIR, alter native syntax, or reserve vocabulary in the kernel. SPEC.md remains
the native format contract. Existing canonical bytes, digests, ordered occurrences,
pattern matching and relational transport remain unchanged.

## Layer boundaries

- `structured/1` encodes structured objects in ordinary SCIR terms.
- `notation/1` lowers optional authoring syntax to those terms.
- `working/1` validates addressable records and their explicit local references.
- `scir-change/1` describes guarded changes, not executable SCIR content.

Callers explicitly select profiles. Extensions never load imports, execute code,
establish truth, authorize actions, or reinterpret a filename automatically.
Production implementations use only the Python standard library. The core does
not import these layers. The private external-grill experiments remain unchanged.

## Structured values

The four profile tags are `scir.tuple`, `scir.kw`, `scir.text`, `scir.ref`.
Their dotted native labels require ordinary JSON quotation in SCIR 1.0. Within
this profile these tags cannot also denote unrelated ordinary constructors;
quoting does not escape that restriction. Generic native documents using these
labels for other purposes are not automatically migrated.

| Authoring expression | Exact native representation |
| --- | --- |
| `()` | `"scir.tuple"` |
| `(a,)` | `"scir.tuple"(a)` |
| `(a,b)` | `"scir.tuple"(a,b)` |
| `t""` | `"scir.text"` |
| `t"hello"` | `"scir.text"(hello)` |
| `&A1` | `"scir.ref"(A1)` |
| `f(a,key:b)` | `f(a,"scir.kw"(key(b)))` |

Native canonical formatting inserts its usual spaces. Text and references carry
literal leaf labels, which are not recursively interpreted as tags. Text has
zero or one leaf child; zero means the empty string. References have exactly one
nonempty leaf ID. Text preserves Unicode scalar sequences, escapes, empty values,
line breaks and case without normalization. `Alice`, `t"Alice"` and `&Alice`
remain distinct. Quoted native labels still escape symbols, not text.

A keyword container is legal only as the final child of an ordinary application
or tuple. It is nonempty. Every entry has a nonempty label and exactly one value.
Keys are unique and sorted by their UTF-8 bytes. Key order does not survive
notation lowering; positional order, nesting and repetitions do. Profile readers
reject malformed or noncanonical containers instead of silently repairing them.
Field labels are labels, not expression heads or alias targets. A keyword value
is an expression, so it cannot be an unattached keyword container.

An application without named roles gets no wrapper. `f(from:a)` differs from
`f(from(a))`. Missing fields remain unspecified. No defaults are fabricated.

## Notation/1

`(a)` groups a single expression. `()` is an empty tuple; `(a,)` a singleton;
`(a,b)` a pair. `f(a,b)` has two positional arguments, whereas `f((a,b))` has one
tuple argument. `f(a,)` means `f(a)`; `f((a,))` passes a singleton tuple. `f()`
is rejected: a zero-child native term remains `f`. Tuple items can also have
named roles: `(doc,from:a,to:b)` is an object. Passing that object does not unpack
its components. There is no flattening, spreading, currying or implicit packing.

Named arguments follow positional ones. Duplicate names fail even when values
agree. Their input order is canonicalized as described above. Names may be
quoted, remain nonempty, and are not rewritten by aliases. An application's
head is a literal symbol, not an arbitrary expression. `$op(a)`, `f(a)(b)` and
`compose(f,g)(x)` are rejected rather than evaluated or guessed.

`t` immediately followed by a JSON string is text syntax. Ordinary JSON quotes
still denote symbols. Empty quoted symbols fail; empty text succeeds. `&name`
or `&"unusual-id"` constructs a reference. Dotted names are single labels, not
attribute access. Number-looking labels preserve spelling: `01`, `1`, `1.0` are
distinct symbols. Numeric interpretation belongs to a domain contract.

Newlines or semicolons separate statements. `#` starts a line comment outside
strings. Heads attach to `(` on the same source line. Trailing commas are allowed.
Successful parsing consumes the full input. Unsupported braces, patterns,
assignment expressions, lambdas, imports and declarations fail explicitly.

### Local bindings

`@using K = TigerKnow.mutation` replaces an unquoted qualified prefix, e.g.
`K.lookup`; bare `K`, quoted names, field names, references and fixed operator
targets are unaffected. Targets resolve immediately. `@let x = expr` stores an
already-resolved expression; `$x` substitutes exactly one expression. A tuple
abbreviation is not spread and a value reference is not a callable head.

Declarations affect subsequent expressions only. Aliases and values occupy
separate namespaces; duplicates within one namespace fail. Forward references,
unbound self-reference and parameterized definitions fail. Each document starts
with fresh bindings; no nested braced declaration scope is introduced in this
version. Declarations emit no roots. Later aliases cannot capture stored values.
Each substituted occurrence counts separately even with physical immutable sharing.
The printer does not invent aliases or recover source declarations/comments.

### Arithmetic/1

Operators are disabled unless the caller explicitly selects `arithmetic/1`.
The immutable profile contains these rows:

| Token | Target | Fixity | Precedence |
| --- | --- | --- | ---: |
| `+` | `plus` | n-ary uninterrupted chain | 50 |
| `-` | `sub` | left binary | 50 |
| `-` | `neg` | prefix | 65 |
| `*` | `mul` | n-ary uninterrupted chain | 60 |
| `/` | `div` | left binary | 60 |
| `^` | `power` | right binary | 70 |

`a+b+c` lowers to `plus(a,b,c)`, `(a+b)+c` to `plus(plus(a,b),c)`, and `a+(b+c)`
to `plus(a,plus(b,c))`. No algebraic associativity follows. Mixed following
operators of the same precedence require parentheses. A newline after an
operator continues its operand; a newline before one ends the root. No arithmetic
is evaluated. Documents cannot configure operators or choose weaker limits.
The old private pack's `+` target remains `"+"`; it is not silently changed.

## Working/1

A collection is an ordered native document of top-level records:
`record(ID,Kind,Payload,optionalNamedFields...)`. IDs are unique nonempty leaves.
Kinds are open symbol leaves; payloads and extension fields are open structured
expressions. Suggested kinds are not a universal ontology. Textual status and
evidence links do not certify truth, proof, reliability or permission.

Standard optional fields: `status` is a symbol; `dependsOn` and `supersedes` are
plain positional tuples of references; `scope` and `evidence` are plain positional
tuples of expressions; `reason` is an expression. A missing field stays absent.
A stricter consumer contract can restrict vocabulary. Contradictions and cycles
may coexist. Supersession never deletes a record automatically.

The host supplies a nonempty collection identity. References are local to it;
there are no implicit network or cross-file resolutions. Build an immutable index
per snapshot. Every explicit reference anywhere in a record must resolve,
including extension fields. Matching text/symbols are not references. Forward
references and cycles are allowed; duplicate IDs and dangling references fail.

Selection starts with explicit IDs and closes over every reachable reference.
It returns whole records in original order, each once, keeping all payload scope
and qualifications. It includes collection/profile identity, original document
digest, requested and selected IDs, reasons and complete status. Missing targets,
unresolved references or exhausted bounds fail instead of returning truncated
success. This is closure over declared edges, not semantic-search completeness.

Review impact is separate: a changed record and every transitive reverse
`dependsOn` dependent need review. General citations are not dependency edges.
Neither operation infers facts or mutates knowledge.

## Consumer boundaries

Selection follows references from the requested record. It does not search for
records that point to that record. Thus, selecting an old record does not find a
newer record that supersedes it. A consumer must define how to resolve competing
replacements, cycles, approval and scope. The generic profile permits these data;
it does not decide which record is effective. Review uses only `dependsOn` edges,
not citations or `supersedes` edges.

A valid field value such as `status: completed` is not proof of completion. A
consumer must check its required evidence and authorization. A record that names
a successful test is not an authenticated execution receipt. The host must check
trusted receipts when that distinction matters.

Choose a transport after selecting complete context. A native collection can fit
its limits while its full notation spelling does not. A small selection may fit;
a selection that needs the whole collection may still fail. Keep that failure
explicit. Do not drop context, raise limits or switch encodings without the
caller's explicit choice. Closure depends on declared links, not on an automatic
judgment of which information is sufficient for a task.

## Guarded changes

`scir-change/1` is a JSON tool request with `version`, `collection`,
`expected_snapshot` and `operations`. Unknown fields, duplicate JSON keys,
malformed operations and conflicting writes fail. Term-valued entries use exact
canonical native SCIR strings, never implicitly selected notation.

Operations:
- `createRecord` with `record`: add a complete record whose ID is absent.
- `replacePayload` with `id`, `value`: replace the existing payload.
- `setField` with `id`, `field`, `value`: add/replace an optional field.
- `removeField` with `id`, `field`: remove an existing optional field.
- `deleteRecord` with `id`: remove a record only if the final collection validates.

IDs/kinds cannot be changed through fields. Creation/deletion conflicts with other
writes to the same ID. Repeated writes to the same payload/field fail. Creation
of mutually referring records in a batch is permitted if the final state validates.
Survivors retain order and unmodified values; creates append in operation order.

The expected full-document content digest and collection identity must match.
Candidate construction is pure and all-or-nothing. Validate the final whole
collection before returning its old/new digests and operations. No operation
writes input files. In-place persistence is outside this release: a host must
atomically enforce its precondition at commit. Content hashes do not detect
A-to-B-to-A histories; a store needing that property supplies its own revision.
An unrelated document change also invalidates this conservative snapshot guard.

## Source ownership

Native `.scir` can be the maintained canonical content. `.scix` can be authored
notation lowered for checking. A content-level change never silently rewrites
notation definitions or guesses between changing a definition and one use.
Printing preserves core structure when re-lowered, not source bytes, aliases or
comments. Source-map rewriting, Markdown migration and generated human summaries
are separate work, not promises of these APIs.

## Bounds and failure

Existing native bounds remain unchanged. Notation starts with 64,000 source
UTF-8 bytes, 16,000 tokens, 8,000 expanded occurrences, depth 64, 256,000 expanded
canonical bytes and 128 declarations. Ground expansion is preflighted before
serialization. All public new operations have explicit aggregate limits.
Bound failures mean incomplete work, not a truncated acceptance report.

## Verification

Preserve native goldens and generated specification views. Add independent
positive/negative vectors for tags, nesting, roles, bindings and combinations.
Check deterministic lowering, exact print roundtrip, lexical noncapture, closure
extensivity/idempotence/minimality, cycle termination, stale change rejection,
whole-candidate validation and unchanged unrelated records. Any proof model must
state its relation to (and limitations relative to) the Python implementation.

Use small commits with tests. Existing tests, properties, examples, specification
freshness, packaging and exact-head CI gate merges. Do not change expected values
to hide regressions. The completed implementation sequence is recorded in the
[change history](../CHANGELOG.md). Passing checks does not publish a release or
authorize a production knowledge migration.

The retained private feature study supports this bounded scope, not universal
optimality or improved agent behavior. Measure payloads and tool envelopes
separately; independent model trials remain a separate evidence gate.
