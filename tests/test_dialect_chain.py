"""Cumulative dialects, explicit preservation, and a source-incompatible target."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

import scir
from scir import Term, digest, format_document, parse, parse_document, replace_at
from scir.annotations import Bundle, annotate
from scir.constraints import check
from scir.relations import decode, encode

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples/dialect-chain"
spec = importlib.util.spec_from_file_location("chain_contracts", CASE / "contracts.py")
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
DOCUMENTS = tuple(parse_document((CASE / "stages" / name).read_text(encoding="utf-8")) for name in chain.FILES)


def invoke(directory=CASE, *args):
    env = dict(os.environ, PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
    return subprocess.run([sys.executable, "-B", "run.py", *args], cwd=directory,
                          env=env, capture_output=True, text=True, timeout=20)


class DialectChainTests(unittest.TestCase):
    def test_fixed_source_is_bound_to_the_oracle(self):
        self.assertEqual(hashlib.sha256((CASE / "source.md").read_bytes()).hexdigest(), chain.SOURCE_SHA256)
        self.assertEqual(len(chain.COMMITMENTS), 4)

    def test_contracts_are_literal_prefixes(self):
        self.assertEqual(chain.CONTRACTS[0], ())
        for i in range(1, 5):
            self.assertEqual(chain.CONTRACTS[i], chain.CONTRACTS[i - 1] + chain.ADDITIONS[i])

    def test_full_acceptance_matrix(self):
        for i, document in enumerate(DOCUMENTS):
            actual = [not check(document, rules) for rules in chain.CONTRACTS]
            self.assertEqual(actual, [j <= i for j in range(5)])

    def test_each_previous_document_fails_the_new_restriction(self):
        expected = ("shape", "record-required", "reference-required")
        for i, rule in enumerate(expected, 1):
            issues = check(DOCUMENTS[i - 1], chain.CONTRACTS[i])
            self.assertIn(rule, {v.rule for v in issues})
            self.assertFalse(check(DOCUMENTS[i], chain.CONTRACTS[i]))

    def test_later_forms_are_permitted_by_the_first_dialect(self):
        for document in DOCUMENTS[1:]:
            self.assertEqual(check(document, chain.CONTRACTS[1]), ())

    def test_first_step_is_an_explicit_reviewed_mapping(self):
        self.assertEqual(chain.translate_draft(DOCUMENTS[0]), DOCUMENTS[1])
        with self.assertRaisesRegex(ValueError, "no reviewed draft mapping"):
            chain.translate_draft(parse_document("believes(Parser, return(Error))"))

    def test_structural_projections_reconstruct_the_prior_stage(self):
        self.assertEqual(chain.unrecord(DOCUMENTS[2]), DOCUMENTS[1])
        self.assertEqual(chain.inline_conditions(DOCUMENTS[3]), DOCUMENTS[2])
        self.assertEqual(chain.unrecord(chain.inline_conditions(DOCUMENTS[3])), DOCUMENTS[1])

    def test_reviewed_source_commitments_survive_all_stages(self):
        for i, document in enumerate(DOCUMENTS):
            review = chain.source_review(document, generic=i == 0)
            self.assertEqual(review["status"], "matches-authored-oracle")
            self.assertEqual(review["commitments"], dict.fromkeys(("S1", "S2", "S3", "S4"), True))
            self.assertEqual(review["missing"] + review["unexpected"], [])

    def test_fixed_questions_have_the_same_answers_at_each_stage(self):
        expected = {
            "state_unchanged_when": ["failure(Parse)"],
            "payload_evaluation_forbidden": True,
            "timeout_unspecified": True,
            "timeout_values": [],
            "parse_failure_effects": ["return(Error)", "unchanged(State)"],
        }
        for i, document in enumerate(DOCUMENTS):
            self.assertEqual(chain.source_review(document, generic=i == 0)["questions"], expected)

    def test_a_shared_condition_is_queryable_without_promoting_it_to_a_fact(self):
        from scir import parse_pattern, query
        pattern = parse_pattern("record(?record, requires(Parser, on(ref(C1), ?effect)))")
        hits = query(DOCUMENTS[3], pattern)
        self.assertEqual([str(h.bindings["record"]) for h in hits], ["R1", "R2"])
        self.assertEqual(query(DOCUMENTS[3], parse_pattern("failure(Parse)")), [])

    def test_adding_or_dropping_source_content_is_detected(self):
        for document in (DOCUMENTS[1][:-1], DOCUMENTS[1] + DOCUMENTS[1][:1]):
            self.assertFalse(check(document, chain.CONTRACTS[1]))
            self.assertEqual(chain.source_review(document)["status"], "differs-from-authored-oracle")

    def test_different_condition_is_not_silently_equivalent(self):
        changed = replace_at(DOCUMENTS[3], (0, 1, 0), Term("AnotherOperation"))
        self.assertFalse(check(changed, chain.CONTRACTS[3]))
        self.assertEqual(chain.source_review(changed)["commitments"],
                         {"S1": False, "S2": False, "S3": True, "S4": True})

    def test_different_record_order_is_not_a_new_source_fact(self):
        self.assertEqual(chain.source_review(tuple(reversed(DOCUMENTS[3])))["status"], "matches-authored-oracle")
        self.assertNotEqual(chain.inline_conditions(tuple(reversed(DOCUMENTS[3]))), DOCUMENTS[2])

    def test_generic_synonyms_are_not_core_normalization(self):
        self.assertNotEqual(DOCUMENTS[0], DOCUMENTS[1])
        self.assertNotEqual(digest(DOCUMENTS[0]), digest(DOCUMENTS[1]))
        self.assertEqual(parse_document(format_document(DOCUMENTS[0])), DOCUMENTS[0])

    def test_empty_is_generic_but_not_a_named_specification(self):
        self.assertFalse(check((), chain.CONTRACTS[1]))
        self.assertIn("record-required", {v.rule for v in check((), chain.CONTRACTS[2])})

    def test_wrong_shapes_do_not_crash_following_rules(self):
        sources = (
            "record(A)", "record(f(A), arbitrary(P))", "condition(C1)",
            "condition(C1, ref(C1))", "record(R1, record(R2, unspecified(timeoutPolicy(Parser))))",
            "requires(Parser, on(failure(Parse), return(Error, Other)))",
            "requires(f(Parser), on(ref(f(C1)), unchanged(State)))",
            "forbids(Parser, execute(Payload))", "unspecified(timeoutPolicy(f(Parser)))",
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertIn("shape", {v.rule for v in check(parse_document(source), chain.CONTRACTS[3])})

    def test_duplicate_ids_do_not_choose_a_declaration(self):
        document = DOCUMENTS[3] + (DOCUMENTS[3][0],)
        codes = {v.rule for v in check(document, chain.CONTRACTS[3])}
        self.assertTrue({"unique-id", "ambiguous-reference"} <= codes)
        with self.assertRaises(ValueError):
            chain.inline_conditions(document)

    def test_unknown_and_wrong_kind_references(self):
        for name, expected in (("C9", "unknown-reference"), ("R1", "reference-kind")):
            document = replace_at(DOCUMENTS[3], (1, 1, 1, 0, 0), Term(name))
            issues = check(document, chain.CONTRACTS[3])
            self.assertIn(expected, {v.rule for v in issues})
            self.assertIn((1, 1, 1, 0, 0), {v.path for v in issues})
            with self.assertRaises(ValueError):
                chain.inline_conditions(document)

    def test_references_can_point_forward(self):
        document = DOCUMENTS[3][1:] + DOCUMENTS[3][:1]
        self.assertFalse(check(document, chain.CONTRACTS[3]))
        self.assertEqual(chain.inline_conditions(document), DOCUMENTS[2])

    def test_open_ids_can_be_consistently_renamed(self):
        document = DOCUMENTS[3]
        for path in ((0, 0), (1, 1, 1, 0, 0), (2, 1, 1, 0, 0)):
            document = replace_at(document, path, Term("a fresh condition ID"))
        self.assertFalse(check(document, chain.CONTRACTS[3]))
        self.assertEqual(chain.inline_conditions(document), DOCUMENTS[2])

    def test_unused_definitions_cannot_be_erased_by_projection(self):
        document = DOCUMENTS[3] + (parse("condition(C2, failure(Other))"),)
        self.assertIn("unused-condition", {v.rule for v in check(document, chain.CONTRACTS[3])})
        with self.assertRaises(ValueError):
            chain.inline_conditions(document)

    def test_timeout_target_does_not_follow_from_the_fixed_source(self):
        issues = check(DOCUMENTS[3], chain.CONTRACTS[4])
        self.assertEqual({v.rule for v in issues}, {"timeout-required", "timeout-unspecified"})

    def test_invented_timeout_conforms_but_fails_source_review(self):
        document = parse_document((CASE / "counterexamples/unsupported-timeout.scir").read_text())
        self.assertFalse(check(document, chain.CONTRACTS[4]))
        review = chain.source_review(document)
        self.assertEqual(review["missing"], [str(chain.COMMITMENTS[3])])
        self.assertEqual(review["unexpected"], ['timeout(Parser, "30s")'])

    def test_timeout_may_not_coexist_with_unspecified_policy(self):
        document = DOCUMENTS[3] + (parse('record(R5, timeout(Parser, "30s"))'),)
        self.assertIn("timeout-unspecified", {v.rule for v in check(document, chain.CONTRACTS[4])})

    def test_nonpositive_or_nonduration_timeout_rejected(self):
        for value in ("0s", "soon", "-1s", "30", "1.5s"):
            document = replace_at(DOCUMENTS[3], (4, 1), Term("timeout", (Term("Parser"), Term(value))))
            self.assertIn("timeout-value", {v.rule for v in check(document, chain.CONTRACTS[4])})

    def test_source_review_does_not_replace_runtime_validation(self):
        with self.assertRaises(ValueError):
            chain.source_review(parse_document("condition(C1, ref(C1))"))

    def test_stage_edits_invalidate_snapshot_annotations(self):
        note = annotate(DOCUMENTS[2], (0,), "source", "S1")
        with self.assertRaises(ValueError):
            Bundle(DOCUMENTS[3], (note,))

    def test_stage_files_are_canonical_and_transport_preserves_checks(self):
        for i, name in enumerate(chain.FILES):
            self.assertEqual(format_document(DOCUMENTS[i]), (CASE / "stages" / name).read_text())
            for rules in chain.CONTRACTS:
                self.assertEqual(check(DOCUMENTS[i], rules), check(decode(encode(DOCUMENTS[i])), rules))

    def test_generated_projection_and_acceptance_laws(self):
        rng = random.Random(941)
        for case in range(500):
            owner, operation, value = (Term(rng.choice(("A", "return", "a name", "Алиса"))) for _ in range(3))
            effect = Term(rng.choice(("return", "unchanged")), (value,))
            condition = Term("failure", (operation,))
            reference = Term("ref", (Term("C"),))
            earlier = (Term("requires", (owner, Term("on", (condition, effect)))),)
            recorded = (Term("record", (Term("R"), earlier[0])),)
            obligation = Term("requires", (owner, Term("on", (reference, effect))))
            referenced = (Term("condition", (Term("C"), condition)),
                          Term("record", (Term("R"), obligation)))
            for rules in chain.CONTRACTS[:4]:
                self.assertFalse(check(referenced, rules))
                self.assertFalse(check(referenced, tuple(reversed(rules))))
            self.assertEqual(chain.inline_conditions(referenced), recorded)
            self.assertEqual(chain.unrecord(recorded), earlier)
            wire = encode(referenced)
            for table in ("nodes", "args", "roots"):
                rng.shuffle(wire[table])
            self.assertEqual(check(decode(wire), chain.CONTRACTS[3]), ())

    def test_runner_emits_a_complete_deterministic_report(self):
        first, second = invoke(CASE, "--json"), invoke(CASE, "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["status"], "checks-passed")
        self.assertEqual(report["blocked_target"]["status"], "blocked-by-fixed-source")
        self.assertFalse(report["counterexample"]["target_violations"])
        self.assertIn("no model evaluation", report["evidence"])

    def test_alternative_stage_files_are_not_silently_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            stages = Path(tmp) / "stages"
            shutil.copytree(CASE / "stages", stages)
            path = stages / chain.FILES[3]
            altered = path.read_text().replace("ref(C1)", "ref(C9)")
            path.write_text(altered)
            result = invoke(CASE, "--stages", str(stages), "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "needs-review")
            self.assertEqual(path.read_text(), altered)

    def test_bad_input_is_incomplete_not_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            stages = Path(tmp) / "stages"
            shutil.copytree(CASE / "stages", stages)
            (stages / chain.FILES[1]).write_text("f(")
            result = invoke(CASE, "--stages", str(stages), "--json")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("check incomplete", result.stderr)

    def test_changed_source_requires_a_new_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "dialect-chain"
            shutil.copytree(CASE, project)
            source = project / "source.md"
            source.write_text(source.read_text().replace("Error", "Success"))
            result = invoke(project, "--json")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("source changed", result.stderr)

    def test_runner_does_not_depend_on_assertions(self):
        env = dict(os.environ, PYTHONPATH=str(Path(scir.__file__).resolve().parent.parent))
        result = subprocess.run([sys.executable, "-O", "run.py", "--json"], cwd=CASE,
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "checks-passed")


if __name__ == "__main__":
    unittest.main()
