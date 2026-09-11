"""Compare this checkout or --src PATH without timing assertions in unit tests."""
import argparse
import gc
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc


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
    return {'median_ms': round(statistics.median(times), 3), 'peak_bytes': peak}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', type=Path, default=Path(__file__).resolve().parents[1] / 'src')
    args = parser.parse_args()
    sys.path.insert(0, str(args.src))
    import scir
    from scir.relations import encode

    source = 'think(Bob, mistakenly(use(Alice, yesterday(SalesData))))\n' * 5000
    document = scir.parse_document(source)
    tail = 'A;' * 100_000
    left = scir.parse_document('f(' * 128 + 'A' + ')' * 128)
    right = scir.parse_document('f(' * 128 + 'B' + ')' * 128)

    def reject_tail():
        try:
            scir.parse_document(tail, max_nodes=1)
        except scir.ParseError:
            return
        raise AssertionError('node budget was ignored')

    cases = {
        'parse_35000_nodes': lambda: scir.parse_document(source),
        'reject_after_one_node': reject_tail,
        'encode_35000_nodes': lambda: encode(document),
        'diff_chain_depth_128': lambda: scir.diff(left, right),
    }
    print(json.dumps({
        'python': platform.python_version(),
        'scir_version': scir.__version__,
        'measurements': {name: measure(operation) for name, operation in cases.items()},
        'method': 'Three warm timing runs; separate tracemalloc peak run; inputs preallocated.',
        'limitations': 'Shared runtime; allocator peaks are not process RSS or universal guarantees.',
    }, indent=2))


if __name__ == '__main__':
    main()
