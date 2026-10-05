"""Repository source locations, resolved statically without importing test code."""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
import re

MAX_SOURCE_BYTES = 2_000_000


def local_file(root: Path, name: str, suffix: str, *, missing_error=ValueError) -> Path:
    parts = name.split("/")
    if ("\\" in name or ":" in name or any(p in ("", ".", "..") for p in parts)
            or PurePosixPath(name).is_absolute() or not name.endswith(suffix)):
        raise ValueError(f"expected a repository-relative {suffix} file: {name!r}")
    path = root.resolve()
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"symlink is not a source reference: {name!r}")
    if not path.is_file():
        raise missing_error(f"missing source file: {name!r}")
    return path


def read_source(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        from scir.profile import LimitError
        raise LimitError("repository source byte limit exceeded")
    return raw.decode("utf-8")


def declarations(root: Path, name: str, kind: str) -> list[str]:
    suffix = {"section": ".md", "test": ".py", "model": ".lean"}[kind]
    path = local_file(root, name, suffix)
    # Inspection accepts ordinary source line endings; stored source and view
    # bytes are neither normalized nor rewritten by this location resolver.
    text = read_source(path).replace("\r\n", "\n").replace("\r", "\n")
    if kind == "section":
        text = re.sub(r"^```[^\n]*\n.*?^```[ \t]*$", "", text, flags=re.M | re.S)
        return re.findall(r"^#{1,6} (.+?)\s*$", text, flags=re.M)
    if kind == "test":
        if not name.startswith("tests/") or not path.name.startswith("test_"):
            raise ValueError("test references must name tests/test_*.py files")
        try:
            module = ast.parse(text, filename=name)
        except SyntaxError as error:
            raise ValueError(f"test file does not parse: {name!r}") from error
        return [f"{cls.name}.{method.name}"
                for cls in module.body if isinstance(cls, ast.ClassDef)
                if any(isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                       and base.value.id == "unittest" and base.attr == "TestCase" for base in cls.bases)
                for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")]
    if not name.startswith("proofs/"):
        raise ValueError("model references must name proofs/*.lean files")
    # Declaration bookkeeping, not elaboration or axiom auditing.
    text = re.sub(r"/-.*?-/|--[^\n]*", "", text, flags=re.S)
    return re.findall(r"^theorem ([A-Za-z_][A-Za-z_0-9]*)\b", text, flags=re.M)
