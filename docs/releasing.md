# Releasing SCIR

The distribution is `symbolic-content-ir`; the Python package and CLI are `scir`.
The version is defined in `src/scir/__init__.py`.

## Prepare the candidate

Review the [changelog](../CHANGELOG.md) and
[compatibility policy](../SPEC.md#versioning-and-compatibility). From a clean
checkout with a virtual environment active, run the
[contributor checks](../AGENTS.md#verify), then build:

```bash
python -m pip install build
python -m build
```

The wheel and source distribution are written to `dist/`. Inspect their contents,
license, and package metadata. The source distribution must include both skills
and the examples.

Test the installed wheel outside the checkout and run the tests from the extracted
source distribution. Check that `python -m scir --version` matches the release
version and that CI passes for the exact candidate commit.

## Publish the release

Confirm the target repository and ownership of the `symbolic-content-ir`
distribution name. Record the candidate commit and archive checksums, and publish
the verified artifacts.

Replace "pending publication" with the actual release date only when releasing.
Update the README's PyPI notice and installation commands only when that upload
succeeds; never substitute the unrelated distribution named `scir`.

A GitHub release and a PyPI publication are separate steps. Verify the links and
first-run instructions for each distribution route that is available.
