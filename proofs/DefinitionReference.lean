import ReferenceCodec
import DefinitionLaws

/- Test-only profile adapter. Definition expansion uses repeated simultaneous
   substitutions, independently of the runtime's iterative reference traversal.
   Existing canonical native relations carry every input and result. -/
open Lean SCIR.Symbols SCIR.Substitution SCIR.Definitions SCIR.ReferenceCodec

namespace SCIR.DefinitionReference

abbrev Expression := Pattern String String

def reserved (label : String) : Bool :=
  ["scir.text", "scir.ref", "scir.kw", "scir.tuple"].contains label

def leaf : Tree String → Checked String
  | .node label [] =>
      if reserved label then throw (.rejected "expected an ordinary symbol leaf") else return label
  | _ => throw (.rejected "expected an ordinary symbol leaf")

def parts (children : List (Tree String)) : Checked (List (Tree String) × List (String × Tree String)) := do
  match children.getLast? with
  | some (.node "scir.kw" entries) =>
      if entries.isEmpty then throw (.rejected "empty keyword container")
      let fields ← entries.mapM fun entry =>
        match entry with
        | .node key [value] => pure (key, value)
        | _ => throw (.rejected "keyword entries must be unary")
      if !((fields.map Prod.fst).zip ((fields.map Prod.fst).drop 1)).all
          (fun (left, right) => decide (left < right)) then
        throw (.rejected "keyword labels must be unique and ordered")
      return (children.dropLast, fields)
  | _ => return (children, [])

def literal : Tree String → Expression
  | .node head children => .node head (children.map literal)

def lower : Nat → Tree String → Checked Expression
  | 0, _ => throw (.incomplete "profile adapter depth exceeded")
  | _ + 1, tree@(.node "scir.text" children) =>
      match children with
      | [] | [.node _ []] => return literal tree
      | _ => throw (.rejected "text payload is an optional literal leaf")
  | _ + 1, .node "scir.ref" [.node name []] => return .var name
  | _ + 1, .node "scir.ref" _ => throw (.rejected "reference payload is one literal leaf")
  | _ + 1, .node "scir.kw" _ => throw (.rejected "keyword container is not an expression")
  | fuel + 1, .node head children => do
      let (positional, fields) ← parts children
      let args ← positional.mapM (lower fuel)
      let named ← fields.mapM fun (key, value) => return Pattern.node key [← lower fuel value]
      return .node head (args ++ if named.isEmpty then [] else [.node "scir.kw" named])

def native : Expression → Tree String
  | .var name => .node "scir.ref" [.node name []]
  | .node head children => .node head (children.map native)

def expressionPaths : Nat → Tree String → Checked (List (List Nat))
  | 0, _ => throw (.incomplete "path adapter depth exceeded")
  | _ + 1, .node "scir.text" _ => return [[]]
  | _ + 1, .node "scir.ref" _ => return [[]]
  | fuel + 1, .node _ children => do
      let (positional, fields) ← parts children
      let args ← positional.zipIdx.mapM fun (child, index) => do
        return (← expressionPaths fuel child).map (index :: ·)
      let named ← fields.zipIdx.mapM fun ((_, value), index) => do
        return (← expressionPaths fuel value).map (fun path => [positional.length, index, 0] ++ path)
      return [] :: (args.flatten ++ named.flatten)

structure Definition where
  name : String
  body : Expression
  dependencies : List String

def plainTuple : Tree String → Checked (List (Tree String))
  | .node "scir.tuple" children => do
      let (args, fields) ← parts children
      if !fields.isEmpty then throw (.rejected "record metadata requires a positional tuple")
      return args
  | _ => throw (.rejected "record metadata requires a tuple")

def definition (tree : Tree String) : Checked Definition := do
  let expression ← lower 129 tree
  let .node "record" children := tree | throw (.rejected "expected a working record")
  let (args, fields) ← parts children
  let [identifier, kind, body] := args | throw (.rejected "record arity must be three")
  let name ← leaf identifier
  if (← leaf kind) != "Definition" then throw (.rejected "expected Definition kind")
  for (key, value) in fields do
    if ["id", "kind", "payload"].contains key then throw (.rejected "reserved record slot")
    if key == "status" then let _ ← leaf value
    if ["dependsOn", "supersedes", "scope", "evidence"].contains key then
      let items ← plainTuple value
      if ["dependsOn", "supersedes"].contains key && !items.all (fun item =>
          match item with | .node "scir.ref" [_] => true | _ => false) then
        throw (.rejected "dependency metadata requires references")
  return ⟨name, ← lower 129 body, references expression⟩

def acyclic : Nat → List Definition → List String → Checked Unit
  | _, [], _ => return ()
  | 0, _, _ => throw (.rejected "cyclic definition environment")
  | fuel + 1, remaining, resolved => do
      let ready := remaining.filter (fun entry => entry.dependencies.all resolved.contains)
      if ready.isEmpty then throw (.rejected "cyclic definition environment")
      let names := ready.map Definition.name
      acyclic fuel (remaining.filter (fun entry => !names.contains entry.name)) (resolved ++ names)

