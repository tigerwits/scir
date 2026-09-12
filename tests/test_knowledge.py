"""Migration bookkeeping and dependency laws; no model or prose-fidelity oracle."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import random
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scir import Term, format_document, parse, parse_document, parse_pattern, query
from scir.relations import decode, encode

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/knowledge"
MODULE = runpy.run_path(str(EXAMPLES / "run.py"))
VALIDATE, AFFECTED, MAIN = (MODULE[k] for k in ("validate", "affected", "main"))
SOURCE = b"S1: Reviewed source material.\n"


def document(body, source=SOURCE):
    return parse_document(f'snapshot("{sha256(source).hexdigest()}")\n{body}')


def load(name):
    folder = EXAMPLES / name
    return parse_document((folder / "knowledge.scir").read_text(encoding="utf-8")), (folder / "source.md").read_bytes()


def inventory(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class KnowledgeTests(unittest.TestCase):
    def test_all_cases_are_canonical_and_conform(self):
        for name, count in (("architecture", 6), ("investigation", 9), ("mathematics", 6)):
            with self.subTest(case=name):
                doc, source = load(name)
                self.assertEqual(VALIDATE(doc, source), ())
                self.assertEqual(sum(t.symbol == "record" for t in doc), count)
                self.assertEqual(format_document(doc).encode(), (EXAMPLES / name / "knowledge.scir").read_bytes())
                self.assertEqual(VALIDATE(decode(encode(doc)), source), ())

    def test_missing_sources_or_changed_source_bytes_do_not_pass(self):
        doc, source = load("architecture")
        for changed in (source + b"\n", source.replace(b"\n", b"\r\n")):
            self.assertIn("snapshot", {v.rule for v in VALIDATE(doc, changed)})
        for invalid in (b"No anchors", b"S1: one\nS1: two\n", b"\xff"):
            with self.assertRaises(ValueError):
                VALIDATE(doc, invalid)

    def test_snapshot_is_required_unique_and_exact(self):
        doc = document("record(A, Assumption, P)\nsource(A, S1)")
        for bad in (doc[1:], doc + (doc[0],), (parse('snapshot("wrong")'),) + doc[1:]):
            self.assertIn("snapshot", {v.rule for v in VALIDATE(bad, SOURCE)})

    def test_malformed_records_and_nested_declarations_are_rejected(self):
        cases = (
            ("record(A)", "form"),
            ("record(f(A), Assumption, P)", "leaf"),
            ("record(A, Assumption(X), P)", "leaf"),
            ("record(A, Magic, P)\nsource(A, S1)", "role"),
            ("box(record(A, Assumption, P))\nsource(A, S1)", "reference"),
            ("record(A, Assumption, P)\nsource(A, S1(X))", "leaf"),
            ("record(A, Assumption, P)\nsource(A, S1)\ndependsOn(A, f(A))", "leaf"),
        )
        for body, rule in cases:
            with self.subTest(body=body):
                self.assertIn(rule, {v.rule for v in VALIDATE(document(body), SOURCE)})

    def test_duplicates_and_ambiguous_references_do_not_choose_a_winner(self):
        doc = document("record(A, Assumption, P)\nrecord(A, Assumption, Q)\nsource(A, S1)\ndependsOn(A, A)")
        rules = {v.rule for v in VALIDATE(doc, SOURCE)}
        self.assertTrue({"duplicate-id", "reference", "uncited", "unmapped"} <= rules)

    def test_duplicate_links_fail(self):
        for link in ("source(A, S1)", "dependsOn(A, A)"):
            doc = document(f"record(A, Assumption, P)\nsource(A, S1)\n{link}\n{link}")
            self.assertIn("duplicate-link", {v.rule for v in VALIDATE(doc, SOURCE)})

    def test_source_coverage_is_bookkeeping_not_semantic_equivalence(self):
        doc, source = load("mathematics")
        changed = tuple(Term("record", (t.args[0], t.args[1], parse("falseConclusion")))
                        if t.symbol == "record" and t.args[0].symbol == "C1" else t for t in doc)
        self.assertEqual(VALIDATE(changed, source), ())
        self.assertNotEqual(changed, doc)  # A valid source link is no semantic oracle.

    def test_missing_record_and_missing_source_link_are_visible(self):
        doc, source = load("architecture")
        without_premise = tuple(t for t in doc if not (t.symbol == "record" and t.args[0].symbol == "A1"))
        self.assertIn("reference", {v.rule for v in VALIDATE(without_premise, source)})
        without_link = tuple(t for t in doc if not (t.symbol == "source" and t.args[0].symbol == "A1"))
        self.assertTrue({"unmapped", "uncited"} <= {v.rule for v in VALIDATE(without_link, source)})

    def test_unknown_source_anchor_and_unmapped_sentence_fail(self):
        doc = document("record(A, Assumption, P)\nsource(A, S9)")
        self.assertTrue({"source", "uncited", "unmapped"} <= {v.rule for v in VALIDATE(doc, SOURCE)})
        source = SOURCE + b"S2: New requirement.\n"
        self.assertIn("unmapped", {v.rule for v in VALIDATE(document("record(A, Assumption, P)\nsource(A, S1)", source), source)})

    def test_forward_links_and_several_records_per_sentence_are_allowed(self):
        doc = document("source(A, S1)\nsource(B, S1)\ndependsOn(B, A)\nrecord(A, Assumption, P)\nrecord(B, Conclusion, Q)")
        self.assertEqual(VALIDATE(doc, SOURCE), ())
        self.assertEqual(AFFECTED(doc, ["A"]), ("A", "B"))

    def test_known_review_closures_are_precise(self):
        for name, ident, expected in (
            ("architecture", "A1", ("A1", "P1")),
            ("investigation", "O2", ("O2", "L1")),
            ("mathematics", "Domain", ("Domain", "C1", "C2", "L1")),
            ("mathematics", "A1", ("A1", "C1", "C2", "L1")),
            ("mathematics", "A2", ("A2", "C1", "C2", "L1")),
            ("mathematics", "L1", ("L1",)),
        ):
            doc, _ = load(name)
            self.assertEqual(AFFECTED(doc, [ident]), expected)
            self.assertEqual(AFFECTED(decode(encode(doc)), [ident]), expected)
            self.assertEqual(AFFECTED(doc, []), ())

    def test_strengthened_premise_flags_the_existing_limitation_for_review(self):
        doc, source = load("mathematics")
        # With a <= b and b < c, the old "strict inequality not established"
        # limitation needs review. Reachability must not silently rewrite it.
        changed = tuple(parse("record(A2, Assumption, less(b, c))")
                        if t.symbol == "record" and t.args[0].symbol == "A2" else t
                        for t in doc)
        self.assertEqual(VALIDATE(changed, source), ())
        before = format_document(changed)
        self.assertEqual(AFFECTED(changed, ["A2"]), ("A2", "C1", "C2", "L1"))
        self.assertEqual(format_document(changed), before)
        pattern = parse_pattern("record(L1, Limitation, ?content)")
        self.assertEqual(query(changed, pattern), query(doc, pattern))

    def test_review_closure_is_extensive_monotone_and_idempotent(self):
        rng = random.Random(812)
        for name in MODULE["CASES"]:
            doc, _ = load(name)
            ids = [t.args[0].symbol for t in doc if t.symbol == "record"]
            for _ in range(100):
                a = {x for x in ids if rng.choice((False, True))}
                b = a | {x for x in ids if rng.choice((False, True))}
                closure = AFFECTED(doc, a)
                self.assertLessEqual(a, set(closure))
                self.assertLessEqual(set(closure), set(AFFECTED(doc, b)))
                self.assertEqual(AFFECTED(doc, closure), closure)
                self.assertEqual(tuple(x for x in ids if x in closure), closure)

    def test_cycles_terminate_and_do_not_infer_new_content(self):
        doc = document("record(A, Assumption, P)\nsource(A, S1)\nrecord(B, Conclusion, Q)\nsource(B, S1)\ndependsOn(A, B)\ndependsOn(B, A)")
        before = format_document(doc)
        self.assertEqual(VALIDATE(doc, SOURCE), ())
        self.assertEqual(AFFECTED(doc, ["B", "B"]), ("A", "B"))
        self.assertEqual(format_document(doc), before)
        for invalid in (["Missing"], "A", b"A"):
            with self.assertRaises(ValueError):
                AFFECTED(doc, invalid)

    def test_role_queries_keep_unresolved_hypotheses_and_withdrawal(self):
        doc, _ = load("investigation")
        hits = query(doc, parse_pattern("record(?id, Hypothesis, ?content)"))
        self.assertEqual([str(h.bindings["id"]) for h in hits], ["H1", "H2"])
        self.assertEqual(len(query(doc, parse_pattern("record(W1, Revision, withdraw(P1))"))), 1)
        self.assertEqual(query(doc, parse_pattern("causes(?x, ?y)")), [])
        self.assertEqual(len(query(doc, parse_pattern("record(Q1, Question, ?content)"))), 1)

    def test_content_payloads_are_never_executed(self):
        doc = document('record(A, Assumption, python("raise RuntimeError()"))\nsource(A, S1)')
        self.assertEqual(VALIDATE(doc, SOURCE), ())

    def run_cli(self, root, *args):
        out, err = StringIO(), StringIO()
        with patch.dict(MAIN.__globals__, ROOT=root), redirect_stdout(out), redirect_stderr(err):
            code = MAIN(args)
        return code, out.getvalue(), err.getvalue()

    def test_cli_never_rewrites_source_knowledge_or_authored_overviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "knowledge"
            shutil.copytree(EXAMPLES, root, ignore=shutil.ignore_patterns("__pycache__"))
            before = inventory(root)
            code, out, err = self.run_cli(root)
            self.assertEqual(code, 0, err)
            self.assertEqual(inventory(root), before)
            self.assertEqual(len(json.loads(out)["cases"]), 3)
            # Authored Markdown need not equal a renderer; even bad prose is not
            # falsely certified by the knowledge contract.
            (root / "mathematics/overview.md").write_text("# A newly authored explanation\nEverything is proven.\n")
            edited = inventory(root)
            code, out, err = self.run_cli(root, "--case", "mathematics", "--changed", "A2")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["authored_overviews"], "not checked or rewritten")
            self.assertEqual(json.loads(out)["source_fidelity"], "requires separate review")
            self.assertEqual(inventory(root), edited)

    def test_cli_rejection_and_incomplete_check_do_not_report_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "knowledge"
            shutil.copytree(EXAMPLES, root, ignore=shutil.ignore_patterns("__pycache__"))
            path = root / "architecture/knowledge.scir"
            original = path.read_bytes()
            for invalid in (original + b"\n", original.replace(b"\n", b"\r\n")):
                path.write_bytes(invalid)
                code, out, err = self.run_cli(root, "--case", "architecture")
                self.assertEqual(code, 1, err)
                self.assertEqual(out, "")
            path.write_bytes(original)
            source = root / "architecture/source.md"
            source.write_bytes(source.read_bytes() + b"\n")
            code, out, err = self.run_cli(root, "--case", "architecture")
            self.assertEqual(code, 1)
            self.assertIn("snapshot", err)
            self.assertEqual(out, "")
            source.unlink()
            code, out, err = self.run_cli(root, "--case", "architecture")
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertIn("incomplete", err)

    def test_cli_unknown_changed_record_is_not_a_success(self):
        code, out, err = self.run_cli(EXAMPLES, "--case", "mathematics", "--changed", "Missing")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("declared", err)

    def test_missing_package_is_not_a_validation_pass(self):
        result = subprocess.run([sys.executable, "-I", "-S", str(EXAMPLES / "run.py")],
                                capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No module named 'scir'", result.stderr)
        self.assertNotIn('"contract": "passed"', result.stdout)


if __name__ == "__main__":
    unittest.main()
