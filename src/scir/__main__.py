"""Read-only CLI; outputs transformed data to stdout, never executes symbols."""
import argparse
import json
import sys

from . import FORMAT_VERSION, __version__, digest, format_document, parse_document, parse_pattern, query
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


def _write(stream, text: str) -> None:
    # Canonical bytes must not inherit the terminal's encoding or CRLF mapping.
    if hasattr(stream, "buffer"):
        stream.flush()
        stream.buffer.write(text.encode("utf-8"))
    else:
        stream.write(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="scir",
        description="Deterministic SCIR tools. Symbol names are never executed.",
    )
    parser.add_argument("--version", action="version", version=f"scir {__version__} (format {FORMAT_VERSION})")
    sub = parser.add_subparsers(dest="command", required=True)
    helps = {
        "check": "parse a document and print valid/root count JSON",
        "fmt": "print canonical content or check its formatting",
        "digest": "print a document fingerprint",
        "encode": "emit relational JSON",
        "decode": "read relational JSON and print SCIR",
        "query": "match a pattern against roots (default) or all occurrences",
    }
    for command, help_text in helps.items():
        p = sub.add_parser(command, help=help_text)
        p.add_argument("file", nargs="?", default="-", help="path, or - for stdin")
        if command == "fmt":
            p.add_argument("--check", action="store_true", help="exit 1 when input is not canonical; write nothing")
        if command == "query":
            p.add_argument("--pattern", required=True)
            p.add_argument("--scope", choices=("roots", "all"), default="roots")
            p.add_argument("--contains", help="filter matches by exact symbol occurrence")
    args = parser.parse_args(argv)
    try:
        if args.file == "-":
            text = _read(sys.stdin)
        else:
            with open(args.file, encoding="utf-8", newline="") as stream:
                text = _read(stream)
        document = decode(json.loads(text, object_pairs_hook=_object)) if args.command == "decode" else parse_document(text)
        if args.command == "check":
            _write(sys.stdout, json.dumps({"valid": True, "roots": len(document)}) + "\n")
        elif args.command in ("fmt", "decode"):
            canonical = format_document(document)
            if args.command == "fmt" and args.check:
                return int(text != canonical)
            _write(sys.stdout, canonical)
        elif args.command == "digest":
            _write(sys.stdout, digest(document) + "\n")
        elif args.command == "encode":
            _write(sys.stdout, json.dumps(encode(document), ensure_ascii=False, indent=2) + "\n")
        elif args.command == "query":
            hits = query(document, parse_pattern(args.pattern), scope=args.scope)
            if args.contains is not None:
                hits = [h for h in hits if any(t.symbol == args.contains for _, t in walk((h.term,)))]
            _write(sys.stdout, json.dumps([
                {"path": h.path, "term": str(h.term), "bindings": {k: str(v) for k, v in h.bindings.items()}}
                for h in hits
            ], ensure_ascii=False, indent=2) + "\n")
        return 0
    except (ValueError, OSError, RecursionError) as e:
        _write(sys.stderr, f"scir: {e}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
