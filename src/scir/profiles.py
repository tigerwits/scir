"""Opt-in Boolean syntax: ordinary subtrees are opaque propositions."""
from __future__ import annotations

from .core import Term

ARITY = {"not": (1, 1), "and": (2, None), "or": (2, None), "if": (2, 2)}


def boolean_normalize(term: Term) -> Term:
    """Never descend through ordinary heads such as think, say or quote.

    This returns a derived tree, not a replacement for source evidence.
    Explicit opt-in gives 'if' a propositional reading, not general English
    conditional semantics. No rewrites involving 'if' are performed.
    """
    if type(term) is not Term:
        raise ValueError("expected a ground Term")
    if term.symbol not in ARITY:
        return term
    low, high = ARITY[term.symbol]
    if len(term.args) < low or (high is not None and len(term.args) > high):
        raise ValueError("invalid Boolean arity")
    args = tuple(boolean_normalize(a) for a in term.args)
    if term.symbol == "not" and args[0].symbol == "not":
        return args[0].args[0]
    if term.symbol in ("and", "or"):
        args = tuple(c for a in args for c in (a.args if a.symbol == term.symbol else (a,)))
    return Term(term.symbol, args)
