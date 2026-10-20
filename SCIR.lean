import Language

/- SCIR is a language specification, formalized in Lean.

   The normative native format and opt-in profile contracts live in
   proofs/Language.lean. SymbolLaws, SubstitutionLaws, DefinitionLaws,
   ProfileLaws and OccurrenceLaws establish their explicitly stated mathematical
   invariants. OccurrenceLaws adds exact path coverage, preorder and append laws.
   NativeCodec and the reference modules are executable specification oracles,
   not an application runtime or a published content-library API.

   Run scripts/check.sh /path/to/lean with the exact lean-toolchain version.
   It elaborates with warnings as errors, audits transitive proof assumptions,
   executes independent frozen vectors and finite corpora, checks deliberate
   boundary mutants, and exports native interoperability corpora in .build/.
   A realization can consume those SCIR corpora and compare its actual behavior.
   Finite conformance and application tests remain distinct from Lean theorems.

   Maintain durable language clauses beside their declarations. Keep only Lean,
   native examples, conformance data, the license and minimal build/CI plumbing.
   Preserve format 1.0 bytes and the fixed vectors. Do not add an application
   service, a second realization, or consumer-specific integrations here. Keep
   source evidence, interpretation, proof scope and unfinished work distinguishable.
   Changes to a consuming application belong to that application's repository.

   Native examples show ordinary trees, structured working records and explicit
   Definition environments. Loading a file never implicitly chooses a profile,
   resolves references into another file, evaluates content or grants authority.

   Migration baseline: main 4df43ba874d6750e9ab16b21903b87e8879b601c, tree
   5e0633611a39059c681bd38ac0be4ef8df124ec0. Earlier implementation and workflow
   history remain there. The separate draft repository-knowledge migration is
   untouched; it is not a dependency of this language-only specification.
-/
