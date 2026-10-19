import NativeCodec
import BoundaryTests
import SymbolReference
import SubstitutionReference
import DefinitionReference
import WorkingSpec

/- A specification conformance driver, deliberately separate from the pure
   statements and proofs. It reads local synthetic fixtures only. Frozen
   reference vectors came from the independently realized S1-S3 gates at
   4df43ba874d6750e9ab16b21903b87e8879b601c. Matching errors compares completion
   classes, since incidental diagnostic wording is not native semantics.
   No test of these finite corpora proves universal codec or backend correctness. -/
namespace SCIR.Conformance
open Lean SCIR.Symbols SCIR.ReferenceCodec SCIR.Native SCIR.BoundaryTests

def admitted (value : Checked α) : IO α := match value with
  | .ok x => pure x
  | .error (.rejected message) => throw (IO.userError ("unexpected rejection: " ++ message))
  | .error (.incomplete message) => throw (IO.userError ("unexpected incomplete result: " ++ message))

def json (source : String) : IO Json := match StrictJson.parse source with
  | .ok value => pure value
  | .error error => throw (IO.userError error)

def member (value : Json) (key : String) : IO Json :=
  match value.getObjVal? key with | .ok item => pure item | .error e => throw (IO.userError e)
def string (value : Json) : IO String :=
  match value.getStr? with | .ok item => pure item | .error e => throw (IO.userError e)
def array (value : Json) : IO (Array Json) :=
  match value.getArr? with | .ok item => pure item | .error e => throw (IO.userError e)

def observation (value : Json) : Json :=
  match value.getObjVal? "status" >>= Json.getStr? with
  | .ok "complete" => value
  | .ok status => Json.mkObj [("status", toJson status)]
  | .error _ => value

def checkCorpus (root name : String) (expectedCount : Nat) (response : String → Json) : IO Nat := do
  let inputs ← IO.FS.lines (root ++ "/conformance/" ++ name ++ "-inputs.jsonl")
  let expected ← IO.FS.lines (root ++ "/conformance/" ++ name ++ "-expected.jsonl")
  ensure (inputs.size == expectedCount && expected.size == expectedCount) (name ++ " corpus length changed")
  for i in [:inputs.size] do
    let want ← json expected[i]!
    let got := response inputs[i]!
    ensure (observation got == observation want) (name ++ " conformance case " ++ toString i)
  IO.println (name ++ " reference cases: " ++ toString inputs.size)
  return inputs.size

