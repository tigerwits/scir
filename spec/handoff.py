"""Repository input bases and explicit shard plans; never writes a source file."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from scir import digest, format_document
from scir._profile_native import native
from scir.changes import ConflictError
from scir.profile import LimitError, ProfileError, read_tuple, read_fields

if __package__:
    from .locations import MAX_SOURCE_BYTES, local_file, read_source
else:
    from locations import MAX_SOURCE_BYTES, local_file, read_source

VERSION = "scir-repository-basis/1"
MAX_FILES = 2048
MAX_BYTES = 32_000_000
DERIVED = ("spec/requirements.scir", "SPEC.md", "docs/api.md")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wire(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def linked_paths(index) -> set[str]:
    names = set()
    for record in index.records.values():
        fields = dict(record.fields)
        source = fields.get("source")
        links = [(source, "section")]
        for key, kind in (("tests", "test"), ("models", "model")):
            if key in fields:
                if read_fields(fields[key]):
                    raise ProfileError(key + " must be a positional tuple")
                links.extend((link, kind) for link in read_tuple(fields[key]))
        for link, kind in links:
            if (link is None or link.symbol != kind or len(link.args) != 2
                    or any(arg.args for arg in link.args)):
                raise ProfileError("expected " + kind + "(file, declaration)")
            names.add(link.args[0].symbol)
    return names


@dataclass(frozen=True)
class Basis:
    collection: str
    snapshot: str
    files: tuple[tuple[str, str], ...]
    membership: tuple[tuple[str, str], ...]

    def as_dict(self):
        return {"version": VERSION, "collection": self.collection,
                "source_snapshot": self.snapshot, "files": dict(self.files),
                "membership": dict(self.membership)}

    @property
    def fingerprint(self) -> str:
        return sha(wire(self.as_dict()).encode("utf-8"))

    def packet(self):
        return {**self.as_dict(), "digest": self.fingerprint}


def capture(root: Path, index, sources, *, extra=()) -> Basis:
    """Bind exact source/link/view bytes and source membership, not just headings."""
    root = root.resolve()
    names = set(sources) | set(DERIVED) | linked_paths(index) | set(extra)
    # Contributor instructions and repository checker code are also maintenance inputs.
    for name in ("AGENTS.md", "spec/OWNERSHIP.md"):
        if (root / name).exists():
            names.add(name)
    names.update(p.relative_to(root).as_posix() for p in (root / "spec").glob("*.py"))
    if len(names) > MAX_FILES:
        raise LimitError("repository basis file limit exceeded")
    files, source_text, total = [], {}, 0
    for name in sorted(names, key=lambda n: n.encode("utf-8")):
        path = local_file(root, name, Path(name).suffix)
        text = read_source(path)
        raw = text.encode("utf-8")
        total += len(raw)
        if total > MAX_BYTES:
            raise LimitError("repository basis byte limit exceeded")
        files.append((name, sha(raw)))
        if name in sources:
            source_text[name] = text
    document, membership, lengths = (), [], {}
    for name in sources:
        shard = native(source_text[name])
        if format_document(shard) != source_text[name]:
            raise ConflictError("source shard is no longer canonical: " + name)
        document += shard
        lengths[name] = len(shard)
    if document != index.document or digest(document) != index.snapshot:
        raise ConflictError("source shards changed while capturing their basis")
    offset = 0
    for name in sources:
        count = lengths[name]
        membership.extend((t.args[0].symbol, name) for t in document[offset:offset + count])
        offset += count
    return Basis(index.collection, index.snapshot, tuple(files), tuple(membership))


def partition(document, basis: Basis, sources, placements=None):
    """Existing IDs keep their owner; new IDs require explicit source placement."""
    placements = {} if placements is None else placements
    if type(placements) is not dict or any(type(k) is not str or type(v) is not str for k, v in placements.items()):
        raise ProfileError("placements must map new record IDs to source shard names")
    owners = dict(basis.membership)
    created = {term.args[0].symbol for term in document} - owners.keys()
    if set(placements) != created or any(name not in sources for name in placements.values()):
        raise ProfileError("each new record needs exactly one declared source placement")
    owners.update(placements)
    shards = {name: [] for name in sources}
    for term in document:
        shards[owners[term.args[0].symbol]].append(term)
    # Source order is explicit; no existing record moves to another file.
    combined = tuple(term for name in sources for term in shards[name])
    return combined, {name: format_document(tuple(shards[name])) for name in sources}


def writes(root: Path, basis: Basis, shards, derived):
    expected = dict(basis.files)
    entries = [(name, content, "authoritative") for name, content in shards.items()]
    entries.extend((path.relative_to(root.resolve()).as_posix(), raw.decode("utf-8"), "derived")
                   for path, raw in derived)
    result = []
    for name, content, role in entries:
        raw = content.encode("utf-8")
        if len(raw) > MAX_SOURCE_BYTES:
            raise LimitError("candidate repository source byte limit exceeded: " + name)
        if role == "authoritative" and format_document(native(content)) != content:
            raise ProfileError("candidate source is not canonical: " + name)
        actual = sha(raw)
        if actual != expected[name]:
            result.append({"path": name, "role": role, "expected_sha256": expected[name],
                           "sha256": actual, "content": content})
    if len(wire(result).encode("utf-8")) > 16_000_000:
        raise LimitError("repository write plan output limit exceeded")
    return result
