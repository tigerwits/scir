"""Explicit, collection-local definitions over unchanged structured/1 expressions."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .core import Document, Path, Symbol, Term, _symbol_value, digest, format_symbol
from . import profile as p
from .changes import ConflictError
from .knowledge import Index, _leaf, _references, build_index
from .tree import at, replace_at


@dataclass(frozen=True, slots=True)
class Factoring:
    document: Document
    definitions: Document


def _environment(definitions: Document) -> Index:
    """Validate every record, including unused definitions and metadata edges."""
    index = build_index(definitions, collection="Definitions")
    remaining, reverse = {}, {identifier: [] for identifier in index.records}
    for identifier, record in index.records.items():
        if record.kind != "Definition":
            raise p.ProfileError("definition environments contain only Definition records")
        remaining[identifier] = len(index.references[identifier])
        for target in index.references[identifier]:
            reverse[target].append(identifier)
    ready = [identifier for identifier, count in remaining.items() if not count]
    count = 0
    while ready:
        identifier = ready.pop()
        count += 1
        for dependent in reverse[identifier]:
            remaining[dependent] -= 1
            if not remaining[dependent]:
                ready.append(dependent)
    if count != len(index.records):
        raise p.ProfileError("definition environment must be acyclic")
    return index


def _expression_at(document: Document, path: Path) -> Term:
    """A native path may enter field values, never literal labels or containers."""
    selected = at(document, path)
    term, position = document[path[0]], 1
    while position < len(path):
        if term.symbol in (p.TEXT, p.REF):
            raise p.ProfileError("text and reference payload labels are opaque")
        args, fields = p._split(term)
        child = path[position]
        if fields and child == len(args):
            if position + 2 >= len(path) or path[position + 2] != 0:
                raise p.ProfileError("select a field value, not its label or keyword container")
            term = term.args[child].args[path[position + 1]].args[0]
            position += 3
        else:
            term = term.args[child]
            position += 1
    return selected


def factor_subtree(document: Document, path: Path, *, definition_id: str | Symbol,
                   expected_snapshot: str, definitions: Document = ()) -> Factoring:
    """Name one expression occurrence under a whole-document snapshot guard.

    The caller allocates and persists an ordinary, collection-local ID. A bare
    head with that spelling remains a literal symbol. External reference targets
    and recognizable root record IDs are reserved to avoid accidental capture.
    """
    p.validate(document)
    if type(expected_snapshot) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
        raise p.ProfileError("expected_snapshot must be a lowercase SHA-256 fingerprint")
    if digest(document) != expected_snapshot:
        raise ConflictError("source snapshot precondition failed")
    index = _environment(definitions)
    identifier = _leaf(Term(_symbol_value(definition_id)), "definition ID")
    reserved = set(index.records)
    for root in document:
        reserved.update(_references(root))
        if root.symbol == "record":
            args, _ = p._split(root)
            if len(args) == 3 and not args[0].args and args[0].symbol not in p.RESERVED:
                reserved.add(args[0].symbol)
    if identifier in reserved:
        raise ConflictError("definition ID is not fresh: " + identifier)
    selected = _expression_at(document, path)
    record = p.application("record", (Term(identifier), Term("Definition"), selected))
    candidate_definitions = definitions + (record,)
    _environment(candidate_definitions)  # The extracted body must also be closed.
    candidate = replace_at(document, path, p.reference(identifier))
    p.validate(candidate)
    return Factoring(candidate, candidate_definitions)


def expand_definitions(document: Document, definitions: Document, *,
                       max_nodes: int = 100_000, max_depth: int = 128) -> Document:
    """Expand declared explicit references, preserving opaque text and other refs.

    Input documents and the whole environment use the existing profile bounds.
    Caller node/depth bounds apply to the complete output, counting occurrences
    and raw profile wrappers. The existing 16 MB canonical-byte bound also applies.
    Budget exhaustion raises LimitError without returning a partial document.
    """
    limits = p.Limits(nodes=max_nodes, depth=max_depth)
    p.validate(document)
    index = _environment(definitions)
    # A reference jump does not emit a node. All other native nodes are charged
    # before construction; keyword labels and literal payloads use distinct roles.
    pending = [("visit", term, 0, "expression") for term in reversed(document)]
    terminals = {}  # Collapse alias-only chains; never cache away output occurrences.
    values, nodes, size, scheduled = [], 0, len(document), len(document)
    while pending:
        operation, value, depth, role = pending.pop()
        if operation == "build":
            children = tuple(values[-depth:]) if depth else ()
            if depth:
                del values[-depth:]
            values.append(Term(value, children))
            continue
        scheduled -= 1
        term = value
        if role == "expression":
            aliases = []
            while term.symbol == p.REF and term.args[0].symbol in index.records:
                identifier = term.args[0].symbol
                if identifier in terminals:
                    term = terminals[identifier]
                    break
                aliases.append(identifier)
                term = index.records[identifier].payload
            for identifier in aliases:
                terminals[identifier] = term
        children = term.args
        if role == "literal" or (role == "expression" and term.symbol in (p.TEXT, p.REF)):
            roles = ("literal",) * len(children)
        elif role == "keywords":
            roles = ("field",) * len(children)
        elif role == "field":
            roles = ("expression",)
        else:
            roles = ("expression",) * len(children)
            if children and children[-1].symbol == p.KW:
                roles = roles[:-1] + ("keywords",)
        nodes += 1
        size += len(format_symbol(term.symbol).encode("utf-8")) + 2 * len(children)
        scheduled += len(children)
        if depth > limits.depth or nodes + scheduled > limits.nodes:
            raise p.LimitError("expanded tree budget exceeded")
        if size > limits.bytes:
            raise p.LimitError("expanded byte budget exceeded")
        pending.append(("build", term.symbol, len(children), ""))
        pending.extend(("visit", child, depth + 1, child_role)
                       for child, child_role in reversed(tuple(zip(children, roles))))
    result = tuple(values)
    p.validate(result, limits=limits)
    return result
