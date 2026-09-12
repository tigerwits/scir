"""Dialect acceptance, diagnostic algebra, and boundaries independent of truth."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import random
import runpy
import unittest

from scir import Term, digest, parse, parse_document, parse_pattern, replace_at, validate
from scir.annotations import Alternatives, Bundle
from scir.constraints import Violation, check, forms, vocabulary
from scir.relations import decode, encode
from scir.tree import walk

ROOT = Path(__file__).resolve().parents[1]


class ConstraintTests(unittest.TestCase):
    def test_no_rules_accept_supported_documents(self):
        for source in ("", "A", "not(A, B)", "think(Bob, not(P))"):
            with self.subTest(source=source):
                self.assertEqual(check(parse_document(source), ()), ())

    def test_forms_are_an_allowlist_not_a_presence_requirement(self):
        rule = forms(parse_pattern("A"), parse_pattern("f(?x)"))
        self.assertEqual(check(parse_document("A; f(B)"), (rule,)), ())
        self.assertEqual(check((), (rule,)), ())
        self.assertEqual(check(parse_document("B"), (rule,))[0].path, (0,))

    def test_empty_form_allowlist_rejects_every_selected_occurrence(self):
        self.assertEqual(check((), (forms(),)), ())
        self.assertEqual([v.path for v in check(parse_document("A; f(A)"), (forms(),))], [(0,), (1,)])

    def test_ground_success_empty_binding_map_is_not_a_failure(self):
        self.assertEqual(check(parse_document("A"), (forms(parse_pattern("A")),)), ())

    def test_root_scope_never_descends_implicitly(self):
        document = parse_document("think(Bob, forbidden(X))")
        self.assertEqual(check(document, (forms(parse_pattern("think(?who, ?what)")),)), ())
        violations = check(document, (forms(parse_pattern("forbidden(?x)")),))
        self.assertEqual([v.path for v in violations], [(0,)])

    def test_all_scope_includes_leaves_and_duplicate_occurrences(self):
        rule = forms(parse_pattern("f(?x, ?y)"), scope="all")
        document = parse_document("f(A, A); f(A, A)")
        self.assertEqual([v.path for v in check(document, (rule,))],
                         [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_captures_are_local_to_each_match(self):
        rule = forms(parse_pattern("pair(?x, ?x)"))
        document = parse_document("pair(A, A); pair(B, B); pair(A, B)")
        self.assertEqual([v.path for v in check(document, (rule,))], [(2,)])

    def test_wildcards_do_not_impose_equality(self):
        self.assertEqual(check(parse_document("pair(A, B)"),
                               (forms(parse_pattern("pair(?_, ?_)")),)), ())

    def test_quoted_capture_label_is_literal(self):
        self.assertEqual(check(parse_document('"?x"'), (forms(parse_pattern('"?x"')),)), ())
        self.assertTrue(check(parse_document("A"), (forms(parse_pattern('"?x"')),)))

    def test_vocabulary_includes_heads_leaves_and_case(self):
        document = parse_document("email(Alice, alice, Report)")
        issues = check(document, (vocabulary({"email", "Alice"}),))
        self.assertEqual([v.path for v in issues], [(0, 1), (0, 2)])
        self.assertEqual(check((), (vocabulary(()),)), ())
        self.assertEqual([v.path for v in check(document, (vocabulary(()),))],
                         [(0,), (0, 0), (0, 1), (0, 2)])

    def test_vocabulary_preserves_unicode_exactly(self):
        issues = check(parse_document('"é"; "é"'), (vocabulary({"é"}),))
        self.assertEqual([v.path for v in issues], [(1,)])

    def test_vocabulary_snapshots_mutable_configuration(self):
        names = {"A"}
        rule = vocabulary(names)
        names.add("B")
        self.assertTrue(check(parse_document("B"), (rule,)))

    def test_diagnostic_order_is_rule_then_occurrence_order(self):
        document = parse_document("f(A); B")
        rules = (vocabulary({"A"}, rule="labels"), forms(parse_pattern("A"), rule="roots"))
        self.assertEqual([(v.rule, v.path) for v in check(document, rules)],
                         [("labels", (0,)), ("labels", (1,)), ("roots", (0,)), ("roots", (1,))])

    def test_duplicate_rules_keep_duplicate_diagnostics(self):
        rule = vocabulary({"A"})
        document = parse_document("B")
        self.assertEqual(check(document, (rule, rule)), check(document, (rule,)) * 2)

    def test_custom_global_rule(self):
        def nonempty(document):
            return () if document else (Violation(None, "nonempty", "empty document"),)
        self.assertEqual(check((), (nonempty,)), (Violation(None, "nonempty", "empty document"),))
        self.assertEqual(check(parse_document("A"), (nonempty,)), ())

    def test_single_pass_rule_iterable(self):
        rules = (rule for rule in (forms(parse_pattern("A")), vocabulary({"A"})))
        self.assertEqual(check(parse_document("A"), rules), ())

    def test_validation_never_mutates_or_rewrites_content(self):
        document = parse_document("and(A, B); not(not(P))")
        before = digest(document)
        self.assertTrue(check(document, (vocabulary({"A"}),)))
        self.assertEqual(digest(document), before)
        self.assertEqual(document, parse_document("and(A, B); not(not(P))"))
        validate(document)

    def test_check_rejects_bundles_patterns_and_alternatives(self):
        document = parse_document("A")
        for value in (Bundle(document), Alternatives((document, parse_document("B"))),
                      parse_pattern("?x"), list(document), document[0]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check(value, ())

    def test_violations_are_immutable(self):
        issue = Violation((0,), "shape", "wrong shape")
        with self.assertRaises(FrozenInstanceError):
            issue.path = (1,)

    def test_invalid_violation_fields(self):
        for path in ((), [], (True,), (-1,), (0, "x")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                Violation(path, "rule", "message")
        for rule, message in (("", "message"), ("rule", ""), (1, "message"),
                              ("rule", "\ud800"), ("\udfff", "message")):
            with self.subTest(rule=rule, message=message), self.assertRaises(ValueError):
                Violation(None, rule, message)

    def test_nonexistent_reported_path_is_a_checker_error(self):
        for path in ((1,), (0, 0)):
            with self.subTest(path=path), self.assertRaises(ValueError):
                check(parse_document("A"), (lambda document: (Violation(path, "bad", "bad path"),),))

    def test_malformed_constraint_output_does_not_pass(self):
        for output in ([False], ["error"], [None]):
            with self.subTest(output=output), self.assertRaises(ValueError):
                check((), (lambda document: output,))
        with self.assertRaises(ValueError):
            check((), (None,))
        with self.assertRaises(TypeError):
            check((), (lambda document: None,))

    def test_callback_failure_is_not_a_content_violation(self):
        error = RuntimeError("checker failed")
        def broken(document):
            yield Violation(None, "first", "one finding")
            raise error
        with self.assertRaises(RuntimeError) as caught:
            check((), (broken,))
        self.assertIs(caught.exception, error)

    def test_diagnostic_limit_raises_instead_of_returning_partial_results(self):
        rule = vocabulary(())
        document = parse_document("A; A")
        self.assertEqual(len(check(document, (rule,), max_violations=2)), 2)
        with self.assertRaisesRegex(ValueError, "check incomplete"):
            check(document, (rule,), max_violations=1)
        for bound in (0, -1, True, 1.5):
            with self.subTest(bound=bound), self.assertRaises(ValueError):
                check((), (), max_violations=bound)

    def test_infinite_diagnostic_iterator_is_stopped(self):
        seen = []
        def broken(document):
            while True:
                seen.append(1)
                yield Violation(None, "broken", "repeated finding")
        with self.assertRaises(ValueError):
            check((), (broken,), max_violations=2)
        self.assertEqual(len(seen), 3)

    def test_input_bounds_apply_before_custom_code_runs(self):
        called = []
        def rule(document):
            called.append(True)
            return ()
        leaf = Term("A")
        self.assertEqual(check((leaf,) * 100_000, ()), ())
        with self.assertRaises(ValueError):
            check((leaf,) * 100_001, (rule,))
        deep = leaf
        for _ in range(128):
            deep = Term("f", (deep,))
        self.assertEqual(check((deep,), ()), ())
        with self.assertRaises(ValueError):
            check((Term("f", (deep,)),), (rule,))
        self.assertEqual(called, [])

    def test_bad_helper_configuration_fails_early(self):
        for value in ("f(?x)", parse("A"), None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                forms(value)
        with self.assertRaises(ValueError):
            forms(scope="facts")
        for value in ("ABC", b"ABC", {""}, {"\ud800"}, {1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                vocabulary(value)
        for factory in (forms, lambda **kw: vocabulary((), **kw)):
            with self.assertRaises(ValueError):
                factory(rule="")

    def test_generated_constraint_laws(self):
        rng = random.Random(1001)
        def tree(depth):
            children = tuple(tree(depth - 1) for _ in range(rng.randrange(3))) if depth else ()
            return Term(rng.choice(("A", "B", "f", "g")), children)
        left = (forms(parse_pattern("A"), parse_pattern("f(?_, ?_)")),)
        right = (vocabulary({"A", "f"}),)
        for _ in range(500):
            document = tuple(tree(3) for _ in range(rng.randrange(4)))
            a, b = check(document, left), check(document, right)
            both = check(document, left + right)
            self.assertEqual(both, a + b)
            self.assertEqual(not both, (not a) and (not b))
            self.assertEqual(bool(check(document, left + left)), bool(a))
            self.assertEqual(bool(check(document, right + left)), bool(both))
            self.assertEqual(check(decode(encode(document)), left + right), both)
            expected = [path for path, t in walk(document) if t.symbol not in {"A", "f"}]
            self.assertEqual([issue.path for issue in b], expected)

    def test_edit_need_not_preserve_acceptance(self):
        rules = (forms(parse_pattern("f(A)")),)
        document = parse_document("f(A)")
        self.assertFalse(check(document, rules))
        edited = replace_at(document, (0, 0), parse("B"))
        validate(edited)
        self.assertTrue(check(edited, rules))


class DialectExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = runpy.run_path(str(ROOT / "examples/dialects.py"))

    def issues(self, source):
        return check(parse_document(source), self.example["INVESTIGATION"])

    def test_example_runs(self):
        for name in ("fixed_vocabulary", "investigation", "correlations"):
            self.example[name]()

    def test_nonempty_rule_is_explicit(self):
        self.assertEqual([(v.path, v.rule) for v in self.issues("")], [(None, "nonempty")])

    def test_ids_are_open_but_payload_vocabulary_is_closed(self):
        self.assertFalse(self.issues('hypothesis("new ID", stale(Cache))'))
        issues = self.issues("hypothesis(H1, stael(Cache))")
        self.assertEqual([(v.path, v.rule) for v in issues], [((0, 1), "payload-form")])

    def test_payload_wrapper_does_not_bypass_checks(self):
        issues = self.issues("hypothesis(H1, probably(stale(Cache)))")
        self.assertEqual([(v.path, v.rule) for v in issues], [((0, 1), "payload-form")])

    def test_malformed_shapes_and_ids_fail_without_crashing_other_rules(self):
        for source, path, rule in (("hypothesis(H1)", (0,), "root-form"),
                                   ("supports(O1)", (0,), "root-form"),
                                   ("hypothesis(id(H1), stale(Cache))", (0, 0), "identifier")):
            with self.subTest(source=source):
                self.assertIn((path, rule), [(v.path, v.rule) for v in self.issues(source)])

    def test_forward_references_are_allowed(self):
        self.assertFalse(self.issues(
            "supports(O1, H1); hypothesis(H1, stale(Cache)); observation(O1, stale(Cache))"))

    def test_references_check_namespace_not_just_name_presence(self):
        source = "hypothesis(H1, stale(Cache)); observation(O1, stale(Cache)); supports(H1, O1)"
        self.assertEqual([(v.path, v.rule) for v in self.issues(source)],
                         [((2, 0), "reference-kind"), ((2, 1), "reference-kind")])

    def test_duplicate_ids_are_not_silently_resolved(self):
        source = "hypothesis(H1, stale(Cache)); hypothesis(H1, wrong(Report)); supports(H1, H1)"
        self.assertEqual([(v.path, v.rule) for v in self.issues(source)],
                         [((1, 0), "unique-id"), ((2, 0), "ambiguous-reference"),
                          ((2, 1), "ambiguous-reference")])

    def test_nested_declarations_do_not_become_referents(self):
        source = "hypothesis(H1, observation(O1, stale(Cache))); supports(O1, H1)"
        issues = self.issues(source)
        self.assertIn(((1, 0), "unknown-reference"), [(v.path, v.rule) for v in issues])

    def test_same_spelling_can_be_used_for_an_id_and_a_label(self):
        self.assertFalse(self.issues("hypothesis(hypothesis, stale(Cache))"))

    def test_conformance_does_not_prove_evidence(self):
        self.assertFalse(self.issues(
            "hypothesis(H1, wrong(Report)); observation(O1, stale(Cache)); supports(O1, H1)"))


if __name__ == "__main__":
    unittest.main()
