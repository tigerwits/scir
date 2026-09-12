# The SCIR algebra

Non-normative explanation of [SPEC.md](../SPEC.md). SCIR uses a conventional
ordered-tree algebra, not a new logic calculus.

## Terms and documents

For a symbol alphabet S:

```text
T = μX. S × List(X)
D = List(T)
```

T contains finite ordered labelled trees; D contains ordered forests. Labels do
not prescribe arity. A ranked signature can equivalently use `(label, arity)`.
Leaves need no separate constructor.

Every operation `k : S × List(A) → A` induces a unique fold:

```text
fold_k(Term(s, children)) = k(s, map(fold_k, children))
```

Recursion on finite trees establishes existence; induction establishes uniqueness.
Node count and depth are examples. This motivates direct algorithms, not a visitor
framework. Documents form a monoid under concatenation, with the empty document
as identity. Presentation order implies no time, causality, or execution order.

Core equality is structural. `not(not(P))` differs from `P`; wrapping each in
`quote(...)` preserves that distinction. Logical equivalence does not justify
substitution through arbitrary uninterpreted heads.

## Matching

Patterns add captures and a wildcard. A substitution maps capture names to ground
Terms. Matching compares labels, arities, and corresponding children. The first
capture occurrence records a subtree; later occurrences must equal it. A wildcard
discards its subtree. No subject-variable solving or backtracking occurs.

For wildcard-free P:

```text
match(P, t) = σ  ⇒  instantiate(P, σ) = t
```

Invariant: processed constructors agree, and each processed capture equals its
environment entry. Recording/comparison preserves it at captures; matching
children preserves it at labelled nodes. Instantiation therefore reconstructs t.

Conversely, `instantiate(P, τ) = t` implies a match with τ restricted to P's
captures. Induction verifies constructors and repeated captures. This minimal
binding is unique, though unused environment entries may vary. Wildcards still
match deterministically but cannot be instantiated, so the reconstruction law
excludes them. These are algorithmic arguments, not machine-checked Python proofs.

## Values, occurrences, and referents

Equal values can occupy different paths and describe one event or several. Neither
tree equality nor DAG sharing determines real-world identity. SCIR uses a forest
with snapshot-local paths; discourse identifiers belong to application vocabulary.

Roots are presented content, not facts. In `think(Bob, use(Alice, Data))`, a nested
query finds `use(...)` without establishing that it happened. Root-only queries
also find questions and commands; they are not fact extractors.

## Transport law

Assign fresh preorder IDs to occurrences; record labels, child positions, and root
positions. Leaves have nodes too. A valid forest has one parent per nonroot, none
for roots, and no cycles or unreachable nodes: `|edges| = |nodes| - |roots|`.

```text
decode(encode(D)) = D
```

A leaf reconstructs from its label. By induction, reconstructed children and
contiguous positions reconstruct each parent. Ordered roots then reconstruct D,
including duplicates. Row permutations and bijective ID renamings preserve this
result. Re-encoding chooses canonical IDs and row order, not the original JSON bytes.

## Metadata and ambiguity

`erase(Bundle(D, M)) = D` is a content projection. It deliberately loses provenance
and says nothing about reliability. Fingerprints identify canonical content, not
a unique historical instance: independently created equal documents share a digest.

Alternatives preserve whole candidate documents. Unresolved interpretation cannot
be erased as decoration on an already chosen reading. Whole-document candidates
also preserve correlated choices: selecting “she” and “her own” independently could
invent crossed readings. Selection is explicit, not a truth judgment.

## Dialects as subsets

Let U = List(T). A dialect is an admissible subset of U; it changes neither T nor
its representation. A policy is a predicate on U, but not every mathematical
predicate has a computable terminating checker.

For a pure total diagnostic rule:

```text
c : U -> List(Violation)
A(c) = {d in U | c(d) = []}
check(d, [c1, ..., ck]) = c1(d) ++ ... ++ ck(d)
A(C) = intersection {A(c) | c in C}
```

Concatenated finite lists are empty exactly when every constituent is empty. Thus:

```text
A([]) = U
A(C ++ E) = A(C) intersection A(E)
A(C ++ E) subseteq A(C)
A(C ++ C) = A(C)
```

Acceptance ignores rule order and duplicates; diagnostic concatenation does not.
Conflicting constraints may accept nothing. The API does not decide satisfiability
or inclusion for arbitrary Python-defined dialects.

A forms rule requires each selected occurrence to belong to the union of supplied
pattern languages. Empty selections pass vacuously; presence is a separate predicate.
Captures are local to matches. Reference consistency needs a document-level rule,
such as a two-pass declaration index.

The reference checker is partial: input bounds, callback failures/nontermination,
and diagnostic limits can prevent completion. The concatenation law applies when
checks complete within limits. Incomplete is neither acceptance nor a completed
rejection report; it must not become a truncated result presented as complete.
Bounds restrict the supported domain, not the mathematical universe U.

With external context x, define `c(d, x)` and `A(C, x)` for fixed x. Changed database
snapshots are different inputs, not a determinism counterexample. Validation
records need contract, checker, and context identity as well as a content digest.
Checking is not part of canonical content or its fingerprint.

Exact transport preserves diagnostics for pure document-local rules by substitution
of equal inputs. Acceptance is not generally preserved by concatenation (IDs may
collide), extraction (declarations may be lost), or editing. Revalidate unless an
application proves a preservation law.

Conformance establishes an acceptance contract, not source fidelity or truth.
Several interpretation candidates—or none—may conform. A failed dialect check
leaves valid generic SCIR. [Dialects](dialects.md) specifies the optional API.

