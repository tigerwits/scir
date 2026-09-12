"""Consumer-owned example contract. Unknown references block acceptance."""
import argparse
from pathlib import Path
import sys

from scir import parse_document, parse_pattern
from scir.constraints import Violation, check, forms


def references(document):
    # Collect declarations before checking references, allowing forward references.
    declarations = {}
    for root, term in enumerate(document):
        if term.symbol not in ("hypothesis", "observation") or len(term.args) != 2:
            continue
        identifier = term.args[0]
        if identifier.args:
            yield Violation((root, 0), "identifier", "a declaration ID must be a leaf")
        elif identifier.symbol in declarations:
            declarations[identifier.symbol] = None
            yield Violation((root, 0), "duplicate-id", "ambiguous declaration ID")
        else:
            declarations[identifier.symbol] = term.symbol
    for root, term in enumerate(document):
        if term.symbol != "supports" or len(term.args) != 2:
            continue
        for position, (identifier, kind) in enumerate(zip(term.args, ("observation", "hypothesis"))):
            path = (root, position)
            if identifier.args:
                yield Violation(path, "identifier", "a reference ID must be a leaf")
            elif identifier.symbol not in declarations:
                yield Violation(path, "unknown-reference", f"no declaration for {identifier.symbol}")
            elif declarations[identifier.symbol] != kind:
                yield Violation(path, "reference-kind", f"reference must unambiguously name a {kind}")


def nonempty(document):
    if not document:
        yield Violation(None, "nonempty", "at least one record is required")


RULES = (
    forms(*(parse_pattern(p) for p in (
        "hypothesis(?id, ?content)", "observation(?id, ?content)", "supports(?observation, ?hypothesis)",
    ))),
    nonempty,
    references,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        content = parse_document(args.file.read_text(encoding="utf-8"))
        issues = check(content, RULES)
    except (OSError, ValueError) as error:
        print(f"check failed: {error}", file=sys.stderr)
        return 2
    for issue in issues:
        print(f"{issue.path}: {issue.rule}: {issue.message}")
    if not issues:
        print("conforms to the supplied handoff contract")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
