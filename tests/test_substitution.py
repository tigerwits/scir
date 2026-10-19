"""Named-variable substitution is separate from labels, wildcards and grounding."""
import unittest

import scir
from scir import Symbol, Term, parse, parse_pattern
from scir.patterns import Node, Var, instantiate, match, substitute


class SubstitutionTests(unittest.TestCase):
    def test_simultaneous_insertion_keeps_unmapped_variables_open(self):
        pattern = parse_pattern("pair(?x, ?y, ?z, ?x)")
        result = substitute(pattern, {"x": Var("y"), "y": Node("A")})
        self.assertEqual(result, parse_pattern("pair(?y, A, ?z, ?y)"))
        self.assertEqual(pattern, parse_pattern("pair(?x, ?y, ?z, ?x)"))
        self.assertEqual(substitute(pattern, {}), pattern)
        self.assertFalse(hasattr(scir, "substitute"))  # Like instantiate, this lives in patterns.

    def test_self_replacement_is_finite_and_has_no_occurs_check(self):
        replacement = parse_pattern("f(?x)")
        self.assertEqual(substitute(Var("x"), {"x": replacement}), replacement)
        self.assertEqual(substitute(parse_pattern("pair(?x, ?x)"), {"x": replacement}),
                         parse_pattern("pair(f(?x), f(?x))"))
        self.assertEqual(substitute(Var("x"), {"x": Var("y"), "y": Var("x")}), Var("y"))

    def test_node_heads_and_binder_looking_labels_remain_literal(self):
        pattern = Node(Symbol("x"), (Var("x"), Node("?x"), Node("_")))
        self.assertEqual(substitute(pattern, {"x": Node("A")}),
                         Node("x", (Node("A"), Node("?x"), Node("_"))))
        self.assertEqual(substitute(parse_pattern("lambda(x, ?x)"), {"x": Var("y")}),
                         parse_pattern("lambda(x, ?y)"))

    def test_composition_substitutes_into_the_first_environment(self):
        pattern = parse_pattern("f(?x, ?y, ?z, ?x)")
        first = {"x": parse_pattern("g(?y)"), "z": Var("x")}
        second = {"y": Node("A"), "x": Node("B")}
        composed = {name: substitute(first.get(name, Var(name)), second)
                    for name in first.keys() | second.keys()}
        self.assertEqual(substitute(substitute(pattern, first), second), substitute(pattern, composed))
        self.assertEqual(substitute(pattern, composed), parse_pattern("f(g(A), A, B, g(A))"))

    def test_wildcards_are_excluded_even_in_unused_replacements(self):
        examples = ((Var("_"), {}), (parse_pattern("f(?_)"), {}),
                    (Node("A"), {"x": Var("_")}), (Node("A"), {"x": parse_pattern("f(?_)")}),
                    (Node("A"), {"_": Node("A")}))
        for pattern, replacements in examples:
            with self.subTest(pattern=pattern, replacements=replacements), self.assertRaises(ValueError):
                substitute(pattern, replacements)
        self.assertEqual(substitute(Node("_"), {}), Node("_"))
        self.assertEqual(substitute(Var("__"), {"__": Node("A")}), Node("A"))
        self.assertEqual(match(parse_pattern("pair(?_, ?_)"), parse("pair(A, B)")), {})
        with self.assertRaises(ValueError):
            instantiate(Var("_"), {"_": Term("A")})

    def test_input_and_whole_environment_are_validated_without_mutation(self):
        pattern = parse_pattern("f(?x)")
        bad = (None, [("x", Node("A"))], {"?x": Node("A")}, {"λ": Node("A")},
               {Symbol("x"): Node("A")}, {True: Node("A")}, {"x": Term("A")},
               {"unused": "A"})
        for replacements in bad:
            with self.subTest(replacements=repr(replacements)), self.assertRaises(ValueError):
                substitute(pattern, replacements)
        with self.assertRaises(ValueError):
            substitute(Term("A"), {})
        self.assertEqual(pattern, parse_pattern("f(?x)"))

    def test_grounding_and_reconstruction_keep_the_existing_boundary(self):
        pattern = parse_pattern("pair(?x, ?x)")
        subject = parse("pair(f(A), f(A))")
        bindings = match(pattern, subject)
        self.assertEqual(instantiate(pattern, bindings), subject)
        self.assertEqual(instantiate(substitute(pattern, {"x": parse_pattern("f(A)")}), {}), subject)
        self.assertIsNone(match(pattern, parse("pair(A, B)")))
        self.assertEqual(match(Node("A"), Term("A")), {})
        with self.assertRaises(ValueError):
            instantiate(Var("missing"), {})
        # Ground instantiation's existing unused-binding behavior is unchanged.
        self.assertEqual(instantiate(Node("A"), {"unused": Var("_")}), Term("A"))

    def test_substitution_traversal_is_stack_safe_for_constructed_patterns(self):
        pattern = Var("x")
        for _ in range(1500):
            pattern = Node("f", (pattern,))
        result = substitute(pattern, {"x": Node("A")})
        count = 0
        while result.args:
            self.assertEqual(result.symbol, "f")
            result, = result.args
            count += 1
        self.assertEqual(count, 1500)
        self.assertEqual(result, Node("A"))
        # Parser, recursive formatting and equality retain their existing bounds.
