"""Run after installing SCIR: metadata, interpretations, and transport."""
from scir import parse_document
from scir.annotations import Alternatives, Bundle, annotate, erase
from scir.relations import decode, encode

content = parse_document("think(Bob, wrong(Chart))")
note = annotate(content, (0,), "source", {"sentence": 1})
bundle = Bundle(content, (note,))
assert erase(bundle) == content
assert decode(encode(content)) == content

choices = Alternatives((
    parse_document("after(speak(Alice, Carol), leave(Alice))"),
    parse_document("after(speak(Alice, Carol), leave(Carol))"),
))
assert choices.choose(0) == choices.options[0]
print("Metadata, alternatives, and transport checks passed.")
