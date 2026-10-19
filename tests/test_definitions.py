"""One-occurrence naming, explicit-reference expansion and bounded profile safety."""
from dataclasses import FrozenInstanceError
import unittest

from scir import Symbol, Term, digest, parse
from scir import profile as p
from scir.changes import ConflictError
from scir.definitions import expand_definitions, factor_subtree
from scir.knowledge import build_index


def definition(identifier, body, *, fields=()):
    return p.application("record", (Term(identifier), Term("Definition"), body), fields=fields)


def factor(document, path, identifier="Named", definitions=()):
    return factor_subtree(document, path, definition_id=identifier,
                          expected_snapshot=digest(document), definitions=definitions)


class DefinitionTests(unittest.TestCase):
    def test_one_occurrence_and_root_factor_round_trip(self):
        document = (parse("pair(f(A), f(A))"), Term("Last"))
        result = factor(document, (0, 1), Symbol("Named"))
        self.assertEqual(result.document, (Term("pair", (parse("f(A)"), p.reference("Named"))), Term("Last")))
        self.assertEqual(result.definitions, (definition("Named", parse("f(A)")),))
        self.assertEqual(expand_definitions(result.document, result.definitions), document)
        self.assertEqual(factor(document, (0,)).document, (p.reference("Named"), Term("Last")))
        self.assertEqual(document, (parse("pair(f(A), f(A))"), Term("Last")))

    def test_bare_heads_never_name_definitions(self):
        definitions = (definition("X", Term("Value")),)
        document = (Term("X"), Term("X", (p.reference("X"),)), p.reference("External"))
        self.assertEqual(expand_definitions(document, definitions),
                         (Term("X"), Term("X", (Term("Value"),)), p.reference("External")))
        result = factor((Term("X"),), (0,), "X")
        self.assertEqual(expand_definitions(result.document, result.definitions), (Term("X"),))

    def test_preexisting_definitions_obey_normal_form_round_trip(self):
        definitions = (definition("Old", parse("f(A)")),)
        document = (Term("pair", (p.reference("Old"), p.reference("Old"))),)
        result = factor(document, (0, 0), definitions=definitions)
        self.assertEqual(result.definitions[-1], definition("Named", p.reference("Old")))
        expanded = expand_definitions(result.document, result.definitions)
        self.assertEqual(expanded, expand_definitions(document, definitions))
        self.assertNotEqual(expanded, document)

    def test_freshness_avoids_external_reference_and_record_id_capture(self):
        cases = (((Term("A"), p.reference("X")), ()),
                 ((Term("A"),), (definition("X", Term("B")),)),
                 ((p.application("record", (Term("X"), Term("Claim"), Term("A"))),), ()))
        for document, definitions in cases:
            with self.subTest(document=document), self.assertRaises(ConflictError):
                factor(document, (0,), "X", definitions)
        # Literal text contents are not references, even when they spell an ID.
        self.assertEqual(factor((p.text("X"),), (0,), "X").definitions,
                         (definition("X", p.text("X")),))
        for identifier in ("", p.REF, p.TEXT, p.KW, p.TUPLE, True, None):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                factor((Term("A"),), (0,), identifier)

    def test_snapshot_guards_the_entire_document(self):
        old, changed = (Term("A"), Term("B")), (Term("A"), Term("C"))
        with self.assertRaises(ConflictError):
            factor_subtree(changed, (0,), definition_id="X", expected_snapshot=digest(old))
        for snapshot in (None, "", "a" * 63, "A" * 64):
            with self.subTest(snapshot=snapshot), self.assertRaises(p.ProfileError):
                factor_subtree(old, (0,), definition_id="X", expected_snapshot=snapshot)

    def test_selection_respects_text_reference_and_field_roles(self):
        value = p.application("f", (p.text("opaque"), p.reference("Old")),
                              fields=(("key", Term("Value")),))
        definitions = (definition("Old", Term("A")),)
        document = (value,)
        for path in ((0, 0, 0), (0, 1, 0), (0, 2), (0, 2, 0)):
            with self.subTest(path=path), self.assertRaises(p.ProfileError):
                factor(document, path, definitions=definitions)
        for path in ((0, 0), (0, 1), (0, 2, 0, 0)):
            result = factor(document, path, definitions=definitions)
            self.assertEqual(expand_definitions(result.document, result.definitions),
                             expand_definitions(document, definitions))
        for path in ((), (True,), (0, -1), (9,), (0, 2, 1), [0]):
            with self.subTest(path=path), self.assertRaises(ValueError):
                factor(document, path, definitions=definitions)

    def test_reserved_field_labels_and_text_contents_are_opaque(self):
        definitions = (definition("X", Term("Value")),)
        value = p.application("f", (p.text("X"), p.text(p.REF), p.text("")),
                              fields=((p.REF, p.reference("X")), (p.TEXT, p.reference("External"))))
        expected = p.application("f", (p.text("X"), p.text(p.REF), p.text("")),
                                 fields=((p.REF, Term("Value")), (p.TEXT, p.reference("External"))))
        self.assertEqual(expand_definitions((value,), definitions), (expected,))

    def test_whole_environment_is_closed_and_acyclic(self):
        bad = (
            (definition("X", Term("A")), definition("X", Term("B"))),
            (p.application("record", (Term("X"), Term("Claim"), Term("A"))),),
            (definition("X", p.reference("Missing")),),
            (definition("X", p.reference("X")),),
            (definition("X", p.reference("Y")), definition("Y", p.reference("X"))),
            (definition("X", Term("A"), fields=(("evidence", p.tuple_value((p.reference("X"),))),)),),
        )
        for definitions in bad:
            with self.subTest(definitions=definitions):
                with self.assertRaises(p.ProfileError):
                    expand_definitions((Term("Unused"),), definitions)
                with self.assertRaises(p.ProfileError):
                    factor((Term("Unused"),), (0,), definitions=definitions)

    def test_selected_external_refs_must_close_without_chasing_input_records(self):
        document = (p.reference("Outside"), Term("A"))
        with self.assertRaises(p.ProfileError):
            factor(document, (0,))
        result = factor(document, (1,))
        self.assertEqual(expand_definitions(result.document, result.definitions), document)

    def test_forward_shared_dependencies_and_metadata_are_order_independent(self):
        definitions = (
            definition("X", Term("pair", (p.reference("Y"), p.reference("Y"))),
                       fields=(("dependsOn", p.tuple_value((p.reference("Y"),))),)),
            definition("Y", Term("Value")),
        )
        self.assertEqual(expand_definitions((p.reference("X"),), definitions), (parse("pair(Value, Value)"),))
        self.assertEqual(expand_definitions((p.reference("X"),), tuple(reversed(definitions))),
                         expand_definitions((p.reference("X"),), definitions))
        self.assertEqual(len(build_index(definitions, collection="Named").records), 2)

    def test_occurrence_budgets_reject_shared_growth_before_full_allocation(self):
        definitions = (definition("X", Term("many", (Term("A"),) * 100)),)
        document = (Term("many", (p.reference("X"),) * 100),)
        with self.assertRaises(p.LimitError):
            expand_definitions(document, definitions, max_nodes=10_100)
        expanded = expand_definitions(document, definitions, max_nodes=10_101)
        self.assertEqual(p.measure(expanded).nodes, 10_101)
        # A reference contributes no output nodes when its body replaces it.
        self.assertEqual(expand_definitions((p.reference("Y"),), (definition("Y", Term("A")),),
                                            max_nodes=1, max_depth=0), (Term("A"),))
        with self.assertRaises(p.LimitError):
            expand_definitions((p.text("body"),), (), max_nodes=1)

    def test_depth_and_literal_wrapper_bounds_are_exact(self):
        definitions = (definition("X", parse("f(A)")),)
        document = (Term("g", (p.reference("X"),)),)
        self.assertEqual(expand_definitions(document, definitions, max_depth=2), (parse("g(f(A))"),))
        with self.assertRaises(p.LimitError):
            expand_definitions(document, definitions, max_depth=1)
        with self.assertRaises(p.LimitError):
            expand_definitions((p.reference("Outside"),), (), max_depth=0)
        for options in ({"max_nodes": 0}, {"max_nodes": True}, {"max_depth": True}, {"max_depth": 129}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                expand_definitions((), (), **options)

    def test_long_reference_chains_are_stack_safe(self):
        definitions = (definition("D0", Term("A")),) + tuple(
            definition(f"D{i}", p.reference(f"D{i - 1}")) for i in range(1, 1500))
        self.assertEqual(expand_definitions((p.reference("D1499"),), definitions), (Term("A"),))
        repeated = (Term("many", (p.reference("D1499"),) * 1000),)
        self.assertEqual(expand_definitions(repeated, definitions, max_nodes=1001),
                         (Term("many", (Term("A"),) * 1000),))
        with self.assertRaises(p.LimitError):
            expand_definitions(repeated, definitions, max_nodes=1000)

    def test_expanded_byte_budget_counts_repeated_literal_text(self):
        definitions = (definition("X", p.text("λ" * 8192)),)
        self.assertEqual(len(expand_definitions((p.reference("X"),), definitions)), 1)
        with self.assertRaises(p.LimitError):
            expand_definitions((Term("many", (p.reference("X"),) * 1000),), definitions)

    def test_result_is_immutable_and_empty_expansion_still_validates(self):
        document = (Term("A"),)
        result = factor(document, (0,))
        with self.assertRaises(FrozenInstanceError):
            result.document = ()
        self.assertEqual(expand_definitions((), ()), ())
        with self.assertRaises(p.ProfileError):
            expand_definitions((), (definition("X", p.reference("Missing")),))
        self.assertEqual(factor(document, (0,)), result)
