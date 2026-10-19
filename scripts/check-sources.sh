#!/usr/bin/env bash
set -euo pipefail
scir_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$scir_root"
scir_inventory=.build/language/source-files.log
git ls-files --cached --others --exclude-standard > "$scir_inventory"
if grep -E '\.(py|pyc|pyo|md|markdown|rst|js|ts|c|cpp|rs)$|(^|/)(pyproject.toml|MANIFEST.in|package.json|Cargo.toml)$' "$scir_inventory"; then
  printf 'The language specification may not contain a second realization, package manifest or prose document.\n' >&2
  exit 1
fi
if grep -REn '^[[:space:]]*((private|protected|noncomputable)[[:space:]]+)*(unsafe|partial|axiom|opaque|sorry|admit)([[:space:]]|$)|\b(implemented_by|sorryAx)\b' --include='*.lean' proofs SCIR.lean; then
  printf 'Unreviewed logical admission or alternate executable definition.\n' >&2
  exit 1
fi
if grep -REn 'setup-python|python[0-9]? |pip install|node |bun |npm |cargo ' .github scripts/check.sh scripts/check-mutants.sh; then
  printf 'The specification gate must use only Lean and minimal shell plumbing.\n' >&2
  exit 1
fi
test -f LICENSE
printf 'SOURCE_POLICY=lean-specification-only; FILES=%s\n' "$(wc -l < "$scir_inventory")"
