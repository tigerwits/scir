"""Local warm-process microbenchmarks; no LLM or semantic-quality claims."""
import gc
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scir import parse_document, parse_pattern, format_document, query, walk
from scir.relations import encode, decode


def median_ms(fn,repeats=3):
    fn()
    times=[]
    for _ in range(repeats):
        gc.collect()
        start=time.perf_counter(); fn(); times.append((time.perf_counter()-start)*1000)
    return round(statistics.median(times),3)


def run():
    row='think(Bob, mistakenly(use(Alice, yesterday(SalesData))))\n'
    pat=parse_pattern('use(Alice, ?x)')
    measurements=[]
    for count in (100,1000,5000):
        source=row*count; doc=parse_document(source); wire=encode(doc)
        measurements.append({'roots':count,'nodes':sum(1 for _ in walk(doc)), 'source_characters':len(source),
            'parse_ms':median_ms(lambda:parse_document(source)),
            'format_ms':median_ms(lambda:format_document(doc)),
            'query_all_ms':median_ms(lambda:query(doc,pat,scope='all')),
            'encode_ms':median_ms(lambda:encode(doc)),
            'decode_ms':median_ms(lambda:decode(wire))})
    return {'python':platform.python_version(),'implementation':platform.python_implementation(),
            'platform':platform.system()+' '+platform.machine(),'repeats':3,'summary':'median after one warmup',
            'measurements':measurements,'limitations':'One shared runtime; no performance regression threshold or cross-model inference comparison.'}


def run_shapes():
    rows=[]
    for kind,size in [('chain',8),('chain',32),('chain',128),('wide',100),('wide',1000),('wide',10000)]:
        source=('f('*size+'A'+')'*size) if kind=='chain' else 'f('+','.join(['A']*size)+')'
        doc=parse_document(source)
        rows.append({'shape':kind,'size':size,'nodes':sum(1 for _ in walk(doc)),
                     'parse_ms':median_ms(lambda:parse_document(source)),
                     'format_ms':median_ms(lambda:format_document(doc)),
                     'encode_ms':median_ms(lambda:encode(doc))})
    return {'python':platform.python_version(),'measurements':rows,
            'scope':'Accepted reference limits only; medians of three runs after warmup.'}


if __name__=='__main__': print(json.dumps(run_shapes() if '--shapes' in sys.argv else run(),indent=2))
