import Lean

/- A bounded reading boundary for specification fixtures and native transports.
   Object keys are checked before constructing Lean.Json. Escaped UTF-16 pairs
   are combined and isolated surrogates fail. This executable parser is tested;
   no parser-correctness theorem is asserted. Numeric allocation is bounded.
   Inputs exceeding the declared bound report incomplete work. -/
namespace SCIR.StrictJson
open Lean

def whitespace (c : Char) : Bool := c == ' ' || c == '\n' || c == '\r' || c == '\t'
def skip (cs : List Char) : List Char := cs.dropWhile whitespace

def hexDigit (c : Char) : Except String Nat :=
  if '0' ≤ c && c ≤ '9' then return c.toNat - 48
  else if 'a' ≤ c && c ≤ 'f' then return c.toNat - 87
  else if 'A' ≤ c && c ≤ 'F' then return c.toNat - 55
  else throw "invalid hexadecimal escape"

def four : List Char → Except String (Nat × List Char)
  | a :: b :: c :: d :: rest => do
      return (4096 * (← hexDigit a) + 256 * (← hexDigit b) + 16 * (← hexDigit c) + (← hexDigit d), rest)
  | _ => throw "short Unicode escape"

def escaped : List Char → Except String (Char × List Char)
  | '"' :: rest => return ('"', rest)
  | '\\' :: rest => return ('\\', rest)
  | '/' :: rest => return ('/', rest)
  | 'b' :: rest => return ('\x08', rest)
  | 'f' :: rest => return ('\x0c', rest)
  | 'n' :: rest => return ('\n', rest)
  | 'r' :: rest => return ('\r', rest)
  | 't' :: rest => return ('\t', rest)
  | 'u' :: rest => do
      let (code, rest) ← four rest
      if 0xD800 ≤ code && code ≤ 0xDBFF then
        let '\\' :: 'u' :: tail := rest | throw "isolated high surrogate"
        let (low, tail) ← four tail
        if low < 0xDC00 || low > 0xDFFF then throw "invalid surrogate pair"
        return (Char.ofNat (0x10000 + 1024 * (code - 0xD800) + low - 0xDC00), tail)
      else if 0xDC00 ≤ code && code ≤ 0xDFFF then throw "isolated low surrogate"
      else return (Char.ofNat code, rest)
  | _ => throw "invalid JSON escape"

def stringBody : Nat → List Char → List Char → Except String (String × List Char)
  | 0, _, _ => throw "incomplete: string work bound"
  | _ + 1, '"' :: rest, acc => return (String.mk acc.reverse, rest)
  | fuel + 1, '\\' :: rest, acc => do
      let (c, rest) ← escaped rest
      stringBody fuel rest (c :: acc)
  | fuel + 1, c :: rest, acc =>
      if c.toNat < 32 then throw "unescaped JSON control character"
      else stringBody fuel rest (c :: acc)
  | _, [], _ => throw "unterminated JSON string"

def readString (cs : List Char) : Except String (String × List Char) :=
  match cs with
  | '"' :: rest => stringBody 2000001 rest []
  | _ => throw "expected JSON string"

def parseString (source : String) : Except String String := do
  let (value, rest) ← readString (skip source.toList)
  if !(skip rest).isEmpty then throw "trailing JSON string input"
  return value

def numberChar (c : Char) : Bool := c.isDigit || ['-', '+', '.', 'e', 'E'].contains c
def decimalDigit (c : Char) : Bool := '0' ≤ c && c ≤ '9'
def decimal (digits : List Char) : Nat := digits.foldl (fun n c => 10 * n + c.toNat - 48) 0

