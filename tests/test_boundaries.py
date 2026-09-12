"""Regression cases and independent laws for the unchanged ground-tree kernel."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from scir import Term, diff, match, parse_document, query, replace_at
from scir.patterns import Node, Var
from scir.tree import at, walk
from scir.__main__ import main
from scir.annotations import Alternatives, Bundle, annotate, erase
from scir.relations import decode, encode
from scir.syntax import ParseError, TOKEN


def reference_match(pattern, term):
    """Collect constraints first; solve them separately from tree traversal."""
    pairs = []

    def collect(p, t):
        if isinstance(p, Var):
            if p.name != '_':
                pairs.append((p.name, t))
            return True
        return (p.symbol == t.symbol and len(p.args) == len(t.args)
                and all(collect(a, b) for a, b in zip(p.args, t.args)))

    if not collect(pattern, term):
        return None
    bindings = dict(pairs)
    return bindings if all(bindings[name] == value for name, value in pairs) else None


class ResourceTests(unittest.TestCase):
    def test_node_budget_stops_lexing_the_tail(self):
        source = 'A;' + 'B;' * 10_000
        with patch('scir.syntax.TOKEN', wraps=TOKEN) as lexer:
            with self.assertRaisesRegex(ParseError, 'resource limit'):
                parse_document(source, max_nodes=1)
            self.assertLessEqual(lexer.match.call_count, 4)

    def test_streaming_parser_still_checks_all_trailing_input(self):
        for source in ('A#comment\n@', 'f(A) B', 'A; "unterminated'):
            with self.subTest(source=source), self.assertRaises(ParseError):
                parse_document(source)


    def test_decoder_rejects_second_parent_before_scanning_tail(self):
        wire = encode(parse_document('f(A)'))
        wire['args'].extend([[0, 1, 1], ['malformed unread tail']])
        with self.assertRaisesRegex(ValueError, 'multiple parents'):
            decode(wire)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.document = parse_document('A')

    def test_object_keys_are_never_silently_coerced(self):
        for payload in ({1: 'one'}, {False: 1}, {'nested': {None: 2}}, {'1': 1, 1: 2}):
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, 'keys must be strings'):
                annotate(self.document, (0,), 'source', payload)

    def test_annotation_key_must_be_unicode_scalar_text(self):
        with self.assertRaises(ValueError):
            annotate(self.document, (0,), '\ud800', 1)
        note = annotate(self.document, (0,), 'source', 1)
        with self.assertRaises(ValueError):
            Bundle(self.document, (replace(note, key='\ud800'),))

    def test_empty_json_keys_and_tuple_arrays_remain_supported(self):
        note = annotate(self.document, (0,), 'source', {'': (1, None, True)})
        self.assertEqual(note.value_json, '{"":[1,null,true]}')
        self.assertEqual(erase(Bundle(self.document, (note,))), self.document)

    def test_unsupported_values_fail_with_value_error(self):
        for payload in (object(), {1, 2}, b'bytes', {'nested': object()}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                annotate(self.document, (0,), 'source', payload)

    def test_cyclic_and_too_deep_json_is_rejected(self):
        cyclic = []
        cyclic.append(cyclic)
        deep = None
        for _ in range(130):
            deep = [deep]
        for payload in (cyclic, deep):
            with self.assertRaisesRegex(ValueError, 'resource limit'):
                annotate(self.document, (0,), 'source', payload)

    def test_raw_annotation_depth_has_no_recursion_error(self):
        note = annotate(self.document, (0,), 'source', None)
        raw = '[' * 1500 + '0' + ']' * 1500
        with self.assertRaises(ValueError):
            Bundle(self.document, (replace(note, value_json=raw),))

    def test_metadata_budgets_are_checked_before_output(self):
        with patch('scir.annotations.MAX_JSON_VALUES', 4):
            with self.assertRaises(ValueError):
                annotate(self.document, (0,), 'source', [None] * 10)
        with patch('scir.annotations.MAX_JSON_CHARS', 10):
            # The input values are short; JSON punctuation/escapes still count.
            with self.assertRaises(ValueError):
                annotate(self.document, (0,), 'source', ['\x00', '\x00'])

    def test_duplicate_keys_are_not_canonical_metadata(self):
        note = annotate(self.document, (0,), 'source', {})
        with self.assertRaises(ValueError):
            Bundle(self.document, (replace(note, value_json='{"x":1,"x":2}'),))

    def test_erasure_accepts_only_bundles(self):
        choices = Alternatives((self.document, parse_document('B')))
        for value in (choices, self.document, object()):
            with self.assertRaises(ValueError):
                erase(value)


class StructuralLawTests(unittest.TestCase):
    def test_deep_diff_is_stack_safe_without_recursive_equality(self):
        left, right = Term('A'), Term('B')
        for _ in range(1500):
            left, right = Term('f', (left,)), Term('f', (right,))
        changes = diff((left,), (right,))
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].path, (0,) * 1501)
        self.assertEqual(changes[0].before, Term('A'))
        self.assertEqual(changes[0].after, Term('B'))
        self.assertEqual(diff((left,), (left,)), [])

    def test_generated_matching_and_disjoint_edits(self):
        rng = random.Random(73184)

        def term(depth):
            args = () if not depth else tuple(term(depth - 1) for _ in range(rng.randrange(4)))
            return Term(rng.choice(('A', 'B', 'f', 'think')), args)

        def pattern(t):
            if rng.random() < .4:
                return Var(rng.choice(('x', 'y', '_')))
            return Node(t.symbol, tuple(pattern(a) for a in t.args))

        for _ in range(500):
            document = (term(4), term(3))
            p = pattern(document[0])
            self.assertEqual(match(p, document[0]), reference_match(p, document[0]))
            self.assertEqual(match(p, document[1]), reference_match(p, document[1]))
            first = replace_at(document, (0,), Term('X'))
            second = replace_at(document, (1,), Term('Y'))
            self.assertEqual(replace_at(first, (1,), Term('Y')), replace_at(second, (0,), Term('X')))
            self.assertEqual(at(first, (1,)), document[1])
            self.assertIs(at(first, (1,)), document[1])
            paths = [path for path, _ in walk(document)]
            self.assertEqual(len(paths), len(set(paths)))
            self.assertEqual([h.path for h in query(document, Var('_'), scope='all')], paths)
            wire = encode(document)
            for key in ('nodes', 'args', 'roots'):
                rng.shuffle(wire[key])
            self.assertEqual(decode(wire), document)

    def test_diff_frontier_reconstructs_same_root_count_documents(self):
        before = parse_document('f(A, B); g(C, D); E')
        after = parse_document('f(X, Y); renamed(Z); E')
        for change in diff(before, after):
            before = replace_at(before, change.path, change.after)
        self.assertEqual(before, after)


class CliBoundaryTests(unittest.TestCase):
    def run_cli(self, args, source):
        out, err = StringIO(), StringIO()
        with patch('sys.stdin', StringIO(source)), redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_duplicate_transport_keys_rejected(self):
        source = '{"version":"wrong","version":"scir-relations/1.0","nodes":[],"args":[],"roots":[]}'
        code, out, err = self.run_cli(['decode'], source)
        self.assertEqual((code, out), (2, ''))
        self.assertIn('duplicate JSON object key', err)
        self.assertNotIn('Traceback', err)

    def test_stdin_is_read_with_a_bound(self):
        with patch('scir.__main__.MAX_INPUT_CHARS', 8):
            code, out, err = self.run_cli(['check'], 'A' * 9)
        self.assertEqual((code, out), (2, ''))
        self.assertIn('input exceeds', err)

    def test_files_use_the_same_input_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.scir'
            path.write_text('A' * 9, encoding='utf-8')
            with patch('scir.__main__.MAX_INPUT_CHARS', 8):
                code, out, err = self.run_cli(['check', str(path)], '')
        self.assertEqual((code, out), (2, ''))
        self.assertIn('input exceeds', err)

    def test_bound_is_inclusive(self):
        with patch('scir.__main__.MAX_INPUT_CHARS', 8):
            code, out, err = self.run_cli(['check'], 'A' * 8)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {'valid': True, 'roots': 1})
        self.assertEqual(err, '')


if __name__ == '__main__': unittest.main()
