"""Check profile prerequisites, exact named-role paths, and fixed helper inputs."""
import unittest
from unittest.mock import patch

from scir import parse_document
from scir.constraints import Violation, check
from scir.dialects import Context, Dialect, evaluate, from_constraint
from scir.dialect_rules import FieldSet, record_fields, reference_targets, structured, working
from scir.notation import lower
from scir.profile import LimitError

IDENTITY = 'b' * 64
CTX = Context('fixture', '1')


def plan(*constraints):
    rules = (from_constraint('structured', '1', IDENTITY, structured),
             from_constraint('working', '1', IDENTITY, working, requires=('structured',)))
    return Dialect('fixture', '1', rules + tuple(
        from_constraint(str(i), '1', IDENTITY, c, requires=('working',))
        for i, c in enumerate(constraints)))


class DialectRuleTests(unittest.TestCase):
    def test_structural_and_working_errors_are_rejections_then_blockers(self):
        cases = ((parse_document('"scir.kw"(x(a))'), ['rejected', 'blocked']),
                 (lower('record(A, Note, &Missing)'), ['passed', 'rejected']),
                 (lower('record(A, Note, x)\nrecord(A, Note, y)'), ['passed', 'rejected']))
        for document, expected in cases:
            result = evaluate(document, plan(), CTX, collection='c')
            self.assertEqual([s.status for s in result.steps], expected)
            self.assertEqual(result.outcome, 'rejected')
        self.assertTrue(evaluate((), plan(), CTX, collection='c').conforms)

    def test_limits_propagate_from_profile_adapters(self):
        with patch('scir.dialect_rules.p.validate', side_effect=LimitError('bound')):
            with self.assertRaises(LimitError):
                tuple(structured(()))
        with patch('scir.dialect_rules.build_index', side_effect=LimitError('bound')):
            with self.assertRaises(LimitError):
                tuple(working(()))

    def test_closed_shapes_have_exact_paths_but_open_ids_and_payloads(self):
        constraint = record_fields({'Task': FieldSet({'status'}, {'reason'}), 'Note': FieldSet()})
        doc = lower('record("arbitrary ID", Task, f(t"not a vocabulary entry"), extra: x)\nrecord(B, Other, x)')
        self.assertEqual(check(doc, (constraint,)), (
            Violation((0,), 'record-fields', 'required field is missing: status'),
            Violation((0, 3, 0), 'record-fields', 'field is not permitted: extra'),
            Violation((1, 1), 'record-fields', 'record kind is not permitted: Other')))
        good = lower('record("arbitrary ID", Task, f(t"not a vocabulary entry"), status: open)')
        self.assertEqual(check(good, (constraint,)), ())
        self.assertEqual(check((), (constraint,)), ())

    def test_shape_configuration_is_copied(self):
        fields = {'status'}
        shape = FieldSet(fields)
        schema = {'Task': shape}
        checker = record_fields(schema)
        fields.clear()
        schema.clear()
        self.assertTrue(check(lower('record(A, Task, x)'), (checker,)))
        for bad in (lambda: FieldSet('status'), lambda: FieldSet({'x'}, {'x'}),
                    lambda: record_fields({'Task': None}), lambda: FieldSet({True})):
            with self.assertRaises(ValueError):
                bad()

    def test_reference_kinds_not_words_or_quoted_text(self):
        checker = reference_targets('decision', {'Decision'}, source_kinds={'Task'})
        doc = lower('record(D, Decision, x)\nrecord(N, Note, t"Decision")\nrecord(T, Task, x, decision: &N)')
        self.assertEqual(check(doc, (checker,)), (
            Violation((2, 3, 0, 0), 'reference-targets', 'reference targets a disallowed record kind'),))
        good = lower('record(D, Decision, x)\nrecord(T, Task, x, decision: &D)')
        self.assertEqual(check(good, (checker,)), ())
        absent = lower('record(T, Task, x)')
        self.assertEqual(check(absent, (checker,)), ())  # Existence is a separate rule.

    def test_reference_tuple_shapes_and_source_filters(self):
        checker = reference_targets('targets', {'Decision'}, source_kinds={'Task'})
        prefix = 'record(D, Decision, x)\n'
        for value in ('(&D, &D)', '()'):
            self.assertEqual(check(lower(prefix + 'record(T, Task, x, targets: '+value+')'), (checker,)), ())
        for value in ('t"D"', 'D', '(&D, D)', '(named: &D)'):
            with self.subTest(value=value):
                self.assertTrue(check(lower(prefix + 'record(T, Task, x, targets: '+value+')'), (checker,)))
        self.assertEqual(check(lower('record(N, Note, x, targets: t"ignored by source filter")'), (checker,)), ())

    def test_mutating_kind_allowlist_cannot_change_the_rule(self):
        kinds, sources = {'Decision'}, {'Task'}
        checker = reference_targets('decision', kinds, source_kinds=sources)
        kinds.add('Note')
        sources.clear()
        doc = lower('record(N, Note, x)\nrecord(T, Task, x, decision: &N)')
        self.assertTrue(check(doc, (checker,)))
        with self.assertRaises(ValueError):
            reference_targets('decision', 'Decision')

    def test_named_fields_are_not_positional_role_applications(self):
        checker = record_fields({'Task': FieldSet({'status'})})
        document = lower('record(T, Task, status(ready))')
        result = evaluate(document, plan(checker), CTX, collection='c')
        self.assertEqual(result.steps[0].status, 'passed')
        self.assertEqual(result.steps[1].status, 'passed')
        self.assertEqual(result.steps[2].violations[0].message, 'required field is missing: status')
