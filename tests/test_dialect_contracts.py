"""Independent outcomes for named plans; no code authentication or agent trial."""
from dataclasses import FrozenInstanceError, replace
import json
import unittest

from scir import Term, parse_document, parse_pattern
from scir.constraints import Violation, forms, check
from scir.dialects import Context, Dialect, Rule, compose, evaluate, from_constraint
from scir.profile import Limits, LimitError

IDENTITY = "a" * 64  # Deliberate test-double identity, not a production code hash.
CONTEXT = Context("fixture", "r1")
DOC = parse_document("a\nb")


def pass_rule(document, context):
    return ()


def rule(name, callback=pass_rule, requires=()):
    return Rule(name, "1", IDENTITY, callback, requires)


class DialectContractTests(unittest.TestCase):
    def test_empty_and_legacy_constraints_keep_their_acceptance(self):
        empty = evaluate((), Dialect("open", "1", ()), CONTEXT, collection="c")
        self.assertTrue(empty.conforms)
        self.assertTrue(empty.as_dict()["all_executed"])
        predicate = forms(parse_pattern("a"))
        r = from_constraint("shape", "1", IDENTITY, predicate)
        d = Dialect("atoms", "1", (r,))
        result = evaluate(DOC, d, CONTEXT, collection="c")
        self.assertEqual(result.steps[0].violations, check(DOC, (predicate,)))
        self.assertEqual(result.steps[0].violations, (Violation((1,), "form", "no permitted form matches this occurrence"),))
        self.assertEqual(result.outcome, "rejected")

    def test_dependency_failure_blocks_only_dependents(self):
        called = []
        def reject(doc, context):
            called.append("a")
            return (Violation(None, "a", "missing prerequisite"),)
        def later(doc, context):
            called.append("independent")
            return ()
        d = Dialect("gated", "1", (rule("a", reject), rule("b", requires=("a",)),
                                     rule("c", requires=("b",)), rule("independent", later)))
        result = evaluate(DOC, d, CONTEXT, collection="c")
        self.assertEqual(called, ["a", "independent"])
        self.assertEqual([s.status for s in result.steps], ["rejected", "blocked", "blocked", "passed"])
        self.assertEqual(result.steps[1].blocked_by, ("a",))
        self.assertEqual(result.steps[2].blocked_by, ("b",))
        self.assertTrue(result.as_dict()["complete"])
        self.assertFalse(result.as_dict()["all_executed"])
        self.assertFalse(result.conforms)

    def test_callback_errors_and_partial_generators_never_conform(self):
        def broken(doc, context):
            yield Violation(None, "partial", "must not be a complete rejection")
            raise OSError("not included in the output")
        result = evaluate(DOC, Dialect("d", "1", (rule("a", broken), rule("b", requires=("a",)))),
                          CONTEXT, collection="c")
        self.assertEqual(result.outcome, "incomplete")
        self.assertEqual(result.steps[0].violations, ())
        self.assertEqual(result.steps[0].error, "callback-error")
        self.assertEqual(result.steps[1].status, "blocked")
        self.assertNotIn("not included", json.dumps(result.as_dict()))
        self.assertFalse(result.as_dict()["complete"])

    def test_invalid_results_and_paths_are_incomplete(self):
        callbacks = (lambda d,c: None, lambda d,c: [None],
                     lambda d,c: [Violation((7,), "bad", "outside document")])
        for callback in callbacks:
            with self.subTest(callback=callback):
                result = evaluate(DOC, Dialect("d", "1", (rule("a", callback),)), CONTEXT, collection="c")
                self.assertEqual(result.outcome, "incomplete")
                self.assertFalse(result.conforms)

    def test_resource_failure_and_rejection_precedence(self):
        def limit(d, c):
            raise LimitError("fixture exhaustion")
        rejected = lambda d,c: (Violation(None, "reject", "invalid"),)
        d = Dialect("d", "1", (rule("bad", rejected), rule("limit", limit)))
        result = evaluate(DOC, d, CONTEXT, collection="c")
        self.assertEqual(result.outcome, "incomplete")
        self.assertEqual(result.steps[1].error, "resource-limit")

    def test_interrupts_are_not_swallowed(self):
        for kind in (KeyboardInterrupt, SystemExit):
            def stop(d,c):
                raise kind()
            with self.assertRaises(kind):
                evaluate(DOC, Dialect("d", "1", (rule("a", stop),)), CONTEXT, collection="c")

    def test_receipt_binds_all_input_identities_not_only_content(self):
        d = Dialect("d", "1", (rule("a"),))
        context = Context("service", "revision-1", parse_document("verified(x)"))
        result = evaluate(DOC, d, context, collection="original")
        self.assertTrue(result.matches(DOC, d, context, collection="original"))
        variants = ((DOC[:-1], d, context, "original"), (DOC, d, context, "other"),
                    (DOC, replace(d, version="2"), context, "original"),
                    (DOC, d, replace(context, revision="revision-2"), "original"),
                    (DOC, d, replace(context, document=()), "original"),
                    (DOC, replace(d, rules=(replace(d.rules[0], implementation="b"*64),)), context, "original"))
        for document, dialect, basis, collection in variants:
            self.assertFalse(result.matches(document, dialect, basis, collection=collection))
        # Returned dictionaries are copies. A content identity still has ABA semantics.
        result.as_dict()["dialect"]["rules"].clear()
        self.assertTrue(result.matches(tuple(DOC), d, context, collection="original"))

    def test_frozen_context_is_supplied_separately_from_candidate(self):
        def only_authorized(doc, ctx):
            if ctx.document != (Term("approved"),):
                yield Violation(None, "authority", "external approval missing")
        d = Dialect("d", "1", (rule("approval", only_authorized),))
        authored = parse_document("approved\ntrusted(yes)")
        self.assertFalse(evaluate(authored, d, CONTEXT, collection="c").conforms)
        trusted = Context("fixture", "r1", (Term("approved"),))
        self.assertTrue(evaluate(authored, d, trusted, collection="c").conforms)
        with self.assertRaises(FrozenInstanceError):
            trusted.document = ()
        with self.assertRaises(ValueError):
            Context("bad", "r1", [])

    def test_plan_errors_fail_before_any_check(self):
        for rules in ((rule("a"), rule("a")), (rule("a", requires=("missing",)),),
                      (rule("a", requires=("b",)), rule("b", requires=("a",)))):
            with self.assertRaises(ValueError):
                Dialect("invalid", "1", rules)
        with self.assertRaises(ValueError):
            rule("self", requires=("self",))
        with self.assertRaises(ValueError):
            rule("a", requires=("x", "x"))
        with self.assertRaises(ValueError):
            Rule("a", "1", "not-an-identity", pass_rule)
        with self.assertRaises(ValueError):
            Dialect("d", "1", [rule("a")])
        with self.assertRaises(ValueError):
            Dialect("d", "1", tuple(rule(str(i)) for i in range(257)))

    def test_composition_preserves_parents_and_deduplicates_shared_binding(self):
        a, b, c = rule("a"), rule("b", requires=("a",)), rule("c", requires=("a",))
        left, right = Dialect("left", "1", (a,b)), Dialect("right", "1", (a,c))
        combined = compose("both", "1", left, right, rules=(rule("d", requires=("b","c")),))
        self.assertEqual(tuple(r.name for r in combined.rules), ("a", "b", "c", "d"))
        self.assertTrue(evaluate(DOC, combined, CONTEXT, collection="c").conforms)
        with self.assertRaises(ValueError):
            compose("bad", "1", left, rules=(a,))
        rebound = replace(a, run=lambda d,c: ())
        with self.assertRaises(ValueError):
            compose("bad", "1", left, Dialect("other", "1", (rebound,)))
        x, y = rule("x"), rule("y")
        with self.assertRaises(ValueError):
            compose("bad", "1", Dialect("xy", "1", (x,y)), Dialect("yx", "1", (y,x)))

    def test_composition_conjunction_and_unchanged_content(self):
        rules = tuple(from_constraint(n, "1", IDENTITY, forms(parse_pattern(n))) for n in ("a", "b"))
        d = compose("contradiction", "1", *(Dialect(r.name, "1", (r,)) for r in rules))
        for doc in ((), parse_document("a"), parse_document("b"), DOC):
            outcomes = [evaluate(doc, Dialect(r.name, "1", (r,)), CONTEXT, collection="c").conforms for r in rules]
            self.assertEqual(evaluate(doc, d, CONTEXT, collection="c").conforms, all(outcomes))
        self.assertEqual(DOC, parse_document("a\nb"))

    def test_input_and_global_output_limits_never_return_partial_success(self):
        called = []
        def count(doc,ctx):
            called.append(1)
            return ()
        d = Dialect("d", "1", (rule("a", count),))
        with self.assertRaises(LimitError):
            evaluate(DOC, d, CONTEXT, collection="c", limits=Limits(nodes=1))
        self.assertEqual(called, [])
        d = Dialect("d", "1", (rule("a", lambda d,c: (Violation(None,"a","x"),)*2),))
        self.assertEqual(len(evaluate(DOC,d,CONTEXT,collection="c",max_violations=2).steps[0].violations), 2)
        for kwargs in ({"max_violations":1}, {"max_bytes":1}):
            with self.assertRaises(LimitError):
                evaluate(DOC, d, CONTEXT, collection="c", **kwargs)
        for kwargs in ({"max_bytes":True}, {"max_violations":0}):
            with self.assertRaises(ValueError):
                evaluate(DOC, d, CONTEXT, collection="c", **kwargs)

    def test_context_limit_precedes_callback_and_manifest_is_deterministic(self):
        context = Context("c", "r", parse_document("a\nb"))
        d = Dialect("d", "1", (rule("a"),))
        with self.assertRaises(LimitError):
            evaluate((), d, context, collection="c", limits=Limits(nodes=1))
        self.assertEqual(d.fingerprint, Dialect("d", "1", (rule("a"),)).fingerprint)
        self.assertNotEqual(d.fingerprint, replace(d, version="2").fingerprint)
