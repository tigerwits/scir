# SCIR kernel study

## Recommendation and evidence level

Adopt one immutable content constructor and an ordered document forest.
Separate patterns, occurrence metadata, unresolved interpretation choices,
templates, and logical profiles. The code implements this boundary; it does
not prove that SCIR improves a model's reasoning or that any English-to-SCIR
translation is faithful.

Baseline reviewed: `295da13366921358f7f76f7b9c45d06c06d63136`.
All seven implementation files and four test files were reconstructed from
connector-returned source and verified against their Git blob SHA-1 values
before execution. All 34 original tests passed. The README, specification and
package metadata were also inspected. Container Git access could not resolve
github.com, so repository reads and writes use the authenticated connector;
local tests operate on the verified snapshot rather than a successful clone.

The original program implements its stated policy reasonably. Rejecting
strings, multiple roots, or trailing commas was intentional, not a parser
bug. Conjunction descent and Boolean rewriting were documented decisions.
The proposed revision changes those policies; it should not disguise a
breaking redesign as a bug fix.

## 1. The algebra, exactly

For a set S of symbols, let F(X) = S × List(X). The least fixed point

    T = μX. S × List(X)

contains finite rooted ordered S-labelled trees. Root arity is not prescribed
by the label: the same string can label zero or more children. These are
unranked trees. Equivalently, use the ranked signature whose operation
symbols are pairs (s,n), with arity n. Calling this a ground term algebra is
then precise; it is not a new logical calculus.

Documents are D = List(T). Concatenation and the empty document form a monoid.
This preserves multiplicity and presentation order without interpreting that
order as temporal order, execution order, conjunction, or causality.

The initial-algebra characterization supplies a useful implementation law.
For any operation k : S × List(A) -> A there is one fold satisfying

    fold_k(node(s, children)) = k(s, map(fold_k, children)).

Existence follows by structural recursion; uniqueness follows by induction
on the tree. Node counts, depth, serialization and many visitors are folds.
That is the practical benefit of this formulation. No extra category-theory
machinery is required in the runtime.

### Structural equality is all the kernel supplies

    node(s, xs) = node(t, ys)

exactly when s=t and the ordered child lists are equal. There are no equations
for ordinary vocabulary or logical-looking vocabulary in Core.

`Alice` and `Alice()` are one leaf, not two constructors. Input accepts both;
canonical output uses the shorter spelling. Rejecting empty parentheses is
not necessary to obtain the one-constructor algebra and creates avoidable
formatting failures. This explicitly rejects the brief's tentative suggestion
to make `Alice()` invalid.

The symbol alphabet is nonempty Unicode-scalar strings. Quoting is lexical
escaping of that same alphabet, not a second String constructor. Distinguish
content roles through explicit application vocabulary, for example
`text(Alice)` versus `Alice`; do not expect quote marks alone to supply it.
A numeral-like symbol is not a number with arithmetic semantics.

## 2. Patterns and matching

Conceptually:

    P = Capture(V) + Wildcard + S × List(P)

The reference representation uses Node and Var, reserving Var("_") for the
wildcard. Ground Term children cannot be either pattern constructor.

A substitution is a finite partial map V -> T. Instantiation is simultaneous
replacement of capture leaves. There are no object-language binders,
quantifiers, or capture-avoiding renaming rules hidden in this operation.

The matcher walks corresponding pattern/subject positions. A node requires
equal label and arity. A first capture records the current subject subtree;
a repeated capture compares it structurally with the recorded subtree.
Wildcards skip a subtree. A mismatch fails the entire match. There is no
backtracking or symmetric solving of subject variables: the subject is ground.

### Soundness

For a wildcard-free P, if match(P,t)=σ, then instantiate(P,σ)=t.
Proof: induction on P. A capture records t or checks it against the prior
binding; either way σ assigns t. At a labelled node, labels and arities agree
and the induction hypothesis applies to each child. Reconstructing the
children gives t. In worklist form the invariant is that every processed
capture occurrence agrees with its environment entry, and every processed
noncapture constructor agrees with the corresponding subject constructor.

