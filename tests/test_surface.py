"""Canonical syntax and read-only CLI behavior."""
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO, TextIOWrapper
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scir import FORMAT_VERSION, __version__, ParseError, digest, parse, parse_document, parse_pattern
from scir.__main__ import main
from scir.relations import encode


class SurfaceTests(unittest.TestCase):
    def test_empty_application_is_invalid_in_both_languages(self):
        for source in ("A()", "A( )", "A(\n)", '"odd name"()', "f(A())"):
            for parser in (parse, parse_document, parse_pattern):
                with self.subTest(source=source, parser=parser.__name__):
                    with self.assertRaisesRegex(ParseError, "leaf.*without parentheses"):
                        parser(source)

    def test_leaf_spelling_and_nonempty_trailing_comma(self):
        self.assertEqual(parse('"Alice"'), parse("Alice"))
        self.assertEqual(parse("f(A,)"), parse("f(A)"))
        self.assertEqual(parse_pattern("f(?x,)"), parse_pattern("f(?x)"))

    def run_cli(self, args, source=""):
        out, err = StringIO(), StringIO()
        with patch("sys.stdin", StringIO(source)), redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_version_never_reads_stdin(self):
        out = StringIO()
        with patch("sys.stdin") as stdin, redirect_stdout(out), self.assertRaises(SystemExit) as exit:
            main(["--version"])
        self.assertEqual(exit.exception.code, 0)
        stdin.read.assert_not_called()
        self.assertEqual(out.getvalue(), f"scir {__version__} (format {FORMAT_VERSION})\n")

    def test_format_check_is_silent_when_canonical(self):
        self.assertEqual(self.run_cli(["fmt", "--check"], "f(A, B)\n"), (0, "", ""))
        self.assertEqual(self.run_cli(["fmt", "--check"], ""), (0, "", ""))

    def test_format_check_reports_difference_without_output(self):
        for source in ("A", " f(A,B) \n", "A # note\n", "A\r\n"):
            self.assertEqual(self.run_cli(["fmt", "--check"], source), (1, "", ""))

    def test_format_check_invalid_is_not_a_difference(self):
        code, out, err = self.run_cli(["fmt", "--check"], "A()")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("without parentheses", err)
        self.assertNotIn("Traceback", err)

    def test_format_check_never_mutates_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.scir"
            original = b"f(A,B)\r\n"
            path.write_bytes(original)
            self.assertEqual(self.run_cli(["fmt", "--check", str(path)]), (1, "", ""))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(self.run_cli(["fmt", str(path)]), (0, "f(A, B)\n", ""))
            self.assertEqual(path.read_bytes(), original)

    def test_data_output_ignores_stream_encoding_and_newline_translation(self):
        source = 'label("café", "雪", "😀")\n'
        document = parse_document(source)
        wire = json.dumps(encode(document), ensure_ascii=False, indent=2) + "\n"
        hits = json.dumps([{
            "path": [0], "term": source.rstrip("\n"), "bindings": {},
        }], ensure_ascii=False, indent=2) + "\n"
        cases = (
            (["fmt"], source, source),
            (["decode"], wire, source),
            (["encode"], source, wire),
            (["query", "--pattern", "?_"], source, hits),
            (["check"], source, '{"valid": true, "roots": 1}\n'),
            (["digest"], source, digest(document) + "\n"),
            (["fmt"], "", ""),
            (["fmt", "--check"], source, ""),
        )
        # TextIOWrapper exercises actual encoding and Windows-style translation
        # on every host; StringIO alone cannot expose either regression.
        for args, input_text, expected in cases:
            with self.subTest(args=args):
                out, err = BytesIO(), BytesIO()
                stdout = TextIOWrapper(out, encoding="ascii", newline="\r\n")
                stderr = TextIOWrapper(err, encoding="ascii", newline="\r\n")
                with patch("sys.stdin", StringIO(input_text)), redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(args)
                    stdout.flush()
                    stderr.flush()
                self.assertEqual(code, 0)
                self.assertEqual(out.getvalue(), expected.encode("utf-8"))
                self.assertEqual(err.getvalue(), b"")

    def test_processing_error_output_is_utf8_lf(self):
        out, err = BytesIO(), BytesIO()
        stdout = TextIOWrapper(out, encoding="ascii", newline="\r\n")
        stderr = TextIOWrapper(err, encoding="ascii", newline="\r\n")
        with patch("sys.stdin", StringIO("A")), patch("scir.__main__._read", side_effect=OSError("café 雪")):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["fmt"])
                stdout.flush()
                stderr.flush()
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), b"")
        self.assertEqual(err.getvalue(), "scir: café 雪\n".encode("utf-8"))

    def test_redirected_process_output_is_utf8_under_ascii_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.scir"
            original = 'label("café", "雪")\r\n'.encode("utf-8")
            path.write_bytes(original)
            env = dict(os.environ, PYTHONIOENCODING="ascii:strict", PYTHONUTF8="0")
            result = subprocess.run(
                [sys.executable, "-m", "scir", "fmt", str(path)],
                env=env, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'label("café", "雪")\n'.encode("utf-8"))
            self.assertEqual(result.stderr, b"")
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
