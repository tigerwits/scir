"""Read-only CLI; outputs transformed data to stdout, never executes symbols."""
import argparse
import json
from pathlib import Path
import sys

from . import digest, format_document, parse_document, parse_pattern, query
from .relations import decode, encode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="scir")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "fmt", "digest", "encode", "decode", "query"):
        p = sub.add_parser(command)
        p.add_argument("file", nargs="?", default="-")
        if command == "query":
            p.add_argument("--pattern", required=True)
            p.add_argument("--scope", choices=("roots", "all"), default="roots")
            p.add_argument("--contains", help="filter matches by exact symbol occurrence")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        document = decode(json.loads(text)) if args.command == "decode" else parse_document(text)
        if args.command == "check":
            print(json.dumps({"valid": True, "roots": len(document)}))
        elif args.command in ("fmt", "decode"):
            print(format_document(document), end="")
        elif args.command == "digest":
            print(digest(document))
        elif args.command == "encode":
            print(json.dumps(encode(document), ensure_ascii=False, indent=2))
        elif args.command == "query":
            from .tree import walk
            hits = query(document, parse_pattern(args.pattern), scope=args.scope)
            if args.contains is not None:
                hits = [h for h in hits if any(t.symbol == args.contains for _, t in walk((h.term,)))]
            print(json.dumps([
                {"path": h.path, "term": str(h.term), "bindings": {k: str(v) for k, v in h.bindings.items()}}
                for h in hits
            ], ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RecursionError) as e:
        print(f"scir: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
