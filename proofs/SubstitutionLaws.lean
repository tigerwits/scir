import SymbolLaws

namespace SCIR.Substitution

open SCIR.Symbols (Tree)

/-- Open finite expressions. Anonymous matching wildcards are outside this type. -/
inductive Pattern (S V : Type) where
  | var : V → Pattern S V
  | node : S → List (Pattern S V) → Pattern S V
  deriving Repr

def substitute (σ : V → Pattern S W) : Pattern S V → Pattern S W
  | .var name => σ name
  | .node head children => .node head (children.map (substitute σ))

mutual
  /-- Substitution replaces a variable once and preserves each ordered head. -/
  inductive Substituted (σ : V → Pattern S W) : Pattern S V → Pattern S W → Prop where
    | var {name} : Substituted σ (.var name) (σ name)
    | node {head children mapped} : SubstitutedList σ children mapped →
        Substituted σ (.node head children) (.node head mapped)
  inductive SubstitutedList (σ : V → Pattern S W) :
      List (Pattern S V) → List (Pattern S W) → Prop where
    | nil : SubstitutedList σ [] []
    | cons {head tail mappedHead mappedTail} : Substituted σ head mappedHead →
        SubstitutedList σ tail mappedTail →
        SubstitutedList σ (head :: tail) (mappedHead :: mappedTail)
end

theorem substitution_sound (σ : V → Pattern S W) (pattern : Pattern S V) :
    Substituted σ pattern (substitute σ pattern) :=
  Pattern.rec (motive_1 := fun p => Substituted σ p (substitute σ p))
    (motive_2 := fun ps => SubstitutedList σ ps (ps.map (substitute σ)))
    (fun name => by simpa only [substitute] using (Substituted.var (σ := σ) (name := name)))
    (fun head _ ih => by
      simpa only [substitute] using (Substituted.node (head := head) ih))
    SubstitutedList.nil (fun _ _ ih ihs => SubstitutedList.cons ih ihs) pattern

theorem substitution_complete (σ : V → Pattern S W) {pattern : Pattern S V}
    {result : Pattern S W} (meaning : Substituted σ pattern result) :
    result = substitute σ pattern :=
  Substituted.rec (σ := σ) (motive_1 := fun p q _ => q = substitute σ p)
    (motive_2 := fun ps qs _ => qs = ps.map (substitute σ)) (by intro name; simp only [substitute])
    (fun _ ih => by simp [substitute, ih]) rfl
    (fun _ _ ih ihs => by simp [ih, ihs]) meaning

theorem substitution_identity (pattern : Pattern S V) :
    substitute Pattern.var pattern = pattern :=
  Pattern.rec (motive_1 := fun p => substitute Pattern.var p = p)
    (motive_2 := fun ps => ps.map (substitute Pattern.var) = ps)
    (fun _ => by simp only [substitute]) (fun _ _ ih => by simp [substitute, ih]) rfl
    (fun _ _ ih ihs => by simp [ih, ihs]) pattern

theorem substitution_variable (σ : V → Pattern S W) (name : V) :
    substitute σ (.var name) = σ name := by simp only [substitute]

theorem substitution_composition (σ : V → Pattern S W) (τ : W → Pattern S U)
    (pattern : Pattern S V) :
    substitute τ (substitute σ pattern) = substitute (fun name => substitute τ (σ name)) pattern :=
  Pattern.rec
    (motive_1 := fun p => substitute τ (substitute σ p) =
      substitute (fun name => substitute τ (σ name)) p)
    (motive_2 := fun ps => (ps.map (substitute σ)).map (substitute τ) =
      ps.map (substitute (fun name => substitute τ (σ name))))
    (fun _ => by simp only [substitute]) (fun _ _ ih => by simp only [substitute]; rw [ih]) rfl
    (fun _ _ ih ihs => by simp [ih, ihs]) pattern

def instantiate (env : V → Option (Tree S)) : Pattern S V → Option (Tree S)
  | .var name => env name
  | .node head children => (children.mapM (instantiate env)).map (.node head)

mutual
  /-- Ground reconstruction means every capture has its declared ground value. -/
  inductive Instantiates (env : V → Option (Tree S)) : Pattern S V → Tree S → Prop where
    | var {name value} : env name = some value → Instantiates env (.var name) value
    | node {head children values} : InstantiatesList env children values →
        Instantiates env (.node head children) (.node head values)
  inductive InstantiatesList (env : V → Option (Tree S)) :
      List (Pattern S V) → List (Tree S) → Prop where
    | nil : InstantiatesList env [] []
    | cons {head tail value values} : Instantiates env head value →
        InstantiatesList env tail values →
        InstantiatesList env (head :: tail) (value :: values)
end