def permute (wire : Json) (rename : Bool) : Json := Id.run do
  let nat := fun j => (j.getNat?).toOption.getD 0
  let ident := fun j => if rename then toJson (7 + 3 * nat j) else j
  let rows := fun key => ((wire.getObjVal? key >>= Json.getArr?).toOption.getD #[]).toList.reverse
  let nodes := (rows "nodes").map fun row =>
    let columns := row.getArr?.toOption.getD #[]
    arr [ident columns[0]!, columns[1]!]
  let args := (rows "args").map fun row =>
    let columns := row.getArr?.toOption.getD #[]
    arr [ident columns[0]!, columns[1]!, ident columns[2]!]
  let roots := (rows "roots").map fun row =>
    let columns := row.getArr?.toOption.getD #[]
    arr [columns[0]!, ident columns[1]!]
  return Json.mkObj [("version", toJson "scir-relations/1.0"), ("nodes", arr nodes),
    ("args", arr args), ("roots", arr roots)]

def nativeGoldens (root : String) : IO Nat := do
  let source ← IO.FS.readFile (root ++ "/conformance/native.json")
  ensure (Sha256.hex source.toUTF8 == "fcb779d1834539e4c8d3fa380574ac454b511802fa4fe798124dc10287d29365") "frozen native vector bytes changed"
  let vectors ← json source
  ensure ((← string (← member vectors "format")) == "1.0") "native format changed"
  let content ← array (← member vectors "content")
  for vector in content do
    let name ← string (← member vector "name")
    let document ← admitted (parseDocument (← string (← member vector "source")))
    ensure (formatDocument document == (← string (← member vector "canonical"))) (name ++ " canonical spelling")
    ensure (digest document == (← string (← member vector "sha256"))) (name ++ " domain digest")
  let transport ← member vectors "transport"
  let wire ← member transport "wire"
  let canonical ← string (← member transport "canonical")
  let document ← admitted (decodeRelations wire)
  ensure (formatDocument document == canonical && encode document == wire) "frozen occurrence table"
  for rename in [false, true] do
    ensure (formatDocument (← admitted (decodeRelations (permute wire rename))) == canonical) "relation row/ID invariance"
  let rejected ← array (← member vectors "reject_content")
  for bad in rejected do ensure (!(parseDocument (← string bad)).isOk) "frozen invalid source accepted"
  return content.size * 2 + rejected.size + 4

def smallTerms : List Native.Term :=
  let labels := ["A", "B", "é", "é", "😀", "scir.ref", "line\nbreak", "\x00"]
  let leaves := labels.map (fun s => Tree.node s [])
  labels.flatMap fun label => .node label [] ::
    leaves.map (fun a => .node label [a]) ++
    leaves.flatMap (fun a => leaves.map (fun b => .node label [a, b]))

def finiteNative : IO Nat := do
  let leaves := [Tree.node "A" [], .node "B" [], .node "é" []]
  let documents := [[]] ++ smallTerms.map (fun t => [t]) ++
    leaves.flatMap (fun a => leaves.map (fun b => [a, b]))
  for document in documents do
    ensure ((← admitted (parseDocument (formatDocument document))) == document) "finite native text reconstruction"
    ensure ((← admitted (decodeRelations (permute (encode document) true))) == document) "finite general transport reconstruction"
  let exact := [
    ("A#comment\nB", "A\nB\n"), ("f(\nA,\nB,\n)", "f(A, B)\n"),
    ("\"\\ud83d\\ude00\"", "\"😀\"\n"), ("\"Alice\"", "Alice\n"),
    ("A\r\nB", "A\nB\n"), ("\"#\"", "\"#\"\n")]
  for (source, expected) in exact do
    ensure (formatDocument (← admitted (parseDocument source)) == expected) "authored native grammar vector"
  let failures := [";", "A\n;", "A; ;B", "f(A\nB)", "f\n(A)", "?x(A)", "?1", "f(A);()", "'A'", "import x"]
  for source in failures do ensure (!(parseDocument source).isOk) ("native invalid grammar accepted: " ++ source)
  ensure (!(parseDocument "f(A)" 1).isOk && !(parseDocument "f(A)" 10 0).isOk) "native resource admission"
  let quoted ← admitted (parsePattern "\"?x\"")
  ensure (match quoted with | .node "?x" [] => true | _ => false) "quoted capture remains literal"
  let pattern ← admitted (parsePattern "f(?x, ?_)")
  ensure (match pattern with | .node "f" [.variable "x", .wildcard] => true | _ => false) "native pattern grammar"
  let badTables := [
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[0,\"A\"]],\"args\":[],\"roots\":[[0,0]],\"extra\":0}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[0,\"A\"],[0,\"B\"]],\"args\":[],\"roots\":[[0,0]]}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[0,\"A\"]],\"args\":[],\"roots\":[[1,0]]}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[0,\"A\"]],\"args\":[[0,0,0]],\"roots\":[]}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[0.0,\"A\"]],\"args\":[],\"roots\":[[0,0]]}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[0e0,\"A\"]],\"args\":[],\"roots\":[[0,0]]}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[[false,\"A\"]],\"args\":[],\"roots\":[[0,0]]}",
    "{\"version\":\"scir-relations/1.0\",\"nodes\":[],\"nodes\":[],\"args\":[],\"roots\":[]}"]
  for source in badTables do ensure (!(parseRelations source).isOk) "malformed relation table accepted"
  return documents.length * 2 + exact.length + failures.length + badTables.length + 3

def fixedPoint (ids : List String) (edges : String → List String) : Nat → List String → List String
  | 0, included => included
  | fuel + 1, included => fixedPoint ids edges fuel
      (ids.filter (fun id => included.contains id || included.any (fun origin => (edges origin).contains id)))

def finiteClosure : IO Nat := do
  let ids := ["A", "B", "C"]
  for graph in [:512] do
    let edges := fun id => (ids.zipIdx).filterMap fun (target, j) =>
      let i := (ids.idxOf id)
      if (graph / 2 ^ (3 * i + j)) % 2 == 1 then some target else none
    for mask in [:8] do
      let seeds := ids.zipIdx.filterMap fun (id, i) => if (mask / 2 ^ i) % 2 == 1 then some id else none
      let found ← admitted (Working.visit edges 32 seeds [])
      let want := fixedPoint ids edges 3 seeds
      ensure (ids.all (fun id => found.contains id == want.contains id)) "closure differs from independent fixed point"
  return 4096

def profileCases : IO Nat := do
  let positives := ["\"scir.text\"", "\"scir.text\"(\"scir.ref\")", "\"scir.ref\"(\"scir.text\")",
    "f(A, \"scir.kw\"(a(B), z(C)))", "\"scir.tuple\"(A, \"scir.kw\"(a(B)))"]
  for source in positives do
    let terms ← admitted (parseDocument source)
    for term in terms do let _ ← admitted (DefinitionReference.lower 129 term)
  let negatives := ["\"scir.ref\"", "\"scir.ref\"(A, B)", "\"scir.text\"(f(A))", "\"scir.kw\"(a(A))",
    "f(\"scir.kw\")", "f(\"scir.kw\"(z(A), a(B)))", "f(\"scir.kw\"(a(A), a(B)))"]
  for source in negatives do
    for term in (← admitted (parseDocument source)) do
      ensure (!(DefinitionReference.lower 129 term).isOk) "malformed structured profile accepted"
  let document ← admitted (parseDocument "record(A, Claim, says(yes), \"scir.kw\"(dependsOn(\"scir.tuple\"(\"scir.ref\"(B)))))\nrecord(B, Claim, says(no), \"scir.kw\"(evidence(\"scir.tuple\"(\"scir.ref\"(A)))))\nrecord(C, Note, unrelated)")
  let records ← admitted (Working.collection "synthetic" document)
  ensure ((← admitted (Working.select records ["A"])) == document.take 2) "working cycles terminate in source order"
  ensure ((← admitted (Working.affected records ["B"])) == document.take 2) "reverse dependencies"
  ensure ((← admitted (Working.affected records ["A"])) == document.take 1) "citations are not dependencies"
  ensure (!(Working.collection "" document).isOk) "empty collection ID"
  ensure (!(Working.collection "synthetic" (document ++ document.take 1)).isOk) "duplicate record identity"
  ensure (!(Working.collection "synthetic" (document.take 1)).isOk) "dangling local reference"
  return positives.length + negatives.length + 6

def exampleCases (root : String) : IO Nat := do
  for name in ["native", "working", "definitions", "definition-use"] do
    let source ← IO.FS.readFile (root ++ "/examples/" ++ name ++ ".scir")
    ensure (formatDocument (← admitted (parseDocument source)) == source) (name ++ " example canonical spelling")
  let working ← admitted (parseDocument (← IO.FS.readFile (root ++ "/examples/working.scir")))
  let _ ← admitted (Working.collection "synthetic" working)
  let definitions ← admitted (parseDocument (← IO.FS.readFile (root ++ "/examples/definitions.scir")))
  let entries ← admitted (DefinitionReference.environment definitions)
  let document ← admitted (parseDocument (← IO.FS.readFile (root ++ "/examples/definition-use.scir")))
  let expressions ← admitted (document.mapM (DefinitionReference.lower 129))
  let expanded ← admitted (DefinitionReference.normalize entries 4096 128 entries.length expressions)
  ensure (formatDocument (expanded.map DefinitionReference.native) == "use(pair(red, red), Pair, \"scir.text\"(Pair))\n") "definition example literal roles"
  return 6

def main (args : List String) : IO UInt32 := do
  let root := args.headD "."
  let boundaries ← BoundaryTests.run
  let goldens ← nativeGoldens root
  let native ← finiteNative
  let closure ← finiteClosure
  let profiles ← profileCases
  let examples ← exampleCases root
  let symbols ← checkCorpus root "symbol" 397 SymbolReference.response
  let substitutions ← checkCorpus root "substitution" 3029 SubstitutionReference.response
  let definitions ← checkCorpus root "definition" 5594 DefinitionReference.response
  IO.println s!"PASS: boundary={boundaries}; native={goldens + native}; closure={closure}; profiles={profiles}; examples={examples}; references={symbols + substitutions + definitions}"
  return 0

end SCIR.Conformance

def main := SCIR.Conformance.main
