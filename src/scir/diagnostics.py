"""Read-only structural costs. These reports do not judge relevance or deliver content."""
from __future__ import annotations

import json
from . import profile as p
from .core import format_document
from ._profile_native import native
from .knowledge import Index, _positive, _select_content
from .notation import Limits as NotationLimits, pretty

VERSION = "scir-selection-diagnostics/1"


def diagnose(index: Index, identifiers: tuple[str, ...], *, encoding: str = "native",
             limits: p.Limits = p.Limits(), max_records: int = 10_000,
             max_output_bytes: int = 16_000_000,
             notation_limits: NotationLimits = NotationLimits()) -> dict:
    """Count exact bytes and distinct declared edges; return a caller-owned report.

    A completed report can record an incomplete encoding check. It is not a
    selection delivery or a statement that its declared context is sufficient.
    """
    if encoding not in ("native", "notation"):
        raise ValueError("encoding must be native or notation")
    if type(notation_limits) is not NotationLimits:
        raise ValueError("expected notation Limits")
    _positive(max_output_bytes, "max_output_bytes")
    selection = _select_content(index, identifiers, limits=limits, max_records=max_records)
    total = p.measure(index.document, limits=limits)
    selected = p.measure(selection.document, limits=limits)
    chosen = set(selection.selected_ids)
    dependency_count = sum(1 for dependents in index.dependents.values()
                           for identifier in dependents if identifier in chosen)
    reference_count = sum(len(index.references[i]) for i in chosen)
    original_packet = json.dumps(selection.as_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
    encoding_check = {"encoding": encoding, "complete": True, "bytes": selected.bytes}
    try:
        if encoding == "notation":
            rendered = pretty(selection.document, limits=notation_limits)
        else:
            rendered = format_document(selection.document)
            if native(rendered) != selection.document:
                raise AssertionError("native delivery roundtrip failed")
        encoding_check["bytes"] = len(rendered.encode("utf-8"))
    except p.LimitError as error:
        encoding_check.update(complete=False, bytes=None, reason=str(error))
    result = {
        "version": VERSION, "profile": "working/1", "collection": index.collection,
        "source_snapshot": index.snapshot, "requested_ids": list(selection.requested_ids),
        "selected_ids": list(selection.selected_ids),
        "total": {"records": len(index.records), "canonical_bytes": total.bytes,
                  "nodes": total.nodes, "depth": total.depth},
        "selected": {"records": len(chosen), "canonical_bytes": selected.bytes,
                     "nodes": selected.nodes, "depth": selected.depth,
                     "reference_edges": reference_count, "dependency_edges": dependency_count,
                     "other_reference_edges": reference_count - dependency_count},
        "legacy_packet_bytes": len(original_packet.encode("utf-8")),
        "encoding_check": encoding_check,
        "reasons": selection.as_dict()["reasons"],
        "complete": True, "content_delivered": False,
    }
    wire = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(wire.encode("utf-8")) > max_output_bytes:
        raise p.LimitError("diagnostic report byte budget exceeded")
    return result
