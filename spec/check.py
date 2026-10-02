"""Repository CLI and compatibility exports; reusable logic lives in catalog."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from scir import format_document, parse_document

if __package__:
    from .catalog import (AREAS, PATTERNS, VIEWS, local_file, source_declarations,
                          targets, example_parts, content_rules, validate_catalog,
                          render_queries, replace_view, view_updates, render)
elif __name__ == "__main__":
    from catalog import (AREAS, PATTERNS, VIEWS, local_file, source_declarations,
                         targets, example_parts, content_rules, validate_catalog,
                         render_queries, replace_view, view_updates, render)
else:
    from spec.catalog import (AREAS, PATTERNS, VIEWS, local_file, source_declarations,
                              targets, example_parts, content_rules, validate_catalog,
                              render_queries, replace_view, view_updates, render)

ROOT = Path(__file__).resolve().parents[1]


def _repository():
    if __package__:
        from . import repository
    elif __name__ == "__main__":
        import repository
    else:
        from spec import repository
    return repository


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["knowledge"]:
        return _repository().main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path, default=ROOT / "spec/requirements.scir")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--markdown", action="store_true", help="print the requirement index")
    mode.add_argument("--write-views", action="store_true", help="refresh the two generated query sections")
    args = parser.parse_args(argv)
    # The real repository uses authoritative working records. Retain the legacy
    # validator API for explicitly supplied catalogs and test fixture roots.
    if (ROOT.resolve() == Path(__file__).resolve().parents[1]
            and args.file.resolve() == Path(__file__).resolve().with_name("requirements.scir")):
        return _repository().maintenance(ROOT, write_views=args.write_views, markdown=args.markdown)
    try:
        text = args.file.read_bytes().decode("utf-8")
        document = parse_document(text)
        issues = validate_catalog(document, ROOT)
        for issue in issues:
            print(f"{issue.path}: {issue.rule}: {issue.message}", file=sys.stderr)
        if issues:
            return 1
        if text != format_document(document):
            print("catalog: noncanonical source; use scir fmt", file=sys.stderr)
            return 1
        if args.write_views and args.file.resolve() != (ROOT / "spec/requirements.scir").resolve():
            raise ValueError("only the maintained catalog can refresh project views")
        updates = view_updates(document, ROOT) if args.file.resolve() == (ROOT / "spec/requirements.scir").resolve() else []
        if updates and not args.write_views:
            for path, _ in updates:
                print(f"stale view: {path.relative_to(ROOT.resolve()).as_posix()}; run python spec/check.py --write-views", file=sys.stderr)
            return 1
        if args.write_views:
            for path, data in updates:
                path.write_bytes(data)
            print(f"Refreshed {len(updates)} query views; other sections were not changed.")
        elif args.markdown:
            print(render(document), end="")
        else:
            count = sum(t.symbol == "requirement" for t in document)
            links = sum(t.symbol in ("specifiedBy", "coveredBy") for t in document)
            examples = sum(t.symbol == "queryExample" for t in document)
            print(f"Checked {count} requirements, {links} links, and {examples} query examples; tests were not run.")
        return 0
    except (ValueError, OSError, RecursionError) as error:
        print(f"catalog: check incomplete: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
