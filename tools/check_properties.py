"""Seeded structural laws; finite checks, not universal proofs."""
import argparse
import json
import random

from scir import Term, format_document, match, parse_document, parse_pattern, replace_at
from scir.annotations import Bundle, annotate, erase
from scir.constraints import check, forms, vocabulary
from scir.patterns import Node, Var, instantiate
from scir.relations import decode, encode
from scir.tree import walk


def run(seed=602, cases=1000):
    rng = random.Random(seed)
    occurrences = 0
    left = (vocabulary({"A", "Bob", "think", "not", "f"}),)
    right = (forms(parse_pattern("think(?_, ?_)"), parse_pattern("A")),)

    def generate(depth):
        symbol = rng.choice(["A", "Bob", "think", "not", "f", "quoted words", "Алиса", "0.7"])
        args = () if not depth or rng.random() < .55 else tuple(
            generate(depth - 1) for _ in range(rng.randrange(1, 4)))
        return Term(symbol, args)

    def abstract(term, names):
        if rng.random() < .35:
            key = str(term)
            if key not in names:
                names[key] = f"x{len(names)}"
            return Var(names[key])
        return Node(term.symbol, tuple(abstract(child, names) for child in term.args))

    for case in range(cases):
        document = tuple(generate(5) for _ in range(rng.randrange(5)))
        assert parse_document(format_document(document)) == document
        wire = encode(document)
        assert decode(wire) == document
        for table in ("nodes", "args", "roots"):
            rng.shuffle(wire[table])
        assert decode(wire) == document
        combined = check(document, left + right, max_violations=10_000)
        assert combined == (check(document, left, max_violations=10_000)
                            + check(document, right, max_violations=10_000))
        assert check(decode(wire), left + right, max_violations=10_000) == combined
        nodes = list(walk(document))
        occurrences += len(nodes)
        for term in document:
            pattern = abstract(term, {})
            assert parse_pattern(str(pattern)) == pattern
            bindings = match(pattern, term)
            assert bindings is not None and instantiate(pattern, bindings) == term
        if nodes:
            path, term = rng.choice(nodes)
            assert replace_at(document, path, term) == document
            bundle = Bundle(document, (annotate(document, path, "source", {"fixture": case}),))
            assert erase(bundle) == document
    return {
        "seed": seed, "documents": cases, "occurrences": occurrences,
        "checks": ["content parse/print", "pattern parse/print", "match/instantiate",
                   "relation round-trip", "row-order invariance", "identity edit", "annotation erasure",
                   "constraint composition", "constraint transport invariance"],
        "status": "passed", "scope": "finite seeded tests, not universal proofs",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=602)
    parser.add_argument("--cases", type=int, default=1000)
    args = parser.parse_args()
    if args.cases < 1:
        parser.error("--cases must be positive")
    print(json.dumps(run(args.seed, args.cases), indent=2))
