"""Execute substitution and matching laws against public Python operations."""
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

if __package__:
    from .check_symbol_reference import audit_axioms, raw_relations, wire
else:
    from check_symbol_reference import audit_axioms, raw_relations, wire

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scir import Term
from scir.patterns import Node, Var, instantiate, match, substitute
from scir.relations import decode, encode

REVISION = "scir-substitution-reference/1"
SEED = 1931


def variable(name):
    return "Var", ((name, ()),)


def node(label, *children):
    return "Node", ((label, ()), *children)


def request(operation, pattern, values):
    value = {"version": REVISION, "operation": operation, "pattern": raw_relations((pattern,))}
    if operation == "match":
        value["document"] = raw_relations((values,))
    else:
        key = "substitutions" if operation == "substitute" else "bindings"
        value[key] = [[name, raw_relations((term,))] for name, term in values]
    return value


def corpus():
    @cache
    def forests(size, open_terms):
        if size == 0:
            return ((),)
        return tuple((head,) + tail for first in range(1, size + 1)
                     for head in trees(first, open_terms) for tail in forests(size - first, open_terms))
    @cache
    def trees(size, open_terms):
        variables = (variable("x"), variable("y")) if size == 1 and open_terms else ()
        return variables + tuple(node(label, *children) if open_terms else (label, children)
                                 for label in ("A", "f") for children in forests(size - 1, open_terms))
    patterns = sum((trees(size, True) for size in range(1, 4)), ())
    ground = sum((trees(size, False) for size in range(1, 4)), ())
    options = (variable("x"), variable("y"), node("A"), node("f"))
    mappings = [[], *[[["x", x], ["y", y]] for x, y in product(options, repeat=2)]]
    bindings = [[[name, value] for name, value in zip(("x", "y"), values) if value is not None]
                for values in product((None, ("A", ()), ("f", ())), repeat=2)]
    cases = [("exhaustive-substitute", request("substitute", p, names)) for p in patterns for names in mappings]
    cases += [("exhaustive-match", request("match", p, t)) for p in patterns for t in ground]
    cases += [("exhaustive-instantiate", request("instantiate", p, env)) for p in patterns for env in bindings]
    rng = random.Random(SEED)
    labels = ("A", "f", "x", "?x", "λ", "é", "e\u0301", "scir.ref", "Node", "Var")
    def generated(depth=0, open_terms=True):
        if open_terms and rng.randrange(3) == 0:
            return variable(rng.choice(("x", "y")))
        children = tuple(generated(depth + 1, open_terms) for _ in range(rng.randrange(4) if depth < 3 else 0))
        label = rng.choice(labels)
        return node(label, *children) if open_terms else (label, children)
    for _ in range(128):
        operation = rng.choice(("substitute", "instantiate", "match"))
        p = generated()
        values = generated(open_terms=False) if operation == "match" else [
            (name, generated(open_terms=operation == "substitute")) for name in ("x", "y") if rng.randrange(2)]
        cases.append(("seeded", request(operation, p, values)))
    authored = (
        request("substitute", node("pair", variable("x"), variable("y")),
                [("x", variable("y")), ("y", node("A"))]),
        request("substitute", variable("x"), [("x", node("f", variable("x")))]),
        request("substitute", node("x", variable("x"), node("?x")), [("x", node("A"))]),
        request("substitute", node("lambda", node("x"), variable("x")), [("x", variable("y"))]),
        request("match", node("f", variable("x"), variable("x")), ("f", (("A", ()), ("B", ())))),
        request("match", node("f", variable("x"), variable("x")), ("f", (("A", ()), ("A", ())))),
        request("match", node("A"), ("A", ())),
        request("instantiate", variable("x"), [("unused", ("B", ()))]),
        request("instantiate", node("f", variable("x"), variable("x")), [("x", ("A", ()))]),
        request("match", node("é", variable("x")), ("e\u0301", (("A", ()),))),
        request("substitute", node("Var", variable("x")), [("x", node("Node"))]),
    )
    return cases + [("authored", value) for value in authored]


