#!/usr/bin/env bash
set -euo pipefail
scir_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$scir_root"
scir_lean=${1:-lean}
scir_build="$scir_root/.build/language"
check_mutant() {
  local scir_name=$1 scir_module=$2 scir_edit=$3
  local scir_mutant="$scir_root/.build/mutants/$scir_name"
  mkdir -p "$scir_mutant"
  cp "$scir_build"/*.olean "$scir_mutant/"
  sed "$scir_edit" "proofs/$scir_module.lean" > "$scir_mutant/$scir_module.lean"
  if cmp --silent "proofs/$scir_module.lean" "$scir_mutant/$scir_module.lean"; then
    printf 'Mutation did not alter %s\n' "$scir_module" >&2
    exit 1
  fi
  LEAN_PATH="$scir_mutant" "$scir_lean" -DwarningAsError=true -o "$scir_mutant/$scir_module.olean" "$scir_mutant/$scir_module.lean" > "$scir_mutant/compile.log" 2>&1 || { cat "$scir_mutant/compile.log"; exit 1; }
  if LEAN_PATH="$scir_mutant" "$scir_lean" -DwarningAsError=true --run proofs/Conformance.lean "$scir_root" > "$scir_mutant/run.log" 2>&1; then
    printf 'Conformance failed to detect mutant %s\n' "$scir_name" >&2
    exit 1
  fi
  grep -F 'uncaught exception:' "$scir_mutant/run.log" >/dev/null
  printf 'MUTANT_KILLED=%s; ' "$scir_name"
  tail -n 1 "$scir_mutant/run.log"
}
check_mutant ignore-relabel SymbolReference 's/let result := relabelDocument rename document/let result := relabelDocument (fun label => if rename label == label then label else label) document/'
check_mutant revisit-substitution SubstitutionReference 's/encodePattern (substitute σ pattern)/encodePattern (substitute σ (substitute σ pattern))/'
check_mutant ignore-freshness DefinitionReference 's/if taken.contains name then/if false \&\& taken.contains name then/'
check_mutant empty-symbol NativeCodec 's/if label.isEmpty then/if false \&\& label.isEmpty then/'
check_mutant duplicate-json-key StrictJson 's/if acc.any (fun pair => pair.1 == key) then/if false \&\& acc.any (fun pair => pair.1 == key) then/'
check_mutant wrong-sha-rotation Sha256 's/rotate x 6 \^\^\^ rotate x 11/rotate x 7 ^^^ rotate x 11/'
