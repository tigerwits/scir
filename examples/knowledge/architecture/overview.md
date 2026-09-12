# Recovering the event store

Recovery is built around the ordered event history. We are considering
checkpoints to shorten replay, but that recovery plan is not yet approved.
A checkpoint from another event stream must be rejected. Compaction policy
is still open.

The [working knowledge](knowledge.scir) keeps the exact obligations, the handler
assumption, and the proposal's dependencies. Change those records when the design
changes; edit this overview for readers, not to mirror every record.
