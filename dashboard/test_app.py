import os
import unittest
import pandas as pd
from dashboard.app import load_cases, filter_cases, get_case_by_id
from checker.rule_checker import RuleChecker
from ai.diagnosis import AIDiagnosisEngine

class TestDashboardApp(unittest.TestCase):
    def setUp(self):
        self.csv_path = os.path.join("data", "cases.csv")
        self.df_cases = load_cases(self.csv_path)

    def test_csv_loading(self):
        self.assertFalse(self.df_cases.empty)
        self.assertIn("case_id", self.df_cases.columns)
        self.assertIn("symptom", self.df_cases.columns)
        self.assertIn("evidence_status", self.df_cases.columns)
        self.assertEqual(len(self.df_cases), 35)

    def test_case_filtering_by_category(self):
        vlan_cases = filter_cases(self.df_cases, category="VLAN")
        self.assertFalse(vlan_cases.empty)
        self.assertTrue(all(vlan_cases["category"] == "VLAN"))

    def test_case_filtering_by_evidence_status(self):
        verified_cases = filter_cases(self.df_cases, evidence_status="VERIFIED_LAB")
        self.assertFalse(verified_cases.empty)
        self.assertTrue(all(verified_cases["evidence_status"] == "VERIFIED_LAB"))
        self.assertEqual(len(verified_cases), 10)

    def test_case_selection(self):
        case = get_case_by_id(self.df_cases, "C001")
        self.assertIsNotNone(case)
        self.assertEqual(case["case_id"], "C001")
        self.assertEqual(case["category"], "VLAN")
        self.assertEqual(case["evidence_status"], "VERIFIED_LAB")

    def test_evidence_loading(self):
        case = get_case_by_id(self.df_cases, "C001")
        self.assertIn("show_outputs", case)
        self.assertIn("Switch1 show interfaces trunk", case["show_outputs"])

    def test_rule_checker_integration(self):
        case = get_case_by_id(self.df_cases, "C001")
        checker = RuleChecker()
        results = checker.run_all_checks(case["show_outputs"])
        self.assertEqual(len(results), 6)
        # Verify trunk pruning failure captured for C001
        failed_checks = [r for r in results if r["status"] == "FAIL"]
        self.assertTrue(len(failed_checks) > 0)

    def test_ai_engine_integration(self):
        case = get_case_by_id(self.df_cases, "C001")
        checker = RuleChecker()
        rule_results = checker.run_all_checks(case["show_outputs"])
        engine = AIDiagnosisEngine(api_key=None)
        diagnosis = engine.diagnose(case, rule_results)
        
        self.assertIsNotNone(diagnosis)
        self.assertIn("root_cause", diagnosis)
        self.assertEqual(diagnosis["ai_mode"], "Offline Demo")
        self.assertEqual(diagnosis["confidence"], "High")

    def test_missing_evidence_handling(self):
        empty_case = {
            "case_id": "C_TEST",
            "category": "Routing",
            "symptom": "Ping failed",
            "topology_note": "Host -> Router",
            "show_outputs": "",
            "evidence_status": "DEMO_TEMPLATE"
        }
        engine = AIDiagnosisEngine(api_key=None)
        diagnosis = engine.diagnose(empty_case, [])
        self.assertEqual(diagnosis["confidence"], "Low")
        self.assertIn("Insufficient", diagnosis["root_cause"])

if __name__ == "__main__":
    unittest.main()
