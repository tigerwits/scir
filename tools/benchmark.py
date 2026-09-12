"""Reproducible structural workloads; no timing gates or model claims."""
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
import tracemalloc

import scir
from scir import diff, format_document, parse_document, parse_pattern, query
from scir.relations import decode, encode


def measure(operation):
    operation()
    times = []
    for _ in range(3):
        gc.collect()
        start = time.perf_counter()
        operation()
        times.append((time.perf_counter() - start) * 1000)
    gc.collect()
    tracemalloc.start()
    try:
        operation()
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return {"median_ms": round(statistics.median(times), 3), "peak_bytes": peak}


def main():
    source = "think(Bob, mistakenly(use(Alice, yesterday(SalesData))))\n" * 5000
    document = parse_document(source)
    pattern = parse_pattern("use(Alice, ?data)")
    wire = encode(document)
    left = parse_document("f(" * 128 + "A" + ")" * 128)
    right = parse_document("f(" * 128 + "B" + ")" * 128)
    tail = "A;" * 100_000
    wide = "f(" + ",".join(["A"] * 10_000) + ")"

    def reject_tail():
        try:
            parse_document(tail, max_nodes=1)
        except scir.ParseError:
            return
        raise AssertionError("node budget was ignored")

    operations = {
        "parse_35000_occurrences": lambda: parse_document(source),
        "format_35000_occurrences": lambda: format_document(document),
        "query_35000_occurrences": lambda: query(document, pattern, scope="all"),
        "encode_35000_occurrences": lambda: encode(document),
        "decode_35000_occurrences": lambda: decode(wire),
        "diff_depth_128": lambda: diff(left, right),
        "parse_10000_children": lambda: parse_document(wide),
        "reject_after_one_node": reject_tail,
    }
    package = Path(scir.__file__).parent
    print(json.dumps({
        "python": platform.python_version(), "platform": platform.platform(),
        "implementation": scir.__version__, "format": scir.FORMAT_VERSION,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(package.glob("*.py"))},
        "method": "One warmup, median of three runs; separate tracemalloc run; inputs preallocated.",
        "measurements": {name: measure(operation) for name, operation in operations.items()},
        "limits": "Local timings and allocation peaks, not process RSS or model-performance evidence.",
    }, indent=2))


if __name__ == "__main__":
    main()
