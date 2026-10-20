import Lean
import SymbolLaws
import SubstitutionLaws
import DefinitionLaws
import ProfileLaws
import OccurrenceLaws

/- SCIR LANGUAGE SPECIFICATION, native format 1.0

   This repository owns the language and its Lean specification. It is not an
   application runtime, installable content library, knowledge-store service, or
   execution engine. Realizations belong in their consuming projects. The former
   realization is preserved at 4df43ba874d6750e9ab16b21903b87e8879b601c in Git
   history; its package APIs and operational tools are retired by this migration.
   No package release or format revision is implied. Native 1.0 remains fixed.

   Authority and verification

   The clauses in this file own the native and opt-in profile contracts. Pure
   declarations and law modules formalize the specified parts.
   NativeCodec, StrictJson, Sha256, WorkingSpec and the three Reference modules
   are bounded executable specifications, used for conformance. Their success
   does not establish parser correctness, cryptographic security, source fidelity,
   application safety, operational durability, or the truth of stored content.
   Conformance checks independent fixed vectors and finite generated cases.
   AxiomAudit checks transitive assumptions of exported laws and named evaluators.
   Every new law must state its actual domain and assumptions; a finite test must
   not be reported as a universal theorem. Keep frozen expected values unchanged
   unless an independently justified specification change requires a new version.

   Content and Symbols

   A Symbol is an exact nonempty finite string of Unicode scalar values. No
   normalization, case folding, trimming, interning identity or interpretation is
   implied. Lean String/Char provide scalar strings; admission of external bytes
   is a separate obligation. The Symbol object below makes this domain explicit.
   Terms are finite ordered trees T(S) = S × List(T(S)). A symbol can occur at any
   arity, including zero. Documents are ordered lists of terms, not sets of facts.
   No symbol is reserved by the native algebra for logic, typing, execution,
   real-world identity, or named definitions. Structural equality compares the
   exact head, arity and corresponding children. Distinct paths remain distinct
   occurrences even when their values are equal or physically shared.

   A document preserves root order and duplicate roots. A nested occurrence must
   never be promoted to a root implicitly. Presentation order does not establish
   time, causation or execution. A conventional ranked signature can use the pair
   (symbol, arity), but SCIR does not globally fix a symbol's arity. Documents form
   the free list monoid of trees under ordered concatenation. Neither structural
   equality nor repeated use of a Symbol identifies real-world entities.

   Native surface grammar

   document   = newlines, [term, {separator, term}, [separator]], EOF
   separator  = newline, newlines | ";", newlines
   term       = symbol, ["(", newlines, term,
                {newlines, ",", newlines, term}, [newlines, ","], newlines, ")"]
   symbol     = identifier | json_string
   identifier = (ASCII_letter | "_"), {ASCII_letter | digit | "_"}
   newlines   = {newline}

   Space, tab, carriage return and form feed are horizontal trivia. An LF remains
   a separator; a # comment consumes through but not including its next LF.
   Inside a quoted symbol, # is data. A head and its opening parenthesis must be
   on the same source line. There is no grouping syntax. A is a leaf; A() fails.
   Nonempty applications permit trailing commas. Empty documents, blank lines and
   one trailing separator are valid. A B and A;;B fail. Parsing must consume all
   input. JSON strings decode Unicode escapes and valid surrogate pairs to scalar
   values; empty symbols, isolated surrogates and raw control characters fail.
   Quoting a symbol does not change its value: "Alice" and Alice denote the same
   leaf. A quoted label can be an applied head. Number-like symbols require quotes
   and have no numeric semantics. Imports, assignments, attributes, declarations,
   evaluation and host-language execution are absent from native SCIR.

   Canonical spelling and digest

   Print exactly ASCII identifiers bare. Quote other symbols with JSON-required
   escapes only. Use short escapes for backspace, tab, LF, form feed and CR, and
   lowercase \u00xx for other code points below U+0020. Do not escape slash or
   other scalar characters. A leaf prints as its symbol. A nonleaf prints as
   head(child, child), with one space after a comma and no other whitespace.
   Each root ends in one LF; the empty document is the empty string. Comments are
   not content. Subject to admitted bounds, parsing canonical spelling must
   reconstruct the document exactly. It need not preserve original source bytes.

   The document fingerprint is lowercase hexadecimal SHA-256 of the UTF-8 bytes
   of "scir:1.0:document\n" followed by the canonical document. The prefix and
   all canonical bytes are normative. Metadata is excluded. A digest is neither
   a historical event ID, a document-instance ID, an authentication receipt, nor
   a mathematical proof of equality. Equal content can recur after intervening
   changes. Cryptographic assumptions do not establish an application's history.

   Patterns and substitution

   Surface patterns add ?identifier in a term position. ?_ is an anonymous
   wildcard; other names capture entire subtrees. Bare _ and quoted "?x" remain
   ordinary symbols. Captures cannot be heads or have arguments. Ground parsers
   reject captures. Matching is one-way against a ground term: heads and arities
   agree, children match in order, repeated captures require structural equality,
   and a wildcard succeeds without creating a binding. Failure differs from a
   successful empty binding map. No unification or backtracking is specified.

   Instantiation simultaneously replaces named captures with ground terms.
   Missing bindings and any wildcard are errors; unused bindings are ignored.
   Open substitution simultaneously replaces named variables with open patterns;
   missing bindings act as identity, inserted expressions are not revisited, and
   wildcard syntax is excluded from the substitution domain and range. There are
   no binding constructs, so no alpha-renaming or capture avoidance is required
   for this open algebra. A future binder extension would need its own rules.
   SubstitutionLaws proves identity, composition, its independent structural
   relation, and successful-match reconstruction under the stated domains. It
   does not prove the native pattern parser or general matcher completeness.

   Relabeling is a distinct operation S → R on every head, simultaneously. It
   preserves arities, order, occurrence paths and multiplicities. SymbolLaws proves
   this naturality law and identity/composition. Relabeling can change profile
   tags, literal text, reference IDs and field names; native validity does not
   imply profile validity. A Symbol→Term replacement requires an extra policy
   such as grafting or an arity-aware context. The Symbol object alone does not
   choose operator-replacement semantics, imply a macro reference, or establish
   algebraic equivalence under arbitrary heads.

   Occurrences, replacement, query and diff

   A path contains a root index followed by zero or more child indices, all
   natural numbers. It is local to one document snapshot. Walking enumerates
   roots in order and each tree in depth-first preorder. Query defaults to roots;
   explicit all-occurrence scope includes nested occurrences. A result preserves
   the path, matched term and bindings, in traversal order, including duplicate
   occurrences. Neither scope computes logical consequences.

   OccurrenceLaws proves that executable path lookup finds exactly the enumerated
   labels, traversal paths are strictly lexicographically ordered and unique,
   and appending roots preserves the old traversal with precisely offset new
   paths. These laws concern the native ordered forest, including repeated equal
   trees. They do not prescribe application chronology or memory grouping.

   A targeted replacement changes one existing occurrence, retains unrelated
   occurrences, does not traverse its inserted replacement and does not relocate
   metadata. Positional diff descends only while heads and arities agree, otherwise
   reports the changed frontier. Missing roots are represented separately. This
   is not minimum-edit alignment or semantic comparison.

   Relational transport

   A JSON envelope has exactly version, nodes, args and roots. version is
   "scir-relations/1.0". nodes contains [id, symbol]; args contains
   [parent_id, position, child_id]; roots contains [position, node_id]. Every
   occurrence, including leaves and duplicates, has its own node. The canonical
   encoder assigns preorder IDs from zero and never deduplicates occurrences.
   Explicit positions determine order, independent of row order and ID magnitude.

   Reject duplicate JSON keys at reading; unknown envelope keys or versions;
   duplicate IDs; invalid symbols; unknown endpoints; noninteger or negative IDs
   or positions; duplicate or noncontiguous positions; duplicate roots; sharing;
   cycles; and unreachable nodes. Roots have no incoming edge; other occurrences
   have exactly one. Positions start at zero. Permuting rows and bijectively
   renaming IDs preserve decoding. Re-encoding chooses canonical IDs and row
   order. decode(encode(document)) reconstructs the original ordered forest.
   NativeCodec specifies this general boundary. ReferenceCodec is deliberately
   narrower test plumbing requiring canonical tables for the historical corpora;
   its extra restriction is not a language restriction.

   External annotations and alternatives

   An annotation is (snapshot, path, key, value_json). Its key is a nonempty scalar
   string, snapshot is the document fingerprint, and its path must exist in that
   snapshot. Stale fingerprints and invalid targets fail; edits do not silently
   relocate annotations. Metadata consists of finite JSON scalars, objects with
   string keys and arrays, with scalar strings and finite numbers. Non-string
   object keys must not be coerced. A host can keep immutable canonical metadata
   with sorted keys and no insignificant spaces, but no additional cross-language
   metadata fingerprint is standardized here. Historical host-specific payload
   encodings are not native language bytes. Erasure projects the chosen document
   and loses metadata and provenance. It says nothing about evidence reliability.

   Alternatives hold at least two whole candidate documents. They must not be
   concatenated as roots or interpreted as logical disjunction. Selection is an
   explicit indexed choice. The candidates need not be exhaustive; selecting one
   does not establish correctness. Unresolved interpretations are not removable
   decorations on an already selected document. No surface ambiguity/hole syntax
   is introduced by this structure.

   Opt-in dialects and structured/1

   A dialect restricts admissible documents without changing Term, native grammar,
   canonical bytes, digest or transport. Native validity does not imply dialect
   conformance. A label cannot select or bypass the caller's required dialect.
   A failed or incomplete check must not report conformance, rewrite input, or
   promote nested occurrences. An arbitrary predicate need not have a terminating
   decision procedure. Intersecting dialect predicates only restricts admission.

   structured/1 explicitly selects four ordinary native tags: scir.tuple,
   scir.kw, scir.text and scir.ref. They cannot simultaneously denote unrelated
   constructors inside that profile; quoting is not an escape from profile rules.
   A tuple preserves ordered positional children, including zero or one child.
   Text has zero children for empty text or one literal leaf. A reference has one
   literal leaf containing its nonempty ID. Literal text/reference payload leaves
   are opaque, even when their spelling equals a profile tag. Alice, text(Alice)
   and ref(Alice) have distinct native structure. No text normalization occurs.

   A keyword container is nonempty and can only be the final child of an ordinary
   application or tuple. Its entries have nonempty unique keys and exactly one
   value. Keys are sorted by UTF-8 bytes. Readers reject malformed/noncanonical
   containers rather than repair them. Field labels are literal names, not
   expression heads or alias targets. Field values are expressions; an unattached
   keyword container is invalid. Missing fields remain absent. An application
   without named fields gets no wrapper. Named and positional role-like values
   remain structurally distinct; constructors do not unpack tuples or add defaults.

   notation/1 and arithmetic/1: retained optional authoring contracts

   These languages lower to native terms; their executable lowering is outside
   the current Lean conformance coverage. They are never auto-selected by a file
   name or a native tag. (a) groups, () is an empty tuple, (a,) is a singleton,
   and (a,b) a pair. f(a,b) differs from f((a,b)); f(a,) is f(a), while f() fails.
   Tuples may have named roles. Named arguments follow positional ones and reject
   duplicates even when values agree; lowering sorts names by UTF-8 bytes. Heads
   remain literal symbols, so $op(a), f(a)(b), compose(f,g)(x) are rejected.
   t immediately followed by a JSON string constructs text; &name or &"id"
   constructs a reference. Dotted names are single symbols. Numeric-looking
   labels preserve spelling without evaluation. Root separators, comments, full
   consumption and head/parenthesis attachment follow the native conventions.
   Unsupported imports, lambdas, braces, patterns and assignments fail.

   @using K = Qualified.prefix replaces subsequent unquoted qualified prefixes,
   not bare K, quoted labels, field names, references or fixed operator targets.
   Targets resolve immediately. @let x = expression stores one resolved value;
   $x substitutes one expression and never spreads a tuple or becomes an operator.
   Alias and value namespaces are separate; duplicate declarations within either
   fail. Forward/unbound self references and parameterized definitions fail.
   Each document starts with fresh environments. Declarations emit no roots;
   later aliases cannot capture stored values. Each expansion occurrence counts
   separately. Printing does not recover declarations, aliases or comments.

   arithmetic/1 is separately enabled: + lowers an uninterrupted n-ary chain to
   plus at precedence 50; binary - is left associative sub at 50; prefix - is neg
   at 65; * is n-ary mul at 60; / is left binary div at 60; ^ is right binary
   power at 70. Parentheses retain nested grouping. Mixed following operators
   with equal precedence require parentheses. A newline after an operator
   continues its operand; a newline before it ends the root. No arithmetic is
   evaluated and documents cannot redefine this table or weaken caller limits.

   working/1

   A collection is an ordered native document of record(ID, Kind, Payload,
   optionalNamedFields...). IDs are unique nonempty ordinary leaves. Kinds are
   open ordinary leaves; payload and extension fields are structured expressions.
   These suggestions do not define a universal ontology. status is an ordinary
   leaf; dependsOn and supersedes are plain positional tuples of references;
   scope and evidence are plain positional tuples of expressions; reason is an
   expression. Optional fields cannot override ID, kind or payload slots.
   The host supplies a nonempty collection identity. Every explicit reference
   anywhere in every record resolves locally, including extension fields. Text
   and matching bare symbols are not references. Forward references and cycles
   are allowed; duplicate IDs and unresolved references fail. Contradictions
   coexist. Supersession does not delete a record or determine which is effective.

   Selection starts at explicit IDs and closes over reachable references. Return
   whole records, once each, in original order, retaining all qualifications and
   scope. The observation identifies collection/profile, source document digest,
   requested/selected IDs, reasons and completion. Missing targets, unresolved
   references and exhausted bounds fail rather than truncate success. This is
   declared-edge closure, not semantic-search completeness. Reverse dependsOn
   closure specifies review impact separately; citations and supersedes are not
   review edges. Selecting an old record does not search for records superseding
   it. Text saying completed or approved is not proof or authority. Contradiction,
   cyclic replacements, approval, privacy and effective-record policy belong to
   the consuming application.

   scir-change/1: retained guarded request contract

   The tool-request JSON fields are version, collection, expected_snapshot and
   operations. Unknown fields, duplicate keys, malformed/conflicting writes fail.
   Term-valued fields use exact canonical native strings, never implicit notation.
   createRecord adds a complete absent-ID record. replacePayload replaces one
   existing payload. setField adds/replaces one optional field; removeField removes
   an existing optional field. deleteRecord succeeds only if the final whole
   collection validates. Field operations cannot modify ID/kind. Creation/deletion
   conflicts with other writes to the same ID, and duplicate writes to a payload
   or field fail. Mutually referring creates are allowed in one validated batch.
   Survivors keep order and unchanged values; creates append in operation order.
   The full-document fingerprint and collection identity must match the request.
   Candidate construction is pure and all-or-nothing, reporting old/new digests
   and operations. The application must atomically enforce this precondition at
   persistence; source hashes do not detect A-to-B-to-A history. No JSON request
   authorizes a write. Executable application change orchestration is not part of
   this language specification repository.

   Named Definition extraction and expansion

   A named environment is an explicit collection of working/1 Definition records.
   Unlike general working collections, all its references must be closed and the
   entire environment acyclic, including unused records and metadata. Expansion
   follows only explicit scir.ref values targeting this declared environment.
   Bare Symbol heads never implicitly become macros; unknown external references
   remain opaque. Profile text and reference-ID payloads are opaque syntax.

   Factoring selects one expression occurrence by its native path and checks an
   expected full snapshot. The fresh ordinary Definition ID must avoid environment
   IDs, existing explicit document references and recognizable top-level record
   IDs. The same spelling as an ordinary head is allowed. Container/field labels
   and text/reference payload leaves cannot be selected as expression positions.
   Replace exactly the selected occurrence by an explicit reference and append a
   Definition with the selected body. Validate the complete resulting environment.
   Selected unclosed references fail; unrelated external references stay opaque.
   No implicit all-occurrence replacement, general macro following, or text
   rewriting is performed. Atomic output preflight counts every expanded native
   occurrence, including repeats; bounded failure never returns partial success.

   DefinitionLaws proves reconstruction of a selected context, substitution through
   a context and factoring expansion, with freshness and normalized-environment
   agreement assumptions stated in each theorem. Reference-free input has an
   exact raw round trip. With preexisting named references, the general result is
   equality of expanded normal forms. The proofs do not establish that the
   executable environment normalizer, SHA guard, profile admission or resource
   checker satisfies every theorem hypothesis. Those boundaries have independent
   finite conformance vectors. Snapshot equality does not detect intervening history.

   Reference bounds and compatibility

   The algebra contains every finite tree. Native parsing has a default cap of
   2,000,000 characters, 100,000 occurrences and depth 128, root depth zero.
   Native relational encode/decode uses 100,000 occurrences and depth 128.
   Explicit positive node budgets and depth budgets 0..128 may narrow admission.
   Invalid structure and incomplete bounded work remain distinguishable.
   General direct mathematical construction does not promise stack/resource safety.
   Historical annotation limits were 100,000 values including keys, depth 128,
   and 2,000,000 canonical characters; application transports may be narrower.
   A 16,000,000-character outer read cap does not weaken the native source cap.
   Notation's bounds are 64,000 UTF-8 input bytes, 16,000 tokens, 8,000 expanded
   occurrences, depth 64, 256,000 expanded canonical bytes and 128 declarations.
   Profile expansion applies aggregate positive node/byte bounds and depth≤128;
   its historical defaults are 100,000 nodes and 16,000,000 canonical UTF-8 bytes.
   The historical reference transport adapters use 4,096 nodes and depth 128;
   StrictJson adds a 4,096-digit/exponent allocation bound for executable fixtures.
   A bounded reference rejection must never be generalized to all finite trees.

   Canonical grammar, UTF-8 bytes, digest domain and relational envelope remain
   format 1.0. Changing those behaviors requires a new format identifier; readers
   reject unsupported identifiers. Frozen native vectors supplement these rules
   without claiming exhaustiveness or English-to-SCIR fidelity. No semantic memory,
   compression, agent-adoption or general performance result follows from syntax
   validation, model proofs, conformance vectors or repository self-use.
