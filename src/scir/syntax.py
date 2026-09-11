"""Small non-executing syntax shared by content and patterns."""
from __future__ import annotations

import json
import re
from .core import Document, Term
from .patterns import Node, Pattern, Var

TOKEN = re.compile(
    r'(?P<space>[ \t\r\f]+)|(?P<comment>\#[^\n]*)|(?P<newline>\n)'
    r'|(?P<var>\?[A-Za-z_][A-Za-z_0-9]*)|(?P<ident>[A-Za-z_][A-Za-z_0-9]*)'
    r'|(?P<string>"(?:\\.|[^"\\\n])*")|(?P<punct>[(),;])'
)


class ParseError(ValueError):
    def __init__(self, source: str, index: int, message: str):
        self.index = index
        self.line = source.count("\n", 0, index) + 1
        self.column = index - source.rfind("\n", 0, index)
        super().__init__(f"{message} at {self.line}:{self.column}")


class _Parser:
    def __init__(self, source: str, pattern: bool, max_depth: int, max_nodes: int):
        if type(source) is not str:
            raise ValueError("source must be text")
        if type(max_depth) is not int or not 0 <= max_depth <= 128:
            raise ValueError("max_depth must be an integer in 0..128")
        if type(max_nodes) is not int or max_nodes < 1:
            raise ValueError("max_nodes must be a positive integer")
        self.source, self.pattern = source, pattern
        self.max_depth, self.remaining = max_depth, max_nodes
        self.tokens, self.i = [], 0
        if len(source) > 2_000_000:
            raise ParseError(source, 0, "source exceeds 2,000,000 characters")
        pos = 0
        while pos < len(source):
            m = TOKEN.match(source, pos)
            if m is None:
                raise ParseError(source, pos, "unexpected character")
            if m.lastgroup not in ("space", "comment"):
                self.tokens.append((m.lastgroup, m.group(), pos))
            pos = m.end()
        self.tokens.append(("eof", "", len(source)))

    def error(self, message: str):
        raise ParseError(self.source, self.tokens[self.i][2], message)

    def newlines(self):
        while self.tokens[self.i][0] == "newline":
            self.i += 1

    def expr(self, depth=0) -> Term | Pattern:
        if depth > self.max_depth or self.remaining <= 0:
            self.error("expression resource limit exceeded")
        self.remaining -= 1
        kind, value, pos = self.tokens[self.i]
        self.i += 1
        if kind == "var":
            if not self.pattern:
                raise ParseError(self.source, pos, "metavariables belong in patterns, not content")
            return Var(value[1:])
        if kind not in ("ident", "string"):
            raise ParseError(self.source, pos, "expected symbol")
        if kind == "string":
            try:
                value = json.loads(value)
            except ValueError as e:
                raise ParseError(self.source, pos, "invalid JSON-quoted symbol") from e
        args = []
        # A newline between a head and '(' terminates a root; no guessing.
        if self.tokens[self.i][1] == "(":
            self.i += 1
            self.newlines()
            if self.tokens[self.i][1] != ")":
                while True:
                    args.append(self.expr(depth + 1))
                    self.newlines()
                    if self.tokens[self.i][1] != ",":
                        break
                    self.i += 1
                    self.newlines()
                    if self.tokens[self.i][1] == ")":
                        break
            if self.tokens[self.i][1] != ")":
                self.error("expected ',' or ')'")
            self.i += 1
        try:
            return (Node if self.pattern else Term)(value, tuple(args))
        except ValueError as e:
            raise ParseError(self.source, pos, str(e)) from e

    def document(self) -> tuple:
        roots = []
        self.newlines()
        while self.tokens[self.i][0] != "eof":
            roots.append(self.expr())
            if self.tokens[self.i][0] == "eof":
                break
            if self.tokens[self.i][0] != "newline" and self.tokens[self.i][1] != ";":
                self.error("expected newline or ';' between roots")
            self.i += 1
            self.newlines()
        return tuple(roots)


def parse_document(source: str, *, max_depth=128, max_nodes=100_000) -> Document:
    return _Parser(source, False, max_depth, max_nodes).document()


def _one(source: str, pattern: bool, max_depth: int, max_nodes: int):
    roots = _Parser(source, pattern, max_depth, max_nodes).document()
    if len(roots) != 1:
        raise ParseError(source, 0, "expected exactly one expression")
    return roots[0]


def parse(source: str, *, max_depth=128, max_nodes=100_000) -> Term:
    return _one(source, False, max_depth, max_nodes)


def parse_pattern(source: str, *, max_depth=128, max_nodes=100_000) -> Pattern:
    return _one(source, True, max_depth, max_nodes)
