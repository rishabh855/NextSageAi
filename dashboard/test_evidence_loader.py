import os
import unittest
from dashboard.evidence_loader import load_case_evidence
from checker.rule_checker import RuleChecker

class TestEvidenceLoader(unittest.TestCase):
    def test_c001_real_evidence_loading(self):
        evidence = load_case_evidence("C001", default_show_outputs="CSV Default")
        self.assertIsNotNone(evidence)
        self.assertIn("--- show_interfaces_trunk_Switch0 ---", evidence)
        self.assertIn("--- show_interfaces_trunk_Switch1 ---", evidence)
        self.assertIn("--- show_running_config_Switch1 ---", evidence)
        self.assertIn("switchport trunk allowed vlan 20", evidence)

    def test_fallback_to_csv_evidence(self):
        # Case with no separate evidence directory
        fallback_text = "--- Default CSV Output ---"
        evidence = load_case_evidence("NONEXISTENT_C999", default_show_outputs=fallback_text)
        self.assertEqual(evidence, fallback_text)


    def test_evidence_formatting(self):
        evidence = load_case_evidence("C001", default_show_outputs="")
        lines = evidence.splitlines()
        # Verify headers formatted with triple dashes
        headers = [line for line in lines if line.startswith("--- ") and line.endswith(" ---")]
        self.assertTrue(len(headers) >= 3)
        self.assertIn("--- show_interfaces_trunk_Switch0 ---", headers)

    def test_c001_vlan_mismatch_detection(self):
        evidence = load_case_evidence("C001", default_show_outputs="")
        checker = RuleChecker()
        res = checker.check_missing_vlan(evidence)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("VLAN trunking mismatch", res["details"])
        self.assertIn("VLAN 10", res["details"])

if __name__ == "__main__":
    unittest.main()
