"""Measure authored fixtures; this does not call a model or translate English."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scir import parse_document, parse_pattern, format_document, query, walk
from scir.annotations import Alternatives
from scir.relations import encode, decode


def run():
    cases=json.loads((Path(__file__).resolve().parents[1]/'examples/corpus.json').read_text())
    rows=[]; docs={}
    for case in cases:
        candidates=tuple(parse_document(s) for s in case['candidates'])
        if len(candidates)>1:
            choice=Alternatives(candidates)
            assert choice.choose(0)==candidates[0]
        docs[case['id']]=candidates
        for doc in candidates:
            assert parse_document(format_document(doc))==doc
            assert decode(encode(doc))==doc
        p=parse_pattern(case['query_pattern'])
        d=candidates[0]; all_hits=query(d,p,scope='all'); root_hits=query(d,p)
        rows.append({'id':case['id'],'candidates':len(candidates),
                     'english_characters':len(case['source']),
                     'scir_characters':len(format_document(d).rstrip('\n')),
                     'first_candidate_roots':len(d),
                     'first_candidate_max_depth':max((len(path)-1 for path,t in walk(d)),default=0),
                     'root_matches':len(root_hits),'all_matches':len(all_hits)})
    assert docs['active']==docs['passive']
    assert docs['sent']!=docs['received']
    assert docs['negation_inside']!=docs['negation_outside']
    return {'method':'Single-assistant authored examples and backtranslations; no independent model evaluation.',
            'fixtures':len(cases),'candidate_documents':sum(r['candidates'] for r in rows),
            'scir_shorter_in_first_candidate':sum(r['scir_characters']<r['english_characters'] for r in rows),
            'rows':rows,'status':'structural checks passed'}

if __name__=='__main__': print(json.dumps(run(),indent=2))
