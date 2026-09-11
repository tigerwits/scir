"""Snapshot-bound metadata. Interpretation alternatives are NOT annotations."""
from __future__ import annotations

from dataclasses import dataclass
import json
from .core import Document, Path, digest, validate
from .tree import at


def _json(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as e:
        raise ValueError("annotation JSON must contain Unicode scalar values") from e
    return raw


@dataclass(frozen=True, slots=True)
class Annotation:
    snapshot: str
    path: Path
    key: str
    value_json: str


def annotate(document: Document, path: Path, key: str, value) -> Annotation:
    at(document, path)
    if type(key) is not str or not key:
        raise ValueError("annotation keys must be nonempty strings")
    return Annotation(digest(document), path, key, _json(value))


@dataclass(frozen=True, slots=True)
class Bundle:
    document: Document
    annotations: tuple[Annotation, ...] = ()

    def __post_init__(self):
        validate(self.document)
        if type(self.annotations) is not tuple:
            raise ValueError("annotations must be a tuple")
        snapshot = digest(self.document)
        for note in self.annotations:
            if type(note) is not Annotation or note.snapshot != snapshot:
                raise ValueError("annotation targets a different document snapshot")
            at(self.document, note.path)
            if type(note.key) is not str or not note.key or type(note.value_json) is not str:
                raise ValueError("malformed annotation")
            if _json(json.loads(note.value_json)) != note.value_json:
                raise ValueError("annotation payload must be canonical finite JSON")


def erase(bundle: Bundle) -> Document:
    """Content projection only; this does not preserve evidence or confidence."""
    return bundle.document


@dataclass(frozen=True, slots=True)
class Alternatives:
    """An unresolved choice of whole documents, never a conjunction of roots."""
    options: tuple[Document, ...]

    def __post_init__(self):
        if type(self.options) is not tuple or len(self.options) < 2:
            raise ValueError("an ambiguity needs at least two candidate documents")
        for option in self.options:
            validate(option)

    def choose(self, index: int) -> Document:
        if type(index) is not int or not 0 <= index < len(self.options):
            raise ValueError("invalid alternative index")
        return self.options[index]
