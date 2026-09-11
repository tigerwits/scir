"""Reproducible generated checks, not a substitute for universal proofs."""
import json
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scir import Term, Node, Var, parse_document, parse_pattern, format_document, match, instantiate, walk, replace_at
from scir.annotations import Bundle, annotate, erase
from scir.relations import encode, decode


def run(seed=602, cases=1000):
    rng=random.Random(seed)
    nodes_checked=0
    def generate(depth):
        symbol=rng.choice(['A','Bob','think','not','f','quoted words','Алиса','0.7'])
        args=() if not depth or rng.random()<.55 else tuple(generate(depth-1) for _ in range(rng.randrange(1,4)))
        return Term(symbol,args)
    def abstract(term,seen):
        if rng.random()<.35:
            key=str(term)
            if key not in seen: seen[key]=f'x{len(seen)}'
            return Var(seen[key])
        return Node(term.symbol,tuple(abstract(a,seen) for a in term.args))
    for _ in range(cases):
        doc=tuple(generate(5) for _ in range(rng.randrange(5)))
        assert parse_document(format_document(doc))==doc
        wire=encode(doc)
        assert decode(wire)==doc
        for name in ('nodes','args','roots'): rng.shuffle(wire[name])
        assert decode(wire)==doc
        nodes=list(walk(doc)); nodes_checked+=len(nodes)
        for t in doc:
            p=abstract(t,{})
            assert parse_pattern(str(p))==p
            env=match(p,t)
            assert env is not None and instantiate(p,env)==t
        if nodes:
            path,term=rng.choice(nodes)
            assert replace_at(doc,path,term)==doc
            bundle=Bundle(doc,(annotate(doc,path,'source',{'fixture':_}),))
            assert erase(bundle)==doc
    return {'seed':seed,'documents':cases,'occurrences':nodes_checked,
            'checks':['content parse/print','pattern parse/print','match/instantiate soundness on generated patterns',
                      'relation encode/decode','relational row-order invariance','identity edit','annotation erasure'],
            'status':'passed','scope':'finite seeded tests, not universal proofs'}


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
