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
    from .projection import legacy_document, QUERY_FIELDS
else:
    from locations import declarations, local_file, read_source
    from projection import legacy_document, QUERY_FIELDS

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = "scir-repository"
SOURCES = ("spec/native.scir", "spec/knowledge.scir")
KINDS = frozenset(("Requirement", "Decision", "Limitation", "Question"))
AREAS = frozenset(("Core", "Syntax", "Patterns", "Tree", "Annotations", "Transport",
                   "Constraints", "CLI", "Structured", "Notation", "Working", "Changes",
                   "Workflow", "Evidence"))
FIELDS = frozenset(("ownership", "source", "area", "tests", "models", "status",
                    "dependsOn", "scope", "evidence", "reason", "supersedes", "projection")) | QUERY_FIELDS


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
        if _leaf(fields["ownership"], "ownership") not in ("index", "record"):
            raise ProfileError("ownership must be index or record")
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
    projected = legacy_document(index)
    if projected:
        issues = _legacy().validate_catalog(projected, root)
        if issues:
            raise ProfileError("invalid legacy projection: " + "; ".join(i.message for i in issues))
    return index


def _legacy():
    if __package__:
        from . import check
    else:
        import check
    return check


def load(root: Path = ROOT) -> Index:
    document = ()
    for name in SOURCES:
        source = read_source(local_file(root, name, ".scir"))
        shard = parse_document(source)
        if format_document(shard) != source:
            raise ProfileError("repository knowledge must be canonical: " + name)
        document += shard
    return validate(document, root)


def updates(index: Index, root: Path = ROOT):
    """Preflight all three derived destinations before the caller writes any."""
    projected = legacy_document(index)
    if not projected:
        raise ProfileError("maintained repository requires native projection records")
    legacy = local_file(root, "spec/requirements.scir", ".scir")
    expected = format_document(projected).encode("utf-8")
    changes = [] if legacy.read_bytes() == expected else [(legacy, expected)]
    changes.extend(_legacy().view_updates(projected, root))
    return changes


def propose_checked(index: Index, request: str, root: Path = ROOT):
    """Generic candidate acceptance is weaker than repository-source acceptance."""
    from scir.changes import propose
    proposal = propose(index, request)
    candidate = validate(proposal.document, root)
    updates(candidate, root)  # Preflight derived views, but do not write them.
    return proposal


def maintenance(root: Path = ROOT, *, write_views=False, markdown=False) -> int:
    try:
        index = load(root)
        changes = updates(index, root)
        if changes and not write_views:
            raise ProfileError("stale derived files: " + ", ".join(p.relative_to(root).as_posix() for p, _ in changes))
        if write_views:
            for path, data in changes:
                path.write_bytes(data)
            print(f"Refreshed {len(changes)} derived files; authoritative records were not changed.")
        elif markdown:
            print(_legacy().render(legacy_document(index)), end="")
        else:
            print(f"Checked {len(index.records)} repository records and all derived views; linked tests were not run.")
        return 0
    except ProfileError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (ValueError, OSError, RecursionError) as error:
        print(f"repository check incomplete: {error}", file=sys.stderr)
        return 2


def _emit(stream, value):
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > 16_000_000:
        raise LimitError("repository packet byte limit exceeded")
    if hasattr(stream, "buffer"):
        stream.flush()
        stream.buffer.write(raw)
    else:
        stream.write(raw.decode("utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check")
    sub.add_parser("refresh")
    pick = sub.add_parser("select")
    pick.add_argument("--id", action="append", required=True)
    review = sub.add_parser("affected")
    review.add_argument("--changed", action="append", required=True)
    change = sub.add_parser("propose")
    change.add_argument("--change", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command in (None, "check", "refresh"):
        return maintenance(write_views=args.command == "refresh")
    try:
        from scir.knowledge import select, affected
        index = load()
        if args.command == "select":
            result = select(index, tuple(args.id)).as_dict()
        elif args.command == "affected":
            result = {"collection": COLLECTION, "source_snapshot": index.snapshot,
                      "review_ids": affected(index, tuple(args.changed))}
        else:
            request = read_source(args.change)
            result = propose_checked(index, request).as_dict()
        result["repository_contract"] = "scir-repository/1"
        _emit(sys.stdout, result)
        return 0
    except ProfileError as error:
        _emit(sys.stderr, {"status": "rejected", "error": str(error)})
        return 1
    except (ValueError, OSError, RecursionError) as error:
        _emit(sys.stderr, {"status": "incomplete", "error": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
