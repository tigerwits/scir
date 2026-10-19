import NativeCodec

/- A deterministic synthetic corpus for independent realizations. Each output
   is a canonical working/1 record carrying source and expected observation as
   ordinary data. A consumer must compare its real parser/formatter/digest with
   these observations; reading this file alone establishes no conformance. -/
namespace SCIR.NativeCorpus
open Lean SCIR.Symbols SCIR.Native

def terms : List Native.Term :=
  let labels := ["A", "B", "é", "é", "😀", "scir.ref", "line\nbreak", "\x00"]
  let leaves := labels.map (fun s => Tree.node s [])
  labels.flatMap fun label => .node label [] ::
    leaves.map (fun a => .node label [a]) ++
    leaves.flatMap (fun a => leaves.map (fun b => .node label [a, b]))

def alternative : Native.Term → String
  | .node head [] => quote head
  | .node head children => quote head ++ "(\n" ++
      String.intercalate " ,\n" (children.map alternative) ++ ",\n)"

def text (value : String) : Native.Term :=
  .node "scir.text" (if value.isEmpty then [] else [.node value []])

def specimen (index : Nat) (source : String) : Native.Term :=
  let result := match parseDocument source with
    | .ok document => [text source, .node "complete" [], text (formatDocument document), .node (digest document) []]
    | .error (.rejected _) => [text source, .node "rejected" []]
    | .error (.incomplete _) => [text source, .node "incomplete" []]
  .node "record" [.node ("Case" ++ toString index) [], .node "NativeCase" [], .node "case" result]

def get (value : Except String α) : IO α := match value with
  | .ok x => pure x
  | .error e => throw (IO.userError e)

def sources (root : String) : IO (List String) := do
  let vectors ← get (StrictJson.parse (← IO.FS.readFile (root ++ "/conformance/native.json")))
  let positive ← get (← get (vectors.getObjVal? "content")).getArr?
  let positive ← positive.toList.mapM (fun v => get ((v.getObjVal? "source") >>= Json.getStr?))
  let negative ← get (← get (vectors.getObjVal? "reject_content")).getArr?
  let negative ← negative.toList.mapM (fun v => get v.getStr?)
  let leaves := [Tree.node "A" [], .node "B" [], .node "é" []]
  let documents := [[]] ++ terms.map (fun t => [t]) ++
    leaves.flatMap (fun a => leaves.map (fun b => [a, b]))
  let spellings := documents.flatMap fun document =>
    [formatDocument document, "# synthetic source\n" ++ String.intercalate ";\n" (document.map alternative) ++ "\n"]
  return positive ++ negative ++ spellings ++
    ["A# comment\nB", "\"\\ud83d\\ude00\"", "f(A\nB)", "A\n;", "f\n(A)", "?x(A)", "import x"]

def main (args : List String) : IO UInt32 := do
  let root := args.headD "."
  let input ← sources root
  let output := formatDocument (input.zipIdx.map (fun (source, index) => specimen index source))
  match (args[1]? : Option String) with
  | some path => IO.FS.writeFile (System.FilePath.mk path) output
  | none => (← IO.getStdout).putStr output
  return 0

end SCIR.NativeCorpus
