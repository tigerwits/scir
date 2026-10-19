"""Independent observations and mutation sensitivity for the executed reference."""
from pathlib import Path
import unittest

from tools import check_substitution_reference as reference


class SubstitutionReferenceTests(unittest.TestCase):
    def test_independent_substitution_observation_detects_sequential_mutant(self):
        value = reference.request("substitute", reference.variable("x"),
                                  [("x", reference.variable("y")), ("y", reference.node("A"))])
        expected = {"status": "complete", "pattern": {
            "version": "scir-relations/1.0", "nodes": [[0, "Var"], [1, "y"]],
            "args": [[0, 0, 1]], "roots": [[0, 0]]}}
        self.assertEqual(reference.runtime_observation(value), expected)
        self.assertNotEqual(reference.runtime_observation(value, mutant="sequential-substitution"), expected)

    def test_repeated_capture_mutant_and_empty_success_are_distinguished(self):
        value = reference.request("match", reference.node("f", reference.variable("x"), reference.variable("x")),
                                  ("f", (("A", ()), ("B", ()))))
        self.assertEqual(reference.runtime_observation(value), {"status": "complete", "matched": False})
        self.assertTrue(reference.runtime_observation(value, mutant="ignore-repeated-captures")["matched"])
        empty = reference.runtime_observation(reference.request("match", reference.node("A"), ("A", ())))
        self.assertTrue(empty["matched"])
        self.assertEqual(empty["bindings"], {})

    def test_corpus_replays_and_has_complete_small_domain_products(self):
        corpus = reference.corpus()
        self.assertEqual(corpus, reference.corpus())
        counts = {kind: sum(group == kind for group, _ in corpus) for kind in (
            "exhaustive-substitute", "exhaustive-match", "exhaustive-instantiate")}
        self.assertEqual(counts, {"exhaustive-substitute": 60 * 17,
                                 "exhaustive-match": 60 * 22, "exhaustive-instantiate": 60 * 9})
        self.assertNotEqual(reference.semantic_observation({"status": "rejected"}),
                            reference.semantic_observation({"status": "incomplete"}))

    def test_pinned_ci_executes_both_references(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/profiles.yml").read_text(encoding="utf-8")
        for name in ("symbol", "substitution"):
            self.assertIn(f'python tools/check_{name}_reference.py "$RUNNER_TEMP/lean-4.19.0-linux/bin/lean"', workflow)
