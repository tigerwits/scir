"""Three self-checking handoffs. Vocabulary conventions are in docs/examples.md."""
from pathlib import Path

from scir import diff, parse, parse_document, parse_pattern, query, replace_at
from scir.annotations import Alternatives, Bundle, annotate, erase
from scir.relations import decode, encode

HERE = Path(__file__).resolve().parent


def incident():
    content = parse_document((HERE / "incident.scir").read_text(encoding="utf-8"))
    hypotheses = query(content, parse_pattern(
        "suspects(?who, causes(?cause, timeout(Checkout, Database)))"))
    contradictions = query(content, parse_pattern("contradicts(?trace, ?cause)"))

    # Exact join of recorded claims; this neither validates a trace nor proves a cause.
    challenged = [(h.bindings["who"], c.bindings["trace"])
                  for h in hypotheses for c in contradictions
                  if h.bindings["cause"] == c.bindings["cause"]]
    assert challenged == [(parse("Bob"), parse("Trace18"))]
    assert query(content, parse_pattern("timeout(Checkout, Database)")) == []
    mentions = query(content, parse_pattern("timeout(Checkout, Database)"), scope="all")
    assert [h.path for h in mentions] == [(0, 1), (1, 1, 1), (2, 1, 1)]
    assert decode(encode(content)) == content
    return challenged


def handoff():
    content = parse_document((HERE / "handoff.scir").read_text(encoding="utf-8"))
    report = query(content, parse_pattern("report(?id, ?who, ?claim)"))[0]
    correction = query(content, parse_pattern("correction(?id, ?who, ?old, ?claim)"))[0]
    assert correction.bindings["old"] == report.bindings["id"]
    assert correction.bindings["who"] == report.bindings["who"]
    assert report.bindings["claim"] == parse("unavailable(Database)")
    assert correction.bindings["claim"] == parse("exhausted(ConnectionPool)")
    assert query(content, parse_pattern("unavailable(Database)")) == []
    assert query(content, parse_pattern("exhausted(ConnectionPool)")) == []

    rule = query(content, parse_pattern(
        "requires(ParseTask, on(failure(ParseDocument), ?obligations))"))[0]
    assert rule.bindings["obligations"] == parse(
        "all(preserve(Payload), return(Error), unchanged(State))")
    assert query(content, parse_pattern("unchanged(State)")) == []
    assert query(content, parse_pattern("forbids(ParseTask, evaluate(Symbols))"))

    note = annotate(content, rule.path, "source", {"document": "handoff", "sentence": 3})
    assert erase(Bundle(content, (note,))) == content

    # A caller requests this one edit; SCIR neither proposes nor executes the task.
    target = query(content, parse_pattern("pass(TestSuite)"), scope="all")[0]
    changed = replace_at(content, target.path, parse("pass(RegressionSuite)"))
    assert [d.path for d in diff(content, changed)] == [(4, 1, 0)]
    assert changed[:4] == content[:4]
    try:
        Bundle(changed, (note,))
    except ValueError:
        pass
    else:
        raise AssertionError("old annotations must not silently attach to edited snapshots")
    assert decode(encode(changed)) == changed
    return content, changed


def ambiguity():
    # Context permits Alice or Carol; actor and owner must be the same candidate.
    choices = Alternatives((
        parse_document("edits(Alice, reportOf(Alice))"),
        parse_document("edits(Carol, reportOf(Carol))"),
    ))
    pattern = parse_pattern("edits(?person, reportOf(?person))")
    people = [query(candidate, pattern)[0].bindings["person"] for candidate in choices.options]
    assert people == [parse("Alice"), parse("Carol")]
    assert query(parse_document("edits(Alice, reportOf(Carol))"), pattern) == []
    assert query(parse_document("edits(Carol, reportOf(Alice))"), pattern) == []
    for operation in (lambda: query(choices, pattern), lambda: erase(choices)):
        try:
            operation()
        except ValueError:
            pass
        else:
            raise AssertionError("unresolved alternatives are not a presented document")
    selected = choices.choose(1)  # Explicit caller choice, not inferred correctness.
    assert selected == choices.options[1]
    return choices


if __name__ == "__main__":
    incident()
    print("incident: exact join finds Bob / Trace18; nested mentions stay nested")
    handoff()
    print("handoff: correction retained, scoped requirements inspected, stale annotation rejected")
    ambiguity()
    print("ambiguity: two correlated readings retained; crossed readings do not match")
