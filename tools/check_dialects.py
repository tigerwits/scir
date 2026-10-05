#!/usr/bin/env python3
"""Validate SCIR's own repository contract on an isolated, hash-checked file basis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

import scir
from scir.changes import ConflictError
from scir.constraints import Violation
from scir.dialects import Context, Dialect, Rule, evaluate
from scir.profile import ProfileError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spec import handoff, repository


def code_identity():
    files = {"scir/" + p.name: p for p in Path(scir.__file__).resolve().parent.glob("*.py")}
    files.update(("spec/" + p.name, p) for p in (ROOT / "spec").glob("*.py"))
    files["tools/check_dialects.py"] = Path(__file__).resolve()
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
    return hashlib.sha256(handoff.wire(hashes).encode("utf-8")).hexdigest()


def run():
    index = repository.load(ROOT)
    basis = handoff.capture(ROOT, index, repository.sources(ROOT), extra=("tools/check_dialects.py",))
    identity = code_identity()
    context = Context("scir-repository-inputs/1", basis.fingerprint)
    with tempfile.TemporaryDirectory(prefix="scir-dialect-basis-") as temporary:
        snapshot = Path(temporary)
        for name, expected in basis.files:
            raw = (ROOT / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ConflictError("repository input changed before snapshot copy")
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)

        def local_contract(document, fixed_context):
            if fixed_context != context:
                raise ValueError("incorrect fixed repository basis")
            try:
                repository.validate(document, snapshot)
            except ProfileError as error:
                yield Violation(None, "repository-contract", str(error))

        # The repository contract owns profile, link and view checks. Do not
        # repeat its structural/index validation in preliminary adapter stages.
        contract = Dialect("scir-repository", "2", (
            Rule("repository", "2", identity, local_contract),
        ))
        result = evaluate(index.document, contract, context, collection=index.collection)
        if not result.conforms:
            raise ValueError("repository dialect did not conform: " + result.outcome)
    if handoff.capture(ROOT, index, repository.sources(ROOT), extra=("tools/check_dialects.py",)) != basis or code_identity() != identity:
        raise ConflictError("repository inputs or checker files changed during evaluation")
    return {"example": "repository-dialect/1", "validation": result.as_dict(),
            "input_basis": basis.packet(), "source_written": False, "agent_trials": 0,
            "scope": "Declared repository contract on a fixed file copy; linked tests were not executed."}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
