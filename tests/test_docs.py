"""Local links and executable examples in maintained documentation."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import runpy
import unittest
from urllib.parse import unquote, urlsplit

from scir import format_document, parse_document

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^```([\w-]*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")


def documents():
    return (sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
            + sorted((ROOT / "skills").rglob("*.md"))
            + sorted((ROOT / "examples").rglob("*.md"))
            + sorted((ROOT / "spec").glob("*.md")))


def headings(source):
    counts, anchors = {}, set()
    for title in re.findall(r"^#{1,6} (.+)$", source, re.M):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        anchors.add(slug if not count else f"{slug}-{count}")
        counts[slug] = count + 1
    return anchors


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links(self):
        for path in documents():
            text = FENCE.sub("", path.read_text(encoding="utf-8"))
            for target in LINK.findall(text):
                parts = urlsplit(target)
                if parts.scheme or parts.netloc:
                    continue
                resolved = (path.parent / unquote(parts.path)).resolve() if parts.path else path
                with self.subTest(path=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue(resolved.is_relative_to(ROOT))
                    self.assertTrue(resolved.exists(), target)
                    if parts.fragment:
                        anchors = headings(FENCE.sub("", resolved.read_text(encoding="utf-8")))
                        self.assertIn(unquote(parts.fragment), anchors)

    def test_python_examples(self):
        for path in documents():
            for language, source in FENCE.findall(path.read_text(encoding="utf-8")):
                if language == "python":
                    with self.subTest(path=str(path.relative_to(ROOT))), redirect_stdout(StringIO()):
                        exec(compile(source, str(path), "exec"), {})

    def test_scir_examples(self):
        for path in documents():
            for language, source in FENCE.findall(path.read_text(encoding="utf-8")):
                if language == "scir":
                    with self.subTest(path=str(path.relative_to(ROOT))):
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
        for path in documents():
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(sum(line.startswith("```") for line in lines) % 2, 0, str(path))


if __name__ == "__main__":
    unittest.main()
