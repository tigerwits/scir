from copy import deepcopy
from dataclasses import replace
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import json
import unittest
from unittest.mock import patch

from scir import Term, parse, parse_document, validate
from scir.tree import at
from scir.annotations import Bundle, Alternatives, annotate, erase
from scir.relations import encode, decode
from scir.__main__ import main


class RelationTests(unittest.TestCase):
    def test_round_trip(self):
        for src in ('', 'A', 'f(A,B); f(A,B)', 'think(Bob, wrong(Chart))', '"many words"("Алиса")'):
            d=parse_document(src)
            self.assertEqual(decode(encode(d)),d)

    def test_no_object_identity_or_dedup(self):
        t=parse('f(A)')
        wire=encode((t,t))
        self.assertEqual(len(wire['nodes']),4)
        self.assertEqual(wire['roots'],[[0,0],[1,2]])
        self.assertEqual(len({row[0] for row in wire['nodes']}),4)

    def test_leaf_nodes_are_explicit(self):
        wire=encode(parse_document('think(Bob, wrong(Chart))'))
        self.assertEqual(wire['nodes'],[[0,'think'],[1,'Bob'],[2,'wrong'],[3,'Chart']])
        self.assertEqual(wire['args'],[[0,0,1],[0,1,2],[2,0,3]])
        self.assertEqual(wire['roots'],[[0,0]])

    def test_row_order_is_not_child_order(self):
        d=parse_document('f(A,g(B,C)); D')
        wire=encode(d)
        for key in ('nodes','args','roots'):
            wire[key].reverse()
        self.assertEqual(decode(wire),d)

    def test_arbitrary_id_renaming(self):
        d=parse_document('f(A,g(B,C)); D')
        wire=encode(d)
        rename=lambda x:10000-37*x
        wire['nodes']=[[rename(i),s] for i,s in wire['nodes']]
        wire['args']=[[rename(p),pos,rename(c)] for p,pos,c in wire['args']]
        wire['roots']=[[pos,rename(i)] for pos,i in wire['roots']]
        self.assertEqual(decode(wire),d)

    def test_duplicate_node(self):
        w=encode(parse_document('f(A)')); w['nodes'].append(w['nodes'][0])
        with self.assertRaises(ValueError): decode(w)

    def test_duplicate_edge(self):
        w=encode(parse_document('f(A)')); w['args'].append(w['args'][0])
        with self.assertRaises(ValueError): decode(w)

    def test_dangling_edge(self):
        w=encode(parse_document('f(A)')); w['args'][0][2]=999
        with self.assertRaises(ValueError): decode(w)

    def test_child_gap(self):
        w=encode(parse_document('f(A)')); w['args'][0][1]=10**30
        with self.assertRaises(ValueError): decode(w)

    def test_root_gap(self):
        w=encode(parse_document('A')); w['roots'][0][0]=2
        with self.assertRaises(ValueError): decode(w)

    def test_duplicate_root(self):
        w=encode(parse_document('A')); w['roots'].append([1,0])
        with self.assertRaises(ValueError): decode(w)

    def test_shared_child(self):
        w=encode(parse_document('f(A)')); w['args'].append([0,1,1])
        with self.assertRaises(ValueError): decode(w)

    def test_orphan(self):
        w=encode(parse_document('A')); w['nodes'].append([1,'B'])
        with self.assertRaises(ValueError): decode(w)

    def test_cycles(self):
        for args, roots in (([[0,0,0]],[]), ([[0,0,1],[1,0,0]],[]), ([[0,0,0]],[[0,0]])):
            w=encode(())
            w.update(nodes=[[i, 'f'] for i in range(1 if len(args)==1 else 2)], args=args, roots=roots)
            with self.assertRaises(ValueError): decode(w)

    def test_malformed_tables(self):
        original=encode(parse_document('f(A)'))
        variants=[]
        for field in ('nodes','args','roots'):
            w=deepcopy(original); w[field]=None; variants.append(w)
        w=deepcopy(original); w['extra']=1; variants.append(w)
        w=deepcopy(original); w['version']='future'; variants.append(w)
        w=deepcopy(original); w['nodes'][0][0]=True; variants.append(w)
        w=deepcopy(original); w['nodes'][0][1]=''; variants.append(w)
        w=deepcopy(original); w['args'][0][1]=-1; variants.append(w)
        w=deepcopy(original); w['roots'][0][1]=1.0; variants.append(w)
        w=deepcopy(original); w['nodes'][0]=[0]; variants.append(w)
        for w in variants:
            with self.subTest(w=w), self.assertRaises(ValueError): decode(w)

    def test_limits(self):
        w=encode(parse_document('f(g(A))'))
        with self.assertRaises(ValueError): decode(w,max_nodes=2)
        with self.assertRaises(ValueError): decode(w,max_depth=1)
        with self.assertRaises(ValueError): decode(w,max_depth=True)
        t=Term('A')
        for _ in range(129): t=Term('f',(t,))
        with self.assertRaises(ValueError): encode((t,))


