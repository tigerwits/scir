import SubstitutionLaws

namespace SCIR.Definitions

open SCIR.Substitution

/- The test adapter lowers explicit reference VALUES to the free slots of this
   algebra. Native heads, text payloads and field labels remain literal nodes.
   This reuse does not make a production Pattern.Var a ground reference. -/

inductive Context (S N : Type) where
  | hole : Context S N
  | frame : S → List (Pattern S N) → Context S N → List (Pattern S N) → Context S N

def plug (context : Context S N) (body : Pattern S N) : Pattern S N :=
  match context with
  | .hole => body
  | .frame head before inner after => .node head (before ++ plug inner body :: after)

def mapContext (σ : N → Pattern S M) : Context S N → Context S M
  | .hole => .hole
  | .frame head before inner after =>
      .frame head (before.map (substitute σ)) (mapContext σ inner) (after.map (substitute σ))

def references : Pattern S N → List N
  | .var name => [name]
  | .node _ children => children.flatMap references

def contextReferences : Context S N → List N
  | .hole => []
  | .frame _ before inner after =>
      before.flatMap references ++ contextReferences inner ++ after.flatMap references

theorem substitution_agrees (σ τ : N → Pattern S M) (expression : Pattern S N) :
    (∀ name, name ∈ references expression → σ name = τ name) →
    substitute σ expression = substitute τ expression := by
  refine Pattern.rec
    (motive_1 := fun p => (∀ n, n ∈ references p → σ n = τ n) → substitute σ p = substitute τ p)
    (motive_2 := fun ps => (∀ n, n ∈ ps.flatMap references → σ n = τ n) →
      ps.map (substitute σ) = ps.map (substitute τ)) ?_ ?_ ?_ ?_ expression
  · intro name agrees
    simpa only [substitute] using agrees name (by simp [references])
  · intro head children ih agrees
    simpa only [substitute] using congrArg (Pattern.node head) (ih (by simpa only [references] using agrees))
  · intro _
    rfl
  · intro head tail ih ihs agrees
    simp only [List.map_cons]
    rw [ih (fun n member => agrees n (by simp [member])),
      ihs (fun n member => agrees n (by simp [member]))]

theorem context_substitution_agrees (σ τ : N → Pattern S M) (context : Context S N)
    (agrees : ∀ name, name ∈ contextReferences context → σ name = τ name) :
    mapContext σ context = mapContext τ context := by
  induction context with
  | hole => rfl
  | frame head before inner after ih =>
      simp only [mapContext]
      have first : before.map (substitute σ) = before.map (substitute τ) := by
        apply List.map_congr_left
        intro p member
        apply substitution_agrees
        intro n found
        exact agrees n (by simp [contextReferences]; exact Or.inl ⟨p, member, found⟩)
      have last : after.map (substitute σ) = after.map (substitute τ) := by
        apply List.map_congr_left
        intro p member
        apply substitution_agrees
        intro n found
        exact agrees n (by simp [contextReferences]; exact Or.inr (Or.inr ⟨p, member, found⟩))
      rw [first, last, ih (fun n member => agrees n (by simp [contextReferences, member]))]

theorem substitution_plug (σ : N → Pattern S M) (context : Context S N) (body : Pattern S N) :
    substitute σ (plug context body) = plug (mapContext σ context) (substitute σ body) := by
  induction context with
  | hole => rfl
  | frame head before inner after ih => simp [plug, mapContext, substitute, ih]

/-- A fresh reference replaces exactly the hole. Old and extended normalized
    environments agree on every other name; the new name denotes the old normal
    form of the selected body. There are no binders or implicit head macros. -/
theorem factor_expansion (σ τ : N → Pattern S M) (context : Context S N)
    (body : Pattern S N) (name : N) (fresh : name ∉ contextReferences context)
    (resolved : τ name = substitute σ body)
    (unchanged : ∀ other, other ≠ name → τ other = σ other) :
    substitute τ (plug context (.var name)) = substitute σ (plug context body) := by
  rw [substitution_plug, substitution_plug]
  have same : mapContext τ context = mapContext σ context :=
    context_substitution_agrees τ σ context (fun other member =>
      unchanged other (by intro equal; subst other; exact fresh member))
  rw [same]
  simpa only [substitute] using congrArg (plug (mapContext σ context)) resolved

theorem fresh_factor_round_trip [DecidableEq N] (context : Context S N)
    (body : Pattern S N) (name : N) (fresh : name ∉ contextReferences context) :
    substitute (fun other => if other = name then body else .var other)
      (plug context (.var name)) = plug context body := by
  have law := factor_expansion Pattern.var (fun other => if other = name then body else .var other)
    context body name fresh (by simp [substitution_identity]) (by intro other distinct; simp [distinct])
  simpa only [substitution_identity] using law

def select : List Nat → Pattern S N → Option (Context S N × Pattern S N)
  | [], expression => some (.hole, expression)
  | _ :: _, .var _ => none
  | index :: rest, .node head children => do
      let child ← children[index]?
      let (inner, body) ← select rest child
      return (.frame head (children.take index) inner (children.drop (index + 1)), body)

theorem selection_reconstructs (path : List Nat) (expression : Pattern S N)
    (context : Context S N) (body : Pattern S N)
    (selected : select path expression = some (context, body)) : plug context body = expression := by
  induction path generalizing expression context body with
  | nil =>
      simp only [select, Option.some.injEq, Prod.mk.injEq] at selected
      rcases selected with ⟨rfl, rfl⟩
      rfl
  | cons index rest ih =>
      cases expression with
      | var name => simp [select] at selected
      | node head children =>
          cases found : children[index]? with
          | none => simp [select, found] at selected
          | some child =>
              cases nested : select rest child with
              | none => simp [select, found, nested] at selected
              | some pair =>
                  rcases pair with ⟨inner, value⟩
                  simp [select, found, nested] at selected
                  rcases selected with ⟨rfl, rfl⟩
                  simp only [plug, ih child inner value nested]
                  have decomposition := List.take_append_drop index children
                  rw [List.drop_eq_getElem_cons (List.getElem?_eq_some_iff.mp found).1] at decomposition
                  simpa only [(List.getElem?_eq_some_iff.mp found).2] using congrArg (Pattern.node head) decomposition

theorem selected_factor_expansion (σ τ : N → Pattern S M) (path : List Nat)
    (expression : Pattern S N) (context : Context S N) (body : Pattern S N) (name : N)
    (selected : select path expression = some (context, body))
    (fresh : name ∉ contextReferences context) (resolved : τ name = substitute σ body)
    (unchanged : ∀ other, other ≠ name → τ other = σ other) :
    substitute τ (plug context (.var name)) = substitute σ expression := by
  rw [factor_expansion σ τ context body name fresh resolved unchanged,
    selection_reconstructs path expression context body selected]

#print axioms substitution_agrees
#print axioms context_substitution_agrees
#print axioms substitution_plug
#print axioms factor_expansion
#print axioms fresh_factor_round_trip
#print axioms selection_reconstructs
#print axioms selected_factor_expansion
#print axioms plug
#print axioms select
#print axioms references
#print axioms mapContext

end SCIR.Definitions