### Completeness and uniqueness on used variables

If instantiate(P,τ)=t for a wildcard-free P and τ is defined on all captures,
the same constructor checks succeed and match returns σ agreeing with τ on
FV(P). Induction proves this in the same cases. The minimal successful map
has domain exactly FV(P), so it is unique. Arbitrary maps containing unrelated
extra variables are not globally unique; that stronger claim would be false.

For patterns with wildcards, matching still succeeds/fails deterministically,
but instantiating the result is intentionally undefined. A wildcard forgot
content. Our round-trip property does not pretend otherwise.

These are mathematical proof arguments, supported by executable examples
and generated checks. They are not a Lean certificate of the Python code.

## 3. Roots, facts and scope

The safest API name is `roots`, not `asserted facts`. Consider

    past(give(Alice, Bob, Report))

The source English may assert a giving event. The only stored root is the
whole past(...) term. Conversely, `think(Bob, give(...))` must not make that
event factual merely because a matching subtree exists. A structural engine
cannot distinguish veridical, factive, conditional and belief contexts while
also claiming not to know ordinary vocabulary.

Therefore roots/all are syntactic scopes. Profiles or a model may interpret
those scopes later, with explicit dependencies. The initial prototype's
conjunction descent was a useful inference policy, but it was not the same
operation as reading literal document roots.

This correction also applies to the earlier proposed sentence 'a document
asserts exactly its roots.' Core presents roots. The communicative act and
truth conditions are outside it. Implementation requests, questions and
hypotheses need not be reified as factual assertions.

## 4. Values, occurrences, referents

Three different equalities must not be merged:

1. Same tree value: identical labels and ordered children.
2. Same syntax occurrence: same path in the same document snapshot.
3. Same real-world referent or event: an interpretation-dependent identity.

Two copies of `call(Bob, Carol)` have equal values and distinct occurrence
paths. They might describe two calls, or repeat the same claim about one call.
The data alone does not decide. DAG sharing would not solve that either:
sharing a description is not proof that two descriptions have one referent.

V0.2 uses path occurrences, not semantic graph nodes. An explicit discourse
identifier can be encoded using an agreed local vocabulary, for example

    call(Call1, Bob, Carol)
    not(answer(Carol, Call1))

This does not add a core type, event constructor or reference evaluator.
It does require the author/consumer to agree on what Call1 and argument
positions mean. More elaborate reference profiles are future work.

A path is snapshot-local. Inserting an earlier root changes later root
indices. Snapshot fingerprints prevent silent reuse against changed trees;
they do not provide relocation across edits. Positional diff does not claim
minimum edits or cross-version event identity.

## 5. Relational encoding and its proof

For each occurrence p, assign a fresh ID in preorder. Emit its label. For a
child occurrence p.i emit an argument row (ID(p),i,ID(p.i)); roots get
(root_position,ID(root)). Leaves are nodes too. No IDs and symbol strings are
mixed in the child column, unlike the earlier informal relational sketch.

The valid transport invariant is an ordered forest: unique IDs, contiguous
root/child positions, one parent for each nonroot, no parent for roots, no
cycles, no unreachable nodes. In particular |edges|=|nodes|-|roots|.

### decode(encode(D)) = D

For a leaf, encoding records its symbol and no children, and decoding creates
that leaf. Inductively every child occurrence decodes to its original child;
contiguous positions reconstruct the same ordered argument tuple. The same
argument applied to ordered roots reconstructs D, including duplicates.
Fresh IDs are irrelevant to this result.

A bijective relabelling of IDs or permutation of row arrays preserves the
relation and therefore decoding. In the other direction encode(decode(R))
chooses canonical preorder IDs; only equality up to this renaming and row
permutation is warranted, not byte equality with arbitrary R.

