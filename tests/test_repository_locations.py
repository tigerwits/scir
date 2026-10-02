"""Legacy and working catalogs use one bounded static-location resolver."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scir import parse_document
from scir.profile import LimitError
from spec import check, catalog, locations


class RepositoryLocationTests(unittest.TestCase):
    def test_line_endings_are_inspected_without_rewriting_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            path = root / "docs/rules.md"
            for newline in ("\n", "\r\n", "\r"):
                raw = newline.join(("# Visible", "```text", "# Hidden", "```", "## Other", "")).encode()
                path.write_bytes(raw)
                self.assertEqual(locations.declarations(root, "docs/rules.md", "section"), ["Visible", "Other"])
                self.assertEqual(path.read_bytes(), raw)
            self.assertIs(check.local_file, locations.local_file)

    def test_legacy_locations_delegate_to_the_shared_resolver(self):
        document = parse_document('requirement(R, Core, p)\nspecifiedBy(R, section("rules.md", Rules))\ncoveredBy(R, test("tests/test_rules.py", "Rules.test_ok"))')
        def names(root, name, kind):
            return ["Rules"] if kind == "section" else ["Rules.test_ok"]
        with patch.object(catalog, "source_declarations", side_effect=names) as resolve:
            self.assertEqual(check.validate_catalog(document), ())
        self.assertEqual([call.args[1:] for call in resolve.call_args_list], [
            ("rules.md", "section"), ("tests/test_rules.py", "test")])

    def test_resource_failure_is_incomplete_not_a_missing_location(self):
        document = parse_document('requirement(R, Core, p)\nspecifiedBy(R, section("rules.md", Rules))')
        with patch.object(catalog, "source_declarations", side_effect=LimitError("source budget")):
            with self.assertRaises(LimitError):
                check.validate_catalog(document)

    def test_static_test_inspection_never_imports_and_still_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            raw = b'import unittest\r\nraise RuntimeError("must not import")\r\nclass Rules(unittest.TestCase):\r\n    def test_ok(self): pass\r\n'
            path = root / "tests/test_rules.py"
            path.write_bytes(raw)
            self.assertEqual(locations.declarations(root, "tests/test_rules.py", "test"), ["Rules.test_ok"])
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(ValueError):
                locations.declarations(root, "tests/../test_rules.py", "test")
