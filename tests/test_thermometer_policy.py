import unittest

from thermometer_policy import validate_assessment
from thermometer import proportions


class ThermometerPolicyTests(unittest.TestCase):
    def test_direction_requires_matching_mechanism_and_evidence(self):
        base = {"status": "classified", "category": "destabilizing", "reason_codes": ["D2"],
                "reason": "Raginimas smurtauti", "evidence": "ištrauka"}
        self.assertEqual(validate_assessment(base), base)
        with self.assertRaises(ValueError):
            validate_assessment({**base, "reason_codes": ["N1"]})
        with self.assertRaises(ValueError):
            validate_assessment({**base, "reason_codes": ["D1"]})
        with self.assertRaises(ValueError):
            validate_assessment({**base, "evidence": ""})

    def test_uncertainty_never_becomes_neutral(self):
        for status in ("needs_review", "waiting_data", "error"):
            validate_assessment({"status": status, "category": None, "reason_codes": []})
            with self.assertRaises(ValueError):
                validate_assessment({"status": status, "category": "neutral", "reason_codes": []})

    def test_percentages_exclude_pending_and_expose_coverage(self):
        rows = [{"assessment": {"status": "assessed", "category": "neutral"}}]
        rows += [{"assessment": {"status": s, "category": None}} for s in
                 ("waiting_data", "needs_review", "error", "not_analyzed")]
        report = proportions(rows)
        self.assertEqual(report["coverage_percent"], 20)
        self.assertEqual(report["categories"][1]["percent"], 100)
        self.assertEqual(report["pending"], dict.fromkeys(
            ("waiting_data", "needs_review", "error", "not_analyzed"), 1))


if __name__ == "__main__":
    unittest.main()
