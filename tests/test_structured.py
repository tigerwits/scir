import unittest
from scir import Term, parse, format_document, digest, parse_pattern, query
from scir import profile as p


class StructuredTests(unittest.TestCase):
    def test_independent_native_encodings(self):
        pairs = [
            (p.text(""), '"scir.text"'),
            (p.text("hello"), '"scir.text"(hello)'),
            (p.text("scir.ref"), '"scir.text"("scir.ref")'),
            (p.reference("A1"), '"scir.ref"(A1)'),
            (p.tuple_value(), '"scir.tuple"'),
            (p.tuple_value((Term("a"),)), '"scir.tuple"(a)'),
        ]
        for actual, expected in pairs:
            self.assertEqual(actual, parse(expected))
        for value in ("", "hello", "scir.kw", "α\n\x00\"\\", "e\u0301", "é"):
            self.assertEqual(p.read_text(p.text(value)), value)
        self.assertNotEqual(p.text("Alice"), Term("Alice"))
        self.assertNotEqual(p.reference("A1"), Term("A1"))

    def test_nesting_arity_and_duplicates(self):
        a, b, c = map(Term, "abc")
        flat = Term("f", (a, b, c))
        nested = Term("f", (a, p.tuple_value((b, c))))
        packed = Term("f", (p.tuple_value((a, b, c)),))
        self.assertEqual(len({digest((t,)) for t in (flat, nested, packed)}), 3)
        self.assertEqual(p.read_tuple(p.tuple_value((a, a))), (a, a))
        self.assertNotEqual(p.tuple_value((a,)), a)
        self.assertEqual(len(query((flat, flat), parse_pattern("a"), scope="all")), 2)

    def test_malformed_tags_and_unicode(self):
        for source in ('"scir.ref"', '"scir.ref"(a,b)', '"scir.text"(f(a))',
                       '"scir.text"(a,b)', '"scir.kw"', 'f("scir.kw")'):
            term = parse(source)  # Native validity does not imply profile validity.
            with self.subTest(source=source), self.assertRaises(p.ProfileError):
                p.validate((term,))
        for value in (None, 1, "\ud800"):
            with self.assertRaises(ValueError):
                p.text(value)
        with self.assertRaises(ValueError):
            p.reference("")

    def test_exact_size_and_bounded_shared_occurrences(self):
        document = (parse('f(a, "é", "x y")'), p.text(""), p.tuple_value())
        size = p.measure(document)
        self.assertEqual(size.bytes, len(format_document(document).encode("utf-8")))
        self.assertEqual(size.nodes, 6)
        self.assertEqual(p.measure(()).bytes, 0)
        for limits in (p.Limits(nodes=5), p.Limits(depth=0), p.Limits(bytes=size.bytes-1)):
            with self.assertRaises(p.LimitError):
                p.validate(document, limits=limits)
        self.assertEqual(p.validate(document, limits=p.Limits(nodes=6, depth=1, bytes=size.bytes)), size)
        leaf = Term("a")
        for _ in range(20):
            leaf = Term("pair", (leaf, leaf))
        with self.assertRaises(p.LimitError):
            p.validate((leaf,), limits=p.Limits(nodes=100))
        for kw in ({"nodes": True}, {"depth": 129}, {"bytes": 0}):
            with self.assertRaises(ValueError):
                p.Limits(**kw)


if __name__ == "__main__":
    unittest.main()
