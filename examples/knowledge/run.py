"""Check three knowledge migrations and query review impact; never rewrite prose."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import sys

from scir import Document, format_document, parse_document, parse_pattern
from scir.constraints import Violation, check, forms

ROOT = Path(__file__).resolve().parent
CASES = {"architecture": "A1", "investigation": "O2", "mathematics": "A2"}
ROLES = frozenset(("Decision", "Requirement", "Assumption", "Proposal", "Question",
                   "Observation", "Hypothesis", "Limitation", "Revision", "Conclusion"))
ARITY = {"snapshot": 1, "record": 3, "source": 2, "dependsOn": 2}
FORMS = tuple(map(parse_pattern, (
    "snapshot(?hash)", "record(?id, ?role, ?content)",
    "source(?id, ?sentence)", "dependsOn(?id, ?premise)",
)))


def source_ids(source: bytes) -> set[str]:
    ids = re.findall(r"^(S[1-9][0-9]*): .+", source.decode("utf-8"), re.M)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("source needs distinct S1: ... sentence anchors")
    return set(ids)


def links(document: Document, source: bytes):
    anchors, records, edges, snapshots = source_ids(source), defaultdict(list), [], []
    for i, term in enumerate(document):
        if len(term.args) != ARITY.get(term.symbol):
            continue  # The form rule owns malformed roots.
        leaves = term.args[:2] if term.symbol == "record" else term.args
        if any(arg.args for arg in leaves):
            yield Violation((i,), "leaf", "IDs, roles, anchors, and hashes must be leaves")
            continue
        if term.symbol == "record":
            ident, role, _ = term.args
            records[ident.symbol].append(i)
            if role.symbol not in ROLES:
                yield Violation((i, 1), "role", "unknown knowledge role")
        elif term.symbol == "snapshot":
            snapshots.append(term.args[0].symbol)
        else:
            edges.append((i, term))
    if snapshots != [hashlib.sha256(source).hexdigest()]:
        yield Violation(None, "snapshot", "require exactly one matching source-byte SHA-256")
    if not records:
        yield Violation(None, "nonempty", "at least one knowledge record is required")
    for ident, positions in records.items():
        for i in positions[1:]:
            yield Violation((i, 0), "duplicate-id", f"duplicate record: {ident}")
    seen, cited, covered = set(), set(), set()
    for i, term in edges:
        owner, target = (arg.symbol for arg in term.args)
        if term in seen:
            yield Violation((i,), "duplicate-link", "duplicate source or dependency link")
        seen.add(term)
        references = ((0, owner), (1, target)) if term.symbol == "dependsOn" else ((0, owner),)
        for position, ident in references:
            if len(records.get(ident, ())) != 1:
                yield Violation((i, position), "reference", f"unknown or ambiguous record: {ident}")
        if term.symbol == "source":
            if target not in anchors:
                yield Violation((i, 1), "source", f"unknown source anchor: {target}")
            elif len(records.get(owner, ())) == 1:
                cited.add(owner)
                covered.add(target)
    for ident, positions in records.items():
        if ident not in cited:
            yield Violation((positions[0],), "uncited", f"record needs a source anchor: {ident}")
    for anchor in sorted(anchors - covered):
        yield Violation(None, "unmapped", f"source anchor has no record: {anchor}")


def validate(document: Document, source: bytes) -> tuple[Violation, ...]:
    """Check this example's contract, not prose fidelity or domain truth."""
    return check(document, (forms(*FORMS), lambda d: links(d, source)))


def affected(document: Document, changed) -> tuple[str, ...]:
    """Review candidates reachable through declared dependencies in a checked document."""
    if isinstance(changed, (str, bytes)):
        raise ValueError("changed IDs must be a collection, not one string")
    order = [t.args[0].symbol for t in document if t.symbol == "record"]
    pending = deque(changed)
    if not set(pending) <= set(order):
        raise ValueError("changed IDs must name declared records")
    dependents = defaultdict(list)
    for term in document:
        if term.symbol == "dependsOn":
            owner, premise = (arg.symbol for arg in term.args)
            dependents[premise].append(owner)
    reached = set()
    while pending:
        ident = pending.popleft()
        if ident not in reached:
            reached.add(ident)
            pending.extend(dependents[ident])
    return tuple(ident for ident in order if ident in reached)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--changed", action="append", help="record to hypothetically change; requires --case")
    args = parser.parse_args(argv)
    if args.changed and not args.case:
        parser.error("--changed requires --case")
    reports = []
    try:
        for name in (args.case,) if args.case else CASES:
            folder = ROOT / name
            text = (folder / "knowledge.scir").read_bytes().decode("utf-8")
            document = parse_document(text)
            issues = validate(document, (folder / "source.md").read_bytes())
            if issues or text != format_document(document):
                for issue in issues:
                    print(f"{name} {issue.path}: {issue.rule}: {issue.message}", file=sys.stderr)
                if text != format_document(document):
                    print(f"{name}: noncanonical knowledge source", file=sys.stderr)
                return 1
            changed = args.changed or [CASES[name]]
            reports.append({"case": name, "contract": "passed", "hypothetical_change": changed,
                            "review_candidates": affected(document, changed)})
        print(json.dumps({"cases": reports, "source_fidelity": "requires separate review",
                          "authored_overviews": "not checked or rewritten",
                          "domain_inference": "not performed"}, indent=2))
        return 0
    except (ValueError, OSError, RecursionError) as error:
        print(f"knowledge: check incomplete: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
