"""Local links and executable examples in canonical SCIR document records."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import runpy
import unittest
from urllib.parse import unquote, urlsplit

from scir import format_document, parse_document
from spec import documents as corpus, repository

ROOT = Path(__file__).resolve().parents[1]
FENCE = corpus.FENCE
LINK = corpus.LINK


def headings(source):
    counts, anchors = {}, set()
    for title in re.findall(r"^#{1,6} (.+)$", source, re.M):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        anchors.add(slug if not count else f"{slug}-{count}")
        counts[slug] = count + 1
    return anchors


class DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = repository.load(ROOT)
        cls.documents = corpus.rendered_documents(cls.index, ROOT)

    def test_local_markdown_links(self):
        for name, source in self.documents.items():
            path = ROOT / name
            text = FENCE.sub("", source)
            for target in LINK.findall(text):
                parts = urlsplit(target)
                if parts.scheme or parts.netloc:
                    continue
                resolved = (path.parent / unquote(parts.path)).resolve() if parts.path else path
                with self.subTest(path=name, target=target):
                    self.assertTrue(resolved.is_relative_to(ROOT))
                    key = resolved.relative_to(ROOT).as_posix()
                    self.assertTrue(key in self.documents or resolved.exists(), target)
                    if parts.fragment:
                        target_text = self.documents[key] if key in self.documents else resolved.read_text(encoding="utf-8")
                        self.assertIn(unquote(parts.fragment), headings(FENCE.sub("", target_text)))

    def test_python_examples(self):
        for name, text in self.documents.items():
            for language, source in FENCE.findall(text):
                if language == "python":
                    with self.subTest(path=name), redirect_stdout(StringIO()):
                        exec(compile(source, name, "exec"), {})

    def test_scir_examples(self):
        for name, text in self.documents.items():
            for language, source in FENCE.findall(text):
                if language == "scir":
                    with self.subTest(path=name):
                        doc = parse_document(source)
                        self.assertEqual(parse_document(format_document(doc)), doc)
        for path in (ROOT / "examples").glob("*.scir"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(format_document(parse_document(text)), text)

    def test_example_scripts_are_executable(self):
        for path in sorted((ROOT / "examples").glob("*.py")):
            with self.subTest(example=path.name), redirect_stdout(StringIO()):
                runpy.run_path(str(path), run_name="__main__")

    def test_no_unclosed_fences(self):
        for name, text in self.documents.items():
            lines = text.splitlines()
            self.assertEqual(sum(line.startswith("```") for line in lines) % 2, 0, name)


if __name__ == "__main__":
    unittest.main()
