"""Count audit retrieval as real delivery cost; do not count failed arms as cheap."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("study_delivery", ROOT / "tools/study_delivery.py")
STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STUDY)


class DeliveryCostTests(unittest.TestCase):
    def test_complete_costs_preserve_negative_and_positive_comparisons(self):
        report, payloads = STUDY.study()
        self.assertEqual(len(report["observations"]), 12)
        for name, expected in report["payloads"].items():
            raw = payloads[name].encode("utf-8")
            self.assertEqual(len(raw), expected["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])
        for row in report["observations"]:
            self.assertEqual(row["packet_and_artifact_bytes"], row["packet_bytes"] + row["artifact_bytes"])
            self.assertGreater(row["packet_and_artifact_bytes"], row["legacy_bytes"])
            if row["kind"] == "selection":
                self.assertEqual(row["selected_records"], {"independent": 1, "modules": 8, "chain": 128}[row["topology"]])
        chain = next(r for r in report["observations"] if r["kind"] == "selection" and r["topology"] == "chain" and r["encoding"] == "notation")
        single = next(r for r in report["observations"] if r["kind"] == "selection" and r["topology"] == "independent" and r["encoding"] == "notation")
        self.assertLess(chain["packet_bytes"], chain["legacy_bytes"])
        self.assertGreater(single["packet_bytes"], single["legacy_bytes"])
        self.assertEqual(report["tokens"], "unmeasured")
        self.assertEqual(report["agent_trials"], 0)
