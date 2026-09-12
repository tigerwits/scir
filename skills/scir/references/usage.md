# Operations

Requires SCIR format 1.0. Commands run in the consuming project's environment;
this reference does not depend on the SCIR repository being next to the skill.

## Parse, query, edit

```python
from scir import parse, parse_document, parse_pattern, query, replace_at, format_document

content = parse_document("think(Bob, use(Alice, SalesData))")
pattern = parse_pattern("use(Alice, ?data)")
assert query(content, pattern) == []
hit = query(content, pattern, scope="all")[0]
assert hit.path == (0, 1)
assert str(hit.bindings["data"]) == "SalesData"

# An explicit caller decision, not a correction inferred by the library.
changed = replace_at(content, hit.path, parse("use(Alice, Report)"))
assert format_document(changed) == "think(Bob, use(Alice, Report))\n"
assert str(content[0]) == "think(Bob, use(Alice, SalesData))"
```

`parse` accepts one Term; `parse_document` returns an ordered tuple of Terms.
Duplicates remain distinct occurrences. Paths belong to a document snapshot,
not to real-world entities. Do not detach nested results from their context.

## Preserve ambiguity and provenance

```python
from scir import parse_document
from scir.annotations import Alternatives, Bundle, annotate

source = "Alice spoke to Carol after she left."
choices = Alternatives((
    parse_document("after(speak(Alice, Carol), leave(Alice))"),
    parse_document("after(speak(Alice, Carol), leave(Carol))"),
))
bundles = tuple(Bundle(candidate, (annotate(candidate, (0,), "source", source),))
                for candidate in choices.options)
assert len(bundles) == 2
```

These are candidate readings, not jointly presented claims. `choose(index)` selects
one; it does not establish that reading's correctness. Preserve the candidates
until context or the user resolves them. Correlated choices must stay together.

After an edit, review and attach new annotations explicitly. Old annotations
cannot be reused against changed content; erasure loses provenance.

## CLI

```bash
python -m scir check draft.scir
python -m scir fmt --check draft.scir
python -m scir query draft.scir --pattern 'use(Alice, ?data)' --scope all
```

`check` parses; it does not check a dialect. `fmt --check` returns 0 for canonical
input, 1 for formatting differences, and 2 for errors. `fmt` writes to stdout,
not back to the file. Preserve source and review changes before saving output.
