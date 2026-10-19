import NativeCodec
import DefinitionReference
import ProfileLaws

/- structured/1 and working/1 are explicitly selected profiles over the native
   algebra. They do not reserve any native label, assign truth, or execute an
   import. A working collection permits reference cycles and contradictory
   records; named Definition environments impose their separate acyclic rule.
   This finite executable closure is compared with an independent fixed point
   over every three-node graph. ProfileLaws proves the abstract Reach laws,
   not the correctness of these parsing, indexing, or ordering calculations. -/
namespace SCIR.Working
open SCIR.Symbols SCIR.Substitution SCIR.ReferenceCodec SCIR.DefinitionReference

structure Record where
  id : String
  kind : String
  raw : Tree String
  references : List String
  dependencies : List String

def record (tree : Tree String) : Checked Record := do
  let value ← lower 129 tree
  let .node "record" children := tree | throw (.rejected "expected a working record")
  let (args, fields) ← parts children
  let [identifier, kind, _] := args | throw (.rejected "working record requires ID, kind, payload")
  let id ← leaf identifier
  let kind ← leaf kind
  let mut dependencies := []
  for (key, value) in fields do
    if ["id", "kind", "payload"].contains key then throw (.rejected "reserved working slot")
    if key == "status" then let _ ← leaf value
    if ["dependsOn", "supersedes", "scope", "evidence"].contains key then
      let items ← plainTuple value
      if ["dependsOn", "supersedes"].contains key then
        let refs ← items.mapM fun item =>
          match item with
          | .node "scir.ref" [.node id []] => pure id
          | _ => throw (.rejected "working dependency requires an explicit reference")
        if key == "dependsOn" then dependencies := refs
  return ⟨id, kind, tree, SCIR.Definitions.references value, dependencies⟩

def collection (identity : String) (document : Native.Document) : Checked (List Record) := do
  if identity.isEmpty then throw (.rejected "collection identity is empty")
  let _ ← document.foldlM (fun budget term => remainingNodes 129 budget term) 100000
  if (Native.formatDocument document).toUTF8.size > 16000000 then
    throw (.incomplete "working canonical byte bound")
  let records ← document.mapM record
  let ids := records.map Record.id
  if ids.eraseDups.length != ids.length then throw (.rejected "duplicate working ID")
  if !(records.flatMap Record.references).all ids.contains then throw (.rejected "unresolved local reference")
  return records

def visit (edges : String → List String) : Nat → List String → List String → Checked (List String)
  | _, [], seen => return seen
  | 0, _, _ => throw (.incomplete "closure work bound")
  | fuel + 1, id :: pending, seen =>
      if seen.contains id then visit edges fuel pending seen
      else visit edges fuel (edges id ++ pending) (id :: seen)

def select (records : List Record) (seeds : List String) : Checked Native.Document := do
  let ids := records.map Record.id
  if !seeds.all ids.contains then throw (.rejected "missing selection seed")
  let edges := fun id => ((records.find? (fun record => record.id == id)).map Record.references).getD []
  let selected ← visit edges (seeds.length + (records.flatMap Record.references).length + records.length + 1) seeds []
  return (records.filter (fun record => selected.contains record.id)).map Record.raw

def affected (records : List Record) (seeds : List String) : Checked Native.Document := do
  let ids := records.map Record.id
  if !seeds.all ids.contains then throw (.rejected "missing review seed")
  let edges := fun id => (records.filter (fun record => record.dependencies.contains id)).map Record.id
  let selected ← visit edges (seeds.length + (records.flatMap Record.dependencies).length + records.length + 1) seeds []
  return (records.filter (fun record => selected.contains record.id)).map Record.raw

end SCIR.Working
