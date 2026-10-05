"""Explicit working-record projection to the legacy requirement/view dialect."""
from __future__ import annotations

from scir import Term
from scir.knowledge import Index
from scir.profile import read_text, read_tuple

if __package__:
    from .views import QUERY_FIELDS, query_records
else:
    from views import QUERY_FIELDS, query_records


def legacy_document(index: Index):
    """Explicit compatibility export. Not used by normal repository validation."""
    views = query_records(index)
    roots = []
    for record in index.records.values():
        fields = dict(record.fields)
        if fields.get("projection") != Term("native"):
            continue
        roots.append(Term("requirement", (Term(record.id), fields["area"], record.payload)))
        roots.append(Term("specifiedBy", (Term(record.id), fields["source"])))
        roots.extend(Term("coveredBy", (Term(record.id), target)) for target in read_tuple(fields["tests"]))
    for record in views:
        fields = dict(record.fields)
        roots.extend((Term("topic", (Term(record.id), Term("Queries"))),
                      Term("wording", (Term(record.id), Term(read_text(fields["wording"]))))))
    for record in views:
        fields = dict(record.fields)
        if "apiNote" in fields:
            roots.append(Term("note", (Term(record.id), Term(read_text(fields["apiNote"])))))
    for record in views:
        fields = dict(record.fields)
        if "queryExamples" in fields:
            for example in read_tuple(fields["queryExamples"]):
                roots.append(Term("queryExample", (example.args[0], Term(record.id), *example.args[1:])))
    return tuple(roots)
