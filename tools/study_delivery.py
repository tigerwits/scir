"""Measure complete optional delivery costs on small public synthetic collections."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

from scir import Term, format_document, parse_document
from scir import delivery, profile as p
from scir.changes import propose
from scir.knowledge import build_index, select
from scir.notation import lower


def wire(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def measure(text):
    raw = text.encode("utf-8")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def study():
    payloads, observations = {}, []
    for topology in ("independent", "modules", "chain"):
        records = []
        for number in range(128):
            fields = ()
            if number and (topology == "chain" or topology == "modules" and number % 8):
                fields = (("dependsOn", p.tuple_value((p.reference("R" + str(number - 1)),))),)
            records.append(p.application("record", (Term("R" + str(number)), Term("Note"),
                                                      p.text("Public fixture, not evidence.")), fields=fields))
        document = tuple(records)
        index = build_index(document, collection="delivery-study")
        selected = select(index, ("R127",))
        request = wire({"version": "scir-change/1", "collection": index.collection,
                        "expected_snapshot": index.snapshot, "operations": [
                            {"op": "setField", "id": "R127", "field": "reason", "value": "reviewed"}]})
        complete = propose(index, request)
        for kind, full in (("selection", selected.as_dict()), ("proposal", complete.as_dict())):
            label = topology + "-" + kind
            original = json.dumps(full, ensure_ascii=False, separators=(",", ":")) + "\n"
            payloads[label + "-full.json"] = original
            for encoding in ("native", "notation"):
                result = (delivery.selection(index, ("R127",), encoding=encoding) if kind == "selection"
                          else delivery.proposal(index, request, encoding=encoding))
                packet = json.loads(result.packet)
                decoded = (parse_document if encoding == "native" else lower)(packet["content"])
                expected = selected.document if kind == "selection" else complete.document[-1:]
                if decoded != expected or json.loads(result.artifact)["value"] != full:
                    raise AssertionError("delivery changed selected content or complete candidate")
                name = label + "-" + encoding
                payloads[name + "-packet.json"] = result.packet
                payloads[name + "-artifact.json"] = result.artifact
                observations.append({"topology": topology, "kind": kind, "encoding": encoding,
                                     "selected_records": len(decoded), "legacy_bytes": len(original.encode()),
                                     "packet_bytes": len(result.packet.encode()),
                                     "artifact_bytes": len(result.artifact.encode()),
                                     "packet_and_artifact_bytes": len((result.packet + result.artifact).encode())})
        if format_document(index.document) != format_document(document):
            raise AssertionError("source changed")
    return {"schema": "scir-delivery-costs/1", "python": platform.python_version(),
            "observations": observations, "payloads": {name: measure(text) for name, text in payloads.items()},
            "source_written": False, "agent_trials": 0, "tokens": "unmeasured",
            "scope": "Exact UTF-8 response bytes; later artifact reads count. No latency or model-quality claim."}, payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("use a fresh evidence directory")
    report, payloads = study()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, text in payloads.items():
        (args.output / name).write_bytes(text.encode("utf-8"))
    for name in ("tools/study_delivery.py", "src/scir/delivery.py", "src/scir/changes.py", "src/scir/knowledge.py"):
        raw = (Path(__file__).resolve().parents[1] / name).read_bytes()
        report.setdefault("sources", {})[name] = hashlib.sha256(raw).hexdigest()
    (args.output / "results.json").write_bytes(wire(report).encode("utf-8"))
    print(wire(report), end="")


if __name__ == "__main__":
    main()
