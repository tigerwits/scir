import StrictJson
import Sha256
import ReferenceCodec
import SubstitutionLaws
import Language

/- Executable native 1.0 grammar and canonical spelling. This file specifies
   an interoperable, bounded reference calculation, not a production library.
   The tests compare independent fixed spellings, digests, relation tables and
   rejected sources; generic parser/serializer correctness remains unproved. -/
namespace SCIR.Native
open Lean SCIR.Symbols SCIR.Substitution SCIR.ReferenceCodec

abbrev Term := Tree String
abbrev Document := List Term
abbrev OpenTerm := Pattern String String

def identifierFirst (c : Char) : Bool :=
  ('a' ≤ c && c ≤ 'z') || ('A' ≤ c && c ≤ 'Z') || c == '_'
def identifierRest (c : Char) : Bool := identifierFirst c || ('0' ≤ c && c ≤ '9')
def identifier (s : String) : Bool :=
  !s.isEmpty && identifierFirst (s.toList.headD '0') && s.toList.all identifierRest
def horizontal (c : Char) : Bool := [' ', '\t', '\r', '\x0c'].contains c

def quote (s : String) : String := Id.run do
  let mut out := "\""
  for c in s.toList do
    out := out ++ match c with
      | '"' => "\\\""
      | '\\' => "\\\\"
      | '\x08' => "\\b"
      | '\t' => "\\t"
      | '\n' => "\\n"
      | '\x0c' => "\\f"
      | '\r' => "\\r"
      | c => if c.toNat < 32 then
          "\\u00" ++ String.singleton (Sha256.digit (c.toNat / 16)) ++
            String.singleton (Sha256.digit (c.toNat % 16))
        else String.singleton c
  return out ++ "\""

def formatSymbol (s : String) : String := if identifier s then s else quote s

def formatTerm : Term → String
  | .node head [] => formatSymbol head
  | .node head children => formatSymbol head ++ "(" ++ String.intercalate ", " (children.map formatTerm) ++ ")"

def formatDocument (document : Document) : String :=
  String.join (document.map (fun tree => formatTerm tree ++ "\n"))

def digest (document : Document) : String :=
  Sha256.hex ("scir:1.0:document\n" ++ formatDocument document).toUTF8

inductive Token where
  | label : String → Token
  | variable : String → Token
  | left | right | comma | newline | semicolon
  deriving BEq, Repr

def tokenize : Nat → List Char → List Token → Checked (List Token)
  | 0, _, _ => throw (.incomplete "native token work bound")
  | _, [], acc => return acc.reverse
  | fuel + 1, cs@(c :: rest), acc => do
      if horizontal c then tokenize fuel rest acc
      else if c == '#' then tokenize fuel (rest.dropWhile (· != '\n')) acc
      else if c == '\n' then tokenize fuel rest (.newline :: acc)
      else if c == '(' then tokenize fuel rest (.left :: acc)
      else if c == ')' then tokenize fuel rest (.right :: acc)
      else if c == ',' then tokenize fuel rest (.comma :: acc)
      else if c == ';' then tokenize fuel rest (.semicolon :: acc)
      else if c == '"' then
        let (label, rest) ← checked (StrictJson.readString cs)
        if label.isEmpty then throw (.rejected "empty native symbol")
        tokenize fuel rest (.label label :: acc)
      else if c == '?' then
        let first :: _ := rest | throw (.rejected "missing capture name")
        if !identifierFirst first then throw (.rejected "invalid capture name")
        let name := rest.takeWhile identifierRest
        tokenize fuel (rest.drop name.length) (.variable (String.mk name) :: acc)
      else if identifierFirst c then
        let name := cs.takeWhile identifierRest
        tokenize fuel (cs.drop name.length) (.label (String.mk name) :: acc)
      else throw (.rejected "invalid native token")

def newlines (tokens : List Token) : List Token := tokens.dropWhile (· == .newline)

mutual
  def expression : Nat → Nat → Nat → List Token → Checked (OpenTerm × List Token × Nat)
    | 0, _, _, _ => throw (.incomplete "native parsing work bound")
    | _, _, 0, _ => throw (.incomplete "native node bound")
    | _, 0, _, _ => throw (.incomplete "native depth bound")
    | fuel + 1, depth + 1, nodes + 1, .label head :: rest => do
        match rest with
        | .left :: rest =>
            let (children, rest, nodes) ← arguments fuel depth nodes (newlines rest) []
            return (.node head children, rest, nodes)
        | _ => return (.node head [], rest, nodes)
    | _ + 1, _ + 1, nodes + 1, .variable name :: rest =>
        match rest with
        | .left :: _ => throw (.rejected "capture cannot be an application head")
        | _ => return (.var name, rest, nodes)
    | _, _, _, _ => throw (.rejected "expected native term")

  def arguments : Nat → Nat → Nat → List Token → List OpenTerm → Checked (List OpenTerm × List Token × Nat)
    | 0, _, _, _, _ => throw (.incomplete "native argument work bound")
    | fuel + 1, depth, nodes, tokens, acc => do
        let (child, rest, nodes) ← expression fuel depth nodes tokens
        match newlines rest with
        | .right :: rest => return ((child :: acc).reverse, rest, nodes)
        | .comma :: rest =>
            match newlines rest with
            | .right :: rest => return ((child :: acc).reverse, rest, nodes)
            | rest => arguments fuel depth nodes rest (child :: acc)
        | _ => throw (.rejected "expected comma or closing application")
end

