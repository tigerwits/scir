import Lean
import SymbolLaws
import StrictJson

/- Test-only bounded codec for canonical scir-relations/1.0 forests.
   This boundary is empirically checked; it is outside the model proofs.
   NativeCodec.decodeRelations specifies general format-1.0 transport admission;
   this narrower adapter intentionally requires canonical reference inputs. -/
open Lean SCIR.Symbols

namespace SCIR.ReferenceCodec

inductive BoundaryError where
  | rejected : String → BoundaryError
  | incomplete : String → BoundaryError

abbrev Checked := Except BoundaryError

def checked (value : Except String α) : Checked α := value.mapError .rejected

def readJson (source : String) : Checked Json :=
  (StrictJson.parse source).mapError fun error =>
    if error.startsWith "incomplete:" then .incomplete error else .rejected error

def required (message : String) (value : Option α) : Checked α :=
  match value with
  | some item => return item
  | none => throw (.rejected message)

def row (value : Json) (width : Nat) : Checked (Array Json) := do
  let values ← checked value.getArr?
  if values.size != width then throw (.rejected "invalid row width")
  return values

def symbol (value : Json) : Checked String := do
  let label ← checked value.getStr?
  if label.isEmpty || label.toList.any (fun c => 0xD800 ≤ c.toNat && c.toNat ≤ 0xDFFF) then
    throw (.rejected "invalid native symbol")
  return label

def natAt (values : Array Json) (index : Nat) : Checked Nat := do
  checked (← required "missing column" values[index]?).getNat?

def arr (values : List Json) : Json := Json.arr values.toArray

def encode (document : List (Tree String)) : Json := Id.run do
  let located := (documentOccurrences document).zipIdx
  let nodes := located.map fun ((_, label), ident) => arr [toJson ident, toJson label]
  let roots := located.filterMap fun ((path, _), ident) =>
    match path with
    | [position] => some (arr [toJson position, toJson ident])
    | _ => none
  let args := located.filterMap fun ((path, _), ident) => do
    if path.length ≤ 1 then none else do
      let (_, parent) ← located.find? (fun ((p, _), _) => p == path.dropLast)
      let position ← path.getLast?
      some (arr [toJson parent, toJson position, toJson ident])
  return Json.mkObj [("version", toJson "scir-relations/1.0"), ("nodes", arr nodes),
    ("args", arr args), ("roots", arr roots)]

def build (labels : List (Nat × String)) (edges : List (Nat × Nat × Nat)) :
    Nat → List Nat → Nat → Checked (Tree String)
  | 0, _, _ => throw (.incomplete "reference depth limit exceeded")
  | fuel + 1, trail, ident => do
      if trail.contains ident then throw (.rejected "cyclic occurrence table")
      let (_, label) ← required "unknown node" (labels.find? (fun pair => pair.1 == ident))
      let children := edges.filterMap fun (parent, _, child) =>
        if parent == ident then some child else none
      let terms ← children.mapM (build labels edges fuel (ident :: trail))
      return .node label terms

def decode (value : Json) : Checked (List (Tree String)) := do
  if (← checked (← checked (value.getObjVal? "version")).getStr?) != "scir-relations/1.0" then
    throw (.rejected "unsupported relation version")
  let rawNodes ← checked (← checked (value.getObjVal? "nodes")).getArr?
  if rawNodes.size > 4096 then throw (.incomplete "reference node limit exceeded")
  let labels ← rawNodes.toList.mapM fun item => do
    let cells ← row item 2
    let ident ← natAt cells 0
    let label ← symbol (← required "missing label" cells[1]?)
    return (ident, label)
  let rawEdges ← checked (← checked (value.getObjVal? "args")).getArr?
  if rawEdges.size > 4096 then throw (.incomplete "reference edge limit exceeded")
  let edges ← rawEdges.toList.mapM fun item => do
    let cells ← row item 3
    return (← natAt cells 0, ← natAt cells 1, ← natAt cells 2)
  let rawRoots ← checked (← checked (value.getObjVal? "roots")).getArr?
  if rawRoots.size > 4096 then throw (.incomplete "reference root limit exceeded")
  let roots ← rawRoots.toList.mapM fun item => do
    let cells ← row item 2
    return (← natAt cells 0, ← natAt cells 1)
  let incoming := roots.map Prod.snd ++ edges.map (fun (_, _, child) => child)
  if (labels.map Prod.fst).eraseDups.length != labels.length ||
      incoming.eraseDups.length != incoming.length || incoming.length != labels.length then
    throw (.rejected "occurrences must have unique identities and one incoming edge or root")
  let document ← roots.mapM fun (_, ident) => build labels edges 129 [] ident
  if encode document != value then
    throw (.rejected "expected canonical forest occurrence tables")
  return document

def remainingNodes : Nat → Nat → Tree String → Checked Nat
  | 0, _, _ => throw (.incomplete "reference output depth exceeded")
  | _, 0, _ => throw (.incomplete "reference output nodes exceeded")
  | depth + 1, remaining + 1, .node _ children =>
      children.foldlM (fun budget child => remainingNodes depth budget child) remaining

def encodeChecked (document : List (Tree String)) : Checked Json := do
  let _ ← document.foldlM (fun budget tree => remainingNodes 129 budget tree) 4096
  return encode document

end SCIR.ReferenceCodec
