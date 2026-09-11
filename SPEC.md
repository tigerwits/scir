# SCIR v0 Specification

SCIR (Symbolic Content IR) is a tiny expression language for exchanging
content between LLM agents.

Thesis: SCIR formalizes the topology/composition of meaning while leaving
the meanings of ordinary symbols neural and informal.

This document is the v0 language definition. It is not a type system,
ontology, knowledge graph, planner, or theorem prover.

## Grammar

Whitespace is ignored except that `?` must be adjacent to its identifier.

```
expr       ::=  atom | variable | call
atom       ::=  ident
variable   ::=  "?" ident
call       ::=  ident "(" [arglist] ")"
arglist    ::=  expr ("," expr)*

ident      ::=  letter (letter | digit)*
letter     ::=  "A"..."Z" | "a"..."z" | "_"
digit      ::=  "0"..."9"
```

- There are no grouping parentheses, number literals, string literals, or comments.
- A call head is an identifier, never an expression.
- `Alice` is an atom. `Alice()` is a distinct 0-argument call.
- `?x` is a variable named `x`. `?` alone is a parse error.
- Trailing, leading, or doubled commas are parse errors.
- A complete input is exactly one `expr`. Trailing tokens are a parse error.

### Canonical print

`str(expr)` is the unique canonical surface form:

- no whitespace except a single space after each comma
- variables printed as `?` immediately followed by the name
- call arguments printed in order, separated by `", "`

Parse/print round-trip preserves canonical structure:

```
parse(str(parse(s))) == parse(s)
```

Whitespace in input is not preserved.

## Expression tree

```
Expr := Atom | Variable | Call
```

Examples:

```
Alice
?x
wrong(Chart)
email(Alice, Bob, Report)
think(Bob, wrong(Chart))
before(email(Alice, Bob, Report), leave(Alice, Office))
```

Nodes are immutable. Structural equality and hashing are by constructor and
contents: `Atom("Alice")` is not `Variable("Alice")` and is not `Call("Alice", ())`.

## Ordinary symbols

Identifiers used as atoms or as call heads have no formally specified
semantics. Their meaning is interpreted by the LLM.

These are ordinary symbols, not operators of the kernel:

```
email  think  wrong  before  yesterday  mistakenly  leave  ...
```

The language does not rewrite ordinary symbols (`email(...)` is not
`send(...)`).

## Reserved structural operators

Only the following call heads have deterministic structural semantics.
They are reserved solely as *calls* of the stated arity. An atom named
`and` is still just an atom.

| Head | Arity | Meaning |
|---|---|---|
| `not` | 1 | negation of its argument |
| `and` | ≥ 2 | conjunction of its arguments, in order |
| `or` | ≥ 2 | disjunction of its arguments, in order |
| `if` | 2 | `if(antecedent, consequent)` |

Validation is structural only: parser validity, reserved-operator arity,
malformed names, and tree-shape invariants. There is no check of
real-world or ontological meaning.

## Assertion versus occurrence

An expression *asserts* its top-level tree.

Nested occurrence is not top-level assertion. Scope is exactly the
expression tree.

```
think(Bob, wrong(Chart))
```

asserts the whole `think(...)` expression. It does **not** independently
assert `wrong(Chart)`.

These two expressions are distinct, and they assert different trees:

```
not(think(Bob, P))
think(Bob, not(P))
```

### `asserted`

The *asserted nodes* of an expression `E` are:

1. `E` itself, and
2. if an asserted node is a call `and(...)`, each of its arguments
   (recursively).

Descent stops at every other constructor: `not`, `or`, `if`, and every
ordinary call (including `think`). So `or`, `not`, and `if` do not
independently assert their children.

`asserted(P)` on subject `E` means: `P` structurally matches at least one
asserted node of `E`.

### `occurs`

`occurs(P)` on subject `E` means: `P` structurally matches at least one
subtree of `E`, at any depth, regardless of assertion.

So for

```
think(Bob, mistakenly(use(Alice, yesterday(SalesData))))
```

- `occurs(use(Alice, ?x))` binds `?x = yesterday(SalesData)`
- `asserted(use(Alice, ?x))` fails
- `asserted(think(Bob, ?content))` succeeds

## Matching

A pattern is itself a SCIR expression. Pattern variables are `?name`.

Matching is one-way structural unification of a pattern against a subject:

- an atom matches only an atom of the same name
- a call matches a call of the same head and the same argument count;
  arguments match pairwise
- a variable `?x` binds to the subject node; a repeated `?x` must bind
  to structurally equal nodes

Bindings map the variable *name* (without `?`) to the bound expression.

Top-level matching unifies the pattern with the subject root only.
Recursive matching tries the pattern at every subtree (`occurs`).

`same(?x, ?x)` matches `same(Alice, Alice)` and does not match
`same(Alice, Bob)`.

A failed structural match yields no bindings.

## Normalization

Normalization is conservative and applies only the reserved kernel,
bottom-up, preserving argument order:

```
not(not(X))          →  X
and(A, and(B, C))    →  and(A, B, C)
or(A, or(B, C))      →  or(A, B, C)
```

Nested `and` (resp. `or`) is flattened in every argument position:

```
and(and(A, B), C)    →  and(A, B, C)
and(A, and(B, C), D) →  and(A, B, C, D)
```

No other rewrites are performed. Ordinary heads are left intact.
Normalization does not invent equivalences between informal symbols.

## Out of scope for v0

Types, sorts, ontologies, modules, quantification, numeric or string
literals, evaluation, planning, embeddings, persistence, and LLM/API
clients. The deterministic library is independently usable.
