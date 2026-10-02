# Repository knowledge ownership

This is repository tooling, not a new runtime profile. It uses the installed
SCIR package's `working/1` representation under the local `scir-repository/1`
contract. Run `python spec/repository.py` or the normal test suite to check it.

## Sources during the transition

| Material | Maintained owner | Role of the other representation |
| --- | --- | --- |
| Native query/occurrence wording | `requirements.scir` | Two marked Markdown views; retain their exact refresh procedure. |
| Other native rules | Linked sections in SPEC/API/dialect docs | The old catalog indexes obligations and tests. |
| New 1.1 rules | `docs/structured-profiles.md` and `docs/profiles-api.md` | `knowledge.scir` indexes the rule and connects its rationale and checks. |
| Adoption decisions and limitations | Linked specification or result section | Knowledge contains an attributed summary, not a competing normative definition. |
| Test expectations | Independently authored test methods | A knowledge link states intended coverage, not test execution or adequacy. |
| Proof model | The Lean source and its stated scope | A model link identifies a declaration; it does not prove Python implementation behavior. |
| Measurements | Identified run artifacts and reports | Never convert reported success into automatic approval or a truth claim. |

The two catalogs have disjoint IDs and nonoverlapping ownership at this stage.
The old [maintenance procedure](README.md) and generated query sections are
unchanged. Do not independently edit those generated sections. Do not blanket
convert Markdown or move historical reports merely to make the layout uniform.

## Local record contract

`knowledge.scir` is canonical native SCIR. Every root is a working record with a
unique ID, an area, one `source: section(path, heading)`, and `ownership: index`.
Kinds are Requirement, Decision, Limitation and Question. Payloads are structural
indexes or summaries; the source section remains authoritative. Decisions and
questions also carry an authored status. Unknown local fields/kinds fail.

Each Requirement has a nonempty `tests` tuple of `test(path, Class.test_method)`.
Optional `models` contains `model(proofs/path.lean, theorem_name)` entries.
References use the ordinary explicit reference tag; dependency, scope, evidence,
reason and supersession fields retain `working/1` meanings. In particular, a
reference is not automatically a review dependency. No record states that a
linked test has run just because its method exists.

The checker resolves exact headings outside triple-backtick fences, direct test
methods in top-level `unittest.TestCase` subclasses, and simple line-start Lean
theorem declarations outside comments. These are repository conventions, not
full Markdown, Python inheritance, or Lean elaboration engines. It reads source
with a byte bound; it never imports tests or invokes a proof checker. Paths must
stay inside the checkout and cannot use symlinks or traversal. Duplicate links,
ambiguous/missing locations and dangling knowledge references are rejected.

A wrong interpretation with valid locations can pass these bookkeeping checks.
Review a changed payload alongside its designated source. Structural acceptance
cannot substitute for source fidelity, negative testing or independent trials.

## Maintenance example

Select NamedRoles to obtain the rule, its positional/named distinction, related
tuple decision, intended negative tests and proof limitations:

```sh
python -m scir knowledge select spec/knowledge.scir --collection scir-repository --id NamedRoles
python -m scir knowledge affected spec/knowledge.scir --collection scir-repository --changed PreserveCallArity
```

This selection preserves whole records and closes only over declared references.
Canonical knowledge is the maintained source; compact notation may be a delivery
view. A proposal never overwrites the authored source or guesses how to edit an
alias. Stronger repository checks must run on candidates before a host persists
anything; a generic working/1 proposal checks less than this local contract.

## Next slices

Add a separately pinned current-package lane to the external grill while leaving
its historical pin and reports unchanged. Then integrate repository selection and
checking at the existing maintenance entry point, migrate the original catalog
with exact projection checks, and exercise multi-step maintenance scenarios.
Retire duplicated maintained facts or adapters only after replacement checks exist.
