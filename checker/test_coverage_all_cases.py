import csv
import os
import unittest
from checker.rule_checker import RuleChecker

class TestRuleCheckerFullCoverage(unittest.TestCase):
    """
    Automated test suite verifying that RuleChecker deterministically evaluates
    all 35 benchmark cases from data/cases.csv.
    """

    @classmethod
    def setUpClass(cls):
        cls.checker = RuleChecker()
        cases_path = os.path.join("data", "cases.csv")
        with open(cases_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cls.cases = list(reader)

    def test_all_35_cases_loaded(self):
        self.assertEqual(len(self.cases), 35, "Dataset must contain exactly 35 benchmark cases.")

    def test_deterministic_rule_coverage_100_percent(self):
        failed_case_ids = []
        for case in self.cases:
            case_id = case["case_id"]
            evidence = case["show_outputs"]
            results = self.checker.run_all_checks(evidence)
            failed_rules = [r for r in results if r["status"] == "FAIL"]
            if not failed_rules:
                failed_case_ids.append(case_id)

        self.assertEqual(
            len(failed_case_ids), 0,
            f"The following cases had no deterministic rule match: {failed_case_ids}"
        )

if __name__ == "__main__":
    unittest.main()