theorem instantiation_complete (env : V → Option (Tree S)) {pattern : Pattern S V}
    {value : Tree S} (meaning : Instantiates env pattern value) :
    instantiate env pattern = some value :=
  Instantiates.rec (env := env) (motive_1 := fun p t _ => instantiate env p = some t)
    (motive_2 := fun ps ts _ => ps.mapM (instantiate env) = some ts)
    (fun premise => by simpa only [instantiate] using premise) (fun _ ih => by simp [instantiate, ih]) rfl
    (fun _ _ ih ihs => by simp [List.mapM_cons, ih, ihs]) meaning

theorem instantiation_sound (env : V → Option (Tree S)) (pattern : Pattern S V) :
    ∀ value, instantiate env pattern = some value → Instantiates env pattern value := by
  refine Pattern.rec
    (motive_1 := fun p => ∀ t, instantiate env p = some t → Instantiates env p t)
    (motive_2 := fun ps => ∀ ts, ps.mapM (instantiate env) = some ts → InstantiatesList env ps ts)
    ?_ ?_ ?_ ?_ pattern
  · intro name value premise
    exact .var (by simpa only [instantiate] using premise)
  · intro head children ih value premise
    cases found : children.mapM (instantiate env) with
    | none => simp [instantiate, found] at premise
    | some values =>
        simp [instantiate, found] at premise
        subst value
        exact .node (ih values found)
  · intro values premise
    simp only [List.mapM_nil, pure, Option.some.injEq] at premise
    subst values
    exact .nil
  · intro head tail ih ihs values premise
    cases first : instantiate env head with
    | none => simp [List.mapM_cons, first] at premise
    | some value =>
        cases rest : tail.mapM (instantiate env) with
        | none => simp [List.mapM_cons, first, rest] at premise
        | some more =>
            simp [List.mapM_cons, first, rest] at premise
            subst values
            exact .cons (ih value first) (ihs more rest)

mutual
  def treeDecEq [DecidableEq S] : (left right : Tree S) → Decidable (left = right)
    | .node head children, .node other values =>
        if heads : head = other then
          match treesDecEq children values with
          | .isTrue same => .isTrue (by cases heads; cases same; rfl)
          | .isFalse different => .isFalse (by intro same; cases same; exact different rfl)
        else .isFalse (by intro same; cases same; exact heads rfl)
  def treesDecEq [DecidableEq S] : (left right : List (Tree S)) → Decidable (left = right)
    | [], [] => .isTrue rfl
    | [], _ :: _ => .isFalse (by intro same; cases same)
    | _ :: _, [] => .isFalse (by intro same; cases same)
    | head :: tail, value :: values =>
        match treeDecEq head value, treesDecEq tail values with
        | .isTrue same, .isTrue rest => .isTrue (by cases same; cases rest; rfl)
        | .isFalse different, _ => .isFalse (by intro same; cases same; exact different rfl)
        | _, .isFalse different => .isFalse (by intro same; cases same; exact different rfl)
end

instance [DecidableEq S] : DecidableEq (Tree S) := treeDecEq

/-- Collect tentative captures without trusting labels, arities or repetitions. -/
def captures : Pattern S V → Tree S → List (V × Tree S)
  | .var name => fun tree => [(name, tree)]
  | .node _ children => fun (.node _ values) =>
      ((children.map captures).zip values).flatMap (fun (f, tree) => f tree)

def lookup [DecidableEq V] (bindings : List (V × Tree S)) (name : V) : Option (Tree S) :=
  ((bindings.find? (fun pair => decide (pair.1 = name))).map Prod.snd)

/-- Independent matching reference: collect candidates, then check reconstruction. -/
def matchReference [DecidableEq S] [DecidableEq V] (pattern : Pattern S V) (tree : Tree S) :
    Option (List (V × Tree S)) :=
  let bindings := captures pattern tree
  if instantiate (lookup bindings) pattern = some tree then some bindings else none

theorem match_reconstruction [DecidableEq S] [DecidableEq V] (pattern : Pattern S V)
    (tree : Tree S) (bindings : List (V × Tree S))
    (success : matchReference pattern tree = some bindings) :
    instantiate (lookup bindings) pattern = some tree := by
  unfold matchReference at success
  dsimp only at success
  split at success
  · rename_i reconstructs
    cases success
    exact reconstructs
  · contradiction

theorem match_sound [DecidableEq S] [DecidableEq V] (pattern : Pattern S V)
    (tree : Tree S) (bindings : List (V × Tree S))
    (success : matchReference pattern tree = some bindings) :
    Instantiates (lookup bindings) pattern tree :=
  instantiation_sound _ _ _ (match_reconstruction pattern tree bindings success)

#print axioms substitution_sound
#print axioms substitution_complete
#print axioms substitution_identity
#print axioms substitution_variable
#print axioms substitution_composition
#print axioms instantiation_complete
#print axioms instantiation_sound
#print axioms match_reconstruction
#print axioms match_sound
#print axioms substitute
#print axioms instantiate
#print axioms matchReference

end SCIR.Substitution
