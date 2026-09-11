# SCIR

**Symbolic Content IR** — a lightweight symbolic representation for exchanging
content between LLM agents.

> SCIR formalizes the topology/composition of meaning while leaving the
> meanings of ordinary symbols neural and informal.

v0 is intentionally tiny: atoms, variables, and calls. There is no ontology,
type system, knowledge graph, planner, or logic framework beyond four
reserved structural operators (`not`, `and`, `or`, `if`). Ordinary symbols
such as `email`, `think`, and `yesterday` have no formal semantics; an LLM
interprets them. Nested occurrence is not top-level assertion.

See [SPEC.md](SPEC.md) for the language definition.

## Canonical example

| Natural language | SCIR |
|---|---|
| Alice left the office at six. | `at(leave(Alice, Office), six)` |
| Before leaving, she emailed Bob the latest report. | `before(email(Alice, Bob, latest(Report)), leave(Alice, Office))` |
| Bob read it on the train and noticed that one chart was wrong. | `and(at(read(Bob, Report), Train), notice(Bob, wrong(chartOf(Report))))` |
| He thinks Alice used yesterday's sales data by mistake. | `think(Bob, mistakenly(use(Alice, yesterday(SalesData))))` |
| Bob called Carol, but she did not answer. | `and(call(Bob, Carol), not(answer(Carol)))` |
| If Carol confirms the numbers tomorrow, Bob will send a corrected report to the client. | `if(tomorrow(confirm(Carol, Numbers)), send(Bob, corrected(Report), Client))` |

## Install

Python 3.10+, standard library only.

```bash
pip install -e .
```

## Usage

```python
from scir import parse, occurs, asserted, normalize

expr = parse("think(Bob, wrong(Chart))")
print(expr)
# think(Bob, wrong(Chart))

# Nested occurrence is not a top-level assertion.
subject = parse("think(Bob, mistakenly(use(Alice, yesterday(SalesData))))")
print(occurs(parse("use(Alice, ?x)"), subject))
# [{'x': yesterday(SalesData)}]
print(asserted(parse("use(Alice, ?x)"), subject))
# []

print(normalize(parse("not(not(wrong(Chart)))")))
# wrong(Chart)
print(normalize(parse("and(A, and(B, C))")))
# and(A, B, C)
```

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests
```
