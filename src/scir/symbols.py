"""Structural label operations; profiles and real-world identities stay explicit."""
from __future__ import annotations

from collections.abc import Mapping

from .core import Document, Path, Symbol, Term, _symbol_value, validate
from .tree import walk


def symbol_occurrences(document: Document) -> tuple[tuple[Path, Symbol], ...]:
    """Return every label in preorder, retaining its snapshot-local occurrence."""
    return tuple((path, term.head) for path, term in walk(document))


def relabel_symbols(document: Document,
                    renaming: Mapping[str | Symbol, str | Symbol]) -> Document:
    """Relabel simultaneously, with identity outside the supplied finite map.

    This visits all native labels, including profile tags and literal payloads.
    It does not preserve arbitrary dialects, resolve references, or move metadata.
    Like native tree operations, it assumes ordinary immutable ground values;
    parser/resource admission belongs at the caller's input boundary.
    """
    validate(document)
    if not isinstance(renaming, Mapping):
        raise ValueError("renaming must map symbols to symbols")
    names = {}
    for source, target in renaming.items():
        key, value = _symbol_value(source), _symbol_value(target)
        if key in names:
            raise ValueError("duplicate symbol after decoding renaming keys")
        names[key] = value
    pending = [(term, False) for term in reversed(document)]
    built = []
    while pending:
        term, ready = pending.pop()
        if not ready:
            pending.append((term, True))
            pending.extend((child, False) for child in reversed(term.args))
            continue
        count = len(term.args)
        children = tuple(built[-count:]) if count else ()
        if count:
            del built[-count:]
        built.append(Term(names.get(term.symbol, term.symbol), children))
    return tuple(built)
