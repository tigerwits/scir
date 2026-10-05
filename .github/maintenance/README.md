# Repository administration

This directory is maintainer tooling, not SCIR runtime, examples or research.
It is not shipped in the wheel or source distribution. Run its independent tests:

```sh
python -m unittest discover -s .github/maintenance -v
```

The branch-maintenance workflow receives one exact tip from a merged local PR.
It checks out the trusted default branch, not the PR source. It verifies current
protection, open PRs, default-branch ancestry and the observed tip. The delete uses
a compare-and-delete lease. A changed, protected, unmerged or reopened branch is
preserved. Squashed branches without ancestral tips are preserved for review.
No branch inventory or completed PR name is maintained in product source.
The reusable CLI accepts an explicit reviewed manifest and defaults to dry-run.
