import ReferenceCodec

/- Executable specification JSONL boundary. The forest
   transport is the existing scir-relations/1.0 canonical occurrence table.
   This codec and its resource checks are tested, not covered by SymbolLaws. -/
open Lean SCIR.Symbols SCIR.ReferenceCodec

namespace SCIR.SymbolReference

def evaluate (request : Json) : Checked Json := do
  let version ← checked (← checked (request.getObjVal? "version")).getStr?
  let operation ← checked (← checked (request.getObjVal? "operation")).getStr?
  if version != "scir-symbol-reference/1" || operation != "relabel" then
    throw (.rejected "unsupported reference operation or revision")
  let document ← decode (← checked (request.getObjVal? "document"))
  let rawNames ← checked (← checked (request.getObjVal? "renaming")).getArr?
  if rawNames.size > 4096 then throw (.incomplete "reference renaming limit exceeded")
  let names ← rawNames.toList.mapM fun item => do
    let cells ← row item 2
    return (← symbol (← required "missing source" cells[0]?),
      ← symbol (← required "missing target" cells[1]?))
  if (names.map Prod.fst).eraseDups.length != names.length then
    throw (.rejected "duplicate renaming source")
  let rename := fun label => ((names.find? (fun pair => pair.1 == label)).map Prod.snd).getD label
  let result := relabelDocument rename document
  let occurrences := (documentOccurrences result).map fun (path, label) =>
    arr [toJson path, toJson label]
  return Json.mkObj [("status", toJson "complete"), ("document", encode result),
    ("occurrences", arr occurrences)]

def response (source : String) : Json :=
  match readJson source >>= evaluate with
  | .ok value => value
  | .error (.rejected message) => Json.mkObj [("status", toJson "rejected"), ("message", toJson message)]
  | .error (.incomplete message) => Json.mkObj [("status", toJson "incomplete"), ("message", toJson message)]

end SCIR.SymbolReference

def SCIR.SymbolReference.main : IO Unit := do
  let input ← IO.getStdin
  let output ← IO.getStdout
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    output.putStrLn ((SCIR.SymbolReference.response line).compress)
