"""Fixed interoperability vectors; not just one implementation round-tripping itself."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from scir import FORMAT_VERSION, ParseError, digest, format_document, parse_document, parse_pattern, match
from scir.relations import decode, encode

VECTORS = json.loads((Path(__file__).resolve().parents[1] / "docs/conformance.json").read_text(encoding="utf-8"))


class ConformanceTests(unittest.TestCase):
    def test_frozen_format_identifier(self):
        self.assertEqual(VECTORS["format"], FORMAT_VERSION)
        self.assertEqual(FORMAT_VERSION, "1.0")

    def test_fixed_canonical_text_and_digest(self):
        for vector in VECTORS["content"]:
            with self.subTest(vector=vector["name"]):
                document = parse_document(vector["source"])
                self.assertEqual(format_document(document), vector["canonical"])
                self.assertEqual(digest(document), vector["sha256"])
                raw = b"scir:1.0:document\n" + vector["canonical"].encode("utf-8")
                self.assertEqual(hashlib.sha256(raw).hexdigest(), vector["sha256"])

    def test_fixed_occurrence_tables(self):
        vector = VECTORS["transport"]
        self.assertEqual(encode(parse_document(vector["canonical"])), vector["wire"])
        self.assertEqual(format_document(decode(vector["wire"])), vector["canonical"])

    def test_wire_is_order_independent_but_positions_are_not(self):
        vector = VECTORS["transport"]
        wire = copy.deepcopy(vector["wire"])
        for name in ("nodes", "args", "roots"):
            wire[name].reverse()
        self.assertEqual(format_document(decode(wire)), vector["canonical"])
        content = parse_document("f(A, B)")
        swapped = encode(content)
        swapped["args"][0][1], swapped["args"][1][1] = 1, 0
        self.assertEqual(format_document(decode(swapped)), "f(B, A)\n")
        self.assertNotEqual(digest(decode(swapped)), digest(content))

    def test_selected_invalid_sources(self):
        for source in VECTORS["reject_content"]:
            with self.subTest(source=source), self.assertRaises(ParseError):
                parse_document(source)

    def test_quoted_capture_is_data(self):
        term = parse_document('"?x"')[0]
        self.assertEqual(match(parse_pattern('"?x"'), term), {})
        self.assertEqual(match(parse_pattern('?value'), term), {"value": term})

    def test_reordering_roots_changes_fingerprint(self):
        document = parse_document("A; B")
        self.assertNotEqual(digest(document), digest(document[::-1]))
        self.assertNotEqual(digest(document), digest(document + (document[0],)))


if __name__ == "__main__":
    unittest.main()
