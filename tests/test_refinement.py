"""Independent acceptance-set, plan-boundary and incomplete-check regressions."""
import unittest
from itertools import product

from scir import Term, digest, format_document, parse_document
from scir.constraints import Violation
from scir.refinement import Checker, compile_profile, evaluate, require_extension


def plan(body):
    return parse_document('validation(Test, ' + body + ')')


def profile(body, registry):
    return compile_profile(plan(body), 'Test', registry)


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.pass_ = Checker(lambda d: ())
        self.fail = Checker(lambda d: (Violation((0,), 'wanted', 'missing'),))

    def test_empty_rule_stage_is_explicit_structural_only(self):
        p = profile('stage(raw, parents, rules)', {})
        r = evaluate((Term('anything'),), p, 'raw')
        self.assertTrue(r.conforms)
        self.assertEqual(r.executed, ())

    def test_conjunction_keeps_earlier_failure(self):
        p = profile('stage(a, parents, rules(no)), stage(b, parents(a), rules(yes))',
                    {'no': self.fail, 'yes': self.pass_})
        r = evaluate((Term('X'),), p, 'b')
        self.assertFalse(r.conforms)
        self.assertEqual(r.executed, ('no',))
        self.assertEqual(r.scheduled, ('no', 'yes'))

    def test_diamond_evaluates_inherited_rule_once(self):
        calls = []
        reg = {n: Checker(lambda d, n=n: calls.append(n) or ()) for n in 'abcd'}
        p = profile('stage(A, parents, rules(a)), stage(B, parents(A), rules(b)), '
                    'stage(C, parents(A), rules(c)), stage(D, parents(B,C), rules(d,a))', reg)
        self.assertTrue(evaluate((), p, 'D').conforms)
        self.assertEqual(calls, list('abcd'))

    def test_forward_parent_and_declaration_order(self):
        p = profile('stage(b, parents(a), rules(y)), stage(a, parents, rules(x))',
                    {'x': self.pass_, 'y': Checker(lambda d: (), ('x',))})
        self.assertEqual(tuple(s.name for s in p.stages), ('b', 'a'))
        self.assertEqual(evaluate((), p, 'b').executed, ('x', 'y'))

    def test_invalid_plans_fail_closed(self):
        cases = [
            'stage(a, parents, rules(x)), stage(a, parents, rules)',
            'stage(a, parents(missing), rules)',
            'stage(a, parents(a), rules)',
            'stage(a, parents(b), rules), stage(b, parents(a), rules)',
            'stage(a, parents, rules(unknown))',
            'stage(a, parents, rules(x,x))',
            'stage(a, parents, rules), stage(b, parents(a,a), rules)',
            'stage(a, wrong, rules)', 'stage(a, parents, wrong)',
            'stage(a, parents)', 'stage(a(x), parents, rules)',
            'stage(a, parents, rules(x(y)))',
        ]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ValueError):
                profile(body, {'x': self.pass_})

    def test_unknown_checker_even_on_unselected_stage(self):
        with self.assertRaises(ValueError):
            profile('stage(a, parents, rules), stage(b, parents, rules(unknown))', {})

    def test_prerequisite_cannot_be_omitted_or_reordered(self):
        reg = {'shape': self.pass_, 'refs': Checker(lambda d: (), ('shape',))}
        for body in ('stage(a, parents, rules(refs))',
                     'stage(a, parents, rules(refs,shape))'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                profile(body, reg)

    def test_registry_is_snapshotted(self):
        reg = {'x': self.pass_}
        p = profile('stage(a, parents, rules(x))', reg)
        reg['x'] = self.fail
        self.assertTrue(evaluate((Term('A'),), p, 'a').conforms)

    def test_unknown_stage(self):
        p = profile('stage(a, parents, rules)', {})
        with self.assertRaises(ValueError):
            evaluate((), p, 'missing')

    def test_explicit_profile_selection_and_no_auto_selection(self):
        source = plan('stage(a, parents, rules)')
        with self.assertRaises(ValueError):
            compile_profile(source, 'Missing', {})
        with self.assertRaises(ValueError):
            compile_profile(source + source, 'Test', {})
        p = compile_profile(source + (Term('execute', (Term('untrusted'),)),), 'Test', {})
        self.assertTrue(evaluate(source, p, 'a').conforms)

    def test_checker_exceptions_propagate(self):
        def broken(doc):
            raise RuntimeError('not completed')
        p = profile('stage(a, parents, rules(x))', {'x': Checker(broken)})
        with self.assertRaises(RuntimeError):
            evaluate((), p, 'a')

    def test_partial_iterator_failure_propagates(self):
        def broken(doc):
            yield Violation(None, 'first', 'first')
            raise ValueError('not completed')
        p = profile('stage(a, parents, rules(x))', {'x': Checker(broken)})
        with self.assertRaises(ValueError):
            evaluate((), p, 'a')

    def test_invalid_diagnostics_and_limit_are_not_success(self):
        for invalid in ('not a violation', Violation((2,), 'path', 'bad path')):
            p = profile('stage(a, parents, rules(x))', {'x': Checker(lambda d: (invalid,))})
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate((Term('X'),), p, 'a')
        p = profile('stage(a, parents, rules(x))', {'x': Checker(lambda d: (
            Violation(None, 'many', 'many'), Violation(None, 'many', 'many')))})
        with self.assertRaises(ValueError):
            evaluate((), p, 'a', max_violations=1)

    def test_checker_definition_boundaries(self):
        for run, requires in ((None, ()), (lambda d: (), []),
                              (lambda d: (), ('x','x')), (lambda d: (), ('',))):
            with self.subTest(requires=requires), self.assertRaises(ValueError):
                Checker(run, requires)

    def test_stage_budget(self):
        with self.assertRaises(ValueError):
            profile(','.join(f'stage(s{i},parents,rules)' for i in range(129)), {})
        with self.assertRaises(ValueError):
            compile_profile(parse_document('validation(Test)'), 'Test', {})

    def test_compiled_rule_budget(self):
        reg = {f'r{i}': self.pass_ for i in range(8193)}
        with self.assertRaises(ValueError):
            profile('stage(a, parents, rules(' + ','.join(reg) + '))', reg)

    def test_profile_identity_binds_data_not_callable_code(self):
        a = profile('stage(a, parents, rules(x))', {'x': self.pass_})
        b = profile('stage(a, parents, rules(x))', {'x': self.fail})
        self.assertEqual(a.fingerprint, b.fingerprint)
        # The evidence collector must separately pin checker implementation bytes.
        d = (Term('A'),)
        self.assertNotEqual(evaluate(d, a, 'a').conforms, evaluate(d, b, 'a').conforms)

    def test_unchanged_content_order_duplicates_and_diagnostics(self):
        doc = parse_document('proof(Lean, "not checked")\nA\nA')
        before = format_document(doc), digest(doc)
        p = profile('stage(a, parents, rules(x))', {'x': self.fail})
        report = evaluate(doc, p, 'a')
        self.assertEqual(before, (format_document(doc), digest(doc)))
        self.assertEqual(report.input_fingerprint, before[1])
        self.assertEqual(report.violations[0].path, (0,))

    def test_extension_requires_same_order_and_bindings(self):
        reg = {'x': self.pass_, 'y': self.fail}
        a = profile('stage(a,parents,rules(x))', reg).stage('a')
        b = profile('stage(b,parents,rules(x,y))', reg).stage('b')
        require_extension(a, b)
        for candidate in (
            profile('stage(a,parents,rules)', reg).stage('a'),
            profile('stage(a,parents,rules(x))', {'x': self.fail}).stage('a'),
        ):
            with self.assertRaises(ValueError):
                require_extension(a, candidate)
        c = profile('stage(c,parents,rules(y,x))', reg).stage('c')
        with self.assertRaises(ValueError):
            require_extension(b, c)

    def test_exhaustive_eight_constraint_acceptance_sets(self):
        # 256 independent documents, all nine prefixes; direct Boolean oracle.
        reg = {f'c{i}': Checker(lambda d, i=i: () if d[i].symbol == 'yes' else
                               (Violation((i,), 'bit', 'no'),)) for i in range(8)}
        body = ['stage(s0, parents, rules)'] + [
            f'stage(s{i+1}, parents(s{i}), rules(c{i}))' for i in range(8)]
        p = profile(','.join(body), reg)
        for bits in product((False,True), repeat=8):
            doc = tuple(Term('yes' if b else 'no') for b in bits)
            results = [evaluate(doc, p, f's{i}').conforms for i in range(9)]
            self.assertEqual(results, [all(bits[:i]) for i in range(9)])
            self.assertTrue(all(not results[i+1] or results[i] for i in range(8)))


if __name__ == '__main__':
    unittest.main()
