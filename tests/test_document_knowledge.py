"""SCIR-owned documentation: independent preservation and adversarial boundaries.

These tests do not measure agent behavior or prove semantic translation fidelity.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scir import Term, format_document, parse_document
from scir import profile as p
from scir.changes import ConflictError
from scir.knowledge import affected, build_index, select
from spec import documents, handoff, repository

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "712b8e2b5e7a006296ca6483401e6752b5cca25d"


def block(source="Preserve every qualification."):
    return Term("blocks", (Term("paragraph", (p.text(source),)),))


def section(identifier="Guide", *, payload=None, **fields):
    defaults = dict(area=Term("Documentation"), ownership=Term("record"),
                    document=Term("guide.md"), title=p.text("Guide"), level=Term("1"),
                    order=Term("0"), origin=Term("authored", (p.text("Independent test fixture."),)))
    defaults.update(fields)
    return p.application("record", (Term(identifier), Term("Guide"), payload or block()),
                         fields=tuple(defaults.items()))


def fixture(root, doc=None):
    (root / "spec").mkdir()
    (root / "README.md").write_bytes(b"# Fixture\n")
    (root / "AGENTS.md").write_bytes(b"# Fixture bootstrap\n")
    (root / "LICENSE").write_bytes(b"Fixture license\n")
    (root / "spec/index.scir").write_bytes(b'collection("scir-repository", shard("spec/docs.scir"))\n')
    (root / "spec/docs.scir").write_bytes(format_document(doc or (section(),)).encode())
    return repository.load(root)


def request(index, operations):
    return json.dumps(dict(version="scir-change/1", collection=index.collection,
                           expected_snapshot=index.snapshot, operations=operations))


class DocumentKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = repository.load(ROOT)

    def test_only_two_tracked_markdown_entrypoints_and_bounded_bootstrap(self):
        if (ROOT / ".git").exists():
            paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
            # Deleted but unstaged paths are not actual source files in a working copy.
            paths = [name for name in paths if name and (ROOT / name).is_file()]
        else:
            paths = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()
                     and not any(part in ("build", "dist", ".venv", "__pycache__") for part in p.parts)]
        documents.check_markdown_policy(paths)
        self.assertLessEqual(len((ROOT / "AGENTS.md").read_text().splitlines()), 40)
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 2500)
        self.assertLessEqual((ROOT / "README.md").stat().st_size, 8000)

    def test_markdown_policy_rejects_alternate_case_extensions_and_nested_readmes(self):
        for extra in ("docs/readme.md", "SKILL.md", "SPEC.MD", "docs/contract.markdown", "guide.mdx"):
            with self.subTest(extra=extra), self.assertRaises(p.ProfileError):
                documents.check_markdown_policy(["README.md", "AGENTS.md", extra])
        with self.assertRaises(p.ProfileError):
            documents.check_markdown_policy(["README.md"])

    def test_manifest_resolves_every_record_once_and_existing_ids_survive(self):
        manifest = repository.sources(ROOT)
        self.assertEqual(len(manifest), len(set(manifest)))
        self.assertEqual(sum(len(parse_document((ROOT / path).read_text())) for path in manifest), len(self.index.records))
        existing = [r for r in self.index.records.values() if r.kind in repository.KINDS]
        self.assertEqual(len(existing), 60)
        for record in existing:
            fields = dict(record.fields)
            self.assertEqual(fields["source"].symbol, "scir.ref")
            self.assertIn(fields["source"], p.read_tuple(fields["dependsOn"]))
        basis = handoff.capture(ROOT, self.index, manifest)
        self.assertIn("spec/index.scir", dict(basis.files))
        self.assertFalse(any(name.endswith(".md") and name not in documents.MARKDOWN for name, _ in basis.files))

    def test_frozen_example_inventory_preserves_each_original_code_block(self):
        expected = parse_document((ROOT / "tests/fixtures/document-example-baseline.scir").read_text())
        self.assertEqual(expected[0], Term("baseline", (Term(BASELINE),)))
        rendered = documents.rendered_documents(self.index, ROOT)
        actual = {name: Counter((lang, hashlib.sha256(body.encode()).hexdigest())
                               for lang, body in documents.FENCE.findall(source))
                  for name, source in rendered.items()}
        # Original entrypoint details moved to SCIR guides; the new front doors are thin.
        relocated = {"README.md": "INTRODUCTION.md", "AGENTS.md": "MAINTAINERS.md"}
        wanted = Counter(tuple(t.symbol for t in item.args) for item in expected[1:])
        self.assertEqual(sum(wanted.values()), 39)
        for (name, language, digest), count in wanted.items():
            with self.subTest(document=name, language=language, digest=digest):
                self.assertGreaterEqual(actual[relocated.get(name, name)][language, digest], count)

    def test_migration_ledger_covers_44_original_files_and_all_targets_exist(self):
        ledger = parse_document((ROOT / "docs/research/migration.scir").read_text())
        self.assertEqual(ledger[0].args[:2], (Term(BASELINE), Term("44")))
        migrations = ledger[1:]
        self.assertEqual(len(migrations), 44)
        self.assertEqual(len({r.args[0] for r in migrations}), 44)
        owners = dict(handoff.capture(ROOT, self.index, repository.sources(ROOT)).membership)
        for record in migrations:
            path, digest, shard, disposition, sections = record.args
            self.assertRegex(digest.symbol, r"^[a-f0-9]{64}$")
            self.assertTrue(disposition.symbol)
            self.assertEqual(sections.symbol, "sections")
            for entry in sections.args:
                self.assertEqual(entry.symbol, "section")
                self.assertEqual(len(entry.args), 5)
                title, source_hash, mode, targets, reason = entry.args
                self.assertRegex(source_hash.symbol, r"^[a-f0-9]{64}$")
                self.assertTrue(p.read_text(reason))
                self.assertEqual(targets.symbol, "targets")
                self.assertTrue(targets.args)
                for target in targets.args:
                    self.assertEqual(owners[target.symbol], shard.symbol)

    def test_manifest_rejects_duplicate_recursive_missing_and_traversal_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            manifest = root / "spec/index.scir"
            for name in ("spec/index.scir", "spec/missing.scir", "../other.scir", "spec/../docs.scir"):
                manifest.write_bytes(format_document((Term("collection", (Term("scir-repository"), Term("shard", (Term(name),)))),)).encode())
                with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                    documents.source_paths(root)
            manifest.write_bytes(b'collection("scir-repository", shard("spec/docs.scir"), shard("spec/docs.scir"))\n')
            with self.assertRaises(p.ProfileError):
                documents.source_paths(root)

    def test_manifest_limits_are_incomplete_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            with patch.object(documents, "MAX_SHARDS", 0), self.assertRaises(p.LimitError):
                documents.source_paths(root)
            with patch.object(documents, "MAX_BLOCKS", 0), self.assertRaises(p.LimitError):
                documents.validate(build_index((section(),), collection="fixture"))

    def test_malformed_document_blocks_and_metadata_fail(self):
        candidates = (
            section(payload=Term("wrong")),
            section(payload=Term("blocks", (Term("execute", (p.text("bad"),)),))),
            section(payload=Term("blocks", (Term("code", (Term("python"),)),))),
            section(order=Term("01")), section(level=Term("7")),
            section(document=Term("../escape.md")), section(ownership=Term("index")),
            section(origin=Term("authored", (p.text(""),))),
            section(links=p.tuple_value(fields=(("wrong", Term("value")),))),
        )
        for candidate in candidates:
            with self.subTest(candidate=str(candidate)), self.assertRaises(ValueError):
                documents.validate(build_index((candidate,), collection="fixture"))

    def test_validation_never_executes_literal_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = Term("blocks", (Term("code", (Term("python"), p.text("raise RuntimeError('not executed')\n"))),))
            self.assertEqual(len(fixture(root, (section(payload=code),)).records), 1)

    def test_navigation_is_not_a_dependency_and_unknown_local_targets_fail(self):
        navigation = p.tuple_value((Term("link", (Term("Other"), Term("other.md"))),))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root, (section(links=navigation), section("Other", document=Term("other.md"))))
            self.assertEqual(select(index, ("Guide",)).selected_ids, ("Guide",))
            with self.assertRaises(ValueError):
                repository.validate((section(links=navigation),), root)
            with self.assertRaises(ValueError):
                repository.validate((section(payload=block("[Broken](other.md#absent)")), section("Other", document=Term("other.md"))), root)

    def test_parent_order_cycles_and_wrong_child_declarations_fail(self):
        for doc in (
            (section(parent=p.reference("Guide")),),
            (section("A", parent=p.reference("B")), section("B", parent=p.reference("A"), order=Term("10"))),
            (section(children=p.tuple_value((p.reference("Other"),))), section("Other", document=Term("other.md"))),
            (section(order=Term("20")), section("Child", parent=p.reference("Guide"), level=Term("2"), order=Term("10"))),
        ):
            with self.subTest(doc=str(doc)), self.assertRaises(ValueError):
                documents.validate(build_index(doc, collection="fixture"))

    def test_scoped_subsection_changes_reach_requirements_without_inventing_dependencies(self):
        found = False
        for record in self.index.records.values():
            if record.kind != "Requirement":
                continue
            owner = dict(record.fields)["source"].args[0].symbol
            children = dict(self.index.records[owner].fields).get("children")
            if children is not None:
                child = p.read_tuple(children)[0].args[0].symbol
                self.assertIn(record.id, affected(self.index, (child,)))
                self.assertIn(child, select(self.index, (record.id,)).selected_ids)
                found = True
        self.assertTrue(found, "the regression must exercise a real scoped subsection")

    def test_document_edits_are_guarded_and_only_the_owner_shard_is_planned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            before = handoff.capture(root, index, repository.sources(root))
            original = (root / "spec/docs.scir").read_bytes()
            change = request(index, [{"op": "replacePayload", "id": "Guide", "value": str(block("Reviewed new wording."))}])
            result = repository.propose_handoff(index, change, before.fingerprint, root)
            self.assertEqual([w["path"] for w in result["write_plan"]], ["spec/docs.scir"])
            self.assertEqual((root / "spec/docs.scir").read_bytes(), original)
            self.assertFalse(result["source_written"])
            (root / "AGENTS.md").write_bytes(b"# Changed bootstrap\n")
            with self.assertRaises(ConflictError):
                repository.propose_handoff(index, change, before.fingerprint, root)

    def test_new_document_id_needs_explicit_source_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = fixture(root)
            before = handoff.capture(root, index, repository.sources(root))
            change = request(index, [{"op": "createRecord", "record": str(section("New", document=Term("new.md")))}])
            with self.assertRaises(p.ProfileError):
                repository.propose_handoff(index, change, before.fingerprint, root)
            result = repository.propose_handoff(index, change, before.fingerprint, root, placements={"New": "spec/docs.scir"})
            self.assertEqual(result["placements"], {"New": "spec/docs.scir"})

    def test_exports_are_deterministic_relocatable_and_do_not_modify_sources(self):
        before = handoff.capture(ROOT, self.index, repository.sources(ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = documents.export(self.index, ROOT, root / "a", skill="scir")
            b = documents.export(self.index, ROOT, root / "b", skill="scir")
            self.assertEqual(a, b)
            self.assertTrue((root / "a/SKILL.md").is_file())
            self.assertTrue((root / "a/knowledge.scir").is_file())
            self.assertEqual((root / "a/assets/LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes())
            shutil.move(root / "a", root / "relocated")
            for name in a["sha256"]:
                self.assertEqual(hashlib.sha256((root / "relocated" / name).read_bytes()).hexdigest(), a["sha256"][name])
            with self.assertRaises(p.ProfileError):
                documents.export(self.index, ROOT, root / "b", skill="scir")
        self.assertEqual(before, handoff.capture(ROOT, self.index, repository.sources(ROOT)))

    def test_export_rejects_checkout_destinations_aliases_and_unknown_skills(self):
        with self.assertRaises(p.ProfileError):
            documents.export(self.index, ROOT, ROOT / "should-not-exist")
        self.assertFalse((ROOT / "should-not-exist").exists())
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp)
            with self.assertRaises(p.ProfileError):
                documents.export(self.index, ROOT, outside / "unknown", skill="unknown")
            try:
                (outside / "alias").symlink_to(ROOT, target_is_directory=True)
            except OSError:
                return  # Windows without symlink privilege still tests direct paths.
            with self.assertRaises(p.ProfileError):
                documents.export(self.index, ROOT, outside / "alias/new")

    def test_cli_discovery_search_and_show_work_without_a_markdown_handbook(self):
        for args in (("list",), ("search", "--text", "Repository knowledge ownership"), ("show", "--id", "NamedRoles")):
            result = subprocess.run([sys.executable, "spec/check.py", "knowledge", *args], cwd=ROOT,
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout)
            if args[0] == "show":
                self.assertIn(b"NamedRoles", result.stdout)
            else:
                packet = json.loads(result.stdout)
                self.assertTrue(packet["items"])
                self.assertEqual(packet["repository_contract"], "scir-repository/2")

    def test_missing_manifest_is_an_incomplete_cli_result_not_an_import_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec").mkdir()
            for path in (ROOT / "spec").glob("*.py"):
                shutil.copy2(path, root / "spec" / path.name)
            result = subprocess.run([sys.executable, str(root / "spec/check.py"), "knowledge", "list"],
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertFalse(json.loads(result.stderr)["complete"])
            self.assertNotIn(b"Traceback", result.stderr)

    def test_export_rejects_a_stale_index_before_creating_a_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            index = fixture(root)
            (root / "spec/docs.scir").write_bytes(format_document((section(payload=block("Changed.")),)).encode())
            target = Path(tmp) / "export"
            with self.assertRaises(ConflictError):
                documents.export(index, root, target)
            self.assertFalse(target.exists())

    def test_observed_auxiliary_change_aborts_export_and_removes_only_its_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, target = Path(tmp) / "repository", Path(tmp) / "export"
            root.mkdir()
            index = fixture(root)
            original_write = Path.write_bytes
            changed = False
            def write(path, raw):
                nonlocal changed
                if path.parent == target and not changed:
                    changed = True
                    original_write(root / "LICENSE", b"Changed during the temporary scenario.\n")
                return original_write(path, raw)
            with patch.object(Path, "write_bytes", write), self.assertRaises(ConflictError):
                documents.export(index, root, target)
            self.assertTrue(changed)
            self.assertFalse(target.exists())
            self.assertTrue((root / "spec/docs.scir").exists())


if __name__ == "__main__":
    unittest.main()
