import random
import unittest
from scir import Term, parse_document, digest
from scir import profile as p
from scir.notation import lower, pretty, Limits


class NotationProfileTests(unittest.TestCase):
    def test_independent_structural_goldens(self):
        cases = (
            ('(a)', 'a'), ('()', '"scir.tuple"'), ('(a,)', '"scir.tuple"(a)'),
            ('f(a,b)', 'f(a,b)'), ('f((a,b))', 'f("scir.tuple"(a,b))'),
            ('f(a,)', 'f(a)'), ('f((a,))', 'f("scir.tuple"(a))'),
            ('f(a,(b,c))', 'f(a,"scir.tuple"(b,c))'),
            ('send(doc,to:b,from:a)', 'send(doc,"scir.kw"(from(a),to(b)))'),
            ('(doc,from:a,to:b)', '"scir.tuple"(doc,"scir.kw"(from(a),to(b)))'),
            ('(only:a)', '"scir.tuple"("scir.kw"(only(a)))'),
            ('t""', '"scir.text"'), ('t"scir.ref"', '"scir.text"("scir.ref")'),
            ('&A1', '"scir.ref"(A1)'), ('&"odd-id"', '"scir.ref"("odd-id")'),
            ('f("scir.kw": t"&not-a-reference")', 'f("scir.kw"("scir.kw"("scir.text"("&not-a-reference"))))'),
            ('Domain.X(01,1,1.0)', '"Domain.X"("01","1","1.0")'),
            ('# hi\nf(\n a,\n b,\n)\n', 'f(a,b)'),
        )
        for source, native in cases:
            with self.subTest(source=source):
                expected = parse_document(native)
                self.assertEqual(lower(source), expected)
                self.assertEqual(lower(pretty(expected)), expected)
        sources = ('f(a,b,c)', 'f(a,(b,c))', 'f((a,b,c))')
        self.assertEqual(len({digest(lower(s)) for s in sources}), 3)

    def test_negative_notation_and_no_implicit_execution(self):
        cases = ('f()', 'f(a,key:b,a)', 'f(key:a,key:a)', 'f(a)(b)', '&A(x)',
                 't"x"(y)', '""', 'f("":a)', 'a;;b', 'a b', 'f(a b)',
                 '"scir.text"', 'scir.tuple(a)', '{a}', '?x', 'a=b', 'a+b',
                 'f(a', '"unterminated', 't"\\ud800"')
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ValueError):
                lower(source)
        self.assertEqual(lower('send(doc)'), parse_document('send(doc)'))

    def test_head_newline_is_not_implicit_application(self):
        self.assertEqual(lower('f\n(a)'), parse_document('f\na'))
        self.assertEqual(lower('f(a)\n(b,)'), parse_document('f(a)\n"scir.tuple"(b)'))
        self.assertEqual(lower('t"é\\n#x"'), parse_document('"scir.text"("é\\n#x")'))

    def test_resource_bounds_and_no_truncated_print(self):
        for source, limits in (('a', Limits(source_bytes=1)), ('f(a)', Limits(tokens=3)),
                               ('f(a)', Limits(nodes=1)), ('((a))', Limits(depth=1)),
                               ('a', Limits(expanded_bytes=1))):
            if source == 'a' and limits.source_bytes == 1:
                self.assertEqual(lower(source, limits=limits), (Term('a'),))
            else:
                with self.assertRaises(p.LimitError):
                    lower(source, limits=limits)
        with self.assertRaises(p.LimitError):
            lower('é', limits=Limits(source_bytes=1))
        with self.assertRaises(p.LimitError):
            pretty((p.text('x'*100),), limits=Limits(source_bytes=10))
        for kwargs in ({'depth': 65}, {'nodes': True}, {'tokens': 0}):
            with self.assertRaises(ValueError):
                Limits(**kwargs)

    def test_seeded_profile_print_roundtrips(self):
        rng = random.Random(20261002)
        names = ('a', 'b', 'Domain.X', '01', 'é', 'e\u0301', 'a b')
        def value(depth):
            choice = rng.randrange(3 if depth == 0 else 5)
            if choice == 0:
                return Term(rng.choice(names))
            if choice == 1:
                return p.text(rng.choice(names + ('', 'scir.kw', '\n\\"')))
            if choice == 2:
                return p.reference(rng.choice(names))
            children = tuple(value(depth-1) for _ in range(rng.randrange(3)))
            fields = (("role", value(depth-1)),) if rng.randrange(2) else ()
            return p.tuple_value(children, fields=fields) if choice == 3 else p.application('f', children, fields=fields)
        for _ in range(400):
            document = tuple(value(3) for _ in range(rng.randrange(4)))
            self.assertEqual(lower(pretty(document)), document)
