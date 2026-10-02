# Adopting the additive profiles

Package 1.1.0 adds optional interfaces; native content format 1.0, canonical bytes,
occurrence identity and documented native commands remain unchanged. No existing
file needs migration. A source checkout is not a newly published package release.

Read the [contract](structured-profiles.md) and [public API](profiles-api.md).
Run `python examples/working-profile/run.py` from an installed checkout for a
bounded example that checks authored notation against an independent native golden,
selects whole context, computes review impact and proposes a change without writing.

## Choose the smallest useful workflow

Ephemeral scratch text does not require record IDs. Durable decisions, assumptions,
requirements and questions can use working/1 records with literal explanations.
Make independently changing commitments addressable; preserve unresolved and
contradictory material rather than rewriting it into an apparently agreed fact.

Use ordinary positional calls for stable small signatures, named roles when they
make distinct roles or extension points explicit. Tuple notation preserves nested
structure; it does not change call arity. Use aliases or ground abbreviations only
when reuse repays declarations and their editing complexity. Arithmetic is a fixed,
opt-in spelling profile. No execution or higher-order language has been added.

## Choose ownership before editing

Native `.scir` may be maintained canonical content. Authored `.scix` may instead be
lowered for checking. Do not keep both as independently editable authorities.
The example's dual files are checked fixtures, not a requirement for every project.
Do not rewrite original Markdown, production skills or private experiments merely
to adopt a package update. Human prose remains optional and independently authored.

An Index contains native records, not Bundle annotations or unresolved alternatives.
Carry external provenance explicitly where required. Selection closes only declared
references; it cannot prove that all relevant evidence and dependencies were named.
Guard changes against the full source snapshot. The host owns policy, authorization,
persistent revision history and atomic commits. No tool here performs those actions.

## Policy and context boundaries

A parsed record can still contain a wrong role, unsupported completion claim or
incorrect scope. Apply the consumer's trusted rules after `working/1` checks.
Keep policy code separate from input content. Do not make a status string or
represented evidence act as an authorization grant or execution receipt.

Selecting a historical record does not find its future replacements. Define
supersession queries in the consumer. Conflicting replacements and cycles need
an explicit result, not an arbitrary newest-record choice. A content fingerprint
also cannot detect an A-to-B-to-A history; a host that needs this guarantee must
supply a persistent revision token.

Selection helps when records have separable context. A complete dependency chain
can require all records. Measure full serialized packets, including audit detail,
not only selected record counts. JSON and Markdown can use the same selection and
update guarantees; do not attribute all workflow savings to SCIR punctuation.

Maintain native content when complete authored notation exceeds its explicit
limits. Select the whole required context before producing a bounded presentation.
A failed encoding is incomplete delivery, not a zero-cost success. Small selected
packets can fit even when a full notation document cannot. Never truncate a chain
of prerequisites to pass a size test.

## Verification and evaluation

The historical source-byte check verifies the recorded baseline revision, not
current implementation files. Current compatibility is checked through native
format, fingerprint, query and transport expectations. CI runs those tests and additional
profile tests on supported Python versions, plus new workflow checks on Linux,
macOS and Windows. A source distribution is rebuilt outside the checkout and its
installed package contents are compared with the directly built wheel.

`proofs/ProfileLaws.lean` checks a small abstract closure/tree model. See its
[scope statement](../proofs/README.md); it does not prove the Python implementation.
`python tools/check_profile_laws.py` compares actual selection/review operations
against finite independent oracles across every three-record graph and seed set.

`python tools/study_profiles.py --output .build/profile-evaluation` validates four
information-identical transports of 20 synthetic records and reports actual UTF-8
sizes. `--tokens` requires the optional measurement dependency tiktoken 0.12.0 and
measures o200k_base/cl100k_base; those are encodings, not current model identities.
CI retains complete payloads, request/selection/proposal envelopes, code identities
and JSON/CSV evidence. Output directories must be fresh; input content is not edited.

The compact JSON baseline is a lossless tree encoding, not an optimized JSON record
schema. The corpus is implementer-authored, not held out. Guide costs are included
in a separate illustrative scenario; guide sufficiency, model understanding,
semantic-search quality, provider framing and tool-definition overhead are not
measured. No independent model trials or end-to-end agent cost claims are made.
In particular, a small change request does not mean its complete candidate response
is small: the evaluation accounts for that response separately.

No fixed percentage saving, feature count or preferred spelling may override
correctness. Before a broad migration, compare independent agent workflows with
matched knowledge/tools and retain failures, scope loss, stale-edit rejection,
repair cost and uncertainty handling. Structural checks alone are not that evidence.

## Use the complete workflow

Inspect sizes and capacity with [selection diagnostics](workflow-tools.md).
Choose compact delivery explicitly; keep full responses for tasks that need audit
information immediately. Compact output is not always smaller. Fetch and check
the artifact hash when a complete candidate or repository write plan is needed.
Never save a proposal delta over its source collection.

Run the [consumer lifecycle example](../examples/consumer-lifecycle/README.md)
to distinguish valid structure from trusted application policy. It uses fixed test
doubles, not a live service. Preserve these trust limits when adapting the example.
