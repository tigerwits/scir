# Profile implementation: verification and measured costs

Date: 2026-10-02. Package 1.1.0 source implementation; native content format 1.0.
No release or package publication follows from these implementation changes.

## Reproducible evidence

The first successful Profile verification run is
[37005279184](https://github.com/tigerwits/scir/actions/runs/37005279184), at PR head
`2272313372cacb68b4f2790e1d16b5da1b74e682`. GitHub tested its merge with base
`b7bf167cb3873d0bf65930ffe5e6418391ba0e9f` as
`734d8a4138b6e5fe982e5c3c4602724f6dd687b3`.

All five profile jobs passed: integration/packaging on Linux, macOS and Windows,
the Lean model, and the executable law/measurement job. At that same head, the
separate full original Check workflow exposed two integration problems: a stale
package-version assertion and a 167-character skill description exceeding the
existing 160-character limit. Follow-up changes update the package assertion to
1.1.0 while retaining the exact format-1.0 assertions, and shorten the description
without weakening its limit. Do not interpret the first profile run as proof that
the original full suite passed; final exact-head gates are recorded on PR #7.

The measured production modules, corpus and evaluation driver are unchanged by
those metadata fixes and by the subsequent report/checksum-pinning changes.
Evidence job `110831986458` ran CPython 3.12.14 with tiktoken 0.12.0 and measured
`o200k_base` and `cl100k_base`. Those identify encodings, not current models.
[Artifact 11225292581](https://github.com/tigerwits/scir/actions/runs/37005279184/artifacts/11225292581)
contains fifteen files: four complete information-matched representations, nine
workflow payloads, results JSON and a representation CSV. Its ZIP SHA-256 is
`7687514962413d5b22dd72f149f4fd0489056cfd0341dd3c617b83c04dfb830b`.
Retention is 90 days, not permanent. The generator, fixtures, protocol and selected
observations remain in Git. This report transcribes observed CI output, not an
independent rerun or an agent trial.

Reproduce with the installed project interpreter:

```sh
python tools/check_profile_laws.py
python tools/study_profiles.py --tokens --output .build/profile-evaluation
python examples/working-profile/run.py
```

The token option requires the pinned optional measurement dependency. Output paths
must be fresh. Without it, only actual UTF-8 bytes are reported; no token estimates.
The complete result includes source/code hashes and profile/content identities.

## Structural verification

The executable finite model covers all 512 directed graphs on three record IDs
and all eight seed subsets: 4,096 cases. It checks selection against a separate
fixed-point oracle, reverse-dependency impact, seed inclusion, idempotence,
monotonicity and least closed-superset membership. Generated notation tests also
exercise 400 structured print/parse roundtrips, lexical renaming, nesting and
combined alias/operator/role/tuple cases. These finite checks are not universal
proofs of the Python implementation.

The separate Lean 4.19.0 model compiled successfully in job `110831986768`.
Four closure theorems use no axioms; five constructor/distinction theorems report
only Lean's propositional extensionality (`propext`). There are no admissions or
custom axioms. The model covers seed inclusion, monotonicity, least closed-set
membership, idempotence, tuple/reference injectivity, text/reference separation,
call arity versus a packed tuple, and named versus positional role structure.
It does not prove Python parsing, canonical UTF-8, field sorting, resource limits,
source fidelity, or persistent concurrency. See [proof scope](../proofs/README.md).

The verified release archive's SHA-256 is
`6fe3ce97a58f44e2b3567d455b994eacec5bfe9ae7774f2a573444480ba813fe`.
CI now requires that checksum before extraction, rather than merely recording it.
Lean remains a verification dependency, not a Python runtime dependency.

Cross-platform packaging checks build a wheel and source distribution, rebuild
a second wheel from the source archive outside the checkout, compare package
member bytes, and exercise both installed copies outside the checkout. Profile
CLI tests preserve source files and check UTF-8 output under an ASCII terminal.
Native core/parser/matching/traversal/transport byte sentinels protect the baseline.

## Information-matched representation costs

Twenty implementer-authored synthetic records are represented by four lossless
encodings. The compact JSON baseline is a tree encoding, not an optimized JSON
record schema. No translation from unrestricted English is evaluated.

| Representation | UTF-8 bytes | o200k body | cl100k body | o200k body + guide |
| --- | ---: | ---: | ---: | ---: |
| Native tagged SCIR | 2947 | 744 | 748 | 780 |
| Compact JSON trees | 3615 | 1050 | 1054 | 1081 |
| Explicit notation, no aliases | 2631 | 612 | 612 | 657 |
| Authored aliases and arithmetic | 2659 | 624 | 624 | 677 |

Explicit notation is smaller for these records, but the extra alias/arithmetic
setup is slightly larger than explicit notation. This supports keeping those
features optional, not a universal claim that aliases or SCIR compress better.
The illustrative guides are counted separately; sufficiency for an agent is not
measured. No current-model mapping or chat framing cost is inferred.

## Complete workflow costs

All values below are actual o200k_base tokens. The full native collection is 744.

| Task | Selected native content | Full selection packet | Change request | Full candidate proposal |
| --- | ---: | ---: | ---: | ---: |
| Resume T1 with dependencies and staging scope | 152 | 309 | 80 | 971 |
| Inspect assumption A1 | 21 | 117 | 80 | 971 |
| Resume T1 plus an independent note | 189 | 366 | 80 | 971 |

Selection packets retain collection/profile identity, source snapshot, IDs,
reasons and whole record strings. Reporting only the selected-content column
would hide the metadata cost. A small change request does not imply a small
response: the candidate proposal contains the entire candidate collection and
therefore costs more than the original native body in this example. It is not
an end-to-end token-saving or latency claim. Hosts may separate candidate storage
from a concise acknowledgment in a future explicitly specified workflow; the
current API deliberately returns the full reviewable candidate.

Target IDs are known inputs. This is declared-reference closure, not semantic
search or proof that an author supplied all relevant edges. Scope, status and
literal uncertainty remain content; their presence does not establish truth or
authorization. Snapshot guards construct candidates only; persistent atomic writes
and stronger consumer policies belong to the host.

## Adoption decision and limits

Keep the native kernel unchanged. Use optional tuple/text/reference/role notation,
first-order calls, explicit record identity, complete context selection and guarded
changes. Keep local aliases, ground abbreviations and fixed arithmetic optional.
Do not add automatic evaluation, higher-order heads, dynamic macros, implicit
rewriting, native graph storage or source rewriting through aliases in this release.

Independent model trials: zero. No result here establishes improved reasoning,
role accuracy, instruction following, retrieval quality, wall-clock agent latency
or safety. The corpus is implementer-authored and not held out. Build and tokenizer
transitive dependencies are not completely locked. The checked code uses only the
standard library at runtime. Read [adoption guidance](profile-adoption.md) and the
[public API](profiles-api.md) before choosing an authoritative source workflow.
