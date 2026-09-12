"""Check maintained SCIR content, run query examples, and refresh Markdown views."""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from functools import cache
from html import escape
from pathlib import Path, PurePosixPath
import re
import sys

from scir import Document, format_document, match, parse_document, parse_pattern, query
from scir.constraints import Violation, check, forms

ROOT = Path(__file__).resolve().parents[1]
AREAS = frozenset(("Core", "Syntax", "Patterns", "Tree", "Annotations", "Transport", "Constraints", "CLI"))
PATTERNS = tuple(map(parse_pattern, (
    "requirement(?id, ?area, ?obligation)",
    "specifiedBy(?id, section(?file, ?heading))",
    "coveredBy(?id, test(?file, ?method))",
    "topic(?id, ?topic)",
    "wording(?id, ?text)",
    "note(?id, ?text)",
    "queryExample(?example, ?id, ?input, ?pattern, ?scope, ?paths)",
)))


def local_file(root: Path, name: str, suffix: str) -> Path:
    parts = name.split("/")
    if ("\\" in name or ":" in name or any(p in ("", ".", "..") for p in parts)
            or PurePosixPath(name).is_absolute() or not name.endswith(suffix)):
        raise ValueError(f"expected a repository-relative {suffix} file: {name!r}")
    path = root.resolve()
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"symlink is not a source reference: {name!r}")
    if not path.is_file():
        raise ValueError(f"missing source file: {name!r}")
    return path


