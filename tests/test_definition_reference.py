"""Independent observations and bounded domain coverage for the Lean comparison."""
from pathlib import Path
import unittest

from tools import check_definition_reference as reference


class DefinitionReferenceTests(unittest.TestCase):
    def test_named_factor_observation_and_one_occurrence_mutant(self):
        document = (reference.node("pair", reference.node("A"), reference.node("A")),)
        value = reference.request("factor", document, path=(0, 1))
        expected = {"status": "complete", "document": {
            "version": "scir-relations/1.0", "nodes": [[0, "pair"], [1, "A"], [2, "scir.ref"], [3, "Fresh"]],
            "args": [[0, 0, 1], [0, 1, 2], [2, 0, 3]], "roots": [[0, 0]]},
            "definitions": reference.raw_relations((reference.definition("Fresh", reference.node("A")),)),
            "expanded": reference.raw_relations(document)}
        self.assertEqual(reference.runtime_observation(value), expected)
        self.assertNotEqual(reference.runtime_observation(value, mutant="factor-all-equal"), expected)

    def test_head_macros_and_ignored_budget_mutants_change_observations(self):
        definitions = (reference.definition("X", reference.node("A")),)
        value = reference.request("expand", (reference.node("X"),), definitions)
        expected = {"status": "complete", "document": reference.raw_relations((reference.node("X"),))}
        self.assertEqual(reference.runtime_observation(value), expected)
        self.assertNotEqual(reference.runtime_observation(value, mutant="bare-head-macros"), expected)
        limited = reference.request("expand", (reference.reference("Outside"),), max_nodes=1)
        self.assertEqual(reference.runtime_observation(limited)["status"], "incomplete")
        self.assertEqual(reference.runtime_observation(limited, mutant="ignore-output-budget")["status"], "complete")

    def test_corpus_replays_and_covers_the_complete_bounded_forest_domain(self):
        corpus = reference.corpus()
        self.assertEqual(corpus, reference.corpus())
        counts = {kind: sum(group == kind for group, _ in corpus)
                  for kind in ("exhaustive-expand", "exhaustive-factor", "seeded", "authored")}
        self.assertEqual(counts, {"exhaustive-expand": 205 * 3, "exhaustive-factor": 802 * 3 * 2,
                                 "seeded": 128, "authored": 31})
        self.assertNotEqual(reference.semantic_observation({"status": "rejected"}),
                            reference.semantic_observation({"status": "incomplete"}))

    def test_pinned_ci_runs_the_definition_reference_and_retains_evidence(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/profiles.yml").read_text(encoding="utf-8")
        for name in ("symbol", "substitution", "definition"):
            self.assertIn(f'python tools/check_{name}_reference.py "$RUNNER_TEMP/lean-4.19.0-linux/bin/lean"', workflow)
            self.assertIn(f"path: .build/{name}-reference/", workflow)

    def test_executed_adapter_audit_cannot_hide_new_theorems_or_assumptions(self):
        options = {"namespace": "SCIR.DefinitionReference", "kernels": ("evaluate",), "allow_kernel_only": True}
        report = "'SCIR.DefinitionReference.evaluate' depends on axioms: [propext, Quot.sound]"
        self.assertEqual(reference.audit_axioms("", report, **options), {"evaluate": ["propext", "Quot.sound"]})
        for source, output in (("theorem unreported : True := by trivial", report), ("", ""),
                               ("", report.replace("Quot.sound", "sorryAx"))):
            with self.subTest(source=source, output=output), self.assertRaises(ValueError):
                reference.audit_axioms(source, output, **options)
