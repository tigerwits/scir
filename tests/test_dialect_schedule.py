"""Exhaust every prerequisite DAG and status assignment on three ordered checks."""
from itertools import product
import unittest
from scir import parse_document
from scir.constraints import Violation
from scir.dialects import Context, Dialect, Rule, evaluate

DOC = parse_document("a\nb")
CONTEXT = Context("fixture", "1")


def rule(name, callback, requires):
    return Rule(name, "1", "a"*64, callback, requires)


class DialectScheduleTests(unittest.TestCase):
    def test_all_three_rule_dag_outcomes_match_independent_schedule_oracle(self):
        for edges in product((False, True), repeat=3):
            prerequisites = ((), (("0",) if edges[0] else ()),
                             (("0",) if edges[1] else ()) + (("1",) if edges[2] else ()))
            for outcomes in product(("passed", "rejected", "incomplete"), repeat=3):
                expected, rules = {}, []
                for i in range(3):
                    status = outcomes[i]
                    def callback(document, context, status=status):
                        if status == "incomplete":
                            raise OSError("fixture")
                        return () if status == "passed" else (Violation(None, "fixture", "rejected"),)
                    expected[str(i)] = ("blocked" if any(expected[x] != "passed" for x in prerequisites[i]) else status)
                    rules.append(rule(str(i), callback, prerequisites[i]))
                result = evaluate(DOC, Dialect("dag", "1", tuple(rules)), CONTEXT, collection="c")
                self.assertEqual([s.status for s in result.steps], list(expected.values()))
                overall = ("incomplete" if "incomplete" in expected.values() else
                           "rejected" if any(v != "passed" for v in expected.values()) else "accepted")
                self.assertEqual(result.outcome, overall)
