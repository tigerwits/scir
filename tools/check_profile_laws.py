"""Exhaustive finite closure oracles, separate from Lean's abstract model."""
import itertools
import json
from scir import Term
from scir import profile as p
from scir.knowledge import build_index, select, affected


def closure(graph, seeds):
    result = set(seeds)
    while True:
        next_result = result | {target for source in result for target in graph[source]}
        if result == next_result:
            return result
        result = next_result


def check():
    ids = ('A', 'B', 'C')
    edges = tuple(itertools.product(ids, repeat=2))
    subsets = tuple(tuple(i for bit, i in enumerate(ids) if mask & (1 << bit)) for mask in range(8))
    cases = 0
    for mask in range(512):
        graph = {i: tuple(b for k, (a, b) in enumerate(edges) if a == i and mask & (1 << k)) for i in ids}
        reverse = {i: tuple(a for a in ids if i in graph[a]) for i in ids}
        document = tuple(p.application('record', (Term(i), Term('Note'), Term('p')),
            fields=(('dependsOn', p.tuple_value(tuple(p.reference(t) for t in graph[i]))),)) for i in ids)
        index = build_index(document, collection='finite-law-model')
        results = {}
        for seeds in subsets:
            expected = closure(graph, seeds)
            result = select(index, seeds)
            assert set(result.selected_ids) == expected
            assert set(seeds) <= expected
            assert select(index, result.selected_ids).document == result.document
            assert set(affected(index, seeds)) == closure(reverse, seeds)
            for candidate in subsets:
                candidate_set = set(candidate)
                if set(seeds) <= candidate_set and all(set(graph[i]) <= candidate_set for i in candidate):
                    assert expected <= candidate_set
            results[seeds] = expected
            cases += 1
        for small in subsets:
            for big in subsets:
                if set(small) <= set(big):
                    assert results[small] <= results[big]
    return {'graphs': 512, 'seed_sets': cases, 'closure': 'pass', 'reverse_dependency': 'pass',
            'minimality': 'pass', 'monotonicity': 'pass', 'agent_trials': 0}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
