"""Immutable SCIR expression nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class Atom:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Variable:
    """Pattern/query variable. `name` is the identifier without a leading `?`."""

    name: str

    def __str__(self) -> str:
        return f"?{self.name}"


@dataclass(frozen=True, slots=True)
class Call:
    head: str
    args: tuple[Expr, ...]

    def __str__(self) -> str:
        inner = ", ".join(str(arg) for arg in self.args)
        return f"{self.head}({inner})"


Expr = Union[Atom, Variable, Call]


def equal(left: Expr, right: Expr) -> bool:
    """Structural equality. Same as `==` on frozen nodes."""
    return left == right
