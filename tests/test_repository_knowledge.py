"""Repository bookkeeping is not evidence of execution, truth, or model success."""
from pathlib import Path
import tempfile
import unittest

from scir import Term, format_document, parse_document
from scir.knowledge import select
from scir.profile import ProfileError, application, reference, text, tuple_value
from spec.repository import load, validate
from spec.locations import declarations

ROOT = Path(__file__).resolve().parents[1]


def fixture(root):
    for directory in ("docs", "tests", "proofs", "spec"):
        (root / directory).mkdir()
    (root / "spec/native.scir").write_text("", encoding="utf-8", newline="\n")
    (root / "docs/rules.md").write_text("# Rules\n\n```text\n# Hidden\n```\n", encoding="utf-8", newline="\n")
    (root / "tests/test_rule.py").write_text(
        "import unittest\nraise RuntimeError('must not execute')\n"
        "class RuleTests(unittest.TestCase):\n    def test_rule(self): pass\n", encoding="utf-8", newline="\n")
    (root / "proofs/Laws.lean").write_text(
        "/- theorem fake : True := by trivial -/\ntheorem rule : True := by trivial\n", encoding="utf-8", newline="\n")


def record(identifier="R", kind="Requirement", **extra):
    fields = {"area": Term("Structured"), "ownership": Term("index"),
              "source": Term("section", (Term("docs/rules.md"), Term("Rules")))}
    if kind == "Requirement":
        fields["tests"] = tuple_value((Term("test", (Term("tests/test_rule.py"), Term("RuleTests.test_rule"))),))
    fields.update(extra)
    return application("record", (Term(identifier), Term(kind), Term("preserve")), fields=tuple(fields.items()))


class RepositoryKnowledgeTests(unittest.TestCase):
    def test_authored_catalog_and_legacy_projection_share_preserved_ids(self):
        index = load(ROOT)
        self.assertEqual(len(index.records), 54)
        legacy = parse_document((ROOT / "spec/requirements.scir").read_text(encoding="utf-8"))
        self.assertTrue({t.args[0].symbol for t in legacy if t.symbol == "requirement"} <= set(index.records))
        packet = select(index, ("NamedRoles",))
        self.assertTrue({"NamedRoles", "OptionalRoles", "TupleArity", "ModelProofBoundary"} <= set(packet.selected_ids))
        self.assertIn("test_duplicate_unsorted_and_misplaced_fields_fail", format_document(packet.document))

    def test_locations_do_not_import_tests_or_compile_proofs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            item = record(models=tuple_value((Term("model", (Term("proofs/Laws.lean"), Term("rule"))),)))
            self.assertEqual(tuple(validate((item,), root).records), ("R",))
            self.assertEqual(declarations(root, "proofs/Laws.lean", "model"), ["rule"])

    def test_unknown_fields_kinds_ownership_and_missing_test_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            bad = (record(typo=Term("value")), record(kind="Fact"), record(ownership=Term("both")),
                   record(tests=tuple_value()), record(area=Term("Unknown")), record(kind="Question"))
            for item in bad:
                with self.subTest(item=str(item)), self.assertRaises(ValueError):
                    validate((item,), root)

    def test_missing_ambiguous_and_fenced_locations_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            for name in ("Missing", "Hidden"):
                item = record(source=Term("section", (Term("docs/rules.md"), Term(name))))
                with self.assertRaises(ValueError):
                    validate((item,), root)
            (root / "docs/rules.md").write_text("# Rules\n# Rules\n", encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                validate((record(),), root)

    def test_path_traversal_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            for name in ("../rules.md", "/rules.md", "docs/../rules.md", "docs\\rules.md", "docs//rules.md"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    validate((record(source=Term("section", (Term(name), Term("Rules")))),), root)
            try:
                (root / "docs/link.md").symlink_to(root / "docs/rules.md")
            except OSError:
                return  # Windows without symlink privilege still runs traversal controls.
            with self.assertRaises(ValueError):
                validate((record(source=Term("section", (Term("docs/link.md"), Term("Rules")))),), root)

    def test_duplicate_links_and_dangling_references_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            target = Term("test", (Term("tests/test_rule.py"), Term("RuleTests.test_rule")))
            for item in (record(tests=tuple_value((target, target))),
                         record(evidence=tuple_value((reference("Missing"),)))):
                with self.assertRaises(ValueError):
                    validate((item,), root)

    def test_wrong_conclusion_with_valid_links_is_not_semantically_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            original = record()
            wrong = Term("record", original.args[:2] + (text("An unsupported conclusion."),) + original.args[3:])
            self.assertEqual(validate((wrong,), root).records["R"].payload, wrong.args[2])

    def test_canonical_load_and_empty_catalog_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            path = root / "spec/knowledge.scir"
            path.write_text(format_document((record(),)), encoding="utf-8", newline="\n")
            self.assertEqual(tuple(load(root).records), ("R",))
            path.write_text(str(record()), encoding="utf-8", newline="\n")
            with self.assertRaises(ProfileError):
                load(root)
            with self.assertRaises(ProfileError):
                validate((), root)
