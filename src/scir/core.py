"""Ground ordered trees. No variables, logical operators, or world model."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

FORMAT_VERSION = "1.0"

IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")


def check_symbol(symbol: str) -> None:
    if type(symbol) is not str or not symbol:
        raise ValueError("a symbol must be a nonempty string")
    try:
        symbol.encode("utf-8")
    except UnicodeEncodeError as e:
        raise ValueError("symbols must contain Unicode scalar values") from e


def format_symbol(symbol: str) -> str:
    return symbol if IDENT.fullmatch(symbol) else json.dumps(symbol, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class Symbol:
    """An exact native label value, independent of occurrences and referents."""

    value: str

    def __post_init__(self) -> None:
        check_symbol(self.value)

    def __str__(self) -> str:
        return format_symbol(self.value)


def _symbol_value(symbol: str | Symbol) -> str:
    value = symbol.value if type(symbol) is Symbol else symbol
    check_symbol(value)
    return value


@dataclass(frozen=True, slots=True, init=False)
class Term:
    symbol: str
    args: tuple[Term, ...] = ()

    def __init__(self, symbol: str | Symbol, args: tuple[Term, ...] = ()) -> None:
        # Keep the documented string field and canonical bytes compatible.
        object.__setattr__(self, "symbol", _symbol_value(symbol))
        if type(args) is not tuple or any(type(a) is not Term for a in args):
            raise ValueError("arguments must be a tuple of ground Terms")
        object.__setattr__(self, "args", args)

    @property
    def head(self) -> Symbol:
        return Symbol(self.symbol)

    def __str__(self) -> str:
        head = format_symbol(self.symbol)
        return head if not self.args else head + "(" + ", ".join(map(str, self.args)) + ")"


Document = tuple[Term, ...]
Path = tuple[int, ...]


def validate(document: Document) -> None:
    if type(document) is not tuple or any(type(t) is not Term for t in document):
        raise ValueError("a document must be a tuple of ground Terms")


def format_document(document: Document) -> str:
    validate(document)
    return "".join(str(t) + "\n" for t in document)


def digest(document: Document) -> str:
    """Stable snapshot fingerprint, not a proof of equality or event identity."""
    raw = f"scir:{FORMAT_VERSION}:document\n".encode("utf-8") + format_document(document).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
