"""Independent native witnesses for the approved additive contract."""
import unittest
from scir import Term, parse, parse_pattern, match, digest


class ProfileContractTests(unittest.TestCase):
    def test_native_arity_and_quoted_labels_stay_unchanged(self):
        self.assertEqual(parse('"Alice"'), parse('Alice'))
        self.assertEqual(parse('f(a,)'), parse('f(a)'))
        with self.assertRaises(ValueError):
            parse('f()')
        with self.assertRaises(ValueError):
            parse('f(a, from: b)')
        self.assertIsNone(match(parse_pattern('f(?a, ?b)'), parse('f(a)')))

    def test_tagged_shapes_are_ordinary_distinct_native_trees(self):
        sources = ('a', '"scir.text"(a)', '"scir.ref"(a)',
                   '"scir.tuple"(a)', '"scir.tuple"',
                   'f(a,b)', 'f("scir.tuple"(a,b))',
                   'f("scir.kw"(from(a)))', 'f(from(a))')
        trees = tuple(parse(s) for s in sources)
        self.assertEqual(len(set(digest((t,)) for t in trees)), len(sources))
        for t in trees:
            self.assertEqual(parse(str(t)), t)
