namespace SCIR

universe u

/-- Abstract closure over declared references; no truth interpretation. -/
inductive Reach {α : Type u} (edge : α → α → Prop) (seed : α → Prop) : α → Prop
  | root {a} : seed a → Reach edge seed a
  | step {a b} : Reach edge seed a → edge a b → Reach edge seed b

theorem extensive {α : Type u} {E : α → α → Prop} {S : α → Prop}
    {a : α} (h : S a) : Reach E S a := .root h

theorem monotone {α : Type u} {E : α → α → Prop} {S T : α → Prop}
    (included : ∀ a, S a → T a) {a : α} (h : Reach E S a) : Reach E T a := by
  induction h with
  | root h => exact .root (included _ h)
  | step _ e ih => exact .step ih e

theorem least_closed {α : Type u} {E : α → α → Prop} {S C : α → Prop}
    (contains : ∀ a, S a → C a)
    (closed : ∀ a b, C a → E a b → C b)
    {a : α} (h : Reach E S a) : C a := by
  induction h with
  | root h => exact contains _ h
  | step _ e ih => exact closed _ _ ih e

theorem idempotent {α : Type u} {E : α → α → Prop} {S : α → Prop}
    {a : α} : Reach E (Reach E S) a ↔ Reach E S a := by
  constructor
  · exact least_closed (fun _ h => h) (fun _ _ h e => Reach.step h e)
  · exact Reach.root

/-- Ordered raw tree model of Term; no quotient by algebraic equivalence. -/
inductive Raw where
  | node : String → List Raw → Raw

def tuple (xs : List Raw) : Raw := .node "scir.tuple" xs
def reference (id : String) : Raw := .node "scir.ref" [.node id []]

theorem tuple_injective {xs ys : List Raw} : tuple xs = tuple ys ↔ xs = ys := by
  simp [tuple]

theorem reference_injective {a b : String} : reference a = reference b ↔ a = b := by
  simp [reference]

theorem text_reference_distinct (a b : String) :
    Raw.node "scir.text" [.node a []] ≠ reference b := by
  simp [reference]

theorem argument_arity_distinct (a b : Raw) :
    Raw.node "f" [a, b] ≠ Raw.node "f" [tuple [a, b]] := by
  simp [tuple]

theorem named_role_distinct (a : Raw) :
    Raw.node "f" [.node "scir.kw" [.node "from" [a]]] ≠
    Raw.node "f" [.node "from" [a]] := by
  simp

#print axioms extensive
#print axioms monotone
#print axioms least_closed
#print axioms idempotent
#print axioms tuple_injective
#print axioms reference_injective
#print axioms text_reference_distinct
#print axioms argument_arity_distinct
#print axioms named_role_distinct

end SCIR