class AnnotationTests(unittest.TestCase):
    def test_erasure(self):
        d=parse_document('think(Bob,P)')
        note=annotate(d,(0,), 'source', {'sentence':4})
        b=Bundle(d,(note,))
        self.assertIs(erase(b),d)
        self.assertEqual(note.value_json,'{"sentence":4}')

    def test_occurrence_target_not_structural_value(self):
        d=parse_document('f(A); f(A)')
        a=annotate(d,(0,), 'source','sentence:1')
        b=annotate(d,(1,), 'source','sentence:2')
        self.assertNotEqual(a.path,b.path)
        self.assertEqual(at(d,a.path),at(d,b.path))
        Bundle(d,(a,b))

    def test_stale_annotation_rejected(self):
        d=parse_document('f(A)')
        note=annotate(d,(0,0),'evidence','trace-1')
        with self.assertRaises(ValueError):
            Bundle(parse_document('f(B)'),(note,))
        with self.assertRaises(ValueError):
            Bundle(parse_document('Z; f(A)'),(note,))

    def test_reparse_same_content_not_stale(self):
        a=parse_document('f(A)')
        note=annotate(a,(0,),'x',1)
        Bundle(parse_document(' f( A, ) # same\n'),(note,))

    def test_json_is_copied_not_mutable(self):
        d=parse_document('A'); value={'b':[2],'a':1}
        note=annotate(d,(0,),'test',value)
        value['b'].append(3)
        self.assertEqual(note.value_json,'{"a":1,"b":[2]}')

    def test_bad_json_or_target(self):
        d=parse_document('A'); note=annotate(d,(0,),'x',1)
        for value in (float('nan'),float('inf'),'\ud800'):
            with self.assertRaises(ValueError): annotate(d,(0,),'x',value)
        for bad in (replace(note,path=(9,)),replace(note,key=''),replace(note,value_json='NaN'),
                    replace(note,value_json='{"b": 2}'),replace(note,value_json='garbage')):
            with self.assertRaises(ValueError): Bundle(d,(bad,))

    def test_alternatives_are_not_roots(self):
        a=parse_document('after(speak(Alice,Carol), leave(Alice))')
        b=parse_document('after(speak(Alice,Carol), leave(Carol))')
        choices=Alternatives((a,b))
        self.assertEqual(choices.choose(1),b)
        with self.assertRaises(ValueError): validate(choices)
        for index in (-1,2,True):
            with self.assertRaises(ValueError): choices.choose(index)
        with self.assertRaises(ValueError): Alternatives((a,))


class CliTests(unittest.TestCase):
    def run_cli(self,command,source,*args):
        out,err=StringIO(),StringIO()
        with patch('sys.stdin',StringIO(source)),redirect_stdout(out),redirect_stderr(err):
            code=main([command,'-',*args])
        return code,out.getvalue(),err.getvalue()

    def test_check_and_format(self):
        c,o,e=self.run_cli('check','A; B')
        self.assertEqual(c,0); self.assertEqual(json.loads(o),{'valid':True,'roots':2})
        self.assertEqual(self.run_cli('fmt',' f( A, ) ')[1],'f(A)\n')

    def test_query_scopes_and_filter(self):
        d='think(Bob, wrong(Chart)); think(Alice, broken(Server))'
        c,o,e=self.run_cli('query',d,'--pattern','think(?x, ?y)','--contains','Alice')
        self.assertEqual(c,0); self.assertEqual(json.loads(o)[0]['bindings']['x'],'Alice')
        self.assertEqual(self.run_cli('query',d,'--pattern','wrong(?x)')[1],'[]\n')
        c,o,e=self.run_cli('query',d,'--pattern','wrong(?x)','--scope','all')
        self.assertEqual(json.loads(o)[0]['path'],[0,1])

    def test_encode_decode(self):
        c,o,e=self.run_cli('encode','f(A); B')
        self.assertEqual(c,0)
        self.assertEqual(self.run_cli('decode',o)[1],'f(A)\nB\n')

    def test_errors(self):
        for command,source in (('check','f('),('decode','{}'),('decode','not json')):
            c,o,e=self.run_cli(command,source)
            self.assertEqual(c,2); self.assertTrue(e.startswith('scir:'))


if __name__=='__main__': unittest.main()
