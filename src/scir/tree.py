"""Occurrence paths, explicit roots, and caller-selected structural edits."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import zip_longest
from .core import Document, Path, Term, validate
from .patterns import Bindings, Node, Pattern, Var, match


def walk(document: Document) -> Iterator[tuple[Path, Term]]:
    validate(document)
    pending = [((i,), document[i]) for i in reversed(range(len(document)))]
    while pending:
        path, term = pending.pop()
        yield path, term
        pending.extend((path + (i,), term.args[i]) for i in reversed(range(len(term.args))))


def at(document: Document, path: Path) -> Term:
    validate(document)
    if type(path) is not tuple or not path or any(type(i) is not int or i < 0 for i in path):
        raise ValueError("a path is a nonempty tuple of nonnegative integers")
    children = document
    try:
        for index in path:
            term = children[index]
            children = term.args
        return term
    except IndexError as e:
        raise ValueError("path does not exist in this document") from e


@dataclass(frozen=True)
class Hit:
    path: Path
    term: Term
    bindings: Bindings


def query(document: Document, pattern: Pattern, *, scope: str = "roots") -> list[Hit]:
    """Roots by default. 'all' searches occurrences without asserting them."""
    validate(document)
    if type(pattern) not in (Node, Var):
        raise ValueError("expected a pattern")
    if scope not in ("roots", "all"):
        raise ValueError("scope must be 'roots' or 'all'")
    nodes = walk(document) if scope == "all" else (((i,), t) for i, t in enumerate(document))
    hits = []
    for path, term in nodes:
        bindings = match(pattern, term)
        if bindings is not None:
            hits.append(Hit(path, term, bindings))
    return hits


def replace_at(document: Document, path: Path, replacement: Term) -> Document:
    at(document, path)
    if type(replacement) is not Term:
        raise ValueError("replacement must be a ground Term")
    parents, children = [], document
    for depth, index in enumerate(path[:-1]):
        parent = children[index]
        parents.append((parent, path[depth + 1]))
        children = parent.args
    node = replacement
    for parent, index in reversed(parents):
        node = Term(parent.symbol, parent.args[:index] + (node,) + parent.args[index + 1:])
    i = path[0]
    return document[:i] + (node,) + document[i + 1:]


@dataclass(frozen=True)
class Difference:
    path: Path
    before: Term | None
    after: Term | None


def diff(before: Document, after: Document) -> list[Difference]:
    """Positional changed frontier, not semantic or minimum-edit alignment."""
    validate(before)
    validate(after)
    pending = [((i,), a, b) for i, (a, b) in reversed(list(enumerate(zip_longest(before, after))))]
    changes = []
    while pending:
        path, a, b = pending.pop()
        if a is b:
            continue
        if a is not None and b is not None and a.symbol == b.symbol and len(a.args) == len(b.args):
            pending.extend((path + (i,), a.args[i], b.args[i]) for i in reversed(range(len(a.args))))
        else:
            changes.append(Difference(path, a, b))
    return changes
