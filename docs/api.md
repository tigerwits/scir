# Python API

Install the package first. Names, signatures, return fields, and CLI behavior
here define the 1.x public API. Other helpers are implementation details.
[SPEC.md](../SPEC.md) defines structure and limits; [examples](examples.md) show workflows.

## Primary interface

| Name | Contract |
|---|---|
| `Term(symbol, args=())`, `Document` | Immutable ground tree; document is a tuple of Terms. |
| `parse(source)` | Exactly one ground Term. |
| `parse_document(source)` | An ordered tuple, possibly empty. |
| `format_document(document)` | Canonical source with one LF after each root. |
| `parse_pattern(source)` | Exactly one separate Pattern. |
| `match(pattern, term)` | Capture dictionary on success; `None` on failure. |
| `query(document, pattern, scope="roots")` | See [Queries](#queries). |
| `validate(document)` | Check the Document shape; raise `ValueError` on invalid input. |
| `digest(document)` | Versioned canonical-content fingerprint. |
| `diff(before, after)` | Positional `Difference(path, before, after)` frontier. |
| `replace_at(document, path, term)` | New document with exactly one occurrence replaced. |
| `ParseError` | Parsing failure with `index`, `line`, and `column`. |
| `FORMAT_VERSION`, `__version__` | Structural format version and package implementation version. |

Parsers accept `max_nodes` and `max_depth` for the whole document. Parsing detects
syntax errors, not translation mistakes.

## Pattern construction and substitution

```python
from scir import parse, parse_pattern, match
from scir.patterns import Node, Var, instantiate

pattern = Node("pair", (Var("x"), Var("x")))
assert match(pattern, parse("pair(A, B)")) is None
bindings = match(pattern, parse("pair(A, A)"))
assert bindings is not None
assert instantiate(pattern, bindings) == parse("pair(A, A)")
assert match(parse_pattern("pair(?_, ?_)"), parse("pair(A, B)")) == {}
```

`?_` deliberately discards content and cannot be instantiated. Substitution is
one finite structural operation, not recursive macro evaluation. Ground Term
constructors reject pattern children.

## Queries

<!-- scir:query-api:start -->
<!-- Maintained in spec/requirements.scir; refresh with python spec/check.py --write-views. -->

A path is a nonempty sequence `(root_index, child_index, ...)` of nonnegative integers. Python Booleans are not indices. Paths are local to a document snapshot.

Walking enumerates every occurrence in root-order, depth-first preorder.

Queries default to matching roots.

Explicit `scope="all"` matches every occurrence.

Results include path, matched term, and bindings, in traversal order, including duplicate occurrences.

`query(document, pattern, *, scope="roots")` returns a list of `Hit(path, term, bindings)` records. `Hit` lives in `scir.tree`. A Hit's bindings are a caller-owned dictionary, not a recursively frozen map.

Neither scope computes logical consequences.

Finding `use(Alice, Data)` inside `think(Bob, ...)` does not establish that it happened. The matched path retains its enclosing context; root matches are not necessarily facts either.

<code>DefaultScope</code>

```python
from scir import parse_document, parse_pattern, query

content = parse_document('think(Bob, use(Alice, Data))\n')
pattern = parse_pattern('use(Alice, ?data)')
hits = query(content, pattern)
assert [hit.path for hit in hits] == []
```

<code>NestedMatch</code>

```python
from scir import parse_document, parse_pattern, query

content = parse_document('think(Bob, use(Alice, Data))\n')
pattern = parse_pattern('use(Alice, ?data)')
hits = query(content, pattern, scope='all')
assert [hit.path for hit in hits] == [(0, 1)]
```

<code>DuplicateMatches</code>

```python
from scir import parse_document, parse_pattern, query

content = parse_document('f(A, A)\nf(A, A)\n')
pattern = parse_pattern('A')
hits = query(content, pattern, scope='all')
assert [hit.path for hit in hits] == [(0, 0), (0, 1), (1, 0), (1, 1)]
```
<!-- scir:query-api:end -->

## Occurrences and edits

```python
from scir import parse, parse_document, replace_at, diff
from scir.tree import at, walk

content = parse_document("f(A, A); f(A, A)")
changed = replace_at(content, (0, 1), parse("B"))
assert at(changed, (1,)) == content[1]
assert [item.path for item in diff(content, changed)] == [(0, 1)]
assert len(list(walk(content))) == 6
```

`Difference`, `walk`, and `at` live in `scir.tree`; `Path` lives in
`scir.core`. Editing a document does not relocate its annotation paths.

## Metadata and interpretation choices

```python
from scir import parse_document
from scir.annotations import Alternatives, Bundle, annotate, erase

content = parse_document("think(Bob, wrong(Chart))")
note = annotate(content, (0,), "source", {"sentence": 1})
bundle = Bundle(content, (note,))
assert erase(bundle) == content
assert note.value_json == '{"sentence":1}'

choices = Alternatives((
    parse_document("after(speak(Alice, Carol), leave(Alice))"),
    parse_document("after(speak(Alice, Carol), leave(Carol))"),
))
assert choices.choose(1) == choices.options[1]
```

`annotate` returns a detached record; Bundle checks its snapshot and path.
Use `scir.annotations.Annotation` to load stored records. SCIR neither generates
interpretations nor chooses the correct one. `erase(choices)` is an error.

## Transport

```python
import json
from scir import parse_document
from scir.relations import encode, decode

content = parse_document("f(A, B); f(A, B)")
wire = encode(content)
assert decode(json.loads(json.dumps(wire))) == content
assert len(wire["nodes"]) == 6
```

The codec describes an occurrence forest, not a deduplicated graph. Decode
validates its tables. Applications reading JSON themselves must reject duplicate
object keys before passing the resulting dictionary to `decode`; the SCIR CLI
already does so.

## Optional constraints

`scir.constraints` exports `Violation`, `Constraint`, `check`, `forms`, and
`vocabulary`. They check ground documents without changing structural `validate`.
[Dialects](dialects.md) defines their 1.x signatures, diagnostics, and trust boundary.

## CLI contract

All commands accept an optional file path; absent paths and `-` mean stdin.

| Command | Output |
|---|---|
| `check` | JSON with `valid` and root count. |
| `fmt` | Canonical source, never an in-place write. |
| `fmt --check` | No stdout; return 0 if canonical, 1 if different, 2 if invalid. |
| `query --pattern PATTERN [--scope roots\|all] [--contains SYMBOL]` | JSON results with paths, printed terms, and printed capture values. |
| `digest` | Lowercase hexadecimal fingerprint. |
| `encode` / `decode` | Relational JSON / reconstructed canonical source. |
| `--version` | Package and format versions. |

Errors go to stderr and return 2. `--contains` compares exact symbol labels
inside matched terms. Format checks retain file newline bytes when reading, so
CRLF is noncanonical; stdin checks the text supplied by the host stream.
Command data and processing errors are written as UTF-8 with LF line endings,
independently of the terminal encoding or platform newline translation. Embedded
calls to `main` also support text-only streams such as `io.StringIO`.

## Version information

`scir.__version__` identifies the Python implementation. `scir.FORMAT_VERSION`
identifies canonical content and transport semantics. `scir.relations.VERSION`
is the envelope identifier derived from that format version. Never use a package
patch version or Python `hash()` as a content-format identifier.
