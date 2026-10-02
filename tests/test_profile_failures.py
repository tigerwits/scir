"""The optional boundaries distinguish malformed input from exhausted parsing."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace

from scir import parse_document, digest
from scir.changes import read_request
from scir.profile import ProfileError, LimitError
from scir._profile_cli import execute


class ProfileFailureTests(unittest.TestCase):
    def request(self, value):
        return json.dumps({"version": "scir-change/1", "collection": "x",
            "expected_snapshot": digest(parse_document("record(A, Note, p)")),
            "operations": [{"op": "setField", "id": "A", "field": "reason", "value": value}]})

    def test_change_terms_have_typed_syntax_and_budget_failures(self):
        for value, expected in (("f(", ProfileError), ("f(" * 130 + "a" + ")" * 130, LimitError)):
            with self.subTest(value=value), self.assertRaises(expected):
                read_request(self.request(value))

    def test_document_and_change_value_categories_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            document, change = root / "notes.scir", root / "change.json"
            for value, expected in (("f(", (1, "rejected")),
                                    ("f(" * 130 + "a" + ")" * 130, (2, "incomplete"))):
                for operation in ("check", "propose"):
                    document.write_text(value if operation == "check" else "record(A, Note, p)", encoding="utf-8")
                    change.write_text(self.request(value), encoding="utf-8")
                    args = Namespace(command="knowledge", operation=operation, file=str(document),
                                     change=str(change), collection="x", max_records=10000, max_output_bytes=16000000)
                    out, err = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        code = execute(args, lambda stream, text: stream.write(text))
                    diagnostic = json.loads(err.getvalue())
                    self.assertEqual((code, diagnostic["error"]), expected)
                    self.assertEqual(diagnostic["complete"], code == 1)
                    self.assertEqual(out.getvalue(), "")

    def test_decoder_recursion_is_incomplete_not_invalid_syntax(self):
        with patch("scir.changes.json.loads", side_effect=RecursionError), self.assertRaises(LimitError):
            read_request("{}")
