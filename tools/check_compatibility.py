"""Differential valid-input checks against an explicit 0.2 source checkout."""
import argparse
import importlib.util
import json
from pathlib import Path
import random
import sys


def load(name, source):
    spec = importlib.util.spec_from_file_location(name, source / 'scir' / '__init__.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(baseline, cases=1000, seed=6021):
    sources = (baseline, Path(__file__).resolve().parents[1] / 'src')
    modules = [load(f'_scir_comparison_{i}', src) for i, src in enumerate(sources)]
    relations = [importlib.import_module(f'{m.__name__}.relations') for m in modules]
    templates = [importlib.import_module(f'{m.__name__}.templates') for m in modules]
    rng = random.Random(seed)

    def source(depth):
        symbol = json.dumps(rng.choice(('A', 'B', 'f', 'think', 'not', '?literal', 'two words', 'Алиса')))
        if not depth or rng.random() < .6:
            return symbol + ('()' if rng.random() < .25 else '')
        return symbol + '(' + ', '.join(source(depth - 1) for _ in range(rng.randrange(1, 4))) + ')'

    def hits(module, doc, pattern, scope):
        return [(h.path, str(h.term), {k: str(v) for k, v in h.bindings.items()})
                for h in module.query(doc, module.parse_pattern(pattern), scope=scope)]

    for _ in range(cases):
        text = ';\n'.join(source(4) for _ in range(rng.randrange(4)))
        docs = [m.parse_document(text) for m in modules]
        assert modules[0].format_document(docs[0]) == modules[1].format_document(docs[1])
        assert modules[0].digest(docs[0]) == modules[1].digest(docs[1])
        wires = [r.encode(d) for r, d in zip(relations, docs)]
        assert wires[0] == wires[1]
        for pattern in ('?_', '?x', 'think(?who, ?what)', 'f(?x, ?x)', 'A'):
            for scope in ('roots', 'all'):
                assert hits(modules[0], docs[0], pattern, scope) == hits(modules[1], docs[1], pattern, scope)
        if docs[0]:
            path, _ = rng.choice(list(modules[0].walk(docs[0])))
            changed = [m.replace_at(d, path, m.Term('Replacement')) for m, d in zip(modules, docs)]
            assert modules[0].format_document(changed[0]) == modules[1].format_document(changed[1])
            deltas = [[(x.path, str(x.before), str(x.after)) for x in m.diff(a, b)]
                      for m, a, b in zip(modules, docs, changed)]
            assert deltas[0] == deltas[1]

    for _ in range(5000):
        text = ''.join(rng.choice('ABfx?(),;\n \\"#1=') for _ in range(rng.randrange(60)))
        results = []
        for module in modules:
            try:
                results.append(module.format_document(module.parse_document(text)))
            except module.ParseError:
                results.append(None)
        assert results[0] == results[1], (text, results)

    for _ in range(100):
        text = 'dup_macro(wrap_macro(' + source(3) + '))'
        results = []
        for module, template in zip(modules, templates):
            definitions = {
                'wrap_macro': template.Definition(('x',), module.parse_pattern('wrapped(?x)')),
                'dup_macro': template.Definition(('x',), module.parse_pattern('pair(?x, ?x)')),
            }
            results.append(module.format_document(template.expand(module.parse_document(text), definitions)))
        assert results[0] == results[1]
    return {'seed': seed, 'documents': cases, 'syntax_samples': 5000, 'template_cases': 100,
            'versions': [m.__version__ for m in modules], 'status': 'passed',
            'scope': 'Valid structure and syntax acceptance; new rejection policies are regression-tested separately.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline_src', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.baseline_src), indent=2))
