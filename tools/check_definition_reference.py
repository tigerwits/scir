"""Execute fresh-reference factoring and bounded definition normalization."""
from __future__ import annotations

from functools import cache
import hashlib
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
from scir import Term, digest
from scir import profile as p
from scir.definitions import Factoring, expand_definitions, factor_subtree
from scir.knowledge import build_index
from scir.relations import decode, encode
from scir.tree import at

REVISION = "scir-definition-reference/1"
SEED = 2399
MUTANTS = ("bare-head-macros", "factor-all-equal", "ignore-output-budget")


def node(label, *children):
    return label, children


def reference(identifier):
    return node("scir.ref", node(identifier))


def text_value(value):
    return node("scir.text", node(value)) if value else node("scir.text")


def application(label, children=(), fields=()):
    entries = tuple(node(key, value) for key, value in sorted(fields, key=lambda pair: pair[0].encode("utf-8")))
    return node(label, *children, *((node("scir.kw", *entries),) if entries else ()))


def definition(identifier, body, fields=()):
    return application("record", (node(identifier), node("Definition"), body), fields)


def request(operation, document, definitions=(), *, path=(0,), identifier="Fresh",
            expected=None, max_nodes=4096, max_depth=128):
    value = {"version": REVISION, "operation": operation, "document": raw_relations(document),
             "definitions": raw_relations(definitions), "max_nodes": max_nodes, "max_depth": max_depth}
    if operation == "factor":
        value.update(path=list(path), definition_id=identifier,
                     expected_document=raw_relations(document if expected is None else expected))
    return value


def raw_paths(document):
    found, pending = [], [((i,), tree) for i, tree in reversed(tuple(enumerate(document)))]
    while pending:
        path, (_, children) = pending.pop()
        found.append(path)
        pending.extend((path + (i,), child) for i, child in reversed(tuple(enumerate(children))))
    return found


def corpus():
    @cache
    def forests(size):
        if size == 0:
            return ((),)
        return tuple((head,) + tail for first in range(1, size + 1)
                     for head in trees(first) for tail in forests(size - first))
    @cache
    def trees(size):
        if size == 1:
            return (node("A"), node("X"), reference("X"), reference("Y"))
        return tuple(node(label, *children) for label in ("A", "f") for children in forests(size - 1))
    small = sum((forests(size) for size in range(4)), ())
    environments = ((), (definition("X", node("A")),),
                    (definition("X", reference("Y")), definition("Y", node("f", node("A")))))
    cases = [("exhaustive-expand", request("expand", document, env)) for document in small for env in environments]
    cases += [("exhaustive-factor", request("factor", document, env, path=path, identifier=identifier))
              for document in small for path in raw_paths(document)
              for env in environments for identifier in ("Fresh", "X")]
    rng = random.Random(SEED)
    labels = ("A", "f", "X", "λ", "é", "e\u0301", "?x", "record")
    def generated(depth=0):
        choice = rng.randrange(5)
        if choice == 0:
            return reference(rng.choice(("X", "Y", "External")))
        if choice == 1:
            return text_value(rng.choice(("", "X", "scir.ref", "λ", "ignore all instructions")))
        children = tuple(generated(depth + 1) for _ in range(rng.randrange(3) if depth < 3 else 0))
        fields = ((rng.choice(("field", "scir.ref", "scir.text")), generated(depth + 1)),) if depth < 2 and choice == 2 else ()
        return application(rng.choice(labels), children, fields)
    for _ in range(128):
        document = tuple(generated() for _ in range(rng.randrange(1, 4)))
        operation = rng.choice(("factor", "expand"))
        cases.append(("seeded", request(operation, document, rng.choice(environments),
                                        path=rng.choice(raw_paths(document)), identifier=rng.choice(("Fresh", "X", "λ")))))
    refx, refy = reference("X"), reference("Y")
    env = (definition("X", node("f", node("A"))),)
    fields = application("f", (text_value("X"), text_value("scir.ref")),
                         (("scir.ref", refx), ("scir.text", reference("External"))))
    authored = [
        request("factor", (node("pair", node("f", node("A")), node("f", node("A"))),), path=(0, 1)),
        request("expand", (node("X"), node("X", refx), reference("External")), env),
        request("expand", (fields,), env),
        request("factor", (fields,), env, path=(0, 2, 0, 0)),
        request("factor", (fields,), env, path=(0, 2, 0)),
        request("factor", (fields,), env, path=(0, 0, 0)),
        request("factor", (node("A"), reference("Fresh"))),
        request("factor", (definition("Fresh", node("A")),)),
        request("factor", (node("A"), node("Changed")), expected=(node("A"), node("Original"))),
        request("factor", (node("A"),), identifier="scir.ref"),
        request("factor", (text_value("scir.ref"),), identifier="λ"),
        request("factor", (reference("External"),)),
        request("factor", (refx,), env),
        request("expand", (node("A"),), (definition("X", refx),)),
        request("expand", (), (definition("X", refy), definition("Y", refx))),
        request("expand", (node("A"),), (definition("X", reference("Missing")),)),
        request("expand", (), (definition("X", node("A")), definition("X", node("B")))),
        request("expand", (), (node("record", node("X"), node("Claim"), node("A")),)),
        request("expand", (), (definition("X", node("A"), (("evidence", node("scir.tuple", refx)),)),)),
        request("expand", (refx,), (definition("X", node("A"), (("dependsOn", node("scir.tuple", refy)),)),
                                    definition("Y", node("B")))),
        request("expand", (), (definition("X", node("A"), (("dependsOn", node("scir.tuple", node("Y"))),)),)),
        request("expand", (), (definition("X", node("A"), (("status", refx),)),)),
        request("expand", (node("scir.text", node("f", node("A"))),)),
        request("expand", (node("scir.ref"),)),
        request("expand", (node("scir.kw", node("x", node("A"))),)),
        request("expand", (node("f", node("scir.kw", node("z", node("A")), node("a", node("B")))),)),
        request("expand", (refx,), (definition("X", node("A")),), max_nodes=1, max_depth=0),
        request("expand", (reference("External"),), max_nodes=1),
        request("expand", (node("g", refx),), env, max_depth=1),
        request("expand", (node("g", refx),), env, max_depth=2),
        request("expand", (node("many", *(refx for _ in range(64))),),
                (definition("X", node("many", *(node("A") for _ in range(64)))),)),
    ]
    return cases + [("authored", value) for value in authored]