def targets(document: Document, root: Path):
    """Resolve declaration IDs and static source locations in one fixed checkout."""
    declarations, links = defaultdict(list), []
    for i, term in enumerate(document):
        if term.symbol not in ("requirement", "specifiedBy", "coveredBy"):
            continue
        if not any(match(p, term) is not None for p in PATTERNS):
            continue  # The form rule owns malformed records.
        ident = term.args[0]
        if ident.args:
            yield Violation((i, 0), "identifier", "requirement IDs must be leaves")
            continue
        if term.symbol == "requirement":
            declarations[ident.symbol].append(i)
            if term.args[1].args or term.args[1].symbol not in AREAS:
                yield Violation((i, 1), "area", "unknown area; use a declared area leaf")
        else:
            links.append((i, term))
    if not declarations:
        yield Violation(None, "nonempty", "at least one requirement is required")
    for ident, indices in declarations.items():
        for i in indices[1:]:
            yield Violation((i, 0), "duplicate-id", f"requirement {ident!r} is declared more than once")

    @cache
    def locations(name: str, kind: str):
        suffix = ".md" if kind == "specifiedBy" else ".py"
        path = local_file(root, name, suffix)
        if kind == "coveredBy" and (not name.startswith("tests/") or not path.name.startswith("test_")):
            raise ValueError("test references must name tests/test_*.py files")
        text = path.read_text(encoding="utf-8")
        if kind == "specifiedBy":
            # A code block containing '# Heading' is not a Markdown section.
            text = re.sub(r"^```[^\n]*\n.*?^```[ \t]*$", "", text, flags=re.M | re.S)
            return re.findall(r"^#{1,6} (.+?)\s*$", text, flags=re.M)
        try:
            module = ast.parse(text, filename=name)
        except SyntaxError as error:
            raise ValueError(f"test file does not parse: {name!r}") from error
        return [f"{cls.name}.{method.name}"
                for cls in module.body if isinstance(cls, ast.ClassDef)
                if any(isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                       and base.value.id == "unittest" and base.attr == "TestCase" for base in cls.bases)
                for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")]

    seen, valid = set(), defaultdict(set)
    for i, term in links:
        ident, target = term.args
        indices = declarations.get(ident.symbol, [])
        if len(indices) != 1:
            reason = "unknown" if not indices else "ambiguous"
            yield Violation((i, 0), "reference", f"{reason} requirement: {ident.symbol!r}")
        if any(arg.args for arg in target.args):
            yield Violation((i, 1), "location", "file and location must be leaves")
            continue
        key = (term.symbol, ident.symbol, *(arg.symbol for arg in target.args))
        if key in seen:
            yield Violation((i,), "duplicate-link", "duplicate source or test link")
        seen.add(key)
        name, location = (arg.symbol for arg in target.args)
        try:
            count = locations(name, term.symbol).count(location)
            if count != 1:
                raise ValueError(f"expected one {location!r} in {name!r}; found {count}")
        except ValueError as error:
            yield Violation((i, 1), "location", str(error))
        else:
            if len(indices) == 1:
                valid[ident.symbol].add(term.symbol)
    for ident, indices in declarations.items():
        for kind, rule in (("specifiedBy", "source"), ("coveredBy", "coverage")):
            if kind not in valid[ident]:
                yield Violation((indices[0],), rule, f"{ident!r} needs a valid {kind} link")


def example_parts(term):
    """A query example is data; only the library's query operation is invoked."""
    ident, owner, source, pattern, scope, expected = term.args
    if (ident.args or owner.args or pattern.args or scope.args
            or source.symbol != "input" or expected.symbol != "paths"
            or scope.symbol not in ("default", "roots", "all")):
        raise ValueError("expected leaf IDs/pattern/scope, input(...), and paths(...)")
    paths = []
    for path in expected.args:
        if path.symbol != "path" or not path.args or any(
                x.args or not re.fullmatch(r"0|[1-9][0-9]*", x.symbol) for x in path.args):
            raise ValueError("expected path with canonical nonnegative integer labels")
        paths.append(tuple(int(x.symbol) for x in path.args))
    return source.args, parse_pattern(pattern.symbol), scope.symbol, paths


def content_rules(document: Document):
    declarations = Counter(t.args[0].symbol for t in document
                           if t.symbol == "requirement" and len(t.args) == 3 and not t.args[0].args)
    fields, examples = defaultdict(list), []
    names = set()
    for i, term in enumerate(document):
        if term.symbol not in ("topic", "wording", "note", "queryExample"):
            continue
        if not any(match(p, term) is not None for p in PATTERNS):
            continue
        owner = term.args[1] if term.symbol == "queryExample" else term.args[0]
        if owner.args or declarations[owner.symbol] != 1:
            yield Violation((i,), "content-reference", "content needs one declared requirement")
            continue
        if term.symbol == "queryExample":
            examples.append((i, term))
            if term.args[0].args or term.args[0].symbol in names:
                yield Violation((i, 0), "example-id", "example IDs must be unique leaves")
            names.add(term.args[0].symbol)
            continue
        value = term.args[1]
        fields[owner.symbol, term.symbol].append((i, value))
        if value.args or (term.symbol == "topic" and value.symbol != "Queries"):
            yield Violation((i, 1), "content-field", "expected a text leaf or the topic Queries")
        elif term.symbol != "topic" and "<!-- scir:" in value.symbol:
            yield Violation((i, 1), "content-field", "view markers are not maintained wording")
    for (owner, kind), entries in fields.items():
        if len(entries) != 1:
            yield Violation((entries[1][0],), "duplicate-content", f"duplicate {kind} for {owner}")
        needed = "wording" if kind == "topic" else "topic"
        if (owner, needed) not in fields:
            yield Violation((entries[0][0],), "missing-content", f"{owner} needs {needed}")
    for i, term in examples:
        if (term.args[1].symbol, "topic") not in fields:
            yield Violation((i, 1), "content-reference", "example owner needs a topic")
        try:
            source, pattern, scope, expected = example_parts(term)
            kwargs = {} if scope == "default" else {"scope": scope}
            actual = [hit.path for hit in query(source, pattern, **kwargs)]
        except ValueError as error:
            yield Violation((i,), "query-example", str(error))
        else:
            if actual != expected:
                yield Violation((i, 5), "query-example", f"expected paths {expected!r}; got {actual!r}")


def validate_catalog(document: Document, root: Path = ROOT) -> tuple[Violation, ...]:
    return check(document, (forms(*PATTERNS), lambda d: targets(d, root), content_rules))


# These two project views are fixed renderers, not a document-template language.
VIEWS = (("SPEC.md", "query-spec"), ("docs/api.md", "query-api"))


def render_queries(document: Document, *, examples: bool) -> str:
    owners = [t.args[0].symbol for t in document if t.symbol == "topic"]
    if not owners:
        raise ValueError("the query views require maintained query content")
    fields = {(t.args[0].symbol, t.symbol): t.args[1].symbol for t in document
              if t.symbol in ("wording", "note")}
    lines = ["<!-- Maintained in spec/requirements.scir; refresh with python spec/check.py --write-views. -->", ""]
    for owner in owners:
        lines.extend((fields[owner, "wording"], ""))
        if examples and (owner, "note") in fields:
            lines.extend((fields[owner, "note"], ""))
    if examples:
        for term in document:
            if term.symbol != "queryExample":
                continue
            source, _, scope, paths = example_parts(term)
            pattern = term.args[3].symbol
            argument = "" if scope == "default" else f", scope={scope!r}"
            lines.extend((
                "<code>" + escape(str(term.args[0])) + "</code>", "", "```python",
                "from scir import parse_document, parse_pattern, query", "",
                f"content = parse_document({format_document(source)!r})",
                f"pattern = parse_pattern({pattern!r})",
                f"hits = query(content, pattern{argument})",
                f"assert [hit.path for hit in hits] == {paths!r}", "```", "",
            ))
    return "\n".join(lines).rstrip() + "\n"


def replace_view(text: str, key: str, body: str) -> str:
    start, end = (f"<!-- scir:{key}:{part} -->" for part in ("start", "end"))
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"expected exactly one marker pair for {key}")
    a, b = text.index(start), text.index(end)
    if (a >= b or (a and text[a - 1] != "\n") or text[a + len(start):a + len(start) + 1] != "\n"
            or text[b - 1] != "\n" or text[b + len(end):b + len(end) + 1] not in ("", "\n")):
        raise ValueError(f"invalid marker boundaries for {key}")
    return text[:a + len(start)] + "\n" + body + text[b:]


