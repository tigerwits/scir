"""Optional, bounded delivery views. Complete audit data stays available, not erased."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from .core import Document, check_symbol, format_document
from . import profile as p
from .changes import ConflictError, _propose_content
from ._profile_native import native
from .knowledge import Index, _positive, _select_content
from .notation import Limits as NotationLimits, pretty

VERSION = "scir-delivery/1"


def _wire(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _guards(items: tuple[tuple[str, str], ...]) -> dict:
    if type(items) is not tuple:
        raise ValueError("host guards must be an immutable tuple of pairs")
    if len(items) > 128:
        raise p.LimitError("host guard count budget exceeded")
    result, size = {}, 0
    for pair in items:
        if type(pair) is not tuple or len(pair) != 2:
            raise ValueError("host guard must be a name/value pair")
        name, value = pair
        if type(name) is not str or type(value) is not str:
            raise ValueError("host guard name and value must be strings")
        size += len(name) + len(value)
        if size > 64_000:
            raise p.LimitError("host guard byte budget exceeded")
        size += len(name.encode("utf-8")) + len(value.encode("utf-8")) - len(name) - len(value)
        if size > 64_000:
            raise p.LimitError("host guard byte budget exceeded")
        check_symbol(name)
        check_symbol(value)
        if name in result:
            raise ValueError("duplicate host guard: " + name)
        result[name] = value
    return result


@dataclass(frozen=True, slots=True)
class Delivery:
    packet: str
    artifact: str

    def checked_artifact(self, expected_sha256: str) -> str:
        """Return the exact artifact only if it matches the previous packet's hash."""
        if type(expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
            raise ValueError("expected a lowercase artifact SHA-256")
        if _sha(self.artifact) != expected_sha256:
            raise ConflictError("delivery artifact changed; review fresh context")
        return self.artifact


def _bundle(header: dict, document: Document, audit_value: dict, *, encoding: str,
            limits: p.Limits, notation_limits: NotationLimits,
            max_packet_bytes: int, max_artifact_bytes: int) -> Delivery:
    """Internal presentation boundary for already validated runtime/host results."""
    _positive(max_packet_bytes, "max_packet_bytes")
    _positive(max_artifact_bytes, "max_artifact_bytes")
    if encoding not in ("native", "notation"):
        raise ValueError("encoding must be native or notation")
    if type(notation_limits) is not NotationLimits:
        raise ValueError("expected notation Limits")
    p.validate(document, limits=limits)
    content = format_document(document) if encoding == "native" else pretty(document, limits=notation_limits)
    if encoding == "native" and native(content) != document:
        raise AssertionError("native delivery roundtrip failed")
    # The full artifact must fit even when the caller will send only the packet.
    artifact = _wire({"version": "scir-delivery-artifact/1", "guards": header.get("guards", {}),
                      "kind": header["kind"], "value": audit_value})
    artifact_size = len(artifact.encode("utf-8"))
    if artifact_size > max_artifact_bytes:
        raise p.LimitError("delivery artifact byte budget exceeded")
    packet = _wire({**header, "version": VERSION, "profile": "working/1", "encoding": encoding,
                    "content": content, "artifact": {"sha256": _sha(artifact), "bytes": artifact_size},
                    "complete": True})
    if len(packet.encode("utf-8")) > max_packet_bytes:
        raise p.LimitError("delivery packet byte budget exceeded")
    return Delivery(packet, artifact)


def selection(index: Index, identifiers: tuple[str, ...], *, encoding: str = "native",
              guards: tuple[tuple[str, str], ...] = (), limits: p.Limits = p.Limits(),
              max_records: int = 10_000, max_packet_bytes: int = 16_000_000,
              max_artifact_bytes: int = 16_000_000,
              notation_limits: NotationLimits = NotationLimits()) -> Delivery:
    """Deliver complete referenced context; separate only redundant audit details."""
    host = _guards(guards)
    selected = _select_content(index, identifiers, limits=limits, max_records=max_records)
    return _bundle({"kind": "selection", "collection": index.collection,
                    "source_snapshot": index.snapshot, "requested_ids": list(selected.requested_ids),
                    "content_scope": "reference-closed-records", "guards": host},
                   selected.document, selected.as_dict(), encoding=encoding, limits=limits,
                   notation_limits=notation_limits, max_packet_bytes=max_packet_bytes,
                   max_artifact_bytes=max_artifact_bytes)


def proposal(index: Index, source: str, *, encoding: str = "native",
             guards: tuple[tuple[str, str], ...] = (), limits: p.Limits = p.Limits(),
             max_records: int = 10_000, max_operations: int = 1024,
             max_request_bytes: int = 1_000_000, max_packet_bytes: int = 16_000_000,
             max_artifact_bytes: int = 16_000_000,
             notation_limits: NotationLimits = NotationLimits()) -> Delivery:
    """Deliver a labelled delta, not a complete context packet or a persistent write."""
    host = _guards(guards)
    proposed = _propose_content(index, source, limits=limits, max_records=max_records,
                                max_operations=max_operations, max_request_bytes=max_request_bytes)
    final_ids = {term.args[0].symbol for term in proposed.document}
    changed = tuple(term for term in proposed.document if term.args[0].symbol not in index.records
                    or term != index.records[term.args[0].symbol].term)
    return _bundle({"kind": "proposal", "collection": index.collection,
                    "before_snapshot": index.snapshot, "candidate_snapshot": proposed.candidate_snapshot,
                    "content_scope": "changed-records", "context_complete": False,
                    "deleted_ids": [i for i in index.records if i not in final_ids], "guards": host,
                    "validation": {"profile": "working/1", "complete_candidate": True}},
                   changed, proposed.as_dict(), encoding=encoding, limits=limits,
                   notation_limits=notation_limits, max_packet_bytes=max_packet_bytes,
                   max_artifact_bytes=max_artifact_bytes)
