# Consumer lifecycle example

This example adds trusted application rules to ordinary `working/1` records.
It does not add a policy engine, execute a represented action, or connect to a
service. All approvals and receipts are fixed test doubles. They are not evidence
that a real test or delivery occurred.

From an approved installed checkout, run:

```sh
python examples/consumer-lifecycle/run.py
```

The command reads `notes.scir`. It resolves a declared replacement, rejects an
unsafe status update, prepares a ready candidate, and checks completion evidence.
It rejects an old snapshot and delivers complete selected context. It prints a
JSON report and leaves the source unchanged. The example also runs after relocation
and from the source distribution outside the repository.

## Consumer contract

`policy.py` owns this example's trusted rules. The canonical `notes.scir` owns its
hypothetical records. `run.py` supplies fixed approvals and receipts from a test
fixture, not from the candidate being checked. Do not use these fixture identities
as live credentials or derive new trusted approvals from user-authored records.

The example has a deliberately small contract:

| Kind | Rule |
| --- | --- |
| Decision | Exact sender, recipient and document; explicit staging scope; proposed or approved status |
| Recovery | Preserve the uncertain-outcome condition, original key and lookup-before-retry order |
| Evidence | Explicit decision, scope, receipt ID, operation and outcome coordinates |
| Task | Exact action and scope; declared decision and recovery prerequisites; blocked, ready or completed status |
| Note | Inert supporting text; it does not approve an action |

A ready task must point directly to the resolved decision. It must retain both
prerequisites and a passing test receipt for that exact decision and scope.
A completed task also needs a matching delivery receipt. An approved decision's
complete record fingerprint must occur in the separate trusted approval set.
Changing approved content thus requires new approval and matching evidence.

Evidence records are claims. The consumer compares their coordinates with the
separate `TrustedInputs` object. A matching label alone is insufficient. The
example does not authenticate signatures or execute tests; a production host must
obtain and verify those inputs from its trusted source. The supplied mappings are
copied and immutable during a call. The host must separately guard its revision,
authority and receipt state when persisting a proposal.

The checker rejects unknown kinds/fields, wrong roles, lost scope, missing
prerequisites, changed recovery keys/order and unsupported completion. Generic
SCIR can represent these invalid commitments; the consumer decides whether its
own contract permits them. Both permitted and forbidden cases have tests.

`propose_checked` first constructs a snapshot-guarded generic candidate. It then
checks the whole candidate against the consumer contract. It does not return a
partially accepted change. A valid candidate remains a proposal, not permission
to submit an action or overwrite a shared source.

## Effective-state query

`effective(index, id, scope=STAGING)` is an example query, not a new runtime API.
It follows incoming `supersedes` links among decisions. Generic `select()` still
follows outgoing references and retains historical records.

The query returns one explicit status:

| Status | Meaning |
| --- | --- |
| `resolved` | One terminal decision has declared approved status in the requested scope |
| `unapproved` | The one terminal decision is not declared approved |
| `competing` | More than one terminal replacement exists |
| `cycle` | A reachable replacement cycle prevents a terminal answer |
| `scope-mismatch` | A reachable record has a different or missing scope |

This strict example reports a scope mismatch before other lineage questions.
It does not ignore a competing branch, select by timestamp, or erase an old
record. A proposed intermediate record may precede an approved terminal record.
Unknown IDs and wrong target kinds fail; more than 256 records exceeds the
example's explicit bound. Iterative traversal terminates on cycles.

`resolved` describes the represented lineage. The task checker still verifies
external approval and receipt inputs. It is not a claim that the decision is true
or a general rule for every consumer's definition of current state.

## Verification and limits

`tests/test_consumer_lifecycle.py` covers permitted candidates, policy violations,
receipt substitution, stale changes, lineage conflicts, bounds and relocation.
The runner also executes with Python assertions disabled. No test here establishes
model behavior, authentic remote execution or concurrent persistent commit safety.

Use the host's atomic precondition/write operation for real persistence. Do not
replace that operation with a check followed by an unguarded file write. The
[workflow tools](../../docs/workflow-tools.md) keep complete context separate from
proposal deltas; the [repository handoff](../../spec/HANDOFF.md) retains file bases
and source-owned plans. Those interfaces do not supply the missing host authority.

## Named dialect and result handoff

Run `python examples/consumer-lifecycle/dialect_run.py` to use the additive named
contract API. The adapter composes structured, working, field, reference-kind and
existing consumer-policy checks. `FIELDS` in `policy.py` remains the one owner
of allowed kinds and fields. No second policy vocabulary is introduced.

The host converts its fixed `TrustedInputs` into a separate immutable Context.
Its revision and exact contents are bound to each result. The example rejects an
old context guard even when the SCIR document did not change. Malformed host
context yields incomplete validation, not a claim that the candidate is false.
A checked proposal returns the complete generic candidate and a conforming result;
failed or incomplete policy cannot return a successfully checked candidate.

A result for the full collection is not copied onto a selected subset. The runner
checks the subset again. The regression tests include a consumer requiring an
independent record that reference closure omits. Callers must not assume arbitrary
dialects are preserved by selection, concatenation or editing. Source and service
writes still require the host's atomic guards. All receipt inputs remain test doubles.
