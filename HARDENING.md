# Python implementation review — 0.2.1

This is an implementation pass over merged SCIR 0.2, not another language
redesign. Baseline: `d77e0ae3be9e361924ce3668ceb39a8f8627c820`; its Git tree
`03ee3607a8d3745e7c5e596d7185cb51f6c6d2fe` exactly matched the supplied ZIP before
editing. The baseline's 83 tests passed locally.

The kernel remains `Term(symbol, args)` and `Document = tuple[Term, ...]`.
Canonical content, fingerprints, root/all scopes, pattern semantics,
occurrence order, relational wire version and Boolean opacity are unchanged.

## Simplification before extension

- Share label formatting instead of constructing temporary Terms to print patterns.
- Match reversed child pairs directly, without intermediate zip/list copies.
- Diff corresponding labels and arities once; do not recursively compare the
  entire remaining subtree again at every changed position.
- Encode with the current ancestor-ID chain instead of retaining every path/ID.
- Reconstruct contiguous positions by range lookup rather than sorting keys.
- Use the standard library's topological cycle check, not another scheduler.

No common AST base class, generic visitor framework, registry, schema language,
or new content constructor was introduced. The first refactor commit touches
three files, with 18 insertions and 12 deletions. Hardening is a separate commit.
The runtime grows from 678 to 776 lines because rejection boundaries now have
real checks; deleting those checks merely to reduce line count would be worse.

## Reproduced problems and fixes

| Case | Baseline behavior | 0.2.1 behavior |
|---|---|---|
| Tiny node budget, long input tail | Tokenizes the complete source before checking the budget | One-token lookahead; stop lexing when rejected |
| Deep macro body, small step budget | Unbounded `instantiate` raises `RecursionError` before guarded traversal | Check definitions and expand directly under one budget |
| Shared pattern in variable collection | Revisits a physically shared subtree at every occurrence | Visit each object once for this set-valued query only |
| Unused definition calls a known macro with wrong arity | Accepted until/if executed | Reject during definition validation |
| Metadata `{1: "one"}` | Converts the key to `"1"` | Reject non-string object keys |
| Invalid Unicode annotation key | Accepted | Reject non-scalar text |
| Unsupported/deep metadata | `TypeError` or `RecursionError` can escape | Bounded validation and `ValueError` |
| CLI duplicate JSON keys | Keeps the last value | Reject ambiguous JSON objects |
| CLI very large input | Reads all input before validation | Explicit 16-million-character read bound |
| Invalid dense argument table | Stores repeated incoming edges until final forest check | Reject the second incoming edge immediately |

Metadata is still separate from content. Its serializer accepts JSON scalars,
string-keyed objects and list/tuple arrays; tuples retain the previous JSON-array
conversion. Canonical values are copied, not retained as mutable Python objects.
Annotation data has explicit size, depth and work bounds, including direct raw
Annotation payloads checked through Bundle. Erasure accepts Bundle only.

Macro preparation and expansion share `max_steps`. A visit to a definition body,
a capture, or a copied argument consumes work. This is an intentional tightening:
low custom budgets may need increasing. Acyclic definitions do not imply cheap
expansion. Physical sharing in arguments does not erase occurrence costs.

Inputs with several errors can now report a different first error because the
lexer no longer scans the entire invalid tail in advance. See SPEC.md for the
normative rejection policies; the content/wire format remains 0.2.

## Verification actually run

- **108 unit tests passed** under CPython 3.13.5, including all 83 existing tests.
- **11,000 generated documents / 102,046 occurrences**, seeds 602–612, passed the
  existing parse/print, pattern, substitution, transport, edit and erasure laws.
- An independent collect-then-solve matcher agrees on 1,000 pattern/subject
  comparisons inside the new 500-case structural law test.
- **1,000 differential documents**, **5,000 syntax samples** and **100 template
  cases** agree with the merged 0.2 implementation on valid behavior.
- Ten selected new regression test methods were run against baseline first;
  that run failed as expected, exposing the old errors and missing rejection.
- Editable installation without network/build isolation and CLI smoke tests passed.
- Runtime files parse with Python 3.10 grammar; execution was tested on **3.13.5
  only**, not a multi-version Python matrix.

Tests include duplicate preservation, root versus occurrence scope, independent
matching, commuting disjoint edits, diff reconstruction, stale annotations,
invalid metadata, bounded substitution, malformed transport and deep diffing.
No timing threshold is embedded in the unit tests.

## Focused measurements

Three warm timing runs and a separate tracemalloc peak run, with input objects
preallocated. Decimal MB below; raw bytes and environment are in evidence.

| Probe | Baseline time | 0.2.1 time | Baseline peak | 0.2.1 peak |
|---|---:|---:|---:|---:|
| Parse 35,000 occurrences | 80.849 ms | 80.507 ms | 13.54 MB | 4.46 MB |
| Reject a 100,000-root source after one node | 71.651 ms | 0.062 ms | 20.02 MB | 0.0029 MB |
| Encode 35,000 occurrences | 50.305 ms | 29.099 ms | 10.54 MB | 7.21 MB |
| Diff a changed leaf at depth 128 | 1.166 ms | 0.142 ms | 0.0102 MB | 0.0057 MB |

Parser throughput is effectively unchanged in this run; the clear improvement
is allocation. The rejection probe measures avoiding unnecessary tokenization,
not reading an arbitrarily large file for free. These are local measurements,
not process RSS, performance guarantees, or evidence about LLM reasoning.

## Reproduce

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python tools/check_properties.py
python tools/study_corpus.py
python tools/benchmark.py
python tools/benchmark_hardening.py
python tools/benchmark_hardening.py --src /path/to/baseline/src
python tools/check_compatibility.py /path/to/baseline/src
```

`evidence/hardening.json` records commands, seeds, counts, source hashes and both
sets of allocation/timing measurements. Earlier evidence files are retained as
historical 0.2 results, not relabelled as measurements of this revision.

## Limits

This is not universal verification, a security sandbox, or a claim of production
readiness. Some direct Python operations on manually constructed trees beyond
the documented parser limits remain recursive. No new Lean proof or independent
model-to-model experiment was run. No GitHub Actions result is claimed.
