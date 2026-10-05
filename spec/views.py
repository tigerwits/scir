"""Direct views of authoritative working records; no intermediate catalog dialect."""
from __future__ import annotations

from html import escape
import re

from scir import Term, format_document, parse_pattern, query
from scir.profile import ProfileError, read_fields, read_text, read_tuple

if __package__:
    from .locations import local_file
else:
    from locations import local_file

QUERY_FIELDS = frozenset(("topic", "viewOrder", "wording", "apiNote", "queryExamples"))
VIEWS = (("SPEC.md", "query-spec"), ("docs/api.md", "query-api"))


def example_parts(example):
    if example.symbol != "example" or len(example.args) != 5:
        raise ProfileError("expected example(name, input, pattern, scope, paths)")
    name, source, pattern, scope, expected = example.args
    if (name.args or pattern.args or scope.args or source.symbol != "input"
            or expected.symbol != "paths" or scope.symbol not in ("default", "roots", "all")):
        raise ProfileError("expected leaf name/pattern/scope, input(...), and paths(...)")
    paths = []
    for path in expected.args:
        if path.symbol != "path" or not path.args or any(
                x.args or not re.fullmatch(r"0|[1-9][0-9]*", x.symbol) for x in path.args):
            raise ProfileError("expected a nonempty path of canonical nonnegative integers")
        paths.append(tuple(int(x.symbol) for x in path.args))
    try:
        parsed = parse_pattern(pattern.symbol)
    except ValueError as error:
        raise ProfileError(str(error)) from error
    return source.args, parsed, scope.symbol, paths


def query_records(index):
    """Validate view ownership and order without scanning linked source files."""
    ordered, names = {}, set()
    for record in index.records.values():
        fields = dict(record.fields)
        projected = fields.get("projection")
        if projected is not None and (projected != Term("native") or record.kind != "Requirement"):
            raise ProfileError("only requirements use projection: native")
        has_query = bool(QUERY_FIELDS & fields.keys())
        if not has_query:
            if record.kind == "Requirement" and fields.get("ownership") == Term("record"):
                raise ProfileError("a record owner needs query content")
            continue
        if (projected is None or not {"topic", "viewOrder", "wording"} <= fields.keys()
                or fields["topic"] != Term("Queries") or fields.get("ownership") != Term("record")):
            raise ProfileError("query wording needs one native record owner, topic and viewOrder")
        value = fields["viewOrder"]
        if value.args or not re.fullmatch(r"0|[1-9][0-9]{0,5}", value.symbol):
            raise ProfileError("viewOrder must be a small canonical nonnegative integer")
        order = int(value.symbol)
        if order in ordered:
            raise ProfileError("duplicate query view order")
        for key in ("wording", "apiNote"):
            if key in fields:
                text = read_text(fields[key])
                if not text or "<!-- scir:" in text:
                    raise ProfileError("view wording must be nonempty text without view markers")
        examples = fields.get("queryExamples")
        if examples is not None:
            if read_fields(examples):
                raise ProfileError("query examples must be a positional tuple")
            for example in read_tuple(examples):
                example_parts(example)
                name = example.args[0].symbol
                if name in names:
                    raise ProfileError("query example names must be unique")
                names.add(name)
        ordered[order] = record
    if set(ordered) != set(range(len(ordered))):
        raise ProfileError("query view order must be contiguous from zero")
    return tuple(ordered[i] for i in range(len(ordered)))


def validate(index):
    for record in query_records(index):
        examples = dict(record.fields).get("queryExamples")
        for example in read_tuple(examples) if examples is not None else ():
            source, pattern, scope, expected = example_parts(example)
            actual = [hit.path for hit in query(source, pattern, **({} if scope == "default" else {"scope": scope}))]
            if actual != expected:
                raise ProfileError(f"query example {example.args[0]}: expected {expected!r}; got {actual!r}")


def render_queries(index, *, examples):
    records = query_records(index)
    if not records:
        raise ProfileError("the query views require maintained query content")
    lines = ["<!-- Maintained in spec/native.scir; refresh with python spec/check.py --write-views. -->", ""]
    for record in records:
        fields = dict(record.fields)
        lines.extend((read_text(fields["wording"]), ""))
        if examples and "apiNote" in fields:
            lines.extend((read_text(fields["apiNote"]), ""))
    if examples:
        for record in records:
            items = dict(record.fields).get("queryExamples")
            for example in read_tuple(items) if items is not None else ():
                source, _, scope, paths = example_parts(example)
                argument = "" if scope == "default" else f", scope={scope!r}"
                lines.extend(("<code>" + escape(str(example.args[0])) + "</code>", "", "```python",
                              "from scir import parse_document, parse_pattern, query", "",
                              f"content = parse_document({format_document(source)!r})",
                              f"pattern = parse_pattern({example.args[2].symbol!r})",
                              f"hits = query(content, pattern{argument})",
                              f"assert [hit.path for hit in hits] == {paths!r}", "```", ""))
    return "\n".join(lines).rstrip() + "\n"


def replace_view(text, key, body):
    start, end = (f"<!-- scir:{key}:{part} -->" for part in ("start", "end"))
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"expected exactly one marker pair for {key}")
    a, b = text.index(start), text.index(end)
    if (a >= b or (a and text[a - 1] != "\n") or text[a + len(start):a + len(start) + 1] != "\n"
            or text[b - 1] != "\n" or text[b + len(end):b + len(end) + 1] not in ("", "\n")):
        raise ValueError(f"invalid marker boundaries for {key}")
    return text[:a + len(start)] + "\n" + body + text[b:]


def updates(index, root):
    changes = []
    for name, key in VIEWS:
        path = local_file(root, name, ".md")
        source = path.read_bytes()
        rendered = render_queries(index, examples=key == "query-api")
        expected = replace_view(source.decode("utf-8"), key, rendered).encode("utf-8")
        if source != expected:
            changes.append((path, expected))
    return changes


def render(index):
    def code(value):
        return "<code>" + escape(str(value)).replace("|", "&#124;") + "</code>"
    requirements = [r for r in index.records.values() if r.kind == "Requirement"]
    lines = ["<!-- Generated by python spec/check.py --markdown; do not edit. -->",
             "# Project requirement index", "",
             f"All {len(requirements)} requirements in {len(index.records)} maintained records.", "",
             "Declared links, not proof of coverage or test execution.", "",
             "| ID | Area | Obligation shorthand | Defined in | Declared tests |",
             "| --- | --- | --- | --- | --- |"]
    for record in requirements:
        fields = dict(record.fields)
        cells = [code(Term(record.id)), code(fields["area"]), code(record.payload), code(fields["source"]),
                 "<br>".join(map(code, read_tuple(fields["tests"])))]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
