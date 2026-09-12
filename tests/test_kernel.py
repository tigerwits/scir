import json
import os
import random
import subprocess
import sys
import unittest

from scir import (Term, ParseError, parse, parse_document, parse_pattern, format_document, validate, digest, match, query, replace_at, diff)
from scir.patterns import Var, Node, instantiate
from scir.tree import walk, at

class CoreTests(unittest.TestCase):
    def test_one_constructor(self):
        self.assertEqual(Term('Alice'), Term('Alice', ()))
        self.assertEqual(parse('Alice'), Term('Alice'))
        self.assertEqual(str(Term('Alice')), 'Alice')

    def test_immutable(self):
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            Term('A').symbol = 'B'

    def test_constructor_rejects_non_ground_children(self):
        for args in ([Term('A')], (Var('x'),), (Node('A'),), ('A',)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Term('f', args)

    def test_symbol_validation(self):
        for value in ('', None, 123, '\ud800'):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                Term(value)

    def test_order_and_duplicates(self):
        a = parse_document('f(A, B); f(A, B)')
        self.assertEqual(len(a), 2)
        self.assertNotEqual(a[0], parse('f(B, A)'))
        self.assertNotEqual(a, (a[0],))
        self.assertEqual(hash(a[0]), hash(a[1]))

    def test_document_validation(self):
        for d in ([Term('A')], (Var('x'),), Term('A')):
            with self.assertRaises(ValueError):
                validate(d)
        validate(())

    def test_no_reserved_vocabulary(self):
        for source in ('not(A, B)', 'and', 'if(A)', 'unknownSymbol(A, B, C)'):
            validate((parse(source),))

    def test_no_implicit_normalization(self):
        source = 'think(Bob, not(not(P)))'
        self.assertEqual(str(parse(source)), source)

    def test_no_unicode_normalization(self):
        self.assertNotEqual(Term('\u00e9'), Term('e\u0301'))

    def test_digest_is_process_stable(self):
        code = 'from scir import *; print(digest(parse_document("think(Bob, P)")))'
        results = [subprocess.check_output([sys.executable, '-c', code], text=True,
                   env=dict(os.environ, PYTHONHASHSEED=seed)).strip() for seed in ('1','2')]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], digest(parse_document('think(Bob,P)')))
        self.assertNotEqual(digest(parse_document('A; A')), digest(parse_document('A')))


class SyntaxTests(unittest.TestCase):

    def test_document_separators(self):
        expected = (Term('A'), Term('B'), Term('C'))
        self.assertEqual(parse_document('A\nB\nC'), expected)
        self.assertEqual(parse_document('A; B; C;'), expected)
        self.assertEqual(parse_document('\n\nA\n\nB\nC\n'), expected)

    def test_empty(self):
        self.assertEqual(parse_document(' # nothing\n'), ())
        self.assertEqual(format_document(()), '')
        with self.assertRaises(ParseError):
            parse('')

    def test_comments_multiline_trailing_comma(self):
        src='think(\n Bob, # holder\n wrong(\n Chart,\n ),\n) # end\n'
        self.assertEqual(parse(src), parse('think(Bob, wrong(Chart))'))

    def test_quoted_symbols(self):
        for symbol in ('Alice', 'hello world', 'Алиса', 'line\nbreak', 'a"b', 'a\\b', '?x', '#', '0.7'):
            value = Term(symbol)
            self.assertEqual(parse(str(value)), value)
            self.assertEqual(parse(json.dumps(symbol)), value)
        self.assertEqual(parse('"Alice"'), parse('Alice'))
        self.assertEqual(parse('"an odd head"(X)').symbol, 'an odd head')

    def test_variables_are_not_content(self):
        for src in ('?x', 'f(?x)', '?_'):
            with self.assertRaises(ParseError):
                parse(src)
        self.assertEqual(parse('"?x"'), Term('?x'))

    def test_pattern_roundtrip(self):
        for src in ('?x', 'f(?x, ?_)', 'same(?x, ?x)', '"?x"', '"many words"(?a)'):
            p = parse_pattern(src)
            self.assertEqual(parse_pattern(str(p)), p)

    def test_bad_syntax(self):
        for src in ('f(A,,B)', 'f(,A)', '(A)', 'A B', 'A;;B', '?', 'f(',
                    'f(A', 'f(A B)', 'f(A))', '1', '0.7', 'Алиса',
                    '""', '"bad\\q"', '"unterminated', 'A\n(B)', 'A = B',
                    'f(*A)', 'f(x=A)', 'f(A);;'):
            with self.subTest(src=src), self.assertRaises(ParseError):
                parse_document(src)

    def test_single_expression_rejects_multi(self):
        with self.assertRaises(ParseError):
            parse('A; B')
        with self.assertRaises(ParseError):
            parse_pattern('A\nB')

    def test_precise_error(self):
        with self.assertRaises(ParseError) as ctx:
            parse_document('A\nf(@)')
        self.assertEqual((ctx.exception.line, ctx.exception.column), (2, 3))

    def test_depth_budget(self):
        self.assertEqual(str(parse('f('*128+'A'+')'*128)), 'f('*128+'A'+')'*128)
        with self.assertRaises(ParseError):
            parse('f('*129+'A'+')'*129)
        with self.assertRaises(ParseError):
            parse('f(A)', max_depth=0)

    def test_node_budget(self):
        with self.assertRaises(ParseError):
            parse('f(A, B)', max_nodes=2)
        with self.assertRaises(ParseError):
            parse_document('A; B', max_nodes=1)
        self.assertEqual(parse('f(A)', max_nodes=2), parse('f(A)'))

    def test_invalid_limits(self):
        for kw in ({'max_nodes':0}, {'max_depth':129}, {'max_depth':True}, {'max_nodes':False}):
            with self.assertRaises(ValueError):
                parse('A', **kw)

    def test_character_budget(self):
        with self.assertRaises(ParseError):
            parse('a'*2_000_001)

    def test_no_python_execution(self):
        src='__import__(os)'
        self.assertEqual(parse(src), Term('__import__', (Term('os'),)))
        with self.assertRaises(ParseError):
            parse('__import__(os).system("echo unsafe")')

    def test_deterministic_malformed_fuzz(self):
        rng=random.Random(441)
        for _ in range(2000):
            src=''.join(rng.choice('ABfx?(),;\n \\"#1=') for _ in range(rng.randrange(40)))
            try:
                d=parse_document(src)
            except ParseError:
                continue
            self.assertEqual(parse_document(format_document(d)), d)