def number (cs : List Char) : Except String (Json × List Char) := do
  let word := cs.takeWhile numberChar
  if word.length > 4096 then throw "incomplete: JSON numeric allocation bound"
  let (negative, rest) := match word with | '-' :: rest => (true, rest) | _ => (false, word)
  let first :: _ := rest | throw "expected JSON integer"
  if !decimalDigit first then throw "expected JSON integer"
  let integral := rest.takeWhile decimalDigit
  if first == '0' && integral.length > 1 then throw "JSON leading zero"
  let rest := rest.drop integral.length
  let (fraction, rest) ← match rest with
    | '.' :: rest => do
        let digits := rest.takeWhile decimalDigit
        if digits.isEmpty then throw "empty JSON fractional part"
        pure (digits, rest.drop digits.length)
    | _ => pure ([], rest)
  let exponent ← match rest with
    | 'e' :: rest | 'E' :: rest => do
        let (minus, digits) := match rest with
          | '-' :: tail => (true, tail) | '+' :: tail => (false, tail) | _ => (false, rest)
        if digits.isEmpty || !digits.all decimalDigit then throw "invalid JSON exponent"
        if digits.length > 4 || decimal digits > 4096 then throw "incomplete: JSON exponent allocation bound"
        pure (if minus then -(Int.ofNat (decimal digits)) else Int.ofNat (decimal digits))
    | [] => pure (0 : Int)
    | _ => throw "invalid JSON number suffix"
  let coefficient := Int.ofNat (decimal (integral ++ fraction))
  let coefficient := if negative then -coefficient else coefficient
  let scale := Int.ofNat fraction.length - exponent
  let n : JsonNumber := if scale < 0 then ⟨coefficient * Int.ofNat (10 ^ (-scale).toNat), 0⟩
    else ⟨coefficient, scale.toNat⟩
  -- Preserve the integer-versus-floating lexical boundary of native row IDs.
  -- Lean's numeric equality may erase an exponent; native ID readers may not.
  let floating := word.any fun c => c == '.' || c == 'e' || c == 'E'
  let n := if floating && n.exponent == 0 then { n with mantissa := n.mantissa * 10, exponent := 1 } else n
  return (.num n, cs.drop word.length)

mutual
  def value : Nat → Nat → List Char → Except String (Json × List Char)
    | 0, _, _ => throw "incomplete: JSON value work bound"
    | _, 0, _ => throw "incomplete: JSON depth bound"
    | fuel + 1, depth + 1, cs => do
        match skip cs with
        | '"' :: rest =>
            let (s, rest) ← stringBody 2000001 rest []
            return (.str s, rest)
        | '[' :: rest => array fuel depth (skip rest) [] true
        | '{' :: rest => object fuel depth (skip rest) [] true
        | 't' :: 'r' :: 'u' :: 'e' :: rest => return (.bool true, rest)
        | 'f' :: 'a' :: 'l' :: 's' :: 'e' :: rest => return (.bool false, rest)
        | 'n' :: 'u' :: 'l' :: 'l' :: rest => return (.null, rest)
        | cs@(c :: _) =>
            if c == '-' || c.isDigit then number cs else throw "unexpected JSON token"
        | [] => throw "expected JSON value"

  def array : Nat → Nat → List Char → List Json → Bool → Except String (Json × List Char)
    | 0, _, _, _, _ => throw "incomplete: JSON array work bound"
    | fuel + 1, depth, cs, acc, emptyAllowed => do
        if emptyAllowed then
          if let ']' :: rest := cs then return (.arr acc.reverse.toArray, rest)
        let (item, rest) ← value fuel depth cs
        match skip rest with
        | ']' :: rest => return (.arr (item :: acc).reverse.toArray, rest)
        | ',' :: rest => array fuel depth (skip rest) (item :: acc) false
        | _ => throw "expected comma or closing JSON array"

  def object : Nat → Nat → List Char → List (String × Json) → Bool → Except String (Json × List Char)
    | 0, _, _, _, _ => throw "incomplete: JSON object work bound"
    | fuel + 1, depth, cs, acc, emptyAllowed => do
        if emptyAllowed then
          if let '}' :: rest := cs then return (Json.mkObj acc.reverse, rest)
        let (key, rest) ← readString cs
        if acc.any (fun pair => pair.1 == key) then throw "duplicate JSON object key"
        let ':' :: rest := skip rest | throw "expected JSON colon"
        let (item, rest) ← value fuel depth rest
        match skip rest with
        | '}' :: rest => return (Json.mkObj ((key, item) :: acc).reverse, rest)
        | ',' :: rest => object fuel depth (skip rest) ((key, item) :: acc) false
        | _ => throw "expected comma or closing JSON object"
end

def size : Nat → Json → Nat
  | 0, _ => 100001
  | fuel + 1, .arr values => 1 + (values.toList.map (size fuel)).sum
  | fuel + 1, .obj fields => fields.fold (fun n _ v => n + 1 + size fuel v) 1
  | _, _ => 1

def parse (source : String) : Except String Json := do
  if source.length > 2000000 then throw "incomplete: JSON source bound"
  let (result, rest) ← value (2 * source.length + 4) 129 source.toList
  if !(skip rest).isEmpty then throw "trailing JSON input"
  if size 130 result > 100000 then throw "incomplete: JSON aggregate value bound"
  return result

end SCIR.StrictJson
