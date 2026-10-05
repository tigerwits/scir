# Verification boundaries

The normal contributor commands are `python spec/check.py` and
`python -m unittest discover -s tests -v`. The suite executes documentation,
portable examples, consumer policy, named contracts and repository handoffs.
Run a particular example separately to inspect its report, not as a duplicate gate.

## CI ownership

| Boundary | Job | Coverage |
| --- | --- | --- |
| Runtime and CLI compatibility | Check | Full suite on Python 3.10 through 3.14 |
| Paths, encodings and filesystem behavior | Profile integration | Full suite once on macOS and Windows |
| Installed distributions | Profile integration | Wheel/sdist rebuild and installed checks on all three systems |
| Shipped examples without checkout imports | Adoption | Extracted sdist on Linux; consumer, lifecycle and repository reports |
| Finite and machine-checked laws | Profile laws/evidence | Existing Lean model, closure cases and identified measurements |
| Historical source bytes | Historical integrity | Fixed old pin when its checker or configuration changes, or explicit dispatch |
| Repository administration | Check 3.13 and merged event | Lease/protection tests before exact-tip branch cleanup |

Linux runtime tests do not run again inside the distribution job. Top-level
example scripts and source snippets are already exercised by documentation tests.
The larger seeded property sample runs once on 3.13; its smaller smoke test still
runs across the matrix. The separate repository-portability workflow was removed
because the complete OS suites cover all its tests. No semantic or platform
coverage was discarded to reduce the number of workflow files.

Historical reproduction preserves exact pins. It does not assert that an evolving
implementation must have the same source bytes. Source hashes, declared coverage,
finite scenarios, proof models and actual model trials remain separate evidence.
The main repository needs no private dependency to pass its own checks.

## Examples

Use `examples/workflows.py` for the core, the portable skill's `working_example.py`
for working records, `examples/consumer-lifecycle/run.py` for consumer contracts,
and `tools/check_self_host.py` for repository updates. The lifecycle's old named
entry is only a compatibility view of the same runner. The fixed native/notation
pair remains an independent golden; authored case studies and the blocked-timeout
dialect chain remain distinct preservation examples.

No workflow publishes a package, approves a represented operation, or implements
an atomic persistent multi-file update. Inspect actual failures and exact-head
results before merging. Do not convert incomplete checks into acceptance.
