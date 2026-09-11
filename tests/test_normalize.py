"""Kernel-only normalization: double negation and and/or flattening."""

from __future__ import annotations

import unittest

from scir import normalize, parse, validate


class NormalizeTests(unittest.TestCase):
    def test_double_negation(self) -> None:
        self.assertEqual(normalize(parse("not(not(X))")), parse("X"))
        self.assertEqual(normalize(parse("not(not(wrong(Chart)))")), parse("wrong(Chart)"))
        self.assertEqual(normalize(parse("not(not(not(X)))")), parse("not(X)"))
        self.assertEqual(normalize(parse("not(not(not(not(X))))")), parse("X"))

    def test_nested_and_flattening(self) -> None:
        self.assertEqual(normalize(parse("and(A, and(B, C))")), parse("and(A, B, C)"))
        self.assertEqual(normalize(parse("and(and(A, B), C)")), parse("and(A, B, C)"))
        self.assertEqual(
            normalize(parse("and(A, and(B, C), D)")),
            parse("and(A, B, C, D)"),
        )
        self.assertEqual(
            normalize(parse("and(and(A, B), and(C, D))")),
            parse("and(A, B, C, D)"),
        )

    def test_nested_or_flattening(self) -> None:
        self.assertEqual(normalize(parse("or(A, or(B, C))")), parse("or(A, B, C)"))
        self.assertEqual(normalize(parse("or(or(A, B), C)")), parse("or(A, B, C)"))
        self.assertEqual(
            normalize(parse("or(A, or(B, C), D)")),
            parse("or(A, B, C, D)"),
        )

    def test_does_not_rewrite_ordinary_symbols(self) -> None:
        expr = parse("email(Alice, Bob, Report)")
        self.assertEqual(normalize(expr), expr)
        self.assertEqual(str(normalize(expr)), "email(Alice, Bob, Report)")
        think = parse("think(Bob, wrongly(Chart))")
        self.assertEqual(normalize(think), think)

    def test_does_not_reorder_or_invent_and(self) -> None:
        expr = parse("and(B, A)")
        self.assertEqual(normalize(expr), expr)

    def test_normalization_under_ordinary_and_reserved_heads(self) -> None:
        self.assertEqual(
            normalize(parse("think(Bob, not(not(wrong(Chart))))")),
            parse("think(Bob, wrong(Chart))"),
        )
        self.assertEqual(
            normalize(parse("if(and(A, and(B, C)), D)")),
            parse("if(and(A, B, C), D)"),
        )

    def test_normalize_preserves_valid_kernel_shapes(self) -> None:
        expr = normalize(parse("and(A, and(B, not(not(C))))"))
        self.assertEqual(expr, parse("and(A, B, C)"))
        validate(expr)


if __name__ == "__main__":
    unittest.main()
