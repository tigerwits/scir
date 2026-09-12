"""Snapshot-bound metadata. Interpretation alternatives are NOT annotations."""
from __future__ import annotations

from dataclasses import dataclass
import json
from .core import Document, Path, check_symbol, digest, validate
from .tree import at


MAX_JSON_CHARS = 2_000_000
MAX_JSON_VALUES = 100_000


def _json(value) -> str:
    # Validate before dumps: JSON must not silently coerce object keys.
    pending, remaining = [(value, 0)], MAX_JSON_VALUES
    characters = 0
    while pending:
        item, depth = pending.pop()
        remaining -= 1
        if remaining < 0 or depth > 128:
            raise ValueError("annotation JSON resource limit exceeded")
        kind = type(item)
        if kind is str:
            characters += len(item)
            if characters > MAX_JSON_CHARS:
                raise ValueError("annotation JSON character limit exceeded")
            try:
                item.encode("utf-8")
            except UnicodeEncodeError as e:
                raise ValueError("annotation JSON must contain Unicode scalar values") from e
        elif kind is dict:
            if any(type(k) is not str for k in item):
                raise ValueError("annotation object keys must be strings")
            if 2 * len(item) > remaining - len(pending):
                raise ValueError("annotation JSON resource limit exceeded")
            pending.extend((part, depth + 1) for pair in item.items() for part in pair)
        elif kind in (list, tuple):
            if len(item) > remaining - len(pending):
                raise ValueError("annotation JSON resource limit exceeded")
            pending.extend((part, depth + 1) for part in item)
        elif kind not in (type(None), bool, int, float):
            raise ValueError("annotation payload must be JSON-compatible data")
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    parts, size = [], 0
    for part in encoder.iterencode(value):
        size += len(part)
        if size > MAX_JSON_CHARS:
            raise ValueError("annotation JSON character limit exceeded")
        parts.append(part)
    return "".join(parts)


@dataclass(frozen=True, slots=True)
class Annotation:
    snapshot: str
    path: Path
    key: str
    value_json: str


def annotate(document: Document, path: Path, key: str, value) -> Annotation:
    at(document, path)
    check_symbol(key)
    return Annotation(digest(document), path, key, _json(value))


@dataclass(frozen=True, slots=True)
class Bundle:
    document: Document
    annotations: tuple[Annotation, ...] = ()

    def __post_init__(self) -> None:
        validate(self.document)
        if type(self.annotations) is not tuple:
            raise ValueError("annotations must be a tuple")
        snapshot = digest(self.document)
        for note in self.annotations:
            if type(note) is not Annotation or note.snapshot != snapshot:
                raise ValueError("annotation targets a different document snapshot")
            at(self.document, note.path)
            check_symbol(note.key)
            if type(note.value_json) is not str or len(note.value_json) > MAX_JSON_CHARS:
                raise ValueError("invalid annotation JSON payload")
            try:
                canonical = _json(json.loads(note.value_json))
            except RecursionError as e:
                raise ValueError("annotation JSON depth limit exceeded") from e
            if canonical != note.value_json:
                raise ValueError("annotation payload must be canonical finite JSON")


def erase(bundle: Bundle) -> Document:
    """Content projection only; this does not preserve evidence or confidence."""
    if type(bundle) is not Bundle:
        raise ValueError("erase expects a Bundle, not unresolved alternatives")
    return bundle.document


@dataclass(frozen=True, slots=True)
class Alternatives:
    """An unresolved choice of whole documents, never a conjunction of roots."""
    options: tuple[Document, ...]

    def __post_init__(self) -> None:
        if type(self.options) is not tuple or len(self.options) < 2:
            raise ValueError("an ambiguity needs at least two candidate documents")
        for option in self.options:
            validate(option)

    def choose(self, index: int) -> Document:
        if type(index) is not int or not 0 <= index < len(self.options):
            raise ValueError("invalid alternative index")
        return self.options[index]
