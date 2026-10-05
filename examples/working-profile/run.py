"""Check the independent golden pair, then use the portable consumer workflow."""
from pathlib import Path
import json
import runpy
from scir import format_document, parse_document
from scir.notation import lower


def main():
    here = Path(__file__).resolve().parent
    native = (here / "notes.scir").read_text(encoding="utf-8")
    document = parse_document(native)
    if (format_document(document) != native or
            lower((here / "notes.scix").read_text(encoding="utf-8")) != document):
        raise AssertionError("authored notation differs from the independent native golden")
    example = here.parents[1] / "skills/scir/scripts/working_example.py"
    print(json.dumps(runpy.run_path(str(example))["run"](), sort_keys=True))


if __name__ == "__main__":
    main()
