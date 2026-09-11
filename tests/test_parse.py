"""Nested parsing and parse/print round-trip against the shipped parser."""

from __future__ import annotations

import unittest

from scir import Atom, Call, ParseError, Variable, parse


README_ROWS = [
    "at(leave(Alice, Office), six)",
    "before(email(Alice, Bob, latest(Report)), leave(Alice, Office))",
    "and(at(read(Bob, Report), Train), notice(Bob, wrong(chartOf(Report))))",
    "think(Bob, mistakenly(use(Alice, yesterday(SalesData))))",
    "and(call(Bob, Carol), not(answer(Carol)))",
    "if(tomorrow(confirm(Carol, Numbers)), send(Bob, corrected(Report), Client))",
]


class ParseTests(unittest.TestCase):
    def test_atom_variable_call(self) -> None:
        self.assertEqual(parse("Alice"), Atom("Alice"))
        self.assertEqual(parse("?x"), Variable("x"))
        self.assertEqual(parse("wrong(Chart)"), Call("wrong", (Atom("Chart"),)))

    def test_nested_parsing(self) -> None:
        expr = parse("think(Bob, wrong(Chart))")
        self.assertEqual(
            expr,
            Call("think", (Atom("Bob"), Call("wrong", (Atom("Chart"),)))),
        )
        deeper = parse("think(Bob, mistakenly(use(Alice, yesterday(SalesData))))")
        self.assertIsInstance(deeper, Call)
        self.assertEqual(deeper.head, "think")
        inner = deeper.args[1]
        self.assertIsInstance(inner, Call)
        self.assertEqual(inner.head, "mistakenly")

    def test_print_think_bob_wrong_chart(self) -> None:
        expr = parse("think(Bob, wrong(Chart))")
        self.assertEqual(str(expr), "think(Bob, wrong(Chart))")

    def test_round_trip_nested_and_variables(self) -> None:
        samples = [
            "Alice",
            "?x",
            "?who",
            "wrong(Chart)",
            "email(Alice, Bob, Report)",
            "think(Bob, wrong(Chart))",
            "before(email(Alice, Bob, Report), leave(Alice, Office))",
            "think(?who, ?content)",
            "email(?sender, Bob, ?thing)",
            "use(Alice, ?x)",
            "same(?x, ?x)",
            "f()",
        ]
        for source in samples:
            with self.subTest(source=source):
                expr = parse(source)
                self.assertEqual(str(expr), source)
                self.assertEqual(parse(str(expr)), expr)

    def test_readme_table_round_trip(self) -> None:
        for source in README_ROWS:
            with self.subTest(source=source):
                expr = parse(source)
                self.assertEqual(str(expr), source)
                self.assertEqual(parse(str(expr)), expr)

    def test_whitespace_is_not_canonical(self) -> None:
        expr = parse("  think( Bob , wrong( Chart ) )  ")
        self.assertEqual(str(expr), "think(Bob, wrong(Chart))")
        self.assertEqual(expr, parse("think(Bob, wrong(Chart))"))

    def test_malformed_variables_and_syntax(self) -> None:
        for source in ("?", "??x", "?123", "", "f(a,)", "f(,a)", "f(a,,b)", "(Alice)", "think(Bob"):
            with self.subTest(source=source):
                with self.assertRaises(ParseError):
                    parse(source)

    def test_trailing_input_rejected(self) -> None:
        with self.assertRaises(ParseError):
            parse("think(Bob, wrong(Chart)) extra")

    def test_zero_arity_call_is_not_an_atom(self) -> None:
        self.assertNotEqual(parse("Alice"), parse("Alice()"))
        self.assertEqual(str(parse("Alice()")), "Alice()")


if __name__ == "__main__":
    unittest.main()
