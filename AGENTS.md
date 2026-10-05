# Working on SCIR

Read `spec/index.scir` for the explicit knowledge-source map.
Install the checkout, or set `PYTHONPATH` to its absolute `src` directory.

```sh
python spec/check.py
python spec/check.py knowledge list
python spec/check.py knowledge search --text 'Repository knowledge ownership'
python spec/check.py knowledge select --id NamedRoles
```

Select the relevant SCIR sections, requirements, qualifications and independent tests
before editing. Use `knowledge affected --changed ID` to review declared dependents.
The complete maintainer handbook is in `spec/workflows.scir`; use `knowledge search`
to find it. Navigation links are not dependencies or evidence of entailment.

SCIR owns all durable knowledge. Only root README.md and this thin bootstrap are
maintained Markdown. Edit the owning record, not a disposable export or summary.
Keep stable IDs, conditions, evidence, uncertainty and historical pins intact.
A proposal requires the inspected input-basis digest; never refresh a stale guard
without reviewing changed inputs. Proposals do not persist or approve changes.

```sh
python -m unittest discover -s tests -v
python tools/check_self_host.py
```

Build and test distributions outside the checkout. Run the relevant independent
checks; shape validation does not prove fidelity, execution or Lean elaboration.
Preserve unrelated work. Do not publish releases, force-push or rewrite history
without explicit authorization. Keep the license and native format 1.0 intact.