## Dialect refinement chains

For a fixed context, accumulate rules: `C0 = []`, `C(i+1) = Ci ++ Ei`.
The acceptance law gives `A(C(i+1)) ⊆ A(Ci)`. These are nested subsets of the same
SCIR universe, not successively larger languages. A contract added later must not
require syntax or vocabulary forbidden by an earlier rule. The
[worked chain](../examples/dialect-chain/README.md) permits later record/reference
forms before requiring them.

The document sequence is different: `d0 -> d1 -> ...`, with `di ∈ A(Ci)`.
Subset inclusion does not construct a translation, guarantee one exists, or make
one unique. The identity inclusion already accepts a later document under earlier
rules; a restructuring projection is a separate, optional operation.

Let `F(s)` be documents judged faithful to a fixed source s under stated
interpretation conventions. A refinement needs membership in both
`A(Ci)` and `F(s)`. The intersection may be empty although `A(Ci)` is not: a contract
requiring a timeout value may admit many documents while none preserve a source
that leaves that policy unspecified. The checker does not decide general fidelity
or satisfiability. In the example, a reviewed oracle exposes this particular gap.

Some transitions admit partial projections `pi: A(C(i+1)) -> A(Ci)`. Checking
`pi(d(i+1)) = di` establishes exact reconstruction of that earlier tree view.
Composed projections reconstruct earlier views by substitution of equalities.
This is not an inverse to a general interpretation step or proof of source fidelity.
The example's inlining projection needs unique, resolved, acyclic, used condition
declarations; it rejects inputs where removing declarations could hide content.

For fixed pure total rules, `A(C ++ E) = A(E ++ C)`. The diagnostic order can differ,
and agent translation order may affect the chosen documents and costs. Equality of
accepted sets does not imply equal translations, convergence, or confluence.
Measure those separately. Repeated checking, more constraints, and more model calls
are not interchangeable experimental treatments.

## Working knowledge and authored prose

A project may maintain a SCIR document K and independently authored Markdown M.
There need not be a rendering function with M = R(K). The writer chooses emphasis,
explanation, examples, and audience. K may retain much more working detail than M
shows, including assumptions, explicit argument steps, and unresolved questions.
Neither syntax nor a source citation proves that M faithfully describes K.

Ownership is per commitment, not per extension. Before migration, selected source
text is authoritative. A reviewed migration transfers particular commitments into
K; the original becomes historical evidence. New information in either artifact
needs deliberate reconciliation. Layout or voice edits in M need not change K.
A source hash detects changed bytes, not changed meaning or correct translation.

The [knowledge examples](../examples/knowledge/README.md) implement only declared
review-dependency reasoning. For record IDs V, edges E = {(x, y) | x depends on y},
and changed records C, start I0 = C and iterate:

```text
I(n+1) = In union {x | (x, y) in E and y in In}
```

On this finite graph the sequence stabilizes at its least fixed point. The closure
is extensive, monotone, and idempotent. Cycles do not prevent termination. Output
lists IDs in document order; derived review candidates are not inserted into K.
These are consequences of the declared review rule, not claims that the content
is false, that all semantic dependencies were declared, or that a mathematical
argument has been proved. Other deterministic reasoning needs explicit domain
rules; the SCIR query operation alone does not supply them.

## Maintained content and document views

When exact repetition is useful, a project may choose generated sections instead.
Let K be its document accepted by the content dialect. A deterministic
view is a function `R_i(K)` over selected records. The Markdown section `M_i` is
fresh exactly when `M_i = R_i(K)` byte for byte, within its marked boundary.
Rendering copies or arranges authored fields; it does not infer their meaning.

Selection is recomputed from K, not from a cached list of previously displayed
IDs. A newly selected record can therefore make a view stale. A change to unrelated
content need not affect it. Requirements, wording, examples, and relationships
remain queryable without rendering any prose.

Generated views may omit content: equality of two views does not imply equality
of their sources. An edit to a generated section has no unique automatic inverse. Apply
an intended revision to its source records, validate it, then render again. A
model-written explanation is a different, interpretive operation; source references
alone do not establish that it is faithful.

The [project catalog](../spec/README.md) implements this for query/occurrence
behavior. It owns exact wording and examples, not only pointers to Markdown.
The specification is the readable contract and the API guide adds usage views.
Other topics remain explicitly indexed rather than migrated. No kernel extension
or universal ontology is needed for this division of ownership.

Source and test links use a fixed checkout as context. A renamed method can
invalidate a link. `coveredBy` is a declared dependency, not proof of coverage.
Executing stored examples checks their expected query paths. Independent tests
and review are still required: a statement, example, and rendered page can agree
while all embodying the same mistake. View freshness proves synchronization,
not truth, completeness, or correct implementation.

## Cost and boundaries

Let n count occurrences, h be maximum depth, L serialized length, and P the sum
of path lengths. Materializing paths costs O(P), where P ≤ n(h + 1). Recursive
printing may copy intermediate strings, giving O(Lh). Relational reconstruction
uses contiguous-position lookup: linear under constant-time dictionary assumptions.
Queries scan candidates and incur matching and captured-subtree equality costs;
there is no index or unconditional linear-query guarantee.

Direct Python construction can exceed parser bounds. Recursive printing, equality,
and instantiation are not stack-safe for arbitrary deep or reflected objects.
The [specified bounds](../SPEC.md#reference-implementation-bounds) are not a sandbox.

Induction arguments and finite law tests do not prove the Python implementation
correct for all inputs. Nor do they show that translation costs are outweighed
by better agent handoffs. That requires the [research evaluation](research/README.md).