def environment (document : List (Tree String)) : Checked (List Definition) := do
  let entries ← document.mapM definition
  let names := entries.map Definition.name
  if names.eraseDups.length != names.length then throw (.rejected "duplicate definition ID")
  if !entries.all (fun entry => entry.dependencies.all names.contains) then
    throw (.rejected "unresolved definition reference")
  acyclic entries.length entries []
  return entries

def bounded (document : List (Tree String)) (nodes depth : Nat) : Checked Unit := do
  let _ ← document.foldlM (fun budget tree => remainingNodes (depth + 1) budget tree) nodes
  return ()

def normalize (entries : List Definition) (nodes depth : Nat) :
    Nat → List Expression → Checked (List Expression)
  | fuel, document => do
      -- Each unresolved reference is two native nodes but at least one final
      -- node. Intermediate raw depth can exceed final depth by one literal ID.
      bounded (document.map native) (2 * nodes) (depth + 1)
      let names := entries.map Definition.name
      if !(document.flatMap references).any names.contains then
        bounded (document.map native) nodes depth
        return document
      match fuel with
      | 0 => throw (.rejected "normalization did not resolve the acyclic environment")
      | rest + 1 =>
          let σ := fun name => ((entries.find? (fun entry => entry.name == name)).map Definition.body).getD (.var name)
          normalize entries nodes depth rest (document.map (substitute σ))

def rootRecordIds (document : List (Tree String)) : Checked (List String) := do
  let found ← document.mapM fun tree => do
    match tree with
    | .node "record" children =>
        let (args, _) ← parts children
        match args with
        | [.node name [], _, _] => return if reserved name then [] else [name]
        | _ => return []
    | _ => return []
  return found.flatten

def complete (values : List (String × Json)) : Json :=
  Json.mkObj (("status", toJson "complete") :: values)

def evaluate (request : Json) : Checked Json := do
  let version ← checked (← checked (request.getObjVal? "version")).getStr?
  if version != "scir-definition-reference/1" then throw (.rejected "unsupported reference revision")
  let nodes ← checked (← checked (request.getObjVal? "max_nodes")).getNat?
  let depth ← checked (← checked (request.getObjVal? "max_depth")).getNat?
  if nodes == 0 || depth > 128 then throw (.rejected "invalid output bounds")
  if nodes > 4096 then throw (.incomplete "outside reference output scope")
  let document ← decode (← checked (request.getObjVal? "document"))
  let expressions ← document.mapM (lower 129)
  let definitions ← decode (← checked (request.getObjVal? "definitions"))
  let entries ← environment definitions
  let operation ← checked (← checked (request.getObjVal? "operation")).getStr?
  match operation with
  | "expand" =>
      let result ← normalize entries nodes depth entries.length expressions
      return complete [("document", encode (result.map native))]
  | "factor" =>
      let expected ← decode (← checked (request.getObjVal? "expected_document"))
      if expected != document then throw (.rejected "stale document selection")
      let name ← symbol (← checked (request.getObjVal? "definition_id"))
      if reserved name then throw (.rejected "definition ID must be ordinary")
      let taken := entries.map Definition.name ++ expressions.flatMap references ++ (← rootRecordIds document)
      if taken.contains name then throw (.rejected "definition ID is not fresh")
      let path ← (← checked (← checked (request.getObjVal? "path")).getArr?).toList.mapM
        (fun value => checked value.getNat?)
      let allowed ← document.zipIdx.mapM fun (tree, index) => do
        return (← expressionPaths 129 tree).map (index :: ·)
      if !allowed.flatten.contains path then throw (.rejected "selection is not an expression path")
      let (context, body) ← required "invalid selection" (select path (.node "$document" expressions))
      let .node _ replaced := plug context (.var name) | throw (.rejected "invalid document context")
      let candidate := replaced.map native
      let _ ← candidate.mapM (lower 129)
      let named := definitions ++ [.node "record" [.node name [], .node "Definition" [], native body]]
      let extended ← environment named
      let result ← normalize extended nodes depth extended.length replaced
      return complete [("document", ← encodeChecked candidate), ("definitions", ← encodeChecked named),
        ("expanded", encode (result.map native))]
  | _ => throw (.rejected "unsupported reference operation")

def response (source : String) : Json :=
  match checked (Json.parse source) >>= evaluate with
  | .ok value => value
  | .error (.rejected message) => Json.mkObj [("status", toJson "rejected"), ("message", toJson message)]
  | .error (.incomplete message) => Json.mkObj [("status", toJson "incomplete"), ("message", toJson message)]

end SCIR.DefinitionReference

def main : IO Unit := do
  let input ← IO.getStdin
  let output ← IO.getStdout
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    output.putStrLn ((SCIR.DefinitionReference.response line).compress)
