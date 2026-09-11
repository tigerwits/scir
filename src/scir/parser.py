"""Parse SCIR surface syntax into an expression tree."""

from __future__ import annotations

from .ast import Atom, Call, Expr, Variable

IDENT_START = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
IDENT_CONTINUE = IDENT_START | set("0123456789")


class ParseError(ValueError):
    def __init__(self, message: str, source: str, index: int) -> None:
        self.source = source
        self.index = index
        super().__init__(f"{message} at index {index}")


def parse(source: str) -> Expr:
    """Parse exactly one expression. Raises ParseError on invalid input."""
    parser = _Parser(source)
    expr = parser.parse_expr()
    parser.skip()
    if parser.index != parser.length:
        raise ParseError("unexpected trailing input", source, parser.index)
    return expr


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.index = 0

    def skip(self) -> None:
        source = self.source
        i = self.index
        n = self.length
        while i < n and source[i].isspace():
            i += 1
        self.index = i

    def peek(self) -> str | None:
        self.skip()
        if self.index >= self.length:
            return None
        return self.source[self.index]

    def parse_expr(self) -> Expr:
        ch = self.peek()
        if ch is None:
            raise ParseError("expected expression", self.source, self.index)
        if ch == "?":
            return self.parse_variable()
        if ch in IDENT_START:
            return self.parse_atom_or_call()
        raise ParseError("expected expression", self.source, self.index)

    def parse_variable(self) -> Variable:
        # '?' must be adjacent to the identifier.
        start = self.index
        self.index += 1
        if self.index >= self.length or self.source[self.index] not in IDENT_START:
            raise ParseError("expected identifier after '?'", self.source, start)
        return Variable(self.read_ident())

    def parse_atom_or_call(self) -> Expr:
        name = self.read_ident()
        if self.peek() == "(":
            return Call(name, self.parse_args())
        return Atom(name)

    def parse_args(self) -> tuple[Expr, ...]:
        # Current peek is '('.
        self.index += 1
        if self.peek() == ")":
            self.index += 1
            return ()
        args: list[Expr] = [self.parse_expr()]
        while True:
            ch = self.peek()
            if ch == ",":
                comma_at = self.index
                self.index += 1
                if self.peek() == ")":
                    raise ParseError("trailing comma", self.source, comma_at)
                args.append(self.parse_expr())
                continue
            if ch == ")":
                self.index += 1
                return tuple(args)
            raise ParseError("expected ',' or ')'", self.source, self.index)

    def read_ident(self) -> str:
        if self.index >= self.length or self.source[self.index] not in IDENT_START:
            raise ParseError("expected identifier", self.source, self.index)
        start = self.index
        self.index += 1
        n = self.length
        source = self.source
        while self.index < n and source[self.index] in IDENT_CONTINUE:
            self.index += 1
        return source[start : self.index]
