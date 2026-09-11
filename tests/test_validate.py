"""Structural validation of reserved arity and malformed names."""

from __future__ import annotations

import unittest

from scir import Atom, Call, ValidationError, Variable, parse, validate


class ValidateTests(unittest.TestCase):
    def test_valid_reserved_shapes(self) -> None:
        for source in (
            "not(P)",
            "and(A, B)",
            "and(A, B, C)",
            "or(A, B)",
            "or(A, B, C, D)",
            "if(A, B)",
            "think(Bob, not(P))",
        ):
            with self.subTest(source=source):
                validate(parse(source))

    def test_reserved_arity_rejected(self) -> None:
        cases = [
            "not()",
            "not(A, B)",
            "and(A)",
            "and()",
            "or(A)",
            "or()",
            "if(A)",
            "if(A, B, C)",
            "if()",
        ]
        for source in cases:
            with self.subTest(source=source):
                expr = parse(source)
                with self.assertRaises(ValidationError):
                    validate(expr)

    def test_ordinary_heads_have_no_arity_rule(self) -> None:
        validate(parse("email()"))
        validate(parse("email(Alice)"))
        validate(parse("email(Alice, Bob, Report)"))
        validate(parse("think(Bob, wrong(Chart))"))

    def test_malformed_constructed_names(self) -> None:
        with self.assertRaises(ValidationError):
            validate(Variable(""))
        with self.assertRaises(ValidationError):
            validate(Variable("?x"))
        with self.assertRaises(ValidationError):
            validate(Atom("123"))
        with self.assertRaises(ValidationError):
            validate(Atom(""))
        with self.assertRaises(ValidationError):
            validate(Call("not good", (Atom("X"),)))

    def test_atom_named_and_is_not_an_operator(self) -> None:
        validate(parse("and"))


if __name__ == "__main__":
    unittest.main()
