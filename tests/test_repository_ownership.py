"""Published editing hints must point to authoring sources, not derived views."""
from pathlib import Path
import ast
import unittest
from scir import parse_document
from spec import catalog, documents, repository

ROOT = Path(__file__).resolve().parents[1]


class RepositoryOwnershipTests(unittest.TestCase):
    def test_spec_and_generated_hints_name_the_authoritative_shard(self):
        index = repository.load(ROOT)
        source = documents.render_document(index, "SPEC.md")
        self.assertIn("SCIR records own this entire contract", source)
        document = parse_document((ROOT / "tests/fixtures/native-migration.scir").read_text(encoding="utf-8"))
        for examples in (False, True):
            banner = catalog.render_queries(document, examples=examples).splitlines()[0]
            self.assertIn("spec/native.scir", banner)
            self.assertNotIn("spec/requirements.scir", banner)
        for name in ("SPEC.md", "docs/api.md"):
            self.assertNotIn("Maintained in spec/requirements.scir", documents.render_document(index, name))

    def test_reusable_catalog_does_not_import_or_dispatch_to_orchestration(self):
        source = (ROOT / "spec/catalog.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        self.assertFalse(any(isinstance(n, ast.FunctionDef) and n.name in ("main", "_repository") for n in module.body))
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, ("repository", "check"))
                self.assertFalse(any(n.name in ("repository", "check") for n in node.names) and node.module in (None, "spec"))
