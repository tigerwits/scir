"""Application-owned dialects: fixed forms, reference checks, and explicit repair."""
from pathlib import Path

from scir import digest, match, parse, parse_document, parse_pattern, replace_at, validate
from scir.annotations import Alternatives
from scir.constraints import Violation, check, forms, vocabulary
from scir.relations import decode, encode
from scir.tree import walk

HERE = Path(__file__).resolve().parent
ROOT_FORMS = tuple(map(parse_pattern, (
    "hypothesis(?id, ?content)", "observation(?id, ?content)", "supports(?observation, ?hypothesis)",
)))
PAYLOAD_FORMS = tuple(map(parse_pattern, (
    "causes(?cause, ?effect)", "stale(?entity)", "wrong(?entity)", "Cache", "Report",
)))


def nonempty(document):
    if not document:
        yield Violation(None, "nonempty", "at least one record is required")


def payloads(document):
    # Identifier positions stay open; this allowlist applies only to payloads.
    for root, record in enumerate(document):
        if record.symbol in ("hypothesis", "observation") and len(record.args) == 2:
            for path, term in walk((record.args[1],)):
                if not any(match(pattern, term) is not None for pattern in PAYLOAD_FORMS):
                    yield Violation((root, 1) + path[1:], "payload-form", "unsupported payload form")


def references(document):
    # Two passes allow forward references. Duplicate declarations never choose a winner.
    declarations = {}
    for root, record in enumerate(document):
        if record.symbol in ("hypothesis", "observation") and len(record.args) == 2:
            identifier = record.args[0]
            if identifier.args:
                yield Violation((root, 0), "identifier", "a declaration ID must be a leaf")
                continue
            if identifier.symbol in declarations:
                yield Violation((root, 0), "unique-id", "declaration ID is already in use")
                declarations[identifier.symbol] = None
            else:
                declarations[identifier.symbol] = record.symbol

    for root, record in enumerate(document):
        if record.symbol != "supports" or len(record.args) != 2:
            continue  # Malformed root shapes are rejected by ROOT_FORMS.
        for position, (identifier, expected) in enumerate(zip(record.args, ("observation", "hypothesis"))):
            path = (root, position)
            if identifier.args:
                yield Violation(path, "identifier", "a reference ID must be a leaf")
            elif identifier.symbol not in declarations:
                yield Violation(path, "unknown-reference", f"no declaration for {identifier.symbol}")
            elif declarations[identifier.symbol] is None:
                yield Violation(path, "ambiguous-reference", "reference has duplicate declarations")
            elif declarations[identifier.symbol] != expected:
                yield Violation(path, "reference-kind", f"reference must name a {expected}")


INVESTIGATION = (forms(*ROOT_FORMS, rule="root-form"), nonempty, payloads, references)


def fixed_vocabulary():
    content = parse_document("email(Alice, Bob, Report)")
    rules = (
        forms(parse_pattern("email(?sender, ?recipient, ?thing)")),
        vocabulary({"email", "Alice", "Bob", "Report"}),
    )
    assert check(content, rules) == ()
    typo = parse_document("email(Alice, Bob, Reprot)")
    issue, = check(typo, rules)
    assert issue.path == (0, 2) and issue.rule == "vocabulary"
    return issue


def investigation():
    source = (HERE / "investigation.scir").read_text(encoding="utf-8")
    content = parse_document(source)
    fingerprint = digest(content)
    assert check(content, INVESTIGATION) == ()
    assert digest(content) == fingerprint
    assert check(decode(encode(content)), INVESTIGATION) == ()
    assert check((content[2], content[0], content[1]), INVESTIGATION) == ()

    draft = parse_document("probably(causes(stale(Cache), wrong(Report)))")
    validate(draft)  # Valid generic content, but not this record dialect.
    assert check(draft, INVESTIGATION)[0].rule == "root-form"

    broken = replace_at(content, (2, 1), parse("H7"))
    validate(broken)
    issue, = check(broken, INVESTIGATION)
    assert issue == Violation((2, 1), "unknown-reference", "no declaration for H7")
    fixed = replace_at(broken, issue.path, parse("H1"))  # Explicit caller decision.
    assert check(fixed, INVESTIGATION) == () and fixed == content

    # Structural reference consistency does not establish evidential support.
    unhelpful = replace_at(content, (1, 1), parse("wrong(Cache)"))
    assert check(unhelpful, INVESTIGATION) == ()
    return issue


def correlations():
    rules = (forms(parse_pattern("edits(?person, reportOf(?person))")),)
    choices = Alternatives((
        parse_document("edits(Alice, reportOf(Alice))"),
        parse_document("edits(Carol, reportOf(Carol))"),
    ))
    assert [check(candidate, rules) for candidate in choices.options] == [(), ()]
    assert check(parse_document("edits(Alice, reportOf(Carol))"), rules)
    # Both candidates conform. Validation has not resolved the pronoun.
    return choices


if __name__ == "__main__":
    print("vocabulary:", fixed_vocabulary())
    print("references:", investigation())
    correlations()
    print("ambiguity: both correlated candidates conform; no candidate is selected")