def roots : Nat → Nat → Nat → List Token → List OpenTerm → Checked (List OpenTerm)
  | 0, _, _, _, _ => throw (.incomplete "native root work bound")
  | _, _, _, [], acc => return acc.reverse
  | fuel + 1, depth, nodes, tokens, acc => do
      let (term, rest, nodes) ← expression fuel depth nodes tokens
      match rest with
      | [] => return (term :: acc).reverse
      | .newline :: rest | .semicolon :: rest => roots fuel depth nodes (newlines rest) (term :: acc)
      | _ => throw (.rejected "expected root separator")

def parseOpen (source : String) (nodes : Nat := 100000) (depth : Nat := 128) : Checked (List OpenTerm) := do
  if nodes == 0 || depth > 128 then throw (.rejected "invalid native resource budget")
  if source.length > 2000000 then throw (.incomplete "native source bound")
  let tokens ← tokenize (source.length + 1) source.toList []
  roots (tokens.length * 2 + 4) (depth + 1) nodes (newlines tokens) []

def parseDocument (source : String) (nodes : Nat := 100000) (depth : Nat := 128) : Checked Document := do
  let expressions ← parseOpen source nodes depth
  expressions.mapM fun p => required "captures are not ground content" (instantiate (fun _ => none) p)

def surfacePattern : OpenTerm → Language.SurfacePattern String String
  | .var "_" => .wildcard
  | .var name => .variable name
  | .node head children => .node head (children.map surfacePattern)

def parsePattern (source : String) : Checked (Language.SurfacePattern String String) := do
  match ← parseOpen source with
  | [pattern] => return surfacePattern pattern
  | _ => throw (.rejected "expected one pattern")

def rowNat (value : Json) : Checked Nat := do
  match value with
  | .num ⟨.ofNat n, 0⟩ => return n
  | _ => throw (.rejected "expected nonnegative integer row identifier")

def tableRow (value : Json) (width : Nat) : Checked (List Json) := do
  let values ← checked value.getArr?
  if values.size != width then throw (.rejected "invalid native relation row width")
  return values.toList

def relationBuild (labels : List (Nat × String)) (edges : List (Nat × Nat × Nat)) :
    Nat → List Nat → Nat → Checked Term
  | 0, _, _ => throw (.incomplete "relation depth bound")
  | fuel + 1, trail, ident => do
      if trail.contains ident then throw (.rejected "cyclic relation table")
      let (_, label) ← required "unknown relation endpoint" (labels.find? (fun pair => pair.1 == ident))
      let children := (edges.filter (fun (parent, _, _) => parent == ident)).mergeSort
        (fun (_, a, _) (_, b, _) => a ≤ b)
      let values ← children.mapM (fun (_, _, child) => relationBuild labels edges fuel (ident :: trail) child)
      return .node label values

def decodeRelations (value : Json) (nodes : Nat := 100000) (depth : Nat := 128) : Checked Document := do
  if nodes == 0 || depth > 128 then throw (.rejected "invalid relation resource budget")
  let fields ← checked value.getObj?
  let keys := fields.fold (fun acc k _ => k :: acc) ([] : List String)
  if keys.length != 4 || !keys.all (["version", "nodes", "args", "roots"].contains) then
    throw (.rejected "unexpected native relation envelope")
  if (← checked (← checked (value.getObjVal? "version")).getStr?) != "scir-relations/1.0" then
    throw (.rejected "unsupported native relation version")
  let rawNodes ← checked (← checked (value.getObjVal? "nodes")).getArr?
  let rawArgs ← checked (← checked (value.getObjVal? "args")).getArr?
  let rawRoots ← checked (← checked (value.getObjVal? "roots")).getArr?
  if rawNodes.size > nodes || rawArgs.size > nodes || rawRoots.size > nodes then
    throw (.incomplete "native relation node bound")
  let labels ← rawNodes.toList.mapM fun row => do
    let [id, label] ← tableRow row 2 | throw (.rejected "invalid relation node")
    return (← rowNat id, ← symbol label)
  let edges ← rawArgs.toList.mapM fun row => do
    let [parent, position, child] ← tableRow row 3 | throw (.rejected "invalid relation argument")
    return (← rowNat parent, ← rowNat position, ← rowNat child)
  let rootRows ← rawRoots.toList.mapM fun row => do
    let [position, id] ← tableRow row 2 | throw (.rejected "invalid relation root")
    return (← rowNat position, ← rowNat id)
  let ids := labels.map Prod.fst
  let incoming := rootRows.map Prod.snd ++ edges.map (fun (_, _, child) => child)
  if ids.eraseDups.length != ids.length || incoming.eraseDups.length != incoming.length ||
      incoming.length != ids.length || !incoming.all ids.contains ||
      !edges.all (fun (parent, _, _) => ids.contains parent) then
    throw (.rejected "relation identities or incoming edges are invalid")
  let rootRows := rootRows.mergeSort (fun a b => a.1 ≤ b.1)
  if rootRows.map Prod.fst != List.range rootRows.length then
    throw (.rejected "root positions must be contiguous and unique")
  for id in ids do
    let children := (edges.filter (fun (parent, _, _) => parent == id)).mergeSort
      (fun (_, a, _) (_, b, _) => a ≤ b)
    if children.map (fun (_, position, _) => position) != List.range children.length then
      throw (.rejected "argument positions must be contiguous and unique")
  let document ← rootRows.mapM fun (_, id) => relationBuild labels edges (depth + 1) [] id
  if (documentOccurrences document).length != labels.length then
    throw (.rejected "unreachable relation occurrences")
  return document

def parseRelations (source : String) : Checked Document := do
  decodeRelations (← readJson source)

end SCIR.Native
