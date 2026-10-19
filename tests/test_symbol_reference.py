"""Independent observations and failure controls for the executable-law gate."""
from pathlib import Path
import unittest

from tools import check_symbol_reference as reference


class SymbolReferenceTests(unittest.TestCase):
    def test_authored_observation_and_meaningful_mutants(self):
        request = {"version": "scir-symbol-reference/1", "operation": "relabel",
                   "document": {"version": "scir-relations/1.0", "nodes": [[0, "A"], [1, "B"]],
                                "args": [[0, 0, 1]], "roots": [[0, 0]]},
                   "renaming": [["A", "B"], ["B", "C"]]}
        expected = {"status": "complete",
                    "document": {"version": "scir-relations/1.0", "nodes": [[0, "B"], [1, "C"]],
                                 "args": [[0, 0, 1]], "roots": [[0, 0]]},
                    "occurrences": [[[0], "B"], [[0, 0], "C"]]}
        self.assertEqual(reference.runtime_observation(request), expected)
        for mutant in ("sequential-renaming", "leaf-only-renaming"):
            self.assertNotEqual(reference.runtime_observation(request, mutant=mutant), expected)

    def test_corpus_has_independent_small_forest_coverage_and_replays(self):
        cases = reference.corpus()
        self.assertEqual(cases, reference.corpus())
        small = [value for kind, value in cases if kind == "exhaustive"]
        self.assertEqual(len(small), 255)
        # Catalan(n)*2**n counts ordered forests with n labeled nodes.
        self.assertEqual({n: sum(len(value["document"]["nodes"]) == n for value in small) // 5
                          for n in range(4)}, {0: 1, 1: 2, 2: 8, 3: 40})
        self.assertEqual(len({reference.wire(value) for value in small}), 255)

    def test_axiom_gate_rejects_missing_or_transitively_admitted_claims(self):
        source = "theorem claim : True := by trivial\n"
        reports = "\n".join(f"'SCIR.Symbols.{name}' does not depend on any axioms"
                            for name in ("claim", "relabel", "relabelDocument", "documentOccurrences"))
        self.assertEqual(reference.audit_axioms(source, reports)["claim"], [])
        with self.assertRaises(ValueError):
            reference.audit_axioms(source, reports.replace("'SCIR.Symbols.claim'", "'SCIR.Symbols.other'"))
        with self.assertRaises(ValueError):
            reference.audit_axioms(source, reports.replace(
                "'SCIR.Symbols.claim' does not depend on any axioms",
                "'SCIR.Symbols.claim' depends on axioms: [propext, sorryAx]"))

    def test_the_executed_reference_is_wired_to_the_pinned_ci_gate(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/profiles.yml").read_text(encoding="utf-8")
        self.assertIn('python tools/check_symbol_reference.py "$RUNNER_TEMP/lean-4.19.0-linux/bin/lean"', workflow)