class MatchAndOccurrenceTests(unittest.TestCase):
    def test_bindings(self):
        p=parse_pattern('think(?who, ?content)')
        t=parse('think(Bob, wrong(Chart))')
        self.assertEqual(match(p,t), {'who':Term('Bob'), 'content':parse('wrong(Chart)')})

    def test_repeated_capture(self):
        p=parse_pattern('same(?x, ?x)')
        self.assertIsNone(match(p, parse('same(Alice, Bob)')))
        self.assertEqual(match(p, parse('same(Alice, Alice)')), {'x':Term('Alice')})

    def test_zero_bindings_not_failure(self):
        self.assertEqual(match(parse_pattern('A'),Term('A')), {})
        self.assertIsNone(match(parse_pattern('A'),Term('B')))

    def test_failures(self):
        for p,t in (('f(?x)','g(A)'),('f(?x)','f(A,B)'),('A','A(B)'),('f','f(A)')):
            self.assertIsNone(match(parse_pattern(p),parse(t)))

    def test_wildcard(self):
        self.assertEqual(match(parse_pattern('same(?_, ?_)'), parse('same(A,B)')), {})
        self.assertIsNone(match(parse_pattern('_'),parse('A')))
        with self.assertRaises(ValueError):
            instantiate(parse_pattern('f(?_)'), {})

    def test_ground_subject_required(self):
        with self.assertRaises(ValueError):
            match(parse_pattern('?x'), Var('y'))
        with self.assertRaises(ValueError):
            query((), Term('A'))

    def test_instantiation(self):
        p=parse_pattern('f(?x, g(?y), ?x)')
        t=parse('f(A, g(B), A)')
        self.assertEqual(instantiate(p,match(p,t)),t)
        with self.assertRaises(ValueError):
            instantiate(p, {'x':Term('A')})
        with self.assertRaises(ValueError):
            instantiate(parse_pattern('?x'), {'x':Var('x')})

    def test_roots_do_not_infer(self):
        d=parse_document('and(A,B)\nthink(Bob,A)\nnot(A)\nif(A,B)')
        self.assertEqual(query(d,parse_pattern('A')), [])
        self.assertEqual(len(query(d,parse_pattern('A'),scope='all')), 4)
        self.assertEqual(len(query(d,parse_pattern('and(?a,?b)'))), 1)

    def test_repeated_occurrences_have_paths(self):
        d=parse_document('call(Bob,Carol)\ncall(Bob,Carol)')
        hits=query(d,parse_pattern('call(?a,?b)'))
        self.assertEqual([h.path for h in hits], [(0,),(1,)])
        self.assertEqual(hits[0].term,hits[1].term)

    def test_nested_path(self):
        d=parse_document('think(Bob, mistakenly(use(Alice, Data)))')
        h=query(d,parse_pattern('use(Alice,?x)'),scope='all')[0]
        self.assertEqual(h.path,(0,1,0))
        self.assertEqual(at(d,h.path), h.term)
        self.assertEqual(d[0].symbol,'think')

    def test_preorder(self):
        d=parse_document('f(A,g(B)); C')
        self.assertEqual([p for p,t in walk(d)],[(0,),(0,0),(0,1),(0,1,0),(1,)])

    def test_replace_exact_occurrence(self):
        d=parse_document('f(A,A); f(A,A)')
        self.assertEqual(replace_at(d,(0,1),Term('B')),parse_document('f(A,B); f(A,A)'))
        self.assertEqual(replace_at(d,(1,),Term('C')),parse_document('f(A,A); C'))
        self.assertEqual(d,parse_document('f(A,A); f(A,A)'))

    def test_no_rewrite_of_replacement(self):
        d=parse_document('f(A)')
        self.assertEqual(replace_at(d,(0,0),parse('g(A)')),parse_document('f(g(A))'))

    def test_positional_diff(self):
        a=parse_document('f(A,B); C')
        b=parse_document('f(A,D); C; E')
        changes=diff(a,b)
        self.assertEqual([c.path for c in changes],[(0,1),(2,)])
        self.assertEqual(changes[0].before,Term('B'))
        self.assertIsNone(changes[1].before)
        self.assertEqual(diff(a,a),[])
        self.assertEqual(diff(parse_document('f(A)'),parse_document('f(A,B)'))[0].path,(0,))

    def test_bad_paths(self):
        for p in ((),(-1,),(True,),(0,2),[0],(5,)):
            with self.assertRaises(ValueError):
                at(parse_document('f(A)'),p)
        with self.assertRaises(ValueError):
            query((),parse_pattern('A'),scope='asserted')

    def test_pattern_constructor_validation(self):
        for thunk in (lambda:Var(''),lambda:Var('?x'),lambda:Node('f',(Term('A'),)),lambda:Node('f',[])):
            with self.assertRaises(ValueError):
                thunk()


if __name__=='__main__':
    unittest.main()
