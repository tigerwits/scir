import NativeCorpus
import DefinitionReference

/- Native interoperability observations for the explicit Definition profile.
   Requests whose protocol, operation, core forest or scalar fields cannot be represented by this
   corpus schema are counted and skipped; the full JSONL gate retains them.
   Payload fields are operation, document text, definitions text, node bound,
   depth bound, path tuple, expected document digest, fresh-ID text, status,
   and (on completion) result document text, result definitions text and expanded
   document text. Canonical source is carried as opaque scir.text throughout.
   Consumer-specific admission limits are deliberately not selected here. -/
namespace SCIR.DefinitionCorpus
open Lean SCIR.Symbols SCIR.ReferenceCodec SCIR.NativeCorpus

def nativeDoc (request : Json) (key : String) : Checked Native.Document := do
  decode (← checked (request.getObjVal? key))

def number (n : Nat) : Tree String := .node (toString n) []

def specimen (index : Nat) (source : String) : Checked (Tree String) := do
  let request ← readJson source
  let version ← checked (← checked (request.getObjVal? "version")).getStr?
  if version != "scir-definition-reference/1" then throw (.rejected "protocol-only request is outside native schema")
  let operation ← checked (← checked (request.getObjVal? "operation")).getStr?
  if operation != "factor" && operation != "expand" then throw (.rejected "operation is outside typed native schema")
  let document ← nativeDoc request "document"
  let definitions ← nativeDoc request "definitions"
  let nodes ← checked (← checked (request.getObjVal? "max_nodes")).getNat?
  let depth ← checked (← checked (request.getObjVal? "max_depth")).getNat?
  if nodes > 4096 then throw (.incomplete "outside Definition reference scope")
  let (path, expected, name) ← if operation == "factor" then do
      let path ← (← checked (← checked (request.getObjVal? "path")).getArr?).toList.mapM
        (fun value => checked value.getNat?)
      let name ← checked (← checked (request.getObjVal? "definition_id")).getStr?
      pure (path, ← nativeDoc request "expected_document", name)
    else pure ([], document, "unused")
  let base := [.node operation [], text (Native.formatDocument document), text (Native.formatDocument definitions),
    number nodes, number depth, .node "scir.tuple" (path.map number), .node (Native.digest expected) [], text name]
  let result ← match DefinitionReference.evaluate request with
    | .ok response => do
        let changed ← nativeDoc response "document"
        let named ← if operation == "factor" then nativeDoc response "definitions" else pure definitions
        let expanded ← if operation == "factor" then nativeDoc response "expanded" else pure changed
        pure [Tree.node "complete" [], text (Native.formatDocument changed),
          text (Native.formatDocument named), text (Native.formatDocument expanded)]
    | .error (.rejected _) => pure [.node "rejected" []]
    | .error (.incomplete _) => pure [.node "incomplete" []]
  return .node "record" [.node ("DefinitionCase" ++ toString index) [], .node "DefinitionCase" [],
    .node "case" (base ++ result)]

def main (args : List String) : IO UInt32 := do
  let root := args.headD "."
  let inputs ← IO.FS.lines (root ++ "/conformance/definition-inputs.jsonl")
  let mut output := ""
  let mut included := 0
  let mut skipped := 0
  for i in [:inputs.size] do
    match specimen i inputs[i]! with
    | .ok record =>
        output := output ++ Native.formatTerm record ++ "\n"
        included := included + 1
    | .error _ => skipped := skipped + 1
  if included != 5588 || skipped != 6 then
    throw (IO.userError s!"unexpected native Definition subset: {included} included; {skipped} excluded")
  match (args[1]? : Option String) with
  | some path => IO.FS.writeFile (System.FilePath.mk path) output
  | none => (← IO.getStdout).putStr output
  (← IO.getStderr).putStrLn s!"DEFINITION_CORPUS_INCLUDED={included}; OUTSIDE_NATIVE_SCHEMA={skipped}"
  return 0

end SCIR.DefinitionCorpus
