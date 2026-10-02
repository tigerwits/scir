import itertools
import unittest
from scir import Term, parse, digest
from scir import profile as p


class NamedRoleTests(unittest.TestCase):
    def test_independent_role_tree_and_permutations(self):
        fields = (("to", Term("b")), ("from", Term("a")))
        expected = parse('send(doc,"scir.kw"(from(a),to(b)))')
        for permutation in itertools.permutations(fields):
            term = p.application("send", (Term("doc"),), fields=permutation)
            self.assertEqual(term, expected)
            self.assertEqual(p.read_arguments(term), (Term("doc"),))
            self.assertEqual(p.read_fields(term), tuple(reversed(fields)))
        self.assertNotEqual(expected, parse('send(doc,from(a),to(b))'))
        self.assertEqual(p.application("f", (Term("a"),)), parse('f(a)'))

    def test_tuple_roles_do_not_unpack(self):
        value = p.tuple_value((Term("doc"),), fields=(("to", Term("b")),))
        self.assertEqual(p.read_tuple(value), (Term("doc"),))
        self.assertEqual(p.read_fields(value), (("to", Term("b")),))
        packed = p.application("send", (value,))
        direct = p.application("send", (Term("doc"),), fields=p.read_fields(value))
        self.assertNotEqual(digest((packed,)), digest((direct,)))

    def test_duplicate_unsorted_and_misplaced_fields_fail(self):
        bad = ('f("scir.kw"(a(x),a(x)))', 'f("scir.kw"(z(x),a(y)))',
               'f("scir.kw"(a(x)),b)', 'f("scir.kw"(a))',
               'f("scir.kw"(a(x,y)))', '"scir.kw"(a(x))',
               'f("scir.kw"(a("scir.kw"(b(x)))))')
        for source in bad:
            with self.subTest(source=source), self.assertRaises(p.ProfileError):
                p.validate((parse(source),))
        with self.assertRaises(p.ProfileError):
            p.application("f", fields=(("x", Term("a")), ("x", Term("a"))))
        with self.assertRaises(p.ProfileError):
            p.application("f", (parse('"scir.kw"(a(x))'),))
        with self.assertRaises(p.ProfileError):
            p.application("scir.text")

    def test_literal_tag_names_and_unicode_keys_are_not_expressions(self):
        fields = (("é", Term("x")), ("scir.ref", p.text("scir.kw")), ("e\u0301", Term("y")))
        value = p.application("f", fields=fields)
        self.assertEqual([k for k, _ in p.read_fields(value)], ["e\u0301", "scir.ref", "é"])
        self.assertEqual(p.read_fields(p.text("scir.kw")), ())
        for fields in ({"x": Term("a")}, (("", Term("a")),), (("x", "a"),)):
            with self.assertRaises(ValueError):
                p.application("f", fields=fields)
