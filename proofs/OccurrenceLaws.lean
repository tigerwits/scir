import Std
import SymbolLaws

/- Native occurrence navigation, independent of labels and consuming profiles.
   Paths have lexicographic order, with a parent before its descendants. Coverage
   is exact lookup equivalence; distinct paths remain distinct even for equal
   labels or equal subtrees. Appending roots reuses the exact old traversal and
   offsets only the new roots. This says nothing about a consumer's cache,
   chronological grouping, source authenticity, or bounded parser correctness. -/
namespace SCIR.Occurrences
open SCIR.Symbols

abbrev Before (left right : Occurrence S) : Prop := List.Lex Nat.lt left.1 right.1

def lookup : List Nat → Tree S → Option S
  | [], .node symbol _ => some symbol
  | index :: path, .node _ children => children[index]?.bind (lookup path)

def lookupDocument (document : List (Tree S)) : List Nat → Option S
  | [] => none
  | index :: path => document[index]?.bind (lookup path)

theorem locate_root (start : Nat) (forests : List (List (Occurrence S)))
    {item : Occurrence S} (member : item ∈ locate start forests) :
    ∃ index path, item.1 = index :: path ∧ start ≤ index := by
  induction forests generalizing start with
  | nil => simp [locate] at member
  | cons head tail ih =>
    simp only [locate, List.mem_append] at member
    rcases member with member | member
    · obtain ⟨⟨path, symbol⟩, _, equality⟩ := List.mem_map.mp member
      cases equality
      exact ⟨start, path, rfl, Nat.le_refl _⟩
    · obtain ⟨index, path, equality, lower⟩ := ih (start + 1) member
      exact ⟨index, path, equality, by omega⟩

theorem locate_nonempty (start : Nat) (forests : List (List (Occurrence S))) (symbol : S) :
    ([], symbol) ∉ locate start forests := by
  intro member
  obtain ⟨_, _, equality, _⟩ := locate_root start forests member
  cases equality

theorem locate_before_start (start index : Nat) (forests : List (List (Occurrence S)))
    (path : List Nat) (symbol : S) (earlier : index < start) :
    (index :: path, symbol) ∉ locate start forests := by
  intro member
  obtain ⟨other, _, equality, lower⟩ := locate_root start forests member
  have : index = other := List.cons.inj equality |>.1
  omega

theorem mem_prefix (index start : Nat) (path : List Nat) (symbol : S)
    (items : List (Occurrence S)) :
    (index :: path, symbol) ∈ prefixPath start items ↔ index = start ∧ (path, symbol) ∈ items := by
  constructor
  · intro member
    simp only [prefixPath] at member
    obtain ⟨⟨foundPath, foundSymbol⟩, foundMember, equality⟩ := List.mem_map.mp member
    simp only [Prod.mk.injEq, List.cons.injEq] at equality
    obtain ⟨⟨rfl, rfl⟩, rfl⟩ := equality
    exact ⟨rfl, foundMember⟩
  · rintro ⟨rfl, member⟩
    exact List.mem_map.mpr ⟨(path, symbol), member, rfl⟩

theorem mem_locate (start index : Nat) (forests : List (List (Occurrence S)))
    (path : List Nat) (symbol : S) :
    ((start + index) :: path, symbol) ∈ locate start forests ↔
      ∃ items, forests[index]? = some items ∧ (path, symbol) ∈ items := by
  induction forests generalizing start index with
  | nil => simp [locate]
  | cons head tail ih =>
    cases index with
    | zero =>
      have excluded := locate_before_start (start + 1) start tail path symbol (by omega)
      simp [locate, mem_prefix, excluded]
    | succ index =>
      have different : start + (index + 1) ≠ start := by omega
      have offset : start + (index + 1) = (start + 1) + index := by omega
      simp only [locate, List.mem_append, mem_prefix, different, false_and, false_or,
        List.getElem?_cons_succ]
      rw [offset, ih]

theorem lookup_coverage (tree : Tree S) (path : List Nat) (symbol : S) :
    lookup path tree = some symbol ↔ (path, symbol) ∈ occurrences tree := by
  induction path generalizing tree with
  | nil =>
    cases tree with
    | node head children => simp [lookup, occurrences, locate_nonempty, eq_comm]
  | cons index path ih =>
    cases tree with
    | node head children =>
      simp only [lookup, occurrences, List.mem_cons, Prod.mk.injEq,
        List.cons_ne_nil, false_and, false_or]
      rw [show index = 0 + index from (Nat.zero_add index).symm, mem_locate]
      cases selected : children[index]? with
      | none => simp [List.getElem?_map, selected]
      | some child => simpa [List.getElem?_map, selected] using ih child

