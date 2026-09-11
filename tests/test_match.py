"""Pattern variables, occurs vs asserted, recursive query, failed matches."""

from __future__ import annotations

import unittest

from scir import (
    Atom,
    asserted,
    equal,
    match,
    occurs,
    parse,
    query,
)


class MatchTests(unittest.TestCase):
    def test_pattern_variables(self) -> None:
        bindings = match(parse("think(?who, ?content)"), parse("think(Bob, wrong(Chart))"))
        self.assertIsNotNone(bindings)
        assert bindings is not None
        self.assertEqual(bindings["who"], Atom("Bob"))
        self.assertEqual(bindings["content"], parse("wrong(Chart)"))

    def test_repeated_variable_consistent(self) -> None:
        self.assertEqual(
            match(parse("same(?x, ?x)"), parse("same(Alice, Alice)")),
            {"x": Atom("Alice")},
        )
        self.assertIsNone(match(parse("same(?x, ?x)"), parse("same(Alice, Bob)")))

    def test_failed_structural_matches(self) -> None:
        self.assertIsNone(match(parse("use(Alice, ?x)"), parse("use(Bob, Report)")))
        self.assertIsNone(match(parse("email(?s, Bob, ?t)"), parse("call(Bob, Carol)")))
        self.assertIsNone(match(parse("wrong(Chart)"), parse("wrong(Table)")))
        self.assertIsNone(match(parse("f(A, B)"), parse("f(A)")))
        self.assertEqual(occurs(parse("use(Alice, ?x)"), parse("think(Bob, use(Carol, X))")), [])

    def test_recursive_query_binds_nested_use(self) -> None:
        subject = parse("think(Bob, mistakenly(use(Alice, yesterday(SalesData))))")
        pattern = parse("use(Alice, ?x)")
        bindings = occurs(pattern, subject)
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0]["x"], parse("yesterday(SalesData)"))
        self.assertEqual(str(bindings[0]["x"]), "yesterday(SalesData)")
        # Top-level match must not succeed: the root is think(...).
        self.assertIsNone(match(pattern, subject))
        self.assertEqual(query(subject, pattern, recursive=False), [])
        self.assertEqual(query(subject, pattern, recursive=True), bindings)

    def test_asserted_versus_nested_occurrence(self) -> None:
        subject = parse("think(Bob, mistakenly(use(Alice, yesterday(SalesData))))")
        use_pat = parse("use(Alice, ?x)")
        think_pat = parse("think(Bob, ?content)")
        self.assertEqual(occurs(use_pat, subject)[0]["x"], parse("yesterday(SalesData)"))
        self.assertEqual(asserted(use_pat, subject), [])
        self.assertEqual(
            asserted(think_pat, subject),
            [{"content": parse("mistakenly(use(Alice, yesterday(SalesData)))")}],
        )

    def test_and_conjuncts_are_asserted_but_not_negated_children(self) -> None:
        subject = parse("and(call(Bob, Carol), not(answer(Carol)))")
        self.assertEqual(asserted(parse("call(Bob, Carol)"), subject), [{}])
        self.assertEqual(asserted(parse("not(answer(Carol))"), subject), [{}])
        self.assertEqual(asserted(parse("answer(Carol)"), subject), [])
        self.assertEqual(occurs(parse("answer(Carol)"), subject), [{}])

    def test_not_think_versus_think_not(self) -> None:
        a = parse("not(think(Bob, P))")
        b = parse("think(Bob, not(P))")
        self.assertFalse(equal(a, b))
        self.assertNotEqual(a, b)
        self.assertEqual(asserted(parse("think(Bob, P)"), a), [])
        self.assertEqual(asserted(parse("not(P)"), b), [])
        self.assertEqual(asserted(parse("P"), a), [])
        self.assertEqual(asserted(parse("P"), b), [])
        self.assertEqual(occurs(parse("P"), a), [{}])
        self.assertEqual(occurs(parse("P"), b), [{}])
        self.assertEqual(asserted(parse("not(?x)"), a), [{"x": parse("think(Bob, P)")}])
        self.assertEqual(asserted(parse("think(Bob, ?x)"), b), [{"x": parse("not(P)")}])
        self.assertEqual(asserted(parse("think(Bob, ?x)"), a), [])

    def test_if_does_not_assert_children(self) -> None:
        subject = parse(
            "if(tomorrow(confirm(Carol, Numbers)), send(Bob, corrected(Report), Client))"
        )
        self.assertEqual(asserted(parse("confirm(Carol, Numbers)"), subject), [])
        self.assertEqual(asserted(parse("send(Bob, corrected(Report), Client)"), subject), [])
        self.assertEqual(occurs(parse("confirm(Carol, ?n)"), subject), [{"n": Atom("Numbers")}])

    def test_or_does_not_assert_disjuncts(self) -> None:
        subject = parse("or(call(Bob, Carol), email(Bob, Carol, Report))")
        self.assertEqual(asserted(parse("call(Bob, Carol)"), subject), [])
        self.assertEqual(occurs(parse("call(Bob, Carol)"), subject), [{}])

    def test_think_does_not_assert_nested_ordinary_call(self) -> None:
        subject = parse("think(Bob, wrong(Chart))")
        self.assertEqual(asserted(parse("wrong(Chart)"), subject), [])
        self.assertEqual(occurs(parse("wrong(Chart)"), subject), [{}])


class TreeOpTests(unittest.TestCase):
    def test_walk_find_filter_replace(self) -> None:
        from scir import filter_subtrees, find_symbol, replace, walk

        expr = parse("think(Bob, wrong(Chart))")
        nodes = list(walk(expr))
        self.assertEqual(nodes[0], expr)
        self.assertIn(Atom("Bob"), nodes)
        self.assertIn(Atom("Chart"), nodes)
        self.assertEqual(find_symbol(expr, "wrong"), [parse("wrong(Chart)")])
        self.assertEqual(find_symbol(expr, "Bob"), [Atom("Bob")])
        charts = filter_subtrees(expr, lambda n: n == Atom("Chart"))
        self.assertEqual(charts, [Atom("Chart")])
        rewritten = replace(expr, parse("wrong(Chart)"), parse("right(Chart)"))
        self.assertEqual(rewritten, parse("think(Bob, right(Chart))"))
        self.assertEqual(expr, parse("think(Bob, wrong(Chart))"))

    def test_replace_does_not_rewrite_inside_replacement(self) -> None:
        from scir import replace

        expr = parse("f(A)")
        out = replace(expr, Atom("A"), parse("g(A)"))
        self.assertEqual(out, parse("f(g(A))"))

    def test_hash_and_equality_are_structural(self) -> None:
        a = parse("think(Bob, wrong(Chart))")
        b = parse("think(Bob, wrong(Chart))")
        c = parse("think(Bob, wrong(Table))")
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, c)
        self.assertEqual(len({a, b, c}), 2)
        self.assertNotEqual(parse("Alice"), parse("Alice()"))
        self.assertNotEqual(Atom("x"), parse("?x"))


if __name__ == "__main__":
    unittest.main()
