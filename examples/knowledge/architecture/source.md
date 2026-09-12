# Event-store design notes

S1: EventStore uses an append-only log.
S2: Replaying accepted events in order must reconstruct State.
S3: Replay assumes deterministic handlers for the same ordered events and initial state.
S4: Checkpoint-plus-suffix recovery is proposed to meet the replay requirement under that assumption; it is not approved.
S5: Whether compaction may discard events is undecided.
S6: Recovery must reject a checkpoint from a different event stream than the suffix.
