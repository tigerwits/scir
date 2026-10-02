"""Check a fixed authored example and construct a candidate without writing it."""
from pathlib import Path
import json
from scir import parse_document, format_document
from scir.notation import lower
from scir.knowledge import build_index, select, affected
from scir.changes import propose


def main():
    root = Path(__file__).resolve().parent
    native = (root / "notes.scir").read_text(encoding="utf-8")
    document = parse_document(native)
    assert format_document(document) == native
    assert lower((root / "notes.scix").read_text(encoding="utf-8")) == document
    index = build_index(document, collection="example")
    packet = select(index, ("T1",))
    assert packet.selected_ids == ("A1", "D1", "T1")
    assert affected(index, ("A1",)) == ("A1", "D1", "T1")
    request = json.dumps({"version": "scir-change/1", "collection": "example",
        "expected_snapshot": index.snapshot,
        "operations": [{"op": "setField", "id": "T1", "field": "status", "value": "ready"}]})
    result = propose(index, request)
    assert result.document[0:2] == document[0:2]
    assert result.document[3] == document[3]
    assert index.document == document
    print(json.dumps({"selected": packet.selected_ids, "review": affected(index, ("A1",)),
                      "before": index.snapshot, "candidate": result.candidate_snapshot,
                      "source_written": False}))


if __name__ == "__main__":
    main()
