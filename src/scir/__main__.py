"""Read-only CLI; outputs transformed data to stdout, never executes symbols."""
import argparse
import json
import sys

from . import digest, format_document, parse_document, parse_pattern, query
from .relations import decode, encode
from .tree import walk

MAX_INPUT_CHARS = 16_000_000


def _read(stream) -> str:
    text = stream.read(MAX_INPUT_CHARS + 1)
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(f"input exceeds {MAX_INPUT_CHARS:,} characters")
    return text


def _object(pairs) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON object key")
    return result


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
        if args.file == "-":
            text = _read(sys.stdin)
        else:
            with open(args.file, encoding="utf-8") as stream:
                text = _read(stream)
        document = decode(json.loads(text, object_pairs_hook=_object)) if args.command == "decode" else parse_document(text)
        if args.command == "check":
            print(json.dumps({"valid": True, "roots": len(document)}))
        elif args.command in ("fmt", "decode"):
            print(format_document(document), end="")
        elif args.command == "digest":
            print(digest(document))
        elif args.command == "encode":
            print(json.dumps(encode(document), ensure_ascii=False, indent=2))
        elif args.command == "query":
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
