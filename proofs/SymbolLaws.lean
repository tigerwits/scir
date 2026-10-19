namespace SCIR.Symbols

/-- Finite ordered trees over an alphabet; labels impose no arity. -/
inductive Tree (S : Type) where
  | node : S → List (Tree S) → Tree S
  deriving Repr

def relabel (f : S → R) : Tree S → Tree R
  | .node symbol children => .node (f symbol) (children.map (relabel f))

def relabelDocument (f : S → R) (document : List (Tree S)) : List (Tree R) :=
  document.map (relabel f)

mutual
  /-- Independent structural meaning: each node keeps its ordered children. -/
  inductive Relabeled (f : S → R) : Tree S → Tree R → Prop where
    | node {symbol children mapped} : RelabeledList f children mapped →
        Relabeled f (.node symbol children) (.node (f symbol) mapped)
  inductive RelabeledList (f : S → R) : List (Tree S) → List (Tree R) → Prop where
    | nil : RelabeledList f [] []
    | cons {head tail mappedHead mappedTail} : Relabeled f head mappedHead →
        RelabeledList f tail mappedTail → RelabeledList f (head :: tail) (mappedHead :: mappedTail)
end

theorem reference_sound (f : S → R) (tree : Tree S) : Relabeled f tree (relabel f tree) :=
  Tree.rec (motive_1 := fun t => Relabeled f t (relabel f t))
    (motive_2 := fun ts => RelabeledList f ts (ts.map (relabel f)))
    (fun symbol _ ih => by
      simpa only [relabel] using (Relabeled.node (symbol := symbol) ih)) RelabeledList.nil
    (fun _ _ ih ihs => RelabeledList.cons ih ihs) tree

theorem reference_complete (f : S → R) {tree : Tree S} {result : Tree R}
    (meaning : Relabeled f tree result) : result = relabel f tree :=
  Relabeled.rec (motive_1 := fun t u _ => u = relabel f t)
    (motive_2 := fun ts us _ => us = ts.map (relabel f))
    (fun _ ih => by simp [relabel, ih]) rfl
    (fun _ _ ih ihs => by simp [ih, ihs]) meaning

theorem relabel_identity (tree : Tree S) : relabel id tree = tree :=
  Tree.rec (motive_1 := fun t => relabel id t = t)
    (motive_2 := fun ts => ts.map (relabel id) = ts)
    (fun _ _ ih => by simp [relabel, ih]) rfl
    (fun _ _ ih ihs => by simp [ih, ihs]) tree

theorem relabel_composition (f : S → R) (g : R → U) (tree : Tree S) :
    relabel g (relabel f tree) = relabel (g ∘ f) tree :=
  Tree.rec (motive_1 := fun t => relabel g (relabel f t) = relabel (g ∘ f) t)
    (motive_2 := fun ts => (ts.map (relabel f)).map (relabel g) = ts.map (relabel (g ∘ f)))
    (fun _ _ ih => by simp only [relabel]; rw [ih]; rfl) rfl
    (fun _ _ ih ihs => by simp [ih, ihs]) tree

abbrev Occurrence (S : Type) := List Nat × S

def labelMap (f : S → R) (occurrence : Occurrence S) : Occurrence R :=
  (occurrence.1, f occurrence.2)

def prefixPath (index : Nat) (occurrences : List (Occurrence S)) : List (Occurrence S) :=
  occurrences.map (fun (path, symbol) => (index :: path, symbol))

/-- Child/root positions are introduced without inspecting labels. -/
def locate (index : Nat) : List (List (Occurrence S)) → List (Occurrence S)
  | [] => []
  | head :: tail => prefixPath index head ++ locate (index + 1) tail

def occurrences : Tree S → List (Occurrence S)
  | .node symbol children => ([], symbol) :: locate 0 (children.map occurrences)

def documentOccurrences (document : List (Tree S)) : List (Occurrence S) :=
  locate 0 (document.map occurrences)

theorem labelMap_prefix (f : S → R) (index : Nat) (xs : List (Occurrence S)) :
    (prefixPath index xs).map (labelMap f) = prefixPath index (xs.map (labelMap f)) := by
  simp [prefixPath, List.map_map, Function.comp_def, labelMap]

theorem labelMap_locate (f : S → R) (index : Nat) (xss : List (List (Occurrence S))) :
    (locate index xss).map (labelMap f) =
      locate index (xss.map (fun xs => xs.map (labelMap f))) := by
  induction xss generalizing index with
  | nil => rfl
  | cons head tail ih => simp [locate, labelMap_prefix, ih]

theorem occurrence_preservation (f : S → R) (tree : Tree S) :
    occurrences (relabel f tree) = (occurrences tree).map (labelMap f) :=
  Tree.rec (motive_1 := fun t => occurrences (relabel f t) = (occurrences t).map (labelMap f))
    (motive_2 := fun ts => (ts.map (relabel f)).map occurrences =
      (ts.map occurrences).map (fun xs => xs.map (labelMap f)))
    (fun _ _ ih => by simp only [relabel, occurrences, List.map_cons]; rw [ih, labelMap_locate]; rfl)
    rfl (fun _ _ ih ihs => by simp [ih, ihs]) tree

theorem document_identity (document : List (Tree S)) : relabelDocument id document = document := by
  induction document with
  | nil => rfl
  | cons head tail ih =>
    simp [relabelDocument, relabel_identity] at ih ⊢
    exact ih

theorem document_composition (f : S → R) (g : R → U) (document : List (Tree S)) :
    relabelDocument g (relabelDocument f document) = relabelDocument (g ∘ f) document := by
  simp only [relabelDocument, List.map_map]
  apply List.map_congr_left
  intro tree _
  exact relabel_composition f g tree

theorem document_occurrence_preservation (f : S → R) (document : List (Tree S)) :
    documentOccurrences (relabelDocument f document) =
      (documentOccurrences document).map (labelMap f) := by
  simp only [documentOccurrences, relabelDocument, labelMap_locate, List.map_map]
  congr 1
  apply List.map_congr_left
  intro tree _
  exact occurrence_preservation f tree

#print axioms relabel_identity
#print axioms reference_sound
#print axioms reference_complete
#print axioms relabel_composition
#print axioms labelMap_prefix
#print axioms labelMap_locate
#print axioms occurrence_preservation
#print axioms document_identity
#print axioms document_composition
#print axioms document_occurrence_preservation
#print axioms relabel
#print axioms relabelDocument
#print axioms documentOccurrences

end SCIR.Symbols
