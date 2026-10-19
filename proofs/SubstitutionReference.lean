import ReferenceCodec
import SubstitutionLaws

/- Test-only pattern lowering uses ordinary native terms Node(label, children...)
   and Var(name), carried by the existing canonical occurrence-table transport.
   This is not an added production pattern grammar or a ground-content variable. -/
open Lean SCIR.Symbols SCIR.Substitution SCIR.ReferenceCodec

namespace SCIR.SubstitutionReference

def variableName (name : String) : Checked String := do
  let first := fun c : Char => c.isAlpha && c.toNat < 128 || c == '_'
  let rest := fun c : Char => first c || c.isDigit
  if name == "_" || name.isEmpty || !(first (name.toList.headD '0')) || !name.toList.all rest then
    throw (.rejected "expected a named ASCII variable; wildcards are excluded")
  return name

def decodePattern : Nat → Tree String → Checked (Pattern String String)
  | 0, _ => throw (.incomplete "reference pattern depth exceeded")
  | _ + 1, .node "Var" [.node name []] => return .var (← variableName name)
  | fuel + 1, .node "Node" (.node label [] :: children) =>
      return .node label (← children.mapM (decodePattern fuel))
  | _, _ => throw (.rejected "expected native Node(label, children...) or Var(name)")

def encodePattern : Pattern String String → Tree String
  | .var name => .node "Var" [.node name []]
  | .node label children => .node "Node" (.node label [] :: children.map encodePattern)

def oneTree (value : Json) : Checked (Tree String) := do
  match ← decode value with
  | [tree] => return tree
  | _ => throw (.rejected "expected exactly one root")

def names (value : Json) : Checked (List (String × Json)) := do
  let raw ← checked value.getArr?
  if raw.size > 4096 then throw (.incomplete "reference substitution limit exceeded")
  let entries ← raw.toList.mapM fun item => do
    let cells ← row item 2
    let name ← variableName (← checked (← required "missing name" cells[0]?).getStr?)
    return (name, ← required "missing value" cells[1]?)
  if (entries.map Prod.fst).eraseDups.length != entries.length then
    throw (.rejected "duplicate variable name")
  return entries

def complete (values : List (String × Json)) : Json :=
  Json.mkObj (("status", toJson "complete") :: values)

def evaluate (request : Json) : Checked Json := do
  let version ← checked (← checked (request.getObjVal? "version")).getStr?
  if version != "scir-substitution-reference/1" then throw (.rejected "unsupported reference revision")
  let pattern ← decodePattern 129 (← oneTree (← checked (request.getObjVal? "pattern")))
  let operation ← checked (← checked (request.getObjVal? "operation")).getStr?
  match operation with
  | "substitute" =>
      let raw ← names (← checked (request.getObjVal? "substitutions"))
      let entries ← raw.mapM fun (name, value) => do
        return (name, ← decodePattern 129 (← oneTree value))
      let σ := fun name => ((entries.find? (fun pair => pair.1 == name)).map Prod.snd).getD (.var name)
      return complete [("pattern", ← encodeChecked [encodePattern (substitute σ pattern)])]
  | "instantiate" =>
      let raw ← names (← checked (request.getObjVal? "bindings"))
      let entries ← raw.mapM fun (name, value) => return (name, ← oneTree value)
      match instantiate (lookup entries) pattern with
      | none => throw (.rejected "missing ground substitution")
      | some tree => return complete [("document", ← encodeChecked [tree])]
  | "match" =>
      let tree ← oneTree (← checked (request.getObjVal? "document"))
      match matchReference pattern tree with
      | none => return complete [("matched", toJson false)]
      | some entries =>
          let ids := (entries.map Prod.fst).eraseDups
          let bindings := ids.filterMap fun name =>
            (lookup entries name).map (fun value => (name, encode [value]))
          return complete [("matched", toJson true), ("bindings", Json.mkObj bindings),
            ("document", encode [tree])]
  | _ => throw (.rejected "unsupported reference operation")

def response (source : String) : Json :=
  match readJson source >>= evaluate with
  | .ok value => value
  | .error (.rejected message) => Json.mkObj [("status", toJson "rejected"), ("message", toJson message)]
  | .error (.incomplete message) => Json.mkObj [("status", toJson "incomplete"), ("message", toJson message)]

end SCIR.SubstitutionReference

def SCIR.SubstitutionReference.main : IO Unit := do
  let input ← IO.getStdin
  let output ← IO.getStdout
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    output.putStrLn ((SCIR.SubstitutionReference.response line).compress)
