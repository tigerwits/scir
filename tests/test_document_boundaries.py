"""Adversarial document failures and portable metadata boundaries."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scir import Term
from scir import profile as p
from scir.knowledge import build_index
from spec import documents, locations, repository


def record(identifier, *, kind="Guide", omit=(), **overrides):
    fields = dict(area=Term("Documentation"), ownership=Term("record"),
                  title=p.text("Title"), document=Term("guide.md"), level=Term("1"),
                  order=Term("0"), origin=Term("authored", (p.text("Independent fixture."),)))
    fields.update(overrides)
    for key in omit:
        del fields[key]
    payload = Term("blocks", (Term("paragraph", (p.text("Body"),)),))
    return p.application("record", (Term(identifier), Term(kind), payload), fields=tuple(fields.items()))


class DocumentBoundaryTests(unittest.TestCase):
    def test_malformed_forward_parent_is_profile_failure_not_key_error(self):
        child = record("Child", parent=p.reference("Parent"), level=Term("2"), order=Term("10"))
        for omitted in ("document", "level", "order"):
            parent = record("Parent", omit=(omitted,))
            for records in ((child, parent), (parent, child)):
                with self.subTest(omitted=omitted, child_first=records[0] == child):
                    index = build_index(records, collection="fixture")
                    with self.assertRaises(p.ProfileError):
                        documents.validate(index)
                    with self.assertRaises(p.ProfileError):
                        repository.validate(records)

    def test_logical_documents_cannot_shadow_the_two_authored_entrypoints(self):
        for name in ("README.md", "AGENTS.md"):
            with self.subTest(name=name), self.assertRaises(p.ProfileError):
                documents.validate(build_index((record("Shadow", document=Term(name)),), collection="fixture"))

    def test_skill_description_is_one_yaml_json_scalar(self):
        description = 'Use when text has: a colon # and "quotes".\n---\nname: not-the-skill'
        payload = Term("blocks", (Term("metadata", (Term("scir"), p.text(description))),))
        original = record("Skill", kind="Skill", level=Term("0"))
        term = Term(original.symbol, (*original.args[:2], payload, *original.args[3:]))
        index = build_index((term,), collection="fixture")
        documents.validate(index)
        rendered = documents.render_document(index, "guide.md")
        header = rendered.splitlines()
        self.assertEqual(len(header), 4)
        self.assertEqual(header[:2], ["---", "name: scir"])
        self.assertEqual(header[3], "---")
        self.assertEqual(json.loads(header[2].removeprefix("description: ")), description)

    def test_entrypoint_reads_are_bounded_and_missing_is_incomplete(self):
        index = build_index((record("Guide"),), collection="fixture")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in documents.MARKDOWN:
                (root / name).write_bytes(b"# Entry\n")
            with patch.object(locations, "MAX_SOURCE_BYTES", 4), self.assertRaises(p.LimitError):
                documents.rendered_documents(index, root)
            (root / "README.md").unlink()
            with self.assertRaises(FileNotFoundError):
                documents.rendered_documents(index, root)

    def test_entrypoint_symlink_is_rejected_before_reading(self):
        index = build_index((record("Guide"),), collection="fixture")
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "checkout"
            root.mkdir()
            (root / "AGENTS.md").write_bytes(b"# Entry\n")
            outside = parent / "outside.md"
            outside.write_bytes(b"Do not read this as a repository entrypoint.\n")
            try:
                (root / "README.md").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("platform does not permit creating symlinks")
            original = locations.read_source
            def bounded(path):
                self.assertNotEqual(path.name, "README.md", "symlink was opened")
                return original(path)
            with patch.object(locations, "read_source", bounded), self.assertRaises(ValueError):
                documents.rendered_documents(index, root)


if __name__ == "__main__":
    unittest.main()
