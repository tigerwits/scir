"""The public package boundary and source metadata."""
import ast
from pathlib import Path
import unittest

import scir
from scir import FORMAT_VERSION, digest, parse_document, parse_pattern, query
from scir.relations import VERSION, decode, encode

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_public_api_is_deliberate(self):
        expected = {
            "Term", "Document", "ParseError", "FORMAT_VERSION", "parse",
            "parse_document", "format_document", "parse_pattern", "match",
            "query", "validate", "digest", "diff", "replace_at",
        }
        self.assertEqual(set(scir.__all__), expected)
        self.assertTrue(all(hasattr(scir, name) for name in expected))
        for name in ("Node", "Var", "Pattern", "Hit", "Difference", "walk", "at", "instantiate"):
            self.assertFalse(hasattr(scir, name), name)

    def test_version_has_one_literal_source(self):
        source = ast.parse(Path(scir.__file__).read_text(encoding="utf-8"))
        values = [ast.literal_eval(node.value) for node in source.body
                  if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)]
        self.assertEqual(values, [scir.__version__])
        self.assertEqual(scir.__version__, "1.0.0")
        self.assertEqual(FORMAT_VERSION, "1.0")
        self.assertEqual(VERSION, f"scir-relations/{FORMAT_VERSION}")
        metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = {attr = "scir.__version__"}', metadata)
        self.assertIn('name = "symbolic-content-ir"', metadata)
        self.assertIn('license = "MIT"', metadata)

    def test_typed_marker_exists(self):
        self.assertTrue(Path(scir.__file__).with_name("py.typed").is_file())

    def test_primary_query_example(self):
        doc = parse_document("think(Bob, use(Alice, SalesData))")
        pattern = parse_pattern("use(Alice, ?data)")
        self.assertEqual(query(doc, pattern), [])
        hit = query(doc, pattern, scope="all")[0]
        self.assertEqual(hit.path, (0, 1))
        self.assertEqual(str(hit.bindings["data"]), "SalesData")
        self.assertEqual(digest(doc), digest(parse_document(str(doc[0]) + "\n")))

    def test_unsupported_transport_version_is_rejected(self):
        wire = encode(parse_document("A"))
        wire["version"] = "scir-relations/999.0"
        with self.assertRaisesRegex(ValueError, "unsupported relational version"):
            decode(wire)


if __name__ == "__main__":
    unittest.main()
