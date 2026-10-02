"""Explicit optional commands. No source files are overwritten."""
from __future__ import annotations

import argparse
import json
import sys


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a positive integer") from error
    if value < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return value


def register(subparsers) -> None:
    lower = subparsers.add_parser("lower", help="lower explicit notation/1 to native SCIR")
    lower.add_argument("file", nargs="?", default="-")
    lower.add_argument("--operators", choices=("arithmetic/1",))
    knowledge = subparsers.add_parser("knowledge", help="validate, select or propose working/1 content")
    commands = knowledge.add_subparsers(dest="operation", required=True)
    for name in ("check", "select", "affected", "propose", "diagnose"):
        command = commands.add_parser(name)
        command.add_argument("file", nargs="?", default="-")
        command.add_argument("--collection", required=True, help="host-supplied local collection identity")
        command.add_argument("--max-records", type=_positive, default=10_000)
        command.add_argument("--max-output-bytes", type=_positive, default=16_000_000)
        if name in ("select", "diagnose"):
            command.add_argument("--id", action="append", required=True)
            if name == "diagnose":
                command.add_argument("--encoding", choices=("native", "notation"), default="native")
        elif name == "affected":
            command.add_argument("--changed", action="append", required=True)
        elif name == "propose":
            command.add_argument("--change", required=True, help="JSON request file, or - for stdin")


def _read_file(path: str, maximum: int) -> str:
    from .profile import LimitError
    def read(stream):
        result = stream.read(maximum + 1)
        if len(result) > maximum or len(result.encode("utf-8")) > maximum:
            raise LimitError("input byte budget exceeded")
        return result
    if path == "-":
        return read(sys.stdin)
    with open(path, encoding="utf-8", newline="") as stream:
        return read(stream)


def execute(args, write) -> int:
    from .core import format_document
    from ._profile_native import native, failure
    from . import profile as p
    from .knowledge import VERSION, build_index, select, affected
    from .changes import propose
    try:
        if args.command == "lower":
            from .notation import lower
            output = format_document(lower(_read_file(args.file, 64_000), operators=args.operators))
        else:
            if args.operation == "propose" and args.file == args.change == "-":
                raise p.ProfileError("document and change request cannot both consume stdin")
            source = _read_file(args.file, 16_000_000)
            document = native(source)
            index = build_index(document, collection=args.collection, max_records=args.max_records)
            if args.operation == "check":
                result = {"profile": VERSION, "collection": index.collection,
                          "snapshot": index.snapshot, "records": len(index.records),
                          "valid": True, "complete": True}
            elif args.operation == "select":
                result = select(index, tuple(args.id), max_records=args.max_records,
                                limits=p.Limits(bytes=args.max_output_bytes)).as_dict()
            elif args.operation == "diagnose":
                from .diagnostics import diagnose
                result = diagnose(index, tuple(args.id), encoding=args.encoding,
                                  max_records=args.max_records, max_output_bytes=args.max_output_bytes)
            elif args.operation == "affected":
                result = {"profile": VERSION, "collection": index.collection,
                          "source_snapshot": index.snapshot, "complete": True,
                          "review_ids": list(affected(index, tuple(args.changed),
                              max_records=args.max_records, max_bytes=args.max_output_bytes))}
            else:
                change = _read_file(args.change, 1_000_000)
                result = propose(index, change, max_records=args.max_records,
                                 max_result_bytes=args.max_output_bytes).as_dict()
            output = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
            if len(output.encode("utf-8")) > args.max_output_bytes:
                raise p.LimitError("complete response exceeds the output budget")
        write(sys.stdout, output)
        return 0
    except (ValueError, OSError, RecursionError) as error:
        code, diagnostic = failure(error)
        write(sys.stderr, json.dumps(diagnostic, ensure_ascii=True, separators=(",", ":")) + "\n")
        return code
