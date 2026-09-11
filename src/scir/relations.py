"""Lossless occurrence tables for forests, not a general graph database."""
from __future__ import annotations

from .core import Document, Term, check_symbol
from .tree import walk

VERSION = "scir-relations/0.2"


def encode(document: Document) -> dict:
    nodes, args, roots, parents = [], [], [], []
    for path, term in walk(document):
        ident = len(nodes)
        if ident >= 100_000 or len(path) > 129:
            raise ValueError("forest exceeds reference codec resource limits")
        # Preorder leaves only the current ancestor chain live.
        del parents[len(path) - 1:]
        nodes.append([ident, term.symbol])
        if len(path) == 1:
            roots.append([path[0], ident])
        else:
            args.append([parents[-1], path[-1], ident])
        parents.append(ident)
    return {"version": VERSION, "nodes": nodes, "args": args, "roots": roots}


def _nat(value) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("IDs and positions must be nonnegative integers")
    return value


def _rows(data, key, width):
    rows = data[key]
    if type(rows) is not list:
        raise ValueError(f"{key} must be an array")
    for row in rows:
        if type(row) is not list or len(row) != width:
            raise ValueError(f"invalid {key} row")
        yield row


def _ordered(positions):
    try:
        return [positions[i] for i in range(len(positions))]
    except KeyError as e:
        raise ValueError("positions must be unique and contiguous from zero") from e


def decode(data: dict, *, max_nodes: int = 100_000, max_depth: int = 128) -> Document:
    """Reject malformed tables, cycles, sharing, orphan nodes and order gaps."""
    if type(data) is not dict or set(data) != {"version", "nodes", "args", "roots"}:
        raise ValueError("expected version, nodes, args and roots tables")
    if data["version"] != VERSION:
        raise ValueError("unsupported relational version")
    if type(max_nodes) is not int or max_nodes < 1 or type(max_depth) is not int or not 0 <= max_depth <= 128:
        raise ValueError("invalid resource limits")
    labels, children, incoming = {}, {}, {}
    for ident, label in _rows(data, "nodes", 2):
        _nat(ident)
        check_symbol(label)
        if ident in labels:
            raise ValueError("duplicate node ID")
        if len(labels) >= max_nodes:
            raise ValueError("node limit exceeded")
        labels[ident], children[ident], incoming[ident] = label, {}, 0
    for parent, position, child in _rows(data, "args", 3):
        _nat(parent)
        _nat(position)
        _nat(child)
        if parent not in labels or child not in labels:
            raise ValueError("dangling argument edge")
        if position in children[parent]:
            raise ValueError("duplicate argument position")
        if incoming[child]:
            raise ValueError("a forest occurrence cannot have multiple parents")
        children[parent][position] = child
        incoming[child] = 1
    positions, root_ids = {}, set()
    for position, ident in _rows(data, "roots", 2):
        _nat(position)
        _nat(ident)
        if ident not in labels or position in positions or ident in root_ids:
            raise ValueError("invalid or duplicate root")
        positions[position] = ident
        root_ids.add(ident)
    roots = _ordered(positions)
    adjacency = {ident: _ordered(xs) for ident, xs in children.items()}
    for ident, count in incoming.items():
        if count != (0 if ident in root_ids else 1):
            raise ValueError("tables must be a forest; sharing is not occurrence identity")
    pending, order, seen = [(i, 0) for i in reversed(roots)], [], set()
    while pending:
        ident, depth = pending.pop()
        if depth > max_depth:
            raise ValueError("depth limit exceeded")
        if ident in seen:
            raise ValueError("cycle or shared occurrence")
        seen.add(ident)
        order.append(ident)
        pending.extend((i, depth + 1) for i in reversed(adjacency[ident]))
    if seen != set(labels):
        raise ValueError("unreachable or cyclic nodes")
    built = {}
    for ident in reversed(order):
        built[ident] = Term(labels[ident], tuple(built[c] for c in adjacency[ident]))
    return tuple(built[i] for i in roots)