def pattern_value(value):
    """Test-only inverse of the explicit native constructor lowering."""
    term, = decode(value)
    def read(term):
        if term.symbol == "Var" and len(term.args) == 1 and not term.args[0].args:
            return Var(term.args[0].symbol)
        if term.symbol == "Node" and term.args and not term.args[0].args:
            return Node(term.args[0].symbol, tuple(read(child) for child in term.args[1:]))
        raise ValueError("invalid test-only pattern lowering")
    return read(term)


def pattern_wire(pattern):
    def lower(pattern):
        if type(pattern) is Var:
            return Term("Var", (Term(pattern.name),))
        return Term("Node", (Term(pattern.symbol), *(lower(child) for child in pattern.args)))
    return encode((lower(pattern),))


def runtime_observation(value, *, mutant=None):
    pattern = pattern_value(value["pattern"])
    operation = value["operation"]
    if operation == "substitute":
        names = {name: pattern_value(term) for name, term in value["substitutions"]}
        if mutant == "sequential-substitution":
            for name, replacement in names.items():
                pattern = substitute(pattern, {name: replacement})
        else:
            pattern = substitute(pattern, names)
        return {"status": "complete", "pattern": pattern_wire(pattern)}
    if operation == "instantiate":
        bindings = {name: decode(term)[0] for name, term in value["bindings"]}
        try:
            return {"status": "complete", "document": encode((instantiate(pattern, bindings),))}
        except ValueError as error:
            return {"status": "rejected", "message": str(error)}
    if operation != "match":
        raise ValueError("unknown test operation")
    subject, = decode(value["document"])
    if mutant == "ignore-repeated-captures":
        bindings, pending = {}, [(pattern, subject)]
        while pending:
            p, t = pending.pop()
            if type(p) is Var:
                bindings[p.name] = t
            elif p.symbol != t.symbol or len(p.args) != len(t.args):
                bindings = None
                break
            else:
                pending.extend(zip(p.args, t.args))
    else:
        bindings = match(pattern, subject)
    if bindings is None:
        return {"status": "complete", "matched": False}
    return {"status": "complete", "matched": True,
            "bindings": {name: encode((tree,)) for name, tree in bindings.items()},
            "document": encode((instantiate(pattern, bindings),))}


def semantic_observation(value):
    if value.get("status") in ("rejected", "incomplete"):
        return {"status": value["status"]}  # Diagnostic prose is not a semantic value.
    return value


