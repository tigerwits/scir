"""Explicit working-record projection to the legacy requirement/view dialect."""
from __future__ import annotations

from scir import Term
from scir.knowledge import Index
from scir.profile import ProfileError, read_fields, read_text, read_tuple

QUERY_FIELDS = frozenset(("topic", "viewOrder", "wording", "apiNote", "queryExamples"))


def legacy_document(index: Index):
    """Preserve declared record/test order; query presentation has explicit order."""
    roots, views = [], {}
    for record in index.records.values():
        fields = dict(record.fields)
        if "projection" not in fields:
            if QUERY_FIELDS & fields.keys() or fields.get("ownership") == Term("record"):
                raise ProfileError("query-owned fields need a native projection")
            continue
        if fields["projection"] != Term("native") or record.kind != "Requirement":
            raise ProfileError("only requirements use projection: native")
        roots.append(Term("requirement", (Term(record.id), fields["area"], record.payload)))
        roots.append(Term("specifiedBy", (Term(record.id), fields["source"])))
        roots.extend(Term("coveredBy", (Term(record.id), target)) for target in read_tuple(fields["tests"]))
        query_fields = QUERY_FIELDS & fields.keys()
        if not query_fields:
            if fields["ownership"] != Term("index"):
                raise ProfileError("a non-query requirement indexes its source")
            continue
        if not {"topic", "viewOrder", "wording"} <= fields.keys():
            raise ProfileError("query record needs topic, viewOrder and wording")
        if fields["topic"] != Term("Queries") or fields["ownership"] != Term("record"):
            raise ProfileError("query wording has one record owner")
        value = fields["viewOrder"]
        if value.args or not value.symbol.isascii() or not value.symbol.isdecimal() or len(value.symbol) > 6:
            raise ProfileError("viewOrder must be a small canonical nonnegative integer label")
        order = int(value.symbol)
        if str(order) != value.symbol or order in views:
            raise ProfileError("duplicate/noncanonical query view order")
        wording = read_text(fields["wording"])
        if not wording:
            raise ProfileError("query wording must be nonempty")
        if "apiNote" in fields and not read_text(fields["apiNote"]):
            raise ProfileError("API notes must be nonempty text")
        examples = fields.get("queryExamples")
        if examples is not None:
            if read_fields(examples):
                raise ProfileError("query examples must be a positional tuple")
            for example in read_tuple(examples):
                if example.symbol != "example" or len(example.args) != 5:
                    raise ProfileError("expected example(name, input, pattern, scope, paths)")
        views[order] = record
    if set(views) != set(range(len(views))):
        raise ProfileError("query view order must be contiguous from zero")
    for order in range(len(views)):
        record = views[order]
        fields = dict(record.fields)
        roots.extend((Term("topic", (Term(record.id), Term("Queries"))),
                      Term("wording", (Term(record.id), Term(read_text(fields["wording"]))))))
    for order in range(len(views)):
        record = views[order]
        fields = dict(record.fields)
        if "apiNote" in fields:
            roots.append(Term("note", (Term(record.id), Term(read_text(fields["apiNote"])))))
    for order in range(len(views)):
        record = views[order]
        fields = dict(record.fields)
        if "queryExamples" in fields:
            for example in read_tuple(fields["queryExamples"]):
                roots.append(Term("queryExample", (example.args[0], Term(record.id), *example.args[1:])))
    return tuple(roots)
