#!/usr/bin/env bash
set -euo pipefail
scir_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$scir_root"
scir_lean=${1:-lean}
scir_build="$scir_root/.build/language"
mkdir -p "$scir_build"
"$scir_lean" --version | tee "$scir_build/toolchain.log"
"$scir_lean" --version | grep -F 'version 4.19.0,' >/dev/null
test "$(cat lean-toolchain)" = 'leanprover/lean4:v4.19.0'
sha256sum --check --strict conformance/SHA256SUMS
export LEAN_PATH="$scir_build"
scir_modules=(ProfileLaws SymbolLaws SubstitutionLaws DefinitionLaws Language ConformanceOrigins StrictJson Sha256 ReferenceCodec SymbolReference SubstitutionReference DefinitionReference NativeCodec WorkingSpec BoundaryTests NativeCorpus DefinitionCorpus)
for scir_module in "${scir_modules[@]}"; do
  "$scir_lean" -DwarningAsError=true -o "$scir_build/$scir_module.olean" "proofs/$scir_module.lean" > "$scir_build/$scir_module.log" 2>&1 || { cat "$scir_build/$scir_module.log"; exit 1; }
done
"$scir_lean" -DwarningAsError=true SCIR.lean
"$scir_lean" -DwarningAsError=true proofs/AxiomAudit.lean | tee "$scir_build/axioms.log"
"$scir_lean" -DwarningAsError=true --run proofs/Conformance.lean "$scir_root" | tee "$scir_build/conformance.log"
"$scir_lean" -DwarningAsError=true --run proofs/ExportCorpus.lean "$scir_root" .build/native-corpus.scir
"$scir_lean" -DwarningAsError=true --run proofs/ExportDefinitions.lean "$scir_root" .build/definition-corpus.scir 2> "$scir_build/definition-corpus.log"
sha256sum .build/native-corpus.scir .build/definition-corpus.scir | tee "$scir_build/corpora.log"
bash scripts/check-mutants.sh "$scir_lean"
bash scripts/check-sources.sh
git diff --check
