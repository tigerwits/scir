"""Exact symbols, simultaneous relabeling and occurrence-preserving observations."""
from dataclasses import FrozenInstanceError
import unittest

from scir import (Symbol, Term, digest, format_document, parse, parse_document,
                  parse_pattern, relabel_symbols, symbol_occurrences)
from scir.patterns import Node, Var, match
from scir import profile as p
from scir.knowledge import build_index


class SymbolTests(unittest.TestCase):
    def test_symbol_value_and_legacy_constructor_boundary(self):
        symbol = Symbol("Alice")
        term = Term(symbol, (Term("child"),))
        pattern = Node(symbol, (Var("x"),))
        self.assertEqual(symbol.value, "Alice")
        self.assertEqual(hash(symbol), hash(Symbol("Alice")))
        self.assertEqual(term, Term("Alice", (Term("child"),)))
        self.assertIs(type(term.symbol), str)
        self.assertIs(type(pattern.symbol), str)
        self.assertEqual(term.head, symbol)
        self.assertEqual(pattern.head, symbol)
        self.assertEqual(match(pattern, term), {"x": Term("child")})
        self.assertEqual(term, parse(str(term)))
        self.assertEqual(pattern, parse_pattern(str(pattern)))
        with self.assertRaises(FrozenInstanceError):
            symbol.value = "changed"
        self.assertNotEqual(symbol, Term("Alice"))
        self.assertNotEqual(symbol, "Alice")

    def test_exact_unicode_and_quoting(self):
        for value in ("é", "e\u0301", "A", "a", "two words", "?x", "line\nbreak", "λ"):
            symbol = Symbol(value)
            self.assertEqual(parse(str(symbol)), Term(value))
            self.assertEqual(Term(symbol).head, symbol)
        self.assertNotEqual(Symbol("é"), Symbol("e\u0301"))
        self.assertNotEqual(Symbol("A"), Symbol("a"))
        for value in ("", None, 1, True, "\ud800", Term("A")):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                Symbol(value)

    def test_occurrences_retain_order_duplicates_and_arities(self):
        document = parse_document("f(A, A); f; A(f)")
        self.assertEqual(symbol_occurrences(document), (
            ((0,), Symbol("f")), ((0, 0), Symbol("A")), ((0, 1), Symbol("A")),
            ((1,), Symbol("f")), ((2,), Symbol("A")), ((2, 0), Symbol("f"))))
        self.assertEqual(symbol_occurrences(()), ())

    def test_relabeling_is_simultaneous_and_changes_heads_and_leaves(self):
        document = parse_document("A(B, A); B; A(B, A)")
        result = relabel_symbols(document, {Symbol("A"): Symbol("B"), "B": "C"})
        self.assertEqual(result, parse_document("B(C, B); C; B(C, B)"))
        self.assertEqual(document, parse_document("A(B, A); B; A(B, A)"))
        self.assertEqual(relabel_symbols(document, {}), document)
        self.assertEqual(digest(relabel_symbols(document, {})), digest(document))

    def test_composition_and_occurrence_naturality(self):
        document = parse_document('f(A, B); "two words"(A); f')
        first, second = {"f": "g", "A": "B"}, {"g": "h", "B": "C"}
        composed = {s: second.get(first.get(s, s), first.get(s, s))
                    for s in first.keys() | second.keys()}
        actual = relabel_symbols(relabel_symbols(document, first), second)
        self.assertEqual(actual, relabel_symbols(document, composed))
        self.assertEqual(symbol_occurrences(actual), tuple(
            (path, Symbol(composed.get(symbol.value, symbol.value)))
            for path, symbol in symbol_occurrences(document)))

    def test_invalid_mapping_and_normalized_duplicate_keys_fail(self):
        document = parse_document("f(A)")
        for mapping in (None, [("A", "B")], {"A": ""}, {"": "A"}, {"A": Term("B")},
                        {"A": "B", Symbol("A"): "C"}):
            with self.subTest(mapping=repr(mapping)), self.assertRaises(ValueError):
                relabel_symbols(document, mapping)
        self.assertEqual(format_document(document), "f(A)\n")

    def test_noninjective_relabeling_does_not_preserve_match_failure(self):
        original = parse_document("same(A, B)")
        pattern = parse_pattern("same(?x, ?x)")
        self.assertIsNone(match(pattern, original[0]))
        changed = relabel_symbols(original, {"A": "C", "B": "C"})
        self.assertEqual(match(pattern, changed[0]), {"x": Term("C")})

    def test_native_relabeling_does_not_imply_profile_preservation(self):
        literal = p.text("A")
        self.assertEqual(p.read_text(relabel_symbols((literal,), {"A": "B"})[0]), "B")
        document = tuple(p.application("record", (Term(i), Term("Note"), Term("payload")))
                         for i in ("A", "B"))
        build_index(document, collection="symbols")
        changed = relabel_symbols(document, {"A": "B"})
        with self.assertRaises(p.ProfileError):
            build_index(changed, collection="symbols")


if __name__ == "__main__":
    unittest.main()
