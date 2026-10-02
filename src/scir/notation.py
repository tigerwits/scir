"""Bounded notation/1 elaboration. Symbols are constructed, never executed."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from .core import Document, Term, check_symbol, format_document, format_symbol
from .syntax import ParseError, parse_document
from . import profile as p

VERSION = "notation/1"
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*")
_SEGMENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_STRING = re.compile(r'"(?:\\[^\n]|[^"\\\n])*"')
_ARITHMETIC = (("+", "plus", "chain", 50), ("-", "sub", "left", 50),
               ("-", "neg", "prefix", 65), ("*", "mul", "chain", 60),
               ("/", "div", "left", 60), ("^", "power", "right", 70))


@dataclass(frozen=True, slots=True)
class Limits:
    source_bytes: int = 64_000
    tokens: int = 16_000
    nodes: int = 8_000
    depth: int = 64
    expanded_bytes: int = 256_000
    declarations: int = 128

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 1 for v in (
            self.source_bytes, self.tokens, self.nodes, self.depth,
            self.expanded_bytes, self.declarations)) or self.depth > 64:
            raise ValueError("notation bounds must be positive integers; depth is at most 64")

    def content(self) -> p.Limits:
        return p.Limits(nodes=self.nodes, depth=self.depth, bytes=self.expanded_bytes)


def environment_digest(operators: str | None = None) -> str:
    if operators not in (None, "arithmetic/1"):
        raise ValueError("unknown fixed notation profile")
    value = {"notation": VERSION, "structured": p.VERSION,
             "operators": operators, "table": _ARITHMETIC if operators else ()}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    position: int


@dataclass(frozen=True, slots=True)
class _Value:
    term: Term
    nodes: int
    depth: int
    size: int


class _Parser:
    def __init__(self, source: str, operators: str | None, limits: Limits):
        environment_digest(operators)
        if type(source) is not str or type(limits) is not Limits:
            raise ValueError("expected source text and notation Limits")
        if len(source) > limits.source_bytes or len(source.encode("utf-8")) > limits.source_bytes:
            raise p.LimitError("notation source byte budget exceeded")
        self.source, self.limits = source, limits
        self.prefix = {row[0]: row for row in _ARITHMETIC if row[2] == "prefix"} if operators else {}
        self.following = {row[0]: row for row in _ARITHMETIC if row[2] != "prefix"} if operators else {}
        self.aliases, self.values = {}, {}
        self.declarations = 0
        self.tokens, self.index = self.lex(), 0

    def fail(self, message: str, position: int | None = None):
        raise ParseError(self.source, self.current.position if position is None else position, message)

    def lex(self) -> list[_Token]:
        tokens, position = [], 0
        while position < len(self.source):
            char = self.source[position]
            if char in " \t\r\f":
                position += 1
                continue
            if char == "#":
                end = self.source.find("\n", position)
                position = len(self.source) if end < 0 else end
                continue
            start = position
            text = self.source.startswith('t"', position)
            if char == '"' or text:
                begin = position + int(text)
                match = _STRING.match(self.source, begin)
                if match is None:
                    self.fail("invalid quoted string", start)
                try:
                    value = json.loads(match.group())
                    value.encode("utf-8")
                except (ValueError, UnicodeError) as error:
                    self.fail("invalid Unicode JSON string", start)
                kind, position = ("text" if text else "symbol"), match.end()
            elif char in "@$":
                match = _SEGMENT.match(self.source, position + 1)
                if match is None:
                    self.fail("expected a binding name", start)
                kind, value = ("directive" if char == "@" else "value"), match.group()
                position = match.end()
            elif char in "(),;:&=\n":
                kind, value, position = char, char, position + 1
            else:
                match = _NAME.match(self.source, position) or _NUMBER.match(self.source, position)
                if match:
                    kind, value, position = "name", match.group(), match.end()
                elif char in self.prefix or char in self.following:
                    kind, value, position = "operator", char, position + 1
                else:
                    self.fail("unsupported notation token", start)
            tokens.append(_Token(kind, value, start))
            if len(tokens) > self.limits.tokens:
                raise p.LimitError("notation token budget exceeded")
        tokens.append(_Token("eof", "", position))
        return tokens

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def take(self) -> _Token:
        token = self.current
        if token.kind != "eof":
            self.index += 1
        return token

    def expect(self, kind: str) -> _Token:
        if self.current.kind != kind:
            self.fail("expected " + kind)
        return self.take()

    def newlines(self) -> None:
        while self.current.kind == "\n":
            self.take()

    def qualify(self, name: str) -> str:
        first, dot, rest = name.partition(".")
        return self.aliases.get(first, first) + dot + rest if dot else name

    def node(self, head: str, children: list[_Value], position: int) -> _Value:
        try:
            check_symbol(head)
        except ValueError:
            self.fail("expected a nonempty Unicode symbol", position)
        nodes = 1 + sum(c.nodes for c in children)
        depth = 1 + max((c.depth for c in children), default=-1)
        size = len(format_symbol(head).encode("utf-8")) + sum(c.size for c in children) + 2 * len(children)
        if nodes > self.limits.nodes or depth > self.limits.depth or size > self.limits.expanded_bytes:
            raise p.LimitError("expanded notation tree exceeds bounds")
        return _Value(Term(head, tuple(c.term for c in children)), nodes, depth, size)

    def items(self, head: str, position: int, nesting: int, *, grouping: bool = False) -> _Value:
        self.expect("(")
        self.newlines()
        positional, fields, seen, comma = [], [], set(), False
        if self.current.kind == ")":
            self.take()
            if not grouping:
                self.fail("empty calls are written as leaves", position)
            return self.node(p.TUPLE, [], position)
        while True:
            token = self.current
            named = token.kind in ("name", "symbol") and self.tokens[self.index + 1].kind == ":"
            if named:
                self.take()
                self.take()
                if token.value in seen:
                    self.fail("duplicate named role", token.position)
                seen.add(token.value)
                self.newlines()
                value = self.expr(nesting=nesting + 1)
                fields.append(self.node(token.value, [value], token.position))
            else:
                if fields:
                    self.fail("positional arguments must precede named roles")
                positional.append(self.expr(nesting=nesting + 1))
            self.newlines()
            if self.current.kind != ",":
                break
            comma = True
            self.take()
            self.newlines()
            if self.current.kind == ")":
                break
        self.expect(")")
        if grouping and len(positional) == 1 and not fields and not comma:
            return positional[0]
        if fields:
            fields.sort(key=lambda value: value.term.symbol.encode("utf-8"))
            positional.append(self.node(p.KW, fields, position))
        return self.node(head, positional, position)

    def atom(self, nesting: int) -> _Value:
        token = self.current
        if token.kind == "(":
            return self.items(p.TUPLE, token.position, nesting, grouping=True)
        self.take()
        if token.kind == "text":
            child = [self.node(token.value, [], token.position)] if token.value else []
            return self.node(p.TEXT, child, token.position)
        if token.kind == "&":
            identifier = self.take()
            if identifier.kind not in ("name", "symbol"):
                self.fail("reference requires a literal ID", identifier.position)
            return self.node(p.REF, [self.node(identifier.value, [], identifier.position)], token.position)
        if token.kind == "value":
            if token.value not in self.values:
                self.fail("unknown ground abbreviation", token.position)
            if self.current.kind == "(":
                self.fail("ground abbreviations are not callable heads")
            return self.values[token.value]
        if token.kind == "operator" and token.value in self.prefix:
            op = self.prefix[token.value]
            self.newlines()
            return self.node(op[1], [self.expr(op[3], nesting + 1)], token.position)
        if token.kind in ("name", "symbol"):
            head = self.qualify(token.value) if token.kind == "name" else token.value
            if head in p.RESERVED:
                self.fail("use tuple/text/reference syntax for profile tags", token.position)
        elif token.kind == "operator" and self.current.kind == "(" and token.value in self.following:
            head = self.following[token.value][1]
        else:
            self.fail("expected an expression", token.position)
        if self.current.kind == "(":
            return self.items(head, token.position, nesting)
        return self.node(head, [], token.position)

    def expr(self, minimum: int = 0, nesting: int = 0, inherited=None) -> _Value:
        if nesting > self.limits.depth:
            raise p.LimitError("notation parser depth exceeded")
        left, previous = self.atom(nesting), None
        while self.current.kind == "operator":
            op = self.following.get(self.current.value)
            if op is None or op[3] < minimum:
                break
            for adjacent in (previous, inherited):
                if adjacent and adjacent[3] == op[3] and adjacent[0] != op[0]:
                    self.fail("mixed same-precedence operators require parentheses")
            position = self.current.position
            if op[2] == "chain":
                children = [left]
                while self.current.kind == "operator" and self.current.value == op[0]:
                    self.take()
                    self.newlines()
                    children.append(self.expr(op[3] + 1, nesting + 1))
                left = self.node(op[1], children, position)
            else:
                self.take()
                self.newlines()
                right = self.expr(op[3] + int(op[2] != "right"), nesting + 1,
                                  op if op[2] == "right" else None)
                left = self.node(op[1], [left, right], position)
            previous = op
        return left

    def declaration(self) -> None:
        directive = self.take()
        if directive.value not in ("using", "let"):
            self.fail("unsupported declaration", directive.position)
        name = self.expect("name")
        if not _SEGMENT.fullmatch(name.value):
            self.fail("binding names must be single identifier segments", name.position)
        aliases = directive.value == "using"
        table = self.aliases if aliases else self.values
        if name.value in table:
            self.fail("duplicate binding", name.position)
        self.declarations += 1
        if self.declarations > self.limits.declarations:
            raise p.LimitError("declaration budget exceeded")
        self.expect("=")
        self.newlines()
        if aliases:
            target = self.take()
            if target.kind not in ("name", "symbol"):
                self.fail("expected a qualified alias target", target.position)
            value = self.qualify(target.value) if target.kind == "name" else target.value
            if not _NAME.fullmatch(value):
                self.fail("alias target requires identifier segments", target.position)
            if len(value.encode("utf-8")) > self.limits.expanded_bytes:
                raise p.LimitError("alias expansion byte budget exceeded")
        else:
            value = self.expr()
        table[name.value] = value

    def document(self) -> Document:
        roots, nodes, size = [], 0, 0
        self.newlines()
        while self.current.kind != "eof":
            if self.current.kind == "directive":
                self.declaration()
            else:
                value = self.expr()
                nodes += value.nodes
                size += value.size + 1
                if nodes > self.limits.nodes or size > self.limits.expanded_bytes:
                    raise p.LimitError("expanded document exceeds bounds")
                roots.append(value.term)
            if self.current.kind == "eof":
                break
            if self.current.kind not in ("\n", ";"):
                self.fail("expected a newline or semicolon between statements")
            self.take()
            self.newlines()
        return tuple(roots)


def lower(source: str, *, operators: str | None = None, limits: Limits = Limits()) -> Document:
    document = _Parser(source, operators, limits).document()
    p.validate(document, limits=limits.content())
    # Independent native parser remains the transport oracle.
    if parse_document(format_document(document), max_nodes=limits.nodes, max_depth=limits.depth) != document:
        raise AssertionError("native roundtrip failed")
    return document


def pretty(document: Document, *, operators: str | None = None, limits: Limits = Limits()) -> str:
    """Exact explicit spelling. Does not invent aliases or rewrite authored source."""
    environment_digest(operators)
    if type(limits) is not Limits:
        raise ValueError("expected notation Limits")
    p.validate(document, limits=limits.content())

    def name(value: str) -> str:
        return value if _NAME.fullmatch(value) or _NUMBER.fullmatch(value) else json.dumps(value, ensure_ascii=False)

    def show(term: Term) -> str:
        if term.symbol == p.TEXT:
            value = term.args[0].symbol if term.args else ""
            return "t" + json.dumps(value, ensure_ascii=False)
        if term.symbol == p.REF:
            return "&" + name(term.args[0].symbol)
        positional, fields = p._split(term)
        parts = [show(t) for t in positional] + [name(k) + ": " + show(v) for k, v in fields]
        if term.symbol == p.TUPLE:
            suffix = "," if len(positional) == 1 and not fields else ""
            return "(" + ", ".join(parts) + suffix + ")"
        return name(term.symbol) + ("(" + ", ".join(parts) + ")" if parts else "")

    result = "".join(show(term) + "\n" for term in document)
    if lower(result, operators=operators, limits=limits) != document:
        raise AssertionError("notation print roundtrip failed")
    return result