The decoder validates the preconditions instead of assuming trusted input.
Sharing is rejected because this transport represents occurrences. A compact
value-DAG transport could be added later, but it would need separate
occurrence/provenance semantics and an explicit unsharing boundary.

## 6. Annotations versus ambiguity

Annotations are attached to (content fingerprint,path). A Bundle carries an
unchanged Document plus annotation records. Erasure projects the Document.
Its equality law follows from that representation; it is not a deep theorem
about the truth of metadata.

Crucially, erasure does not preserve evidence, reliability or authority. A
consumer requiring provenance must consume a Bundle, not accept bare content
as an equivalent object. No annotation such as confidence=0.7 is calibrated
or justified merely by being machine-readable.

Ambiguity is not just dispensable decoration. Removing a candidates note
from a chosen tree can silently turn an unresolved reading into a committed
one. V0.2 instead experiments with `Alternatives(tuple[Document, ...])`.
It cannot pass as a Document. Selection is explicit and indexed; no generic
annotation erasure selects or flattens it.

Whole-document alternatives also preserve correlated choices. In 'She
revised her own report', independently choosing an actor and report owner
can introduce mixed readings that the source excludes. A packed choice DAG
may eventually compress shared structure, but it needs correlation IDs and
is not justified merely to save a few nodes in the first implementation.
Local holes and existential semantics remain unimplemented rather than being
smuggled in as query metavariables.

## 7. Templates, not a programming language

Definition parameters are pattern captures; a body is a Pattern. Expansion
substitutes already expanded actual arguments and recursively expands known
macro heads. Bare symbols matching a parameter name remain constants.
Definitions themselves emit no root. There is no implicit assertion on
binding and no global '=' meaning that conflates equality, aliasing and event
identity. Surface `def` and assignment are deferred; the programmatic layer
lets us study substitution without committing to a statement grammar.

Termination of unrestricted expansion is not assumed. The prototype rejects
cycles in the definition dependency graph. A topological rank exists; each
body mentions only lower-ranked macros, while substituted actual arguments
are already macro-free. Structural descent plus decreasing macro rank gives
termination for finite inputs. Acyclic expansion can still grow exponentially
by duplication, so a work budget and depth guard are enforced.

Determinism is a specified traversal and substitution order, not a claim that
an arbitrary user rewrite system is confluent. There are no overlapping
pattern rewrite rules in this macro engine. Scope-changing or semantic edits
must be explicit caller choices.

## 8. Why Boolean normalization is optional and opaque

In the free algebra, `quote(not(not(P)))` and `quote(P)` are different terms.
For an uninterpreted `quote`, a model can distinguish their exact structure.
A Boolean equivalence for the inner expression alone does not justify
substitution through arbitrary ordinary heads.

The new Boolean profile recurses only through its own logical constructors
and treats every other subtree as an opaque propositional atom. Double
negation and associative flattening then preserve Boolean interpretation
under any valuation of those opaque atoms. It retains argument order,
performs no synonym rewrites and never rewrites inside `think`, `say`, or
`quote`. Invalid logical arities are errors only when that profile is chosen.

Termination: each actual rewrite removes constructor nodes, and recursion
visits a finite tree. Idempotence: bottom-up normalization leaves neither
adjacent not nodes nor same-headed logical children to flatten. An ordinary
subtree is unchanged on every pass. Generated truth-table checks exercise
these properties; no global canonical Boolean equivalence class is claimed.
`if` has a propositional interpretation only in this explicit profile, not
as a faithful formalization of all natural-language conditionals.

## 9. Complexity and implementation limits

Let n be node occurrences, h maximum depth, L serialized length, and
P=sum of occurrence path lengths. Parser tokenization and tree construction
are linear in input length plus produced nodes for this grammar. Paths copy
prefixes, so walking with materialized paths and relational encoding use
O(P), not unconditionally O(n); P <= n(h+1). The reference depth cap is 128.

