"""Symbolic content trees and deterministic structural operations."""
from .core import FORMAT_VERSION, Document, Term, digest, format_document, validate
from .patterns import match
from .syntax import ParseError, parse, parse_document, parse_pattern
from .tree import diff, query, replace_at

__version__ = "1.0.0"
__all__ = [
    "Term", "Document", "ParseError", "FORMAT_VERSION",
    "parse", "parse_document", "format_document", "parse_pattern",
    "match", "query", "validate", "digest", "diff", "replace_at",
]