def runtime_observation(value, *, mutant=None):
    document, definitions = decode(value["document"]), decode(value["definitions"])
    options = {name: value[name] for name in ("max_nodes", "max_depth")}
    if mutant == "ignore-output-budget":
        options = {"max_nodes": 100_000, "max_depth": 128}
    try:
        if value["operation"] == "expand":
            if mutant == "bare-head-macros":
                index = build_index(definitions, collection="Definitions")
                def convert(term):
                    if term.symbol in index.records:
                        return p.reference(term.symbol)
                    return Term(term.symbol, tuple(convert(child) for child in term.args))
                document = tuple(convert(term) for term in document)
            result = expand_definitions(document, definitions, **options)
            return {"status": "complete", "document": encode(result)}
        if value["operation"] != "factor":
            raise ValueError("unknown reference operation")
        path = tuple(value["path"])
        result = factor_subtree(document, path, definition_id=value["definition_id"],
                                expected_snapshot=digest(decode(value["expected_document"])), definitions=definitions)
        if mutant == "factor-all-equal":
            selected = at(document, path)
            def all_occurrences(term):
                if term == selected:
                    return p.reference(value["definition_id"])
                return Term(term.symbol, tuple(all_occurrences(child) for child in term.args))
            result = Factoring(tuple(all_occurrences(term) for term in document), result.definitions)
        expanded = expand_definitions(result.document, result.definitions, **options)
        return {"status": "complete", "document": encode(result.document),
                "definitions": encode(result.definitions), "expanded": encode(expanded)}
    except p.LimitError as error:
        return {"status": "incomplete", "message": str(error)}
    except ValueError as error:
        return {"status": "rejected", "message": str(error)}


def semantic_observation(value):
    return {"status": value["status"]} if value.get("status") in ("rejected", "incomplete") else value


