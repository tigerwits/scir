import StrictJson
import Sha256

namespace SCIR.BoundaryTests
open Lean

def ensure (condition : Bool) (label : String) : IO Unit :=
  if condition then pure () else throw (IO.userError label)

def run : IO Nat := do
  let hashes := [
    ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    ("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq", "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")]
  for (source, expected) in hashes do ensure (Sha256.hex source.toUTF8 == expected) "SHA-256 known-answer vector"
  let accepted := ["null", "false", "true", "-12.5e+2", "[]", "{}", "[1,2,3]", "{\"a\":1,\"b\":2}"]
  for source in accepted do ensure (StrictJson.parse source |>.isOk) ("strict JSON rejected " ++ source)
  let rejected := ["", "{\"a\":1,\"a\":2}", "{\"a\":1,\"\\u0061\":2}", "[1,]", "{\"a\":1,}",
    "[01]", "[+1]", "[.1]", "[1.]", "[1e]", "[--1]", "true false", "\"\\ud800\"", "\"\\udfff\"",
    "\"\\ud800\\u0041\"", "\"a\nb\"", "[1] trailing", "1e1000000000", "1e-1000000000"]
  for source in rejected do ensure (!(StrictJson.parse source).isOk) ("strict JSON accepted " ++ source)
  ensure (match StrictJson.parseString "\"\\ud83d\\ude00\"" with | .ok s => s == "😀" | _ => false) "JSON supplementary scalar"
  ensure (match StrictJson.parseString "\"\\u0000\\b\\t\\n\\f\\r\\\"\\\\/\"" with
    | .ok s => s == "\x00\x08\t\n\x0c\r\"\\/" | _ => false) "JSON scalar escapes"
  let exponent ← match StrictJson.parse "1e0" with
    | .ok (.num n) => pure n.exponent
    | _ => throw (IO.userError "strict number fixture")
  ensure (exponent != 0) "floating lexical spelling must not become native integer ID"
  return hashes.length + accepted.length + rejected.length + 3

end SCIR.BoundaryTests
