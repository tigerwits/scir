"""Inspect authored refinements of one frozen source. No model calls; inputs are never rewritten."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

from scir import digest, diff, format_document, parse_document
from scir.constraints import check
from scir.relations import decode, encode
from scir.tree import walk

from contracts import (
    CASE, CONTRACTS, FILES, NAMES, SOURCE_SHA256, inline_conditions,
    source_review, translate_draft, unrecord,
)

HERE = Path(__file__).resolve().parent


def read_document(path: Path):
    with path.open(encoding="utf-8") as stream:
        text = stream.read(2_000_001)
    return parse_document(text)


def review(document, *, generic=False):
    try:
        return source_review(document, generic=generic)
    except ValueError as error:
        return {"status": "unreviewable", "reason": str(error)}


def run(stages: Path | None = None) -> dict:
    source = (HERE / "source.md").read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("source changed: review the oracle before running another case")
    documents = tuple(read_document((stages or HERE / "stages") / name) for name in FILES)
    checks = [[check(d, rules) for rules in CONTRACTS] for d in documents]
    rows = []
    for i, document in enumerate(documents):
        nodes = list(walk(document))
        rows.append({
            "stage": NAMES[i], "digest": digest(document),
            "constraints": [rule.__name__ for rule in CONTRACTS[i]],
            "violations": [asdict(v) for v in checks[i][i]],
            "accepts": [not violations for violations in checks[i]],
            "source_review": review(document, generic=i == 0),
            "roots": len(document), "occurrences": len(nodes),
            "depth": max((len(path) - 1 for path, _ in nodes), default=0),
            "characters": len(format_document(document)),
            "transport_preserves_diagnostics": all(
                check(decode(encode(document)), rules) == checks[i][j]
                for j, rules in enumerate(CONTRACTS)
            ),
        })

    transitions = []
    transforms = (translate_draft, unrecord, inline_conditions)
    for i, transform in enumerate(transforms, 1):
        before, after = documents[i - 1:i + 1]
        try:
            # Only the first step maps forwards. The other two reconstruct a prior view.
            reconstructed = transform(before if i == 1 else after)
            preserved = reconstructed == (after if i == 1 else before)
            preservation = {"operation": transform.__name__, "equal": preserved}
        except ValueError as error:
            preservation = {"operation": transform.__name__, "equal": False, "error": str(error)}
        transitions.append({
            "from": NAMES[i - 1], "to": NAMES[i],
            "previous_under_new_contract": [asdict(v) for v in checks[i - 1][i]],
            "preservation": preservation,
            "positional_diff": [
                {"path": change.path,
                 "before": None if change.before is None else str(change.before),
                 "after": None if change.after is None else str(change.after)}
                for change in diff(before, after)
            ],
        })

    invented = read_document(HERE / "counterexamples/unsupported-timeout.scir")
    witness_issues = check(invented, CONTRACTS[4])
    witness_review = source_review(invented)
    complete = (
        all(not row["violations"] and row["source_review"]["status"] == "matches-authored-oracle"
            and row["transport_preserves_diagnostics"] for row in rows)
        and all(t["preservation"]["equal"] for t in transitions)
        and bool(checks[-1][4])
        and not witness_issues
        and witness_review["status"] == "differs-from-authored-oracle"
    )
    return {
        "case": CASE,
        "source_sha256": SOURCE_SHA256,
        "contracts_sha256": hashlib.sha256((HERE / "contracts.py").read_bytes()).hexdigest(),
        "evidence": "authored fixtures and deterministic checks; no model evaluation",
        "status": "checks-passed" if complete else "needs-review",
        "contract_order": NAMES,
        "stages": rows, "transitions": transitions,
        "blocked_target": {
            "stage": NAMES[4],
            "violations": [asdict(v) for v in checks[-1][4]],
            "reason": "S4 supplies no timeout. A value requires a new source decision, not translation.",
            "status": "blocked-by-fixed-source",
        },
        "counterexample": {
            "file": "counterexamples/unsupported-timeout.scir",
            "target_violations": [asdict(v) for v in witness_issues],
            "source_review": witness_review,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stages", type=Path, help="alternate folder containing the four named stage files")
    parser.add_argument("--json", action="store_true", help="include diagnostics, diffs, metrics, and source review")
    args = parser.parse_args(argv)
    try:
        report = run(args.stages)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("Fixed source:")
            print((HERE / "source.md").read_text(encoding="utf-8").strip())
            print("\nStage        roots nodes chars  acceptance (generic -> timeout)")
            for row in report["stages"]:
                flags = " ".join("pass" if accepted else "fail" for accepted in row["accepts"])
                print(f"{row['stage']:12} {row['roots']:5} {row['occurrences']:5} {row['characters']:5}  {flags}")
                print("  source review:", row["source_review"]["status"])
            for transition in report["transitions"]:
                print(f"\n{transition['from']} -> {transition['to']}:")
                for violation in transition["previous_under_new_contract"]:
                    print(f"  before: {violation['path']} {violation['rule']}: {violation['message']}")
                law = transition["preservation"]
                print(f"  {law['operation']}: exact reconstruction = {law['equal']}")
            print("\nBLOCKED:", report["blocked_target"]["reason"])
            witness = report["counterexample"]
            print("Counterexample: target conforms =", not witness["target_violations"],
                  "; source review =", witness["source_review"]["status"])
            print(report["status"], "(authored examples; no model calls)")
        return 0 if report["status"] == "checks-passed" else 1
    except (ValueError, OSError, RecursionError) as error:
        print(f"dialect-chain: check incomplete: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