def boundary_cases():
    base = request("substitute", variable("x"), [])
    growth = request("substitute", node("f", *(variable("x") for _ in range(64))),
                     [("x", node("g", *(node("A") for _ in range(64))))])
    deep = node("A")
    for _ in range(129):
        deep = node("f", deep)
    return [
        ("revision", {**base, "version": "unknown"}, "rejected"),
        ("operation", {**base, "operation": "unknown"}, "rejected"),
        ("wildcard-input", request("substitute", variable("_"), []), "rejected"),
        ("wildcard-unused", request("substitute", node("A"), [("x", variable("_"))]), "rejected"),
        ("wildcard-key", request("substitute", node("A"), [("_", node("B"))]), "rejected"),
        ("variable-name", request("substitute", variable("λ"), []), "rejected"),
        ("duplicate-key", request("substitute", variable("x"), [("x", node("A")), ("x", node("B"))]), "rejected"),
        ("malformed-pattern", request("substitute", ("Other", ()), []), "rejected"),
        ("depth", request("substitute", deep, []), "incomplete"),
        ("output-growth", growth, "incomplete"),
    ]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_substitution_reference.py /path/to/pinned/lean")
    lean = str(Path(sys.argv[1]).resolve())
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    if "version 4.19.0" not in version:
        raise ValueError("expected the explicitly pinned Lean 4.19.0 toolchain")
    build = ROOT / ".build/substitution-reference"
    build.mkdir(parents=True, exist_ok=True)
    (build / "report.json").unlink(missing_ok=True)
    names = ("SymbolLaws", "ReferenceCodec", "SubstitutionLaws", "SubstitutionReference")
    models = [ROOT / f"proofs/{name}.lean" for name in names]
    paths = [*models, Path(__file__).resolve(), ROOT / "tools/check_symbol_reference.py",
             *sorted((ROOT / "src/scir").glob("*.py"))]
    def hashes():
        return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    before = hashes()
    env = {**os.environ, "LEAN_PATH": str(build)}
    assumptions = None
    for name, path in zip(names, models):
        code = re.sub(r"/-.*?-/|--[^\n]*", "", path.read_text(encoding="utf-8"), flags=re.S)
        if re.search(r"\b(sorry|admit|axiom|unsafe|partial|implemented_by)\b", code):
            raise ValueError("reference contains an admission or executable replacement")
        result = subprocess.run([lean, "-DwarningAsError=true", "-o", str(build / f"{name}.olean"),
                                 str(path)], cwd=ROOT, env=env, capture_output=True, text=True,
                                check=True, timeout=60)
        if name == "SymbolLaws":
            audit_axioms(code, result.stdout)
        if name == "SubstitutionLaws":
            assumptions = audit_axioms(code, result.stdout, namespace="SCIR.Substitution",
                                       kernels=("substitute", "instantiate", "matchReference"))
            (build / "axioms.txt").write_text(result.stdout, encoding="utf-8")
    cases, boundary = corpus(), boundary_cases()
    inputs = "".join(wire(value) for _, value in cases) + "".join(wire(value) for _, value, _ in boundary)
    (build / "inputs.jsonl").write_text(inputs, encoding="utf-8")
    command = [lean, "-DwarningAsError=true", "--run", str(models[-1])]
    result = subprocess.run(command, input=inputs, cwd=ROOT, env=env, capture_output=True,
                            text=True, check=True, timeout=60)
    (build / "reference.jsonl").write_text(result.stdout, encoding="utf-8")
    if result.stderr:
        raise ValueError("unexpected reference diagnostics: " + result.stderr)
    observations = [json.loads(line) for line in result.stdout.splitlines()]
    if len(observations) != len(cases) + len(boundary):
        raise ValueError("reference returned an incomplete protocol stream")
    actual = [runtime_observation(value) for _, value in cases]
    (build / "runtime.jsonl").write_text("".join(wire(value) for value in actual), encoding="utf-8")
    for index, (expected, value) in enumerate(zip(observations, actual)):
        if semantic_observation(expected) != semantic_observation(value):
            raise ValueError(f"runtime/reference mismatch at captured input {index}")
    for (name, _, status), value in zip(boundary, observations[len(cases):]):
        if value.get("status") != status or not value.get("message"):
            raise ValueError("wrong boundary observation: " + name)
    mutants = {}
    for mutant in ("sequential-substitution", "ignore-repeated-captures"):
        wrong = [i for i, (_, value) in enumerate(cases)
                 if semantic_observation(runtime_observation(value, mutant=mutant)) != semantic_observation(observations[i])]
        if not wrong:
            raise ValueError("corpus failed to detect meaningful mutant: " + mutant)
        mutants[mutant] = {"mismatches": len(wrong), "first_case": wrong[0]}
    if hashes() != before:
        raise ValueError("reference or runtime source changed during the gate")
    report = {"version": REVISION, "lean": version, "python": sys.version, "command": command,
              "lean_binary_sha256": hashlib.sha256(Path(lean).read_bytes()).hexdigest(),
              "compiled_model_sha256": hashlib.sha256((build / "SubstitutionLaws.olean").read_bytes()).hexdigest(),
              "seed": SEED, "counts": {kind: sum(group == kind for group, _ in cases)
                                          for kind in sorted({group for group, _ in cases})},
              "observations": {status: sum(value["status"] == status for value in actual)
                               for status in ("complete", "rejected")},
              "boundary_cases": len(boundary), "mutants": mutants, "axioms": assumptions,
              "source_sha256": before, "corpus_sha256": hashlib.sha256(inputs.encode()).hexdigest(),
              "status": "complete", "scope": "open substitution and successful reconstruction; Python, codecs and matcher completeness are tested, not proved"}
    (build / "report.json").write_text(wire(report), encoding="utf-8")
    print(f"SUBSTITUTION_REFERENCE_CHECKED={len(cases)}; boundary={len(boundary)}; "
          f"theorems={len(assumptions) - 3}; mutants={len(mutants)}; evidence=.build/substitution-reference/report.json")


if __name__ == "__main__":
    main()