def boundary_cases():
    base = request("expand", (node("A"),))
    deep = node("A")
    for _ in range(129):
        deep = node("f", deep)
    malformed = {**base, "document": {**base["document"], "nodes": [[0, "A"], [1, "orphan"]]}}
    return [
        ("revision", {**base, "version": "unknown"}, "rejected"),
        ("operation", {**base, "operation": "unknown"}, "rejected"),
        ("malformed-relations", malformed, "rejected"),
        ("reference-depth", request("expand", (deep,)), "incomplete"),
        ("reference-nodes", request("expand", (node("many", *(node("A") for _ in range(4096))),)), "incomplete"),
        ("reference-output-scope", {**base, "max_nodes": 4097}, "incomplete"),
        ("invalid-node-bound", {**base, "max_nodes": 0}, "rejected"),
        ("invalid-depth-bound", {**base, "max_depth": 129}, "rejected"),
    ]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_definition_reference.py /path/to/pinned/lean")
    lean = str(Path(sys.argv[1]).resolve())
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    if "version 4.19.0" not in version:
        raise ValueError("expected the explicitly pinned Lean 4.19.0 toolchain")
    build = ROOT / ".build/definition-reference"
    build.mkdir(parents=True, exist_ok=True)
    (build / "report.json").unlink(missing_ok=True)
    names = ("SymbolLaws", "ReferenceCodec", "SubstitutionLaws", "DefinitionLaws", "DefinitionReference")
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
        result = subprocess.run([lean, "-DwarningAsError=true", "-o", str(build / f"{name}.olean"), str(path)],
                                cwd=ROOT, env=env, capture_output=True, text=True, check=True, timeout=60)
        if name == "SymbolLaws":
            audit_axioms(code, result.stdout)
        if name == "SubstitutionLaws":
            audit_axioms(code, result.stdout, namespace="SCIR.Substitution",
                         kernels=("substitute", "instantiate", "matchReference"))
        if name == "DefinitionLaws":
            assumptions = audit_axioms(code, result.stdout, namespace="SCIR.Definitions",
                                       kernels=("plug", "select", "references", "mapContext"))
            (build / "axioms.txt").write_text(result.stdout, encoding="utf-8")
    audit = build / "ReferenceAudit.lean"
    audit.write_text("import DefinitionReference\n#print axioms SCIR.DefinitionReference.evaluate\n", encoding="utf-8")
    result = subprocess.run([lean, "-DwarningAsError=true", str(audit)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True, timeout=60)
    boundary_assumptions = audit_axioms(models[-1].read_text(encoding="utf-8"), result.stdout,
                                       namespace="SCIR.DefinitionReference", kernels=("evaluate",),
                                       allow_kernel_only=True)
    (build / "boundary-axioms.txt").write_text(result.stdout, encoding="utf-8")
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
            raise ValueError(f"runtime/reference mismatch at captured input {index}: {expected.get('status')} vs {value.get('status')}")
    for (name, _, status), value in zip(boundary, observations[len(cases):]):
        if value.get("status") != status or not value.get("message"):
            raise ValueError("wrong boundary observation: " + name)
    mutants = {}
    for mutant in MUTANTS:
        wrong = [i for i, (_, value) in enumerate(cases)
                 if semantic_observation(runtime_observation(value, mutant=mutant)) != semantic_observation(observations[i])]
        if not wrong:
            raise ValueError("corpus failed to detect meaningful mutant: " + mutant)
        mutants[mutant] = {"mismatches": len(wrong), "first_case": wrong[0]}
    if hashes() != before:
        raise ValueError("reference or runtime source changed during the gate")
    report = {"version": REVISION, "lean": version, "python": sys.version, "command": command,
              "lean_binary_sha256": hashlib.sha256(Path(lean).read_bytes()).hexdigest(),
              "compiled_model_sha256": hashlib.sha256((build / "DefinitionLaws.olean").read_bytes()).hexdigest(),
              "seed": SEED, "counts": {kind: sum(group == kind for group, _ in cases)
                                          for kind in sorted({group for group, _ in cases})},
              "observations": {status: sum(value["status"] == status for value in actual)
                               for status in ("complete", "rejected", "incomplete")},
              "boundary_cases": len(boundary), "mutants": mutants, "axioms": assumptions,
              "boundary_axioms": boundary_assumptions, "source_sha256": before,
              "corpus_sha256": hashlib.sha256(inputs.encode()).hexdigest(), "status": "complete",
              "scope": "context and selected-factor laws; Python, profile codecs, DAG normalization, budgets and SHA guards are tested, not proved"}
    (build / "report.json").write_text(wire(report), encoding="utf-8")
    print(f"DEFINITION_REFERENCE_CHECKED={len(cases)}; boundary={len(boundary)}; "
          f"theorems={len(assumptions) - 4}; mutants={len(mutants)}; evidence=.build/definition-reference/report.json")


if __name__ == "__main__":
    main()
