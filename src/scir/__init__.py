"""SCIR 0.2: one content constructor, ordered roots, separate patterns."""
from .core import Document, Path, Term, digest, format_document, validate
from .syntax import ParseError, parse, parse_document, parse_pattern
from .patterns import Node, Pattern, Var, instantiate, match
from .tree import Difference, Hit, at, diff, query, replace_at, walk

__version__ = "0.2.1"
__all__ = [
    "Document", "Path", "Term", "digest", "format_document", "validate",
    "ParseError", "parse", "parse_document", "parse_pattern", "Node", "Pattern",
    "Var", "instantiate", "match", "Difference", "Hit", "at", "diff", "query", "replace_at", "walk",
]