Canonical recursive string construction can copy subtree strings, giving an
O(Lh) upper bound rather than an unconditional linear guarantee. Record
decoding additionally sorts positional keys: its ordering work is bounded
by O(n log n), plus reconstruction. A query scans occurrences and repeats
structural matching; total work includes repeated captured-subtree equality
checks. There is no index yet and no universal linear-query claim.

These bounds and caps are preferable to hiding Python recursion limits.
Deep/wide shape experiments and warm-process timings are recorded separately.
Constructor validation is for normal immutable Python values, not a secure
sandbox against reflection. Content MUST NOT be evaluated as Python.

Python's built-in string/tuple/dataclass hashes are not stable persistent
identifiers across runs. The new explicit SHA-256 fingerprint uses a versioned
canonical byte string. Equal bytes yield equal fingerprints; cryptographic
collision resistance is not an injectivity proof. See reference [2].

## 10. Decisions against the fifteen review questions

| Question | Decision and consequence |
|---|---|
| Atom / Variable / Call? | Replace content with Term; keep query constructors separate. |
| Is an atom zero arity? | Yes. One structural value. |
| Variables only in patterns? | Yes for captures; unresolved interpretations use a separate envelope. |
| Reject Alice()? | No. Accept as an alias and print Alice. |
| Multiple roots? | Yes, ordered and duplicate-preserving. |
| asserted vs inference? | Remove asserted; explicit roots/all scopes. Neither is a semantic fact extractor. |
| Logical heads in Core? | No; optional Boolean profile only. |
| Normalization in v0? | Syntax formatting only by default; explicit restricted logical derived view. |
| Paths or DAG IDs? | Snapshot paths for occurrences; forest transport. No inferred event identity. |
| Core bindings? | No. Macros may share physical values, not occurrence identity. |
| def as substitution? | Prototype API-only acyclic definitions; defer surface def/assignment. |
| Ambiguity? | Separate candidate-document envelope; no accidental existential/query-variable semantics. |
| Annotation targeting? | Fingerprint + path, stale targets rejected; relocation deferred. |
| Literals? | Quoted labels remain symbols; JSON metadata supports actual numerical values. |
| One immutable recursive content datatype? | Yes, with runtime checks against pattern children and mutable child lists. |

## 11. Proof status and remaining research

The induction arguments above establish properties of the specified
mathematical algorithms. The Python implementation is exercised by unit,
generated, and adversarial tests. This is not full refinement verification.

No Lean binary or configured remote Lean service was available here, and a
toolchain download could not be completed. No uncompiled `.lean` files or
axiom-based 'proofs' are presented as checked deliverables. A useful next
formal slice is a wildcard-free matcher with environment-extension soundness
and completeness, followed by the occurrence codec. Parser refinement and
Python equivalence would still remain distinct obligations. Reference [3]
describes the inductive-type/recursion machinery appropriate for that work.

The decisive empirical question remains whether the neural translation cost
and errors are outweighed by better handoff/query reliability. A standard
ordered-tree algebra alone cannot establish that benefit. Keep a source
ledger, explicit profiles and controlled model comparisons; do not use the
simplicity of the kernel as evidence of semantic fidelity.

## References

[1] Jurdzinski and Lazic, *Alternating Automata on Data Trees and XPath
Satisfiability*, author manuscript, 2008: https://arxiv.org/abs/0805.0330 .
Used only for the established ordered-unranked-tree terminology; SCIR does
not adopt that paper's automata or decision procedures.

[2] Python 3.13 reference, *Data model*, `__hash__` notes:
https://docs.python.org/3.13/reference/datamodel.html .
The documented process-salted string hashes explain why a separate wire
fingerprint is needed; see the independently run seed probe in evidence.

[3] *Theorem Proving in Lean 4*, Inductive Types; Induction and Recursion:
https://docs.lean-lang.org/theorem_proving_in_lean4/Inductive-Types/ and
https://docs.lean-lang.org/theorem_proving_in_lean4/induction_and_recursion.html .
These support the proposed formalization method, not a claim of execution.
