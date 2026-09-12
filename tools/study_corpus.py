"""Check authored fixtures; this does not call a model or translate English."""
import json
from pathlib import Path

from scir import format_document, parse_document, parse_pattern, query
from scir.annotations import Alternatives
from scir.relations import decode, encode
from scir.tree import walk


def run():
    path = Path(__file__).resolve().parents[1] / "docs/research/corpus.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    rows, documents = [], {}
    for case in cases:
        candidates = tuple(parse_document(source) for source in case["candidates"])
        if len(candidates) > 1:
            assert Alternatives(candidates).choose(0) == candidates[0]
        documents[case["id"]] = candidates
        for document in candidates:
            assert parse_document(format_document(document)) == document
            assert decode(encode(document)) == document
        pattern = parse_pattern(case["query_pattern"])
        first = candidates[0]
        rows.append({
            "id": case["id"], "candidates": len(candidates),
            "english_characters": len(case["source"]),
            "scir_characters": len(format_document(first).rstrip("\n")),
            "first_candidate_roots": len(first),
            "first_candidate_max_depth": max((len(p) - 1 for p, _ in walk(first)), default=0),
            "root_matches": len(query(first, pattern)),
            "all_matches": len(query(first, pattern, scope="all")),
        })
    assert documents["active"] == documents["passive"]
    assert documents["sent"] != documents["received"]
    assert documents["negation_inside"] != documents["negation_outside"]
    return {
        "method": "Authored examples and backtranslations; no independent model evaluation.",
        "fixtures": len(cases), "candidate_documents": sum(r["candidates"] for r in rows),
        "scir_shorter_in_first_candidate": sum(r["scir_characters"] < r["english_characters"] for r in rows),
        "rows": rows, "status": "structural checks passed",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