def view_updates(document: Document, root: Path = ROOT) -> list[tuple[Path, bytes]]:
    """Preflight every destination before an explicit write; preserve other bytes."""
    updates = []
    for name, key in VIEWS:
        path = local_file(root, name, ".md")
        source = path.read_bytes()
        rendered = render_queries(document, examples=key == "query-api")
        expected = replace_view(source.decode("utf-8"), key, rendered).encode("utf-8")
        if source != expected:
            updates.append((path, expected))
    return updates


def render(document: Document) -> str:
    """Render a checked catalog as an index, never a paraphrased specification."""
    links = defaultdict(list)
    for term in document:
        if term.symbol in ("specifiedBy", "coveredBy"):
            links[term.args[0].symbol, term.symbol].append(str(term.args[1]))

    def code(value):
        return "<code>" + escape(str(value)).replace("|", "&#124;") + "</code>"

    lines = ["<!-- Generated by python spec/check.py --markdown; do not edit. -->",
             "# Project requirement index", "",
             "Declared links, not proof of coverage or test execution. Query wording is maintained here; other definitions remain in linked sections.", "",
             "| ID | Area | Obligation shorthand | Defined in | Declared tests |",
             "| --- | --- | --- | --- | --- |"]
    for term in document:
        if term.symbol == "requirement":
            ident, area, obligation = term.args
            cells = [code(ident), code(area), code(obligation)]
            cells += ["<br>".join(map(code, links[ident.symbol, kind])) for kind in ("specifiedBy", "coveredBy")]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path, default=ROOT / "spec/requirements.scir")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--markdown", action="store_true", help="print the requirement index")
    mode.add_argument("--write-views", action="store_true", help="refresh the two generated query sections")
    args = parser.parse_args(argv)
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
