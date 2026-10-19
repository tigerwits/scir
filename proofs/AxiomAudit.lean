import Language
import NativeCodec
import WorkingSpec
import NativeCorpus
import SymbolReference
import SubstitutionReference
import DefinitionReference
import DefinitionCorpus

/- This command asks Lean's checked environment for transitive assumptions.
   It audits all exported SCIR theorem declarations, including generated ones,
   then the actual pure evaluators used by conformance. No source-name list is
   accepted as proof that a declaration compiled. IO, compiler and runtime
   behavior remain outside this logical assumption check. -/
open Lean Elab Command

run_cmd do
  let environment ← getEnv
  let requiredLaws := #[
    `SCIR.extensive, `SCIR.monotone, `SCIR.least_closed, `SCIR.idempotent,
    `SCIR.tuple_injective, `SCIR.reference_injective, `SCIR.text_reference_distinct,
    `SCIR.argument_arity_distinct, `SCIR.named_role_distinct,
    `SCIR.Symbols.reference_sound, `SCIR.Symbols.reference_complete,
    `SCIR.Symbols.relabel_identity, `SCIR.Symbols.relabel_composition,
    `SCIR.Symbols.labelMap_prefix, `SCIR.Symbols.labelMap_locate,
    `SCIR.Symbols.occurrence_preservation, `SCIR.Symbols.document_identity,
    `SCIR.Symbols.document_composition, `SCIR.Symbols.document_occurrence_preservation,
    `SCIR.Substitution.substitution_sound, `SCIR.Substitution.substitution_complete,
    `SCIR.Substitution.substitution_identity, `SCIR.Substitution.substitution_variable,
    `SCIR.Substitution.substitution_composition, `SCIR.Substitution.instantiation_complete,
    `SCIR.Substitution.instantiation_sound, `SCIR.Substitution.match_reconstruction,
    `SCIR.Substitution.match_sound, `SCIR.Definitions.substitution_agrees,
    `SCIR.Definitions.context_substitution_agrees, `SCIR.Definitions.substitution_plug,
    `SCIR.Definitions.factor_expansion, `SCIR.Definitions.fresh_factor_round_trip,
    `SCIR.Definitions.selection_reconstructs, `SCIR.Definitions.selected_factor_expansion,
    `SCIR.Language.Symbol.value_injective, `SCIR.Language.append_associative,
    `SCIR.Language.empty_left, `SCIR.Language.empty_right, `SCIR.Language.erase_annotations,
    `SCIR.Language.intersection_restricts, `SCIR.Language.intersection_idempotent]
  for name in requiredLaws do
    let some info := environment.find? name | throwError "missing required language law {name}"
    unless info.isTheorem do throwError "required language law is not a theorem: {name}"
  let mut count := 0
  for (name, info) in environment.constants.toList do
    if (`SCIR).isPrefixOf name && info.isTheorem then
      let assumptions ← collectAxioms name
      for assumption in assumptions do
        unless #[`propext, `Quot.sound].contains assumption do
          throwError "unapproved transitive theorem assumption {name}: {assumption}"
      count := count + 1
  let evaluators := #[
    `SCIR.Symbols.relabel, `SCIR.Symbols.documentOccurrences,
    `SCIR.Substitution.substitute, `SCIR.Substitution.instantiate, `SCIR.Substitution.matchReference,
    `SCIR.Definitions.plug, `SCIR.Definitions.select,
    `SCIR.SymbolReference.evaluate, `SCIR.SubstitutionReference.evaluate, `SCIR.DefinitionReference.evaluate,
    `SCIR.StrictJson.parse, `SCIR.Sha256.hex, `SCIR.Native.parseDocument, `SCIR.Native.formatDocument,
    `SCIR.Native.decodeRelations, `SCIR.Working.collection, `SCIR.Working.select, `SCIR.Working.affected,
    `SCIR.NativeCorpus.specimen, `SCIR.DefinitionCorpus.specimen]
  for name in evaluators do
    let some info := environment.find? name | throwError "missing evaluator {name}"
    if info.isUnsafe then throwError "unsafe evaluator {name}"
    let assumptions ← collectAxioms name
    for assumption in assumptions do
      unless #[`propext, `Quot.sound].contains assumption do
        throwError "unapproved evaluator assumption {name}: {assumption}"
    logInfo m!"AUDITED {name}: {assumptions}"
  logInfo m!"REQUIRED_LAWS={requiredLaws.size}; EXPORTED_THEOREMS_AUDITED={count}; PURE_EVALUATORS_AUDITED={evaluators.size}"