theorem document_coverage (document : List (Tree S)) (path : List Nat) (symbol : S) :
    lookupDocument document path = some symbol ↔ (path, symbol) ∈ documentOccurrences document := by
  cases path with
  | nil => simp [lookupDocument, documentOccurrences, locate_nonempty]
  | cons index path =>
    unfold lookupDocument documentOccurrences
    rw [show index = 0 + index from (Nat.zero_add index).symm, mem_locate]
    cases selected : document[index]? with
    | none => simp [List.getElem?_map, selected]
    | some tree => simpa [List.getElem?_map, selected] using lookup_coverage tree path symbol

theorem prefix_ordered (start : Nat) (items : List (Occurrence S))
    (ordered : items.Pairwise Before) :
    (prefixPath start items).Pairwise Before := by
  exact ordered.map (S := fun (a b : Occurrence S) => a.1 < b.1)
    (fun (item : Occurrence S) => (start :: item.1, item.2))
    (fun _ _ before => List.Lex.cons before)

theorem locate_ordered (start : Nat) (forests : List (List (Occurrence S)))
    (ordered : ∀ items ∈ forests, items.Pairwise Before) :
    (locate start forests).Pairwise Before := by
  induction forests generalizing start with
  | nil => exact .nil
  | cons head tail ih =>
    apply List.pairwise_append.mpr
    refine ⟨prefix_ordered start head (ordered head (by simp)),
      ih (start + 1) (fun items member => ordered items (by simp [member])), ?_⟩
    intro left leftMember right rightMember
    obtain ⟨⟨path, symbol⟩, _, equality⟩ := List.mem_map.mp leftMember
    cases equality
    obtain ⟨index, suffix, equality, lower⟩ := locate_root (start + 1) tail rightMember
    change start :: path < right.1
    rw [equality]
    exact List.Lex.rel (by omega)

theorem occurrences_ordered (tree : Tree S) :
    (occurrences tree).Pairwise Before :=
  Tree.rec (motive_1 := fun tree => (occurrences tree).Pairwise Before)
    (motive_2 := fun trees => ∀ tree ∈ trees, (occurrences tree).Pairwise Before)
    (fun symbol children ih => by
      simp only [occurrences]
      apply List.Pairwise.cons
      · intro item member
        obtain ⟨index, path, equality, _⟩ := locate_root 0 (children.map occurrences) member
        change [] < item.1
        rw [equality]
        exact List.Lex.nil
      · apply locate_ordered
        intro items member
        obtain ⟨child, childMember, equality⟩ := List.mem_map.mp member
        cases equality
        exact ih child childMember)
    (by simp)
    (fun _ _ ih ihs tree member => by
      rcases List.mem_cons.mp member with equality | member
      · cases equality; exact ih
      · exact ihs tree member) tree

theorem document_ordered (document : List (Tree S)) :
    (documentOccurrences document).Pairwise Before := by
  apply locate_ordered
  intro items member
  obtain ⟨tree, _, equality⟩ := List.mem_map.mp member
  cases equality
  exact occurrences_ordered tree

theorem document_paths_unique (document : List (Tree S)) :
    ((documentOccurrences document).map Prod.fst).Nodup := by
  apply List.pairwise_map.mpr
  apply (document_ordered document).imp
  intro a b before equal
  change List.Lex Nat.lt a.1 b.1 at before
  rw [equal] at before
  exact List.lex_irrefl Nat.lt_irrefl _ before

theorem locate_append (start : Nat) (left right : List (List (Occurrence S))) :
    locate start (left ++ right) = locate start left ++ locate (start + left.length) right := by
  induction left generalizing start with
  | nil => simp [locate]
  | cons head tail ih =>
    simp [locate, ih, List.append_assoc, Nat.add_assoc, Nat.add_comm, Nat.add_left_comm]

theorem document_append (before after : List (Tree S)) :
    documentOccurrences (before ++ after) = documentOccurrences before ++
      locate before.length (after.map occurrences) := by
  simp [documentOccurrences, locate_append]

theorem append_batches (first second third : List (Tree S)) :
    documentOccurrences first ++ locate first.length (second.map occurrences) ++
      locate (first.length + second.length) (third.map occurrences) =
        documentOccurrences (first ++ (second ++ third)) := by
  simp [document_append, locate_append, List.append_assoc]

private def duplicateForest : List (Tree String) :=
  [.node "A" [.node "A" [], .node "A" [.node "é" []]], .node "A" []]

#guard documentOccurrences duplicateForest =
  [([0], "A"), ([0, 0], "A"), ([0, 1], "A"), ([0, 1, 0], "é"), ([1], "A")]
#guard lookupDocument duplicateForest [0, 1, 0] = some "é"
#guard lookupDocument duplicateForest [] = none
#guard lookupDocument duplicateForest [0, 2] = none
#guard lookupDocument duplicateForest [0, 0, 0] = none
#guard lookupDocument duplicateForest [2] = none
#guard documentOccurrences (duplicateForest ++ duplicateForest) =
  documentOccurrences duplicateForest ++ locate 2 (duplicateForest.map occurrences)

end SCIR.Occurrences
