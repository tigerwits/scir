# Historical cumulative-profile experiment

The original experiment is preserved in Git at
[`b91b32718dc9bc53b56f6b383c89e3095252623f`](https://github.com/tigerwits/scir/tree/b91b32718dc9bc53b56f6b383c89e3095252623f).
It contains the original `src/scir/refinement.py`, example and two test files.
The archive merge retained this commit as a parent; no history was rewritten.

Use a separate checkout of that exact revision to reproduce it:

```sh
git worktree add --detach ../scir-refinement b91b32718dc9bc53b56f6b383c89e3095252623f
cd ../scir-refinement
PYTHONPATH=src python -B -m unittest discover -s tests -p 'test_refinement*.py' -v
```

These are historical tests, not current passing benchmarks or a supported API.
Current named dialects were adopted separately. The old implementation is not
copied into the active source tree or installed package.
