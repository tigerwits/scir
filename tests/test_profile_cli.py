import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from scir import parse_document, digest
from scir.__main__ import main
from scir.notation import lower


class ProfileCliTests(unittest.TestCase):
    def invoke(self, args, source=""):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO(source)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_lower_is_explicit_and_native_commands_stay_native(self):
        source = 'send(doc, to: b, note: t"é")\n'
        code, out, err = self.invoke(["lower"], source)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(parse_document(out), lower(source))
        self.assertEqual(self.invoke(["check"], source)[0], 2)
        self.assertEqual(self.invoke(["lower"], 'a+b')[0], 1)
        self.assertEqual(self.invoke(["lower", "--operators", "arithmetic/1"], 'a+b')[1], 'plus(a, b)\n')
        self.assertEqual(self.invoke(["fmt", "--check"], 'a\n'), (0, "", ""))
        self.assertEqual(self.invoke(["fmt", "--check"], 'a')[0], 1)

    def test_selection_and_review_packets_preserve_whole_scope(self):
        doc = 'record(A, Assumption, p)\nrecord(T, Task, when(staging, work), "scir.kw"(dependsOn("scir.tuple"("scir.ref"(A)))))\n'
        code, out, err = self.invoke(["knowledge", "select", "--collection", "x", "--id", "T"], doc)
        result = json.loads(out)
        self.assertEqual((code, err, result["selected_ids"]), (0, "", ["A", "T"]))
        self.assertIn("when(staging, work)", result["records"][1])
        self.assertEqual(result["source_snapshot"], digest(parse_document(doc)))
        code, out, err = self.invoke(["knowledge", "affected", "--collection", "x", "--changed", "A"], doc)
        self.assertEqual((code, err, json.loads(out)["review_ids"]), (0, "", ["A", "T"]))

    def test_rejection_conflict_and_incomplete_are_not_partial_success(self):
        for args, source, expected in (
            (["lower"], 'f()', 1),
            (["lower"], 'a'*64_001, 2),
            (["knowledge", "check", "--collection", "x"], 'record(A, Note, "scir.ref"(B))', 1),
            (["knowledge", "select", "--collection", "x", "--id", "A", "--max-output-bytes", "1"], 'record(A, Note, p)', 2),
            (["knowledge", "check", "--collection", "x"], 'f('*130+'a'+')'*130, 2),
        ):
            with self.subTest(args=args):
                code, out, err = self.invoke(args, source)
                self.assertEqual((code, out), (expected, ""))
                self.assertEqual(json.loads(err)["complete"], expected == 1)
        code, out, err = self.invoke(["knowledge", "check", "/missing/scir/file", "--collection", "x"])
        self.assertEqual((code, out, json.loads(err)["error"]), (2, "", "incomplete"))

    def test_proposals_do_not_rewrite_sources_and_reject_stale_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, change = root/'notes.scir', root/'change.json'
            original = b'record(A, Note, p)\r\n'
            source.write_bytes(original)
            request = {"version":"scir-change/1", "collection":"x", "expected_snapshot":digest(parse_document(original.decode())),
                       "operations":[{"op":"setField","id":"A","field":"status","value":"ready"}]}
            change.write_text(json.dumps(request), encoding='utf-8')
            args = ["knowledge", "propose", str(source), "--collection", "x", "--change", str(change)]
            code, out, err = self.invoke(args)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(source.read_bytes(), original)
            self.assertIn('status(ready)', json.loads(out)["records"][0])
            source.write_text('record(A, Note, q)', encoding='utf-8')
            code, out, err = self.invoke(args)
            self.assertEqual((code, out, json.loads(err)["error"]), (1, "", "conflict"))
            self.assertEqual(set(p.name for p in root.iterdir()), {"notes.scir", "change.json"})
        code, out, err = self.invoke(["knowledge", "propose", "--collection", "x", "--change", "-"])
        self.assertEqual((code, out), (1, ""))

    def test_installed_style_subprocess_unicode_output(self):
        # No working-directory or source-file assumption in the executable interface.
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, PYTHONIOENCODING="ascii", PYTHONDONTWRITEBYTECODE="1")
            source = Path(temp)/'input.scix'
            source.write_text('note(t"é")\n', encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'scir', 'lower', str(source)],
                                    cwd=temp, env=env, capture_output=True, check=False)
            self.assertEqual((result.returncode, result.stderr), (0, b''))
            self.assertEqual(result.stdout, 'note("scir.text"("é"))\n'.encode())
