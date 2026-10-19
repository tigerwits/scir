import Lean

/- Executable SHA-256 reference for the fixed SCIR 1.0 digest domain.
   Algorithm and constants: FIPS 180-4, sections 4.1.2, 4.2.2, 5, and 6.2.
   https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf
   Known-answer and SCIR interoperability tests check this definition. It has
   no cryptographic correctness, collision resistance, or runtime proof here. -/
namespace SCIR.Sha256

def rotate (x n : UInt32) : UInt32 := (x >>> n) ||| (x <<< (32 - n))
def big0 (x : UInt32) : UInt32 := rotate x 2 ^^^ rotate x 13 ^^^ rotate x 22
def big1 (x : UInt32) : UInt32 := rotate x 6 ^^^ rotate x 11 ^^^ rotate x 25
def small0 (x : UInt32) : UInt32 := rotate x 7 ^^^ rotate x 18 ^^^ (x >>> 3)
def small1 (x : UInt32) : UInt32 := rotate x 17 ^^^ rotate x 19 ^^^ (x >>> 10)
def choose (x y z : UInt32) : UInt32 := (x &&& y) ^^^ (~~~x &&& z)
def majority (x y z : UInt32) : UInt32 := (x &&& y) ^^^ (x &&& z) ^^^ (y &&& z)

def initial : Array UInt32 := #[
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]

def constants : Array UInt32 := #[
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]

def padded (bytes : ByteArray) : ByteArray := Id.run do
  let mut result := bytes.push 0x80
  let zeros := (56 + 64 - result.size % 64) % 64
  for _ in [:zeros] do result := result.push 0
  let bits := bytes.size.toUInt64 * 8
  for i in [:8] do result := result.push ((bits >>> ((7 - i) * 8).toUInt64).toUInt8)
  return result

def wordAt (bytes : ByteArray) (start : Nat) : UInt32 :=
  (bytes[start]!.toUInt32 <<< 24) ||| (bytes[start + 1]!.toUInt32 <<< 16) |||
  (bytes[start + 2]!.toUInt32 <<< 8) ||| bytes[start + 3]!.toUInt32

def block (state : Array UInt32) (bytes : ByteArray) (offset : Nat) : Array UInt32 := Id.run do
  let mut schedule : Array UInt32 := #[]
  for i in [:16] do schedule := schedule.push (wordAt bytes (offset + 4 * i))
  for i in [16:64] do
    schedule := schedule.push (small1 schedule[i - 2]! + schedule[i - 7]! +
      small0 schedule[i - 15]! + schedule[i - 16]!)
  let mut a := state[0]!
  let mut b := state[1]!
  let mut c := state[2]!
  let mut d := state[3]!
  let mut e := state[4]!
  let mut f := state[5]!
  let mut g := state[6]!
  let mut h := state[7]!
  for i in [:64] do
    let first := h + big1 e + choose e f g + constants[i]! + schedule[i]!
    let second := big0 a + majority a b c
    h := g
    g := f
    f := e
    e := d + first
    d := c
    c := b
    b := a
    a := first + second
  return #[state[0]! + a, state[1]! + b, state[2]! + c, state[3]! + d,
    state[4]! + e, state[5]! + f, state[6]! + g, state[7]! + h]

def hash (bytes : ByteArray) : Array UInt32 := Id.run do
  let bytes := padded bytes
  let mut state := initial
  for i in [:bytes.size / 64] do state := block state bytes (64 * i)
  return state

def digit (n : Nat) : Char := Char.ofNat (if n < 10 then 48 + n else 87 + n)

def hex (bytes : ByteArray) : String := Id.run do
  let mut output := ""
  for word in hash bytes do
    for i in [:8] do output := output.push (digit (((word >>> ((7 - i) * 4).toUInt32) &&& 15).toNat))
  return output

end SCIR.Sha256
