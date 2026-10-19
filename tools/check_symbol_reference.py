"""Run the pinned Lean reference against the public symbol API on captured inputs."""
from __future__ import annotations

from functools import cache
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scir import Term, relabel_symbols, symbol_occurrences
from scir.relations import decode, encode

REVISION = "scir-symbol-reference/1"
SEED = 7128


def wire(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def raw_relations(document):
    """Independent fixture encoder over tuples, without production tree helpers."""
    result = {"version": "scir-relations/1.0", "nodes": [], "args": [], "roots": []}
    def visit(term, parent, position):
        label, children = term
        ident = len(result["nodes"])
        result["nodes"].append([ident, label])
        if parent is None:
            result["roots"].append([position, ident])
        else:
            result["args"].append([parent, position, ident])
        for i, child in enumerate(children):
            visit(child, ident, i)
    for i, term in enumerate(document):
        visit(term, None, i)
    return result


def request(document, names):
    return {"version": REVISION, "operation": "relabel",
            "document": raw_relations(document), "renaming": names}


def corpus():
    """All forests with <=3 nodes over two labels; all total maps plus identity.

    Generation uses size partitions, not the implementation's traversal. Larger
    seeded trees and hand-authored noncommuting/Unicode/literal cases supplement it.
    """
    @cache
    def forests(size):
        if size == 0:
            return ((),)
        return tuple((head,) + tail for first in range(1, size + 1)
                     for head in trees(first) for tail in forests(size - first))
    @cache
    def trees(size):
        return tuple((label, children) for label in ("A", "B") for children in forests(size - 1))
    cases = []
    maps = [[], *[[["A", a], ["B", b]] for a, b in product(("A", "B"), repeat=2)]]
    for size in range(4):
        for forest in forests(size):
            for names in maps:
                cases.append(("exhaustive", request(forest, names)))
    rng = random.Random(SEED)
    labels = ("A", "B", "f", "λ", "é", "e\u0301", "scir.text", "A B", "line\nfeed", "🙂")
    def generated(depth=0):
        arity = rng.randrange(4) if depth < 3 else 0
        return rng.choice(labels), tuple(generated(depth + 1) for _ in range(arity))
    for _ in range(128):
        forest = tuple(generated() for _ in range(rng.randrange(4)))
        names = [[label, rng.choice(labels)] for label in labels if rng.randrange(2)]
        cases.append(("seeded", request(forest, names)))
    authored = (
        ((("f", (("A", ()), ("A", ()))), ("f", ()), ("A", (("f", ()),))),
         [["f", "g"], ["A", "B"]]),
        ((("A", (("B", ()),)),), [["A", "B"], ["B", "C"]]),
        ((("scir.text", (("A", ()),)),), [["A", "B"]]),
        ((("scir.ref", (("target", ()),)),), [["target", "next"]]),
        ((("f", (("A", ()), ("B", ()))),), [["A", "C"], ["B", "C"]]),
        ((("é", (("e\u0301", ()), ("🙂", ()))),), [["é", "e\u0301"], ["e\u0301", "é"]]),
    )
    cases.extend(("authored", request(document, names)) for document, names in authored)
    return cases


def runtime_observation(value, *, mutant=None):
    document = decode(value["document"])
    names = dict(value["renaming"])
    if mutant == "sequential-renaming":
        for source, target in value["renaming"]:
            document = relabel_symbols(document, {source: target})
    elif mutant == "leaf-only-renaming":
        def leaves(term):
            return Term(term.symbol if term.args else names.get(term.symbol, term.symbol),
                        tuple(leaves(child) for child in term.args))
        document = tuple(leaves(term) for term in document)
    elif mutant is None:
        document = relabel_symbols(document, names)
    else:
        raise ValueError("unknown test mutant")
    return {"status": "complete", "document": encode(document),
            "occurrences": [[list(path), label.value] for path, label in symbol_occurrences(document)]}


def boundary_cases():
    empty = request((), [])
    cyclic = {"version": "scir-relations/1.0", "nodes": [[0, "A"]],
              "args": [[0, 0, 0]], "roots": [[0, 0]]}
    shared = {"version": "scir-relations/1.0", "nodes": [[0, "A"], [1, "B"]],
              "args": [[0, 0, 1], [0, 1, 1]], "roots": [[0, 0]]}
    too_deep = ("A", ())
    for _ in range(129):
        too_deep = ("A", (too_deep,))
    return [
        ("revision", {**empty, "version": "unknown"}, "rejected"),
        ("operation", {**empty, "operation": "substitute"}, "rejected"),
        ("symbol", request((("", ()),), []), "rejected"),
        ("duplicate-map", {**empty, "renaming": [["A", "B"], ["A", "C"]]}, "rejected"),
        ("cycle", {**empty, "document": cyclic}, "rejected"),
        ("sharing", {**empty, "document": shared}, "rejected"),
        ("depth", request((too_deep,), []), "incomplete"),
        ("nodes", request(tuple(("A", ()) for _ in range(4097)), []), "incomplete"),
    ]


def audit_axioms(source, output, *, namespace="SCIR.Symbols",
                 kernels=("relabel", "relabelDocument", "documentOccurrences")):
    """Lean reports transitive assumptions; source scans alone are insufficient."""
    declarations = set(re.findall(r"^theorem ([A-Za-z_][A-Za-z_0-9]*)\b", source, re.M))
    prefix = re.escape(namespace)
    reports = dict(re.findall(rf"'{prefix}\.(\w+)' depends on axioms:\s*\[(.*?)\]", output, re.S))
    reports.update({name: "" for name in re.findall(
        rf"'{prefix}\.(\w+)' does not depend on any axioms", output)})
    expected = declarations | set(kernels)
    if not declarations or set(reports) != expected:
        raise ValueError("every exported theorem and executed kernel needs an assumption report")
    for name, values in reports.items():
        axioms = {item.strip() for item in values.split(",") if item.strip()}
        if not axioms <= {"propext", "Quot.sound"}:
            raise ValueError(f"unapproved transitive assumptions for {name}: {axioms}")
    return {name: [item.strip() for item in values.split(",") if item.strip()]
            for name, values in sorted(reports.items())}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_symbol_reference.py /path/to/pinned/lean")
    lean = str(Path(sys.argv[1]).resolve())
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    if "version 4.19.0" not in version:
        raise ValueError("expected the explicitly pinned Lean 4.19.0 toolchain")
    build = ROOT / ".build/symbol-reference"
    build.mkdir(parents=True, exist_ok=True)
    (build / "report.json").unlink(missing_ok=True)
    model = ROOT / "proofs/SymbolLaws.lean"
    driver = ROOT / "proofs/SymbolReference.lean"
    codec = ROOT / "proofs/ReferenceCodec.lean"
    paths = [model, driver, codec, Path(__file__).resolve(), *sorted((ROOT / "src/scir").glob("*.py"))]
    def hashes():
        return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    before = hashes()
    source = model.read_text(encoding="utf-8")
    for path in (model, driver, codec):
        code = re.sub(r"/-.*?-/|--[^\n]*", "", path.read_text(encoding="utf-8"), flags=re.S)
        if re.search(r"\b(sorry|admit|axiom|unsafe|partial|implemented_by)\b", code):
            raise ValueError("reference contains an admission or replacement executable")
    compile_result = subprocess.run([lean, "-DwarningAsError=true", "-o",
        str(build / "SymbolLaws.olean"), str(model)], cwd=ROOT, capture_output=True,
        text=True, timeout=60, check=True)
    (build / "axioms.txt").write_text(compile_result.stdout, encoding="utf-8")
    assumptions = audit_axioms(source, compile_result.stdout)
    env = {**os.environ, "LEAN_PATH": str(build)}
    subprocess.run([lean, "-DwarningAsError=true", "-o", str(build / "ReferenceCodec.olean"), str(codec)],
                   cwd=ROOT, env=env, capture_output=True, text=True, check=True, timeout=60)
    subprocess.run([lean, "-DwarningAsError=true", str(driver)], cwd=ROOT,
                   env=env, capture_output=True, text=True, check=True, timeout=60)
    cases, boundary = corpus(), boundary_cases()
    inputs = "".join(wire(value) for _, value in cases)
    inputs += "".join(wire(value) for _, value, _ in boundary)
    (build / "inputs.jsonl").write_text(inputs, encoding="utf-8")
    command = [lean, "-DwarningAsError=true", "--run", str(driver)]
    reference = subprocess.run(command, input=inputs, cwd=ROOT, env=env,
                               capture_output=True, text=True, timeout=60, check=True)
    (build / "reference.jsonl").write_text(reference.stdout, encoding="utf-8")
    if reference.stderr:
        raise ValueError("unexpected reference diagnostics: " + reference.stderr)
    observations = [json.loads(line) for line in reference.stdout.splitlines()]
    if len(observations) != len(cases) + len(boundary):
        raise ValueError("reference returned an incomplete protocol stream")
    actual = [runtime_observation(value) for _, value in cases]
    (build / "runtime.jsonl").write_text("".join(wire(value) for value in actual), encoding="utf-8")
    for index, (expected, value) in enumerate(zip(observations, actual)):
        if expected != value:
            raise ValueError(f"runtime/reference mismatch at captured input {index}")
    for (name, _, status), observed in zip(boundary, observations[len(cases):]):
        if observed.get("status") != status or not observed.get("message"):
            raise ValueError(f"wrong reference boundary observation for {name}")
    mutants = {}
    for mutant in ("sequential-renaming", "leaf-only-renaming"):
        mismatches = [i for i, (_, value) in enumerate(cases)
                      if runtime_observation(value, mutant=mutant) != observations[i]]
        if not mismatches:
            raise ValueError("corpus failed to detect meaningful mutant: " + mutant)
        mutants[mutant] = {"mismatches": len(mismatches), "first_case": mismatches[0]}
    if hashes() != before:
        raise ValueError("reference or runtime source changed during the gate")
    report = {"version": REVISION, "lean": version, "command": command,
              "lean_binary_sha256": hashlib.sha256(Path(lean).read_bytes()).hexdigest(),
              "compiled_model_sha256": hashlib.sha256((build / "SymbolLaws.olean").read_bytes()).hexdigest(),
              "python": sys.version,
              "seed": SEED, "counts": {kind: sum(group == kind for group, _ in cases)
                                         for kind in ("exhaustive", "seeded", "authored")},
              "boundary_cases": len(boundary), "mutants": mutants, "axioms": assumptions,
              "source_sha256": before,
              "corpus_sha256": hashlib.sha256(inputs.encode()).hexdigest(), "status": "complete",
              "scope": "finite symbol relabeling and ordered occurrence observations; codec and Python are tested, not proved"}
    (build / "report.json").write_text(wire(report), encoding="utf-8")
    print(f"SYMBOL_REFERENCE_CHECKED={len(cases)}; boundary={len(boundary)}; "
          f"theorems={len(assumptions) - 3}; mutants={len(mutants)}; evidence=.build/symbol-reference/report.json")


if __name__ == "__main__":
    main()
