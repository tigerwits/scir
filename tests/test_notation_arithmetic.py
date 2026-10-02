import unittest
from scir import parse_document, digest
from scir.notation import lower, pretty, environment_digest


class NotationArithmeticTests(unittest.TestCase):
    def test_independent_precedence_and_grouping_goldens(self):
        cases = (
            ('a+b', 'plus(a,b)'), ('+(a,b)', 'plus(a,b)'),
            ('a+b+c', 'plus(a,b,c)'), ('(a+b)+c', 'plus(plus(a,b),c)'),
            ('a+(b+c)', 'plus(a,plus(b,c))'), ('a+(b,c)', 'plus(a,"scir.tuple"(b,c))'),
            ('a+b*c', 'plus(a,mul(b,c))'), ('a/b/c', 'div(div(a,b),c)'),
            ('a/(b/c)', 'div(a,div(b,c))'), ('a^b^c', 'power(a,power(b,c))'),
            ('-a^b', 'neg(power(a,b))'), ('a^-b', 'power(a,neg(b))'),
            ('-(a,b)', 'neg("scir.tuple"(a,b))'), ('2+3', 'plus("2","3")'),
            ('a + #comment\n b', 'plus(a,b)'), ('f(a+b, total: c*d)', 'f(plus(a,b),"scir.kw"(total(mul(c,d))))'),
        )
        for source, native in cases:
            with self.subTest(source=source):
                expected = parse_document(native)
                self.assertEqual(lower(source, operators='arithmetic/1'), expected)
                self.assertEqual(lower(pretty(expected), operators='arithmetic/1'), expected)
        forms = ('a+b+c', '(a+b)+c', 'a+(b+c)')
        self.assertEqual(len({digest(lower(s, operators='arithmetic/1')) for s in forms}), 3)

    def test_operators_are_fixed_opt_in_and_non_evaluating(self):
        for source in ('a+b-c', 'a*b/c', 'a/b*c', 'a-b+c', 'a^', '+', 'a=b', 'a!!'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                lower(source, operators='arithmetic/1')
        with self.assertRaises(ValueError):
            lower('a+b')
        with self.assertRaises(ValueError):
            lower('a', operators='custom')
        self.assertNotEqual(environment_digest(), environment_digest('arithmetic/1'))
        self.assertEqual(lower('plus(a,b)'), lower('a+b', operators='arithmetic/1'))
        self.assertNotEqual(lower('2+3', operators='arithmetic/1'), parse_document('"5"'))

    def test_combined_binding_roles_tuples_and_operators(self):
        source = '''@using C = Communication
@let total = a + b
@let pair = (doc, amount: $total)
C.send($pair, to: bob, from: alice)'''
        expected = parse_document('"Communication.send"("scir.tuple"(doc,"scir.kw"(amount(plus(a,b)))),"scir.kw"(from(alice),to(bob)))')
        self.assertEqual(lower(source, operators='arithmetic/1'), expected)
        source = '@using plus = Captured\n@let x = a+b\nhold($x, plus.f(a))'
        self.assertEqual(lower(source, operators='arithmetic/1'), parse_document('hold(plus(a,b),"Captured.f"(a))'))
