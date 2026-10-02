"""Exact structural measurements, explicit capacity results and unchanged selection."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scir import Term, format_document
from scir.knowledge import build_index, select
from scir.diagnostics import diagnose
from scir.notation import Limits as NotationLimits, lower, pretty
from scir import profile as p


def wire(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


class SelectionDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.document = lower('record(A, Note, t"é\\n")\n'
                              'record(B, Task, send(doc, from: a, to: b), '
                              'dependsOn: (&A, &A), evidence: (&A,))\n'
                              'record(C, Note, cite(&A))')
        self.index = build_index(self.document, collection="診断")

    def test_exact_counts_keep_overlapping_relations_distinct(self):
        before = select(self.index, ("B",))
        result = diagnose(self.index, ("B", "B"))
        self.assertEqual(result["selected_ids"], ["A", "B"])
        self.assertEqual(result["requested_ids"], ["B"])
        self.assertEqual(result["total"]["canonical_bytes"], len(format_document(self.document).encode()))
        self.assertEqual(result["selected"]["canonical_bytes"], len(format_document(self.document[:2]).encode()))
        self.assertEqual(result["legacy_packet_bytes"], len(wire(before.as_dict())))
        self.assertEqual({k: result["selected"][k] for k in
                          ("reference_edges", "dependency_edges", "other_reference_edges")},
                         {"reference_edges": 1, "dependency_edges": 1, "other_reference_edges": 0})
        cited = diagnose(self.index, ("C",))
        self.assertEqual(cited["selected"]["dependency_edges"], 0)
        self.assertEqual(cited["selected"]["other_reference_edges"], 1)
        self.assertFalse(result["content_delivered"])
        self.assertEqual(select(self.index, ("B",)), before)
        result["selected_ids"].clear()
        self.assertEqual(tuple(self.index.records), ("A", "B", "C"))

    def test_nodes_depth_and_empty_counts(self):
        simple = build_index((Term("record", (Term("A"), Term("Note"), Term("p"))),), collection="x")
        result = diagnose(simple, ("A",))
        self.assertEqual(result["total"], {"records": 1, "canonical_bytes": 19, "nodes": 4, "depth": 1})
        empty = diagnose(build_index((), collection="x"), ())
        self.assertEqual(empty["total"], {"records": 0, "canonical_bytes": 0, "nodes": 0, "depth": 0})
        self.assertEqual(empty["selected"]["reference_edges"], 0)

    def test_encoding_failure_has_no_invented_zero_cost(self):
        result = diagnose(self.index, ("B",), encoding="notation", notation_limits=NotationLimits(source_bytes=1))
        self.assertTrue(result["complete"])  # Analysis completed; delivery did not.
        self.assertFalse(result["encoding_check"]["complete"])
        self.assertIsNone(result["encoding_check"]["bytes"])
        self.assertIn("byte", result["encoding_check"]["reason"])
        success = diagnose(self.index, ("B",), encoding="notation")
        self.assertEqual(success["encoding_check"]["bytes"], len(pretty(self.document[:2]).encode()))
        self.assertNotIn("records", success)  # This is not a partial content packet.

    def test_report_and_content_bounds_fail_without_truncation(self):
        result = diagnose(self.index, ("B",))
        n = len(wire(result))
        self.assertEqual(diagnose(self.index, ("B",), max_output_bytes=n), result)
        for kwargs in ({"max_output_bytes": n - 1}, {"max_records": 1}, {"limits": p.Limits(nodes=1)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(p.LimitError):
                diagnose(self.index, ("B",), **kwargs)
        for kwargs in ({"max_output_bytes": True}, {"encoding": "guess"}, {"notation_limits": None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                diagnose(self.index, ("B",), **kwargs)
        with self.assertRaises(p.ProfileError):
            diagnose(self.index, ("Missing",))

    def test_actual_cli_keeps_default_selection_and_failure_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.scix"  # Filename does not select notation.
            source.write_text(format_document(self.document), encoding="utf-8")
            args = [sys.executable, "-m", "scir", "knowledge"]
            def run(operation, *flags):
                return subprocess.run(args + [operation, str(source), "--collection", "診断", "--id", "B", *flags],
                                      capture_output=True, timeout=15)
            ordinary = run("select")
            self.assertEqual(json.loads(ordinary.stdout), select(self.index, ("B",)).as_dict())
            report = run("diagnose", "--encoding", "notation")
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(json.loads(report.stdout), diagnose(self.index, ("B",), encoding="notation"))
            failed = run("diagnose", "--max-output-bytes", "1")
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, b"")
            self.assertEqual(json.loads(failed.stderr)["error"], "incomplete")