-/

namespace SCIR.Language

structure Symbol where
  value : String
  nonempty : value ≠ ""
  deriving DecidableEq

def Symbol.ofString (value : String) : Option Symbol :=
  if valid : value = "" then none else some ⟨value, valid⟩

theorem Symbol.value_injective (a b : Symbol) : a.value = b.value ↔ a = b := by
  constructor
  · cases a; cases b; simp_all
  · intro h; cases h; rfl

abbrev Term := Symbols.Tree Symbol
abbrev Document := List Term
abbrev Dialect := Document → Prop

def append (left right : Document) : Document := left ++ right

theorem append_associative (a b c : Document) : append (append a b) c = append a (append b c) := by
  exact List.append_assoc a b c

theorem empty_left (document : Document) : append [] document = document := rfl
theorem empty_right (document : Document) : append document [] = document := List.append_nil document

structure Path where
  root : Nat
  children : List Nat
  deriving DecidableEq

inductive SurfacePattern (S V : Type) where
  | wildcard : SurfacePattern S V
  | variable : V → SurfacePattern S V
  | node : S → List (SurfacePattern S V) → SurfacePattern S V
  deriving Repr

def namedPattern : SurfacePattern S V → Option (Substitution.Pattern S V)
  | .wildcard => none
  | .variable name => some (.var name)
  | .node head children => (children.mapM namedPattern).map (.node head)

structure Annotation where
  snapshot : String
  path : Path
  key : Symbol
  payload : Lean.Json

structure Bundle where
  document : Document
  annotations : List Annotation

def erase (bundle : Bundle) : Document := bundle.document

theorem erase_annotations (document : Document) (first second : List Annotation) :
    erase ⟨document, first⟩ = erase ⟨document, second⟩ := rfl

def intersection (first second : Dialect) : Dialect := fun document => first document ∧ second document

theorem intersection_restricts (first second : Dialect) (document : Document) :
    intersection first second document → first document := And.left

theorem intersection_idempotent (dialect : Dialect) (document : Document) :
    intersection dialect dialect document ↔ dialect document := by
  simp [intersection]

end SCIR.Language
