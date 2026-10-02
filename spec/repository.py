"""Project knowledge contract over working/1; no new runtime vocabulary."""
from __future__ import annotations

import argparse
from functools import cache
import json
from pathlib import Path
import sys

from scir import Document, Term, format_document, parse_document
from scir.knowledge import Index, build_index
from scir.profile import LimitError, ProfileError, read_fields, read_tuple

if __package__:
    from .locations import declarations, local_file, read_source
else:
    from locations import declarations, local_file, read_source

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = "scir-repository"
KINDS = frozenset(("Requirement", "Decision", "Limitation", "Question"))
AREAS = frozenset(("Core", "Syntax", "Patterns", "Tree", "Annotations", "Transport",
                   "Constraints", "CLI", "Structured", "Notation", "Working", "Changes",
                   "Workflow", "Evidence"))
FIELDS = frozenset(("ownership", "source", "area", "tests", "models", "status",
                    "dependsOn", "scope", "evidence", "reason", "supersedes"))


def _leaf(term: Term, role: str) -> str:
    if term.args:
        raise ProfileError(role + " must be a leaf")
    return term.symbol


def _items(term: Term, role: str) -> tuple[Term, ...]:
    items = read_tuple(term)
    if read_fields(term):
        raise ProfileError(role + " must be a positional tuple")
    return items


def validate(document: Document, root: Path = ROOT) -> Index:
    """Check references and declared source/test/model locations, not their adequacy."""
    index = build_index(document, collection=COLLECTION)
    if not index.records:
        raise ProfileError("repository knowledge must not be empty")

    @cache
    def names(path: str, kind: str):
        return declarations(root, path, kind)

    def location(term: Term, kind: str) -> None:
        if term.symbol != kind or len(term.args) != 2:
            raise ProfileError("expected " + kind + "(path, declaration)")
        path, name = (_leaf(a, "location") for a in term.args)
        if names(path, kind).count(name) != 1:
            raise ProfileError(f"expected one {name!r} in {path!r}")

    for record in index.records.values():
        fields = dict(record.fields)
        if record.kind not in KINDS or set(fields) - FIELDS:
            raise ProfileError("unknown repository kind or field: " + record.id)
        if not {"ownership", "source", "area"} <= fields.keys():
            raise ProfileError("record needs ownership, source and area: " + record.id)
        if _leaf(fields["ownership"], "ownership") != "index":
            raise ProfileError("this catalog indexes document-owned statements")
        if _leaf(fields["area"], "area") not in AREAS:
            raise ProfileError("unknown repository area")
        location(fields["source"], "section")
        if record.kind == "Requirement" and "tests" not in fields:
            raise ProfileError("requirement needs independent test links")
        for field, kind in (("tests", "test"), ("models", "model")):
            if field not in fields:
                continue
            items = _items(fields[field], field)
            if not items or len(set(items)) != len(items):
                raise ProfileError(field + " must be nonempty with no duplicate links")
            for item in items:
                location(item, kind)
        if record.kind in ("Decision", "Question") and "status" not in fields:
            raise ProfileError("decision/question needs an authored status")
    return index


def load(root: Path = ROOT) -> Index:
    source = read_source(local_file(root, "spec/knowledge.scir", ".scir"))
    document = parse_document(source)
    if format_document(document) != source:
        raise ProfileError("repository knowledge must use canonical native SCIR")
    return validate(document, root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        index = load()
        print(json.dumps({"contract": "scir-repository/1", "records": len(index.records),
                          "snapshot": index.snapshot, "locations": "resolved",
                          "tests_executed": False, "proofs_checked": False}))
        return 0
    except LimitError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (ValueError, OSError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        return 1 if isinstance(error, ValueError) else 2


if __name__ == "__main__":
    raise SystemExit(main())
