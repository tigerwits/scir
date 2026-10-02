"""Project knowledge contract over working/1; no new runtime vocabulary."""
from __future__ import annotations

import argparse
from functools import cache
import json
from pathlib import Path
import sys

from scir import Document, Term, format_document, parse_document
from scir.knowledge import Index, build_index
from scir._profile_native import native, failure
from scir.profile import LimitError, ProfileError, read_fields, read_tuple

if __package__:
    from .locations import declarations, local_file, read_source
    from .projection import legacy_document, QUERY_FIELDS
    from . import catalog, handoff
else:
    from locations import declarations, local_file, read_source
    from projection import legacy_document, QUERY_FIELDS
    import catalog, handoff

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
        try:
            found = names(path, kind).count(name)
        except LimitError:
            raise
        except ValueError as error:
            raise ProfileError(str(error)) from error
        if found != 1:
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
        issues = catalog.validate_catalog(projected, root)
        if issues:
            raise ProfileError("invalid legacy projection: " + "; ".join(i.message for i in issues))
    return index


def load(root: Path = ROOT) -> Index:
    document = ()
    for name in SOURCES:
        source = read_source(local_file(root, name, ".scir"))
        shard = native(source)
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
    changes.extend(catalog.view_updates(projected, root))
    return changes


def propose_checked(index: Index, request: str, root: Path = ROOT):
    """Generic candidate acceptance is weaker than repository-source acceptance."""
    from scir.changes import propose
    proposal = propose(index, request)
    candidate = validate(proposal.document, root)
    updates(candidate, root)  # Preflight derived views, but do not write them.
    return proposal


def propose_handoff(index: Index, request: str, expected_basis: str,
                    root: Path = ROOT, *, placements=None):
    """Plan a source-owned update against exact maintenance input bytes."""
    from scir.changes import ConflictError, propose
    root = root.resolve()
    before = handoff.capture(root, index, SOURCES)
    if expected_basis != before.fingerprint:
        raise ConflictError("repository input basis changed; select fresh context")
    proposed = propose(index, request)
    document, shards = handoff.partition(proposed.document, before, SOURCES, placements)
    # Capture newly introduced source links too, before checking their contents.
    candidate_index = build_index(document, collection=COLLECTION)
    prospective = handoff.capture(root, index, SOURCES, extra=handoff.linked_paths(candidate_index))
    candidate = validate(document, root)
    derived = updates(candidate, root)
    write_plan = handoff.writes(root, prospective, shards, derived)
    if (handoff.capture(root, index, SOURCES) != before or
            handoff.capture(root, index, SOURCES, extra=handoff.linked_paths(candidate)) != prospective):
        raise ConflictError("repository inputs changed during proposal validation")
    return {"version": "scir-repository-proposal/1", "collection": COLLECTION,
            "before_snapshot": index.snapshot, "candidate_snapshot": candidate.snapshot,
            "runtime_candidate_snapshot": proposed.candidate_snapshot,
            "request": proposed.request.as_dict(), "placements": {} if placements is None else placements,
            "records": [str(t) for t in document], "write_plan": write_plan,
            "input_basis": before.packet(), "commit_basis": prospective.packet(),
            "repository_contract": "scir-repository/1", "complete": True,
            "source_written": False, "validation": {"profile": "scir-repository/1", "complete": True}}


def maintenance(root: Path = ROOT, *, write_views=False, markdown=False) -> int:
    try:
        # Location resolvers return absolute canonical paths, including on macOS
        # temporary-directory aliases and Windows case/short-name aliases.
        root = root.resolve()
        index = load(root)
        changes = updates(index, root)
        if changes and not write_views:
            raise ProfileError("stale derived files: " + ", ".join(p.relative_to(root).as_posix() for p, _ in changes))
        if write_views:
            for path, data in changes:
                path.write_bytes(data)
            print(f"Refreshed {len(changes)} derived files; authoritative records were not changed.")
        elif markdown:
            print(catalog.render(legacy_document(index)), end="")
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
    change.add_argument("--basis", required=True, help="input_basis.digest from a fresh selection")
    change.add_argument("--placements", type=Path, help="JSON mapping of newly created IDs to source shards")
    for command in (pick, change):
        command.add_argument("--view", choices=("full", "compact", "artifact"), default="full")
        command.add_argument("--encoding", choices=("native", "notation"))
        command.add_argument("--expected-artifact", help="SHA-256 from a previous compact packet")
    diagnostic = sub.add_parser("diagnose")
    diagnostic.add_argument("--id", action="append", required=True)
    diagnostic.add_argument("--encoding", choices=("native", "notation"), default="native")
    args = parser.parse_args(argv)
    if args.command in (None, "check", "refresh"):
        return maintenance(write_views=args.command == "refresh")
    try:
        from scir.knowledge import select, affected
        if args.command in ("select", "propose"):
            if args.view == "full" and args.encoding is not None:
                raise ProfileError("encoding requires an explicit delivery view")
            if (args.view == "artifact") != (args.expected_artifact is not None):
                raise ProfileError("artifact view requires its expected hash; other views forbid it")
        index = load()
        basis = handoff.capture(ROOT, index, SOURCES)
        if args.command == "select":
            result = select(index, tuple(args.id)).as_dict()
        elif args.command == "diagnose":
            from scir.diagnostics import diagnose
            result = diagnose(index, tuple(args.id), encoding=args.encoding)
        elif args.command == "affected":
            result = {"collection": COLLECTION, "source_snapshot": index.snapshot,
                      "review_ids": affected(index, tuple(args.changed))}
        else:
            request = read_source(args.change)
            from scir.changes import _object, _constant
            placements = (json.loads(read_source(args.placements), object_pairs_hook=_object,
                                     parse_constant=_constant) if args.placements else None)
            result = propose_handoff(index, request, args.basis, ROOT, placements=placements)
        result.setdefault("input_basis", basis.packet())
        result["repository_contract"] = "scir-repository/1"
        if args.command in ("select", "propose") and args.view != "full":
            if __package__:
                from .delivery import present
            else:
                from delivery import present
            delivered = present(index, result, kind="selection" if args.command == "select" else "proposal",
                                encoding=args.encoding or "native")
            output = delivered.packet if args.view == "compact" else delivered.checked_artifact(args.expected_artifact)
            result = json.loads(output)  # Preserve the exact sorted JSON order and final LF in _emit.
        if handoff.capture(ROOT, index, SOURCES) != basis:
            from scir.changes import ConflictError
            raise ConflictError("repository inputs changed during command")
        _emit(sys.stdout, result)
        return 0
    except (ValueError, OSError, RecursionError) as error:
        code, diagnostic = failure(error)
        _emit(sys.stderr, {"status": diagnostic["error"], "error": diagnostic["message"],
                           "complete": diagnostic["complete"]})
        return code


if __name__ == "__main__":
    raise SystemExit(main())
