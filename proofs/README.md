# Profile law model

`ProfileLaws.lean` is a separate model checked with Lean 4.19.0 and no mathlib.
From this folder with that toolchain installed, run `lean ProfileLaws.lean`.
CI compiles it with warnings as errors and prints the assumptions of each named
theorem. Lean is a verification dependency only; the Python package does not load
or install it. The fixed upstream release is downloaded in the verification job;
its archive checksum and `lean --version` are recorded in that job's logs.

The closure model proves seed inclusion, monotonicity, least closed-set membership
and idempotence. `Reach` follows explicit edges, which may represent references
or reversed dependencies. It does not infer undeclared edges or factual truth.
The raw-tree model proves tuple and reference constructor injectivity and three
specific distinctions: text versus reference, two arguments versus one tuple
argument, and a named role versus a positional role-shaped application.

These are checked logical model theorems, NOT a proof of the Python implementation,
parser, UTF-8 codecs, field sorting, source translation, resource bounds or database
concurrency. Ordered output/reasons and bounded failures are tested in Python.
Finite visited-set traversal terminates because each finite record ID is queued
once; the executable implementation is compared with an independently implemented
fixed-point oracle on all three-node graphs and generated larger graphs.

No admission is used in this source. CI rejects admissions before invoking Lean
and rejects unexpected assumptions afterward. The model deliberately contains no
runtime evaluator, type inference system or persistence state machine.
