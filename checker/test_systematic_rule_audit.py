import csv
import os
import unittest
from checker.fact_extractor import FactExtractor, FactContext
from checker.rule_contracts import RuleStatus
from checker.rule_checker import RuleChecker
from ai.diagnosis import AIDiagnosisEngine, DiagnosticPlanner

class TestSystematicRuleAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = RuleChecker()
        cls.engine = AIDiagnosisEngine(api_key=None)

        cases_path = os.path.join("data", "cases.csv")
        if os.path.exists(cases_path):
            with open(cases_path, "r", encoding="utf-8") as f:
                cls.cases = list(csv.DictReader(f))
        else:
            cls.cases = []

    # 1. All 35 Benchmark Cases Positive Audit
    def test_all_35_benchmark_cases_positive_audit(self):
        failed_case_ids = []
        for case in self.cases:
            case_id = case["case_id"]
            evidence = case["show_outputs"]
            res = self.checker.evaluate_all_rules(evidence)
            if not res["primary_failure"]:
                failed_case_ids.append(case_id)

        self.assertEqual(
            len(failed_case_ids), 0,
            f"The following benchmark cases failed to trigger a deterministic rule: {failed_case_ids}"
        )

    # 2. Partial Evidence -> NEED_MORE_EVIDENCE
    def test_partial_evidence_returns_need_more_evidence(self):
        # Host APIPA without router config
        apipa_host_only = """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 169.254.10.25
Subnet Mask . . . . . . . . . . . : 255.255.0.0
Default Gateway . . . . . . . . . : 0.0.0.0
"""
        res_apipa = self.checker.evaluate_all_rules(apipa_host_only)
        self.assertIsNone(res_apipa["primary_failure"])
        pending_names = [r.check_name for r in res_apipa["pending_evidence_rules"]]
        self.assertIn("DHCP Relay Check", pending_names)

        # Single switch trunk without remote switch trunk or CDP log
        single_trunk = """
--- [Switch0] show interfaces trunk ---
Port        Mode         Encapsulation  Status        Native vlan
Gi0/1       on           802.1q         trunking      10
"""
        res_trunk = self.checker.evaluate_all_rules(single_trunk)
        self.assertIsNone(res_trunk["primary_failure"])
        pending_trunk = [r.check_name for r in res_trunk["pending_evidence_rules"]]
        self.assertIn("Native VLAN Mismatch Check", pending_trunk)

    # 3. Conflicting Evidence -> Correct Suppression
    def test_conflicting_evidence_correct_suppression(self):
        evidence = """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 169.254.10.25
Subnet Mask . . . . . . . . . . . : 255.255.0.0
Default Gateway . . . . . . . . . : 0.0.0.0

--- [Router0] show ip interface brief ---
GigabitEthernet0/0     192.168.10.1    YES manual up                    up

--- [Router0] show running-config ---
interface GigabitEthernet0/0
 ip address 192.168.10.1 255.255.255.0
"""
        res = self.checker.evaluate_all_rules(evidence)
        # Primary failure should be DHCP Relay, NOT Gateway Mismatch
        self.assertIsNotNone(res["primary_failure"])
        self.assertEqual(res["primary_failure"].check_name, "DHCP Relay Check")

        suppressed_names = [r.check_name for r in res["suppressed_rules"]]
        self.assertIn("Default Gateway Check", suppressed_names)

    # 4. Malformed CLI -> No False Confirmation
    def test_malformed_cli_no_false_confirmation(self):
        malformed = """
--- [Switch0] show bogus command ---
% Invalid input detected at '^' marker.
Syntax error in command line.
"""
        res = self.checker.evaluate_all_rules(malformed)
        self.assertIsNone(res["primary_failure"])

    # 5. Unrelated Command Output -> NOT_APPLICABLE
    def test_unrelated_command_output_not_applicable(self):
        unrelated = """
--- [Router0] show clock ---
*00:01:23.456 UTC Mon Mar 1 2026
"""
        res = self.checker.evaluate_all_rules(unrelated)
        self.assertIsNone(res["primary_failure"])

    # 6. Multiple Real Faults -> Primary + Secondary Findings
    def test_multiple_real_faults_primary_and_secondary(self):
        combo_evidence = """
--- [Switch0] show interfaces status ---
Port      Name               Status       Vlan       Duplex  Speed Type
Gi0/1                        err-disabled 1          auto    auto  10/100BaseTX

--- [PC0] ipconfig ---
IP Address. . . . . . . . . . . . : 10.0.1.50
Subnet Mask . . . . . . . . . . . : 255.255.255.0
Default Gateway . . . . . . . . . : 10.0.1.254

--- [Router0] show ip interface brief ---
GigabitEthernet0/0         10.0.1.1        YES manual up                    up
"""
        res = self.checker.evaluate_all_rules(combo_evidence)
        self.assertIsNotNone(res["primary_failure"])
        # Priority 1 err-disabled must be primary
        self.assertEqual(res["primary_failure"].check_name, "Interface Status Check")
        # Priority 4 gateway mismatch must be secondary
        self.assertTrue(any(r.check_name == "Default Gateway Check" for r in res["secondary_findings"]))

    # 7. Exhausted Evidence -> STOPPED Without False Diagnosis
    def test_exhausted_evidence_stopped_without_false_diagnosis(self):
        healthy_full = """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 10.0.1.10
Subnet Mask . . . . . . . . . . . : 255.255.255.0
Default Gateway . . . . . . . . . : 10.0.1.1

--- [Router0] show ip interface brief ---
GigabitEthernet0/0         10.0.1.1        YES manual up                    up

--- [Router0] show ip route ---
Gateway of last resort is 10.0.0.1 to network 0.0.0.0
C    10.0.1.0/24 is directly connected, GigabitEthernet0/0

--- [Switch0] show vlan brief ---
VLAN Name                             Status    Ports
1    default                          active    Gi0/1, Gi0/2
"""
        res = self.checker.evaluate_all_rules(healthy_full)
        self.assertIsNone(res["primary_failure"])

        case_info = {
            "symptom": "User reports network slowdown",
            "show_outputs": healthy_full,
            "network_inventory": {"end_devices": ["PC0"], "routers": ["Router0"], "switches": ["Switch0"]},
            "investigation_history": [
                {"device": "PC0", "command": "ipconfig"},
                {"device": "Router0", "command": "show ip interface brief"},
                {"device": "Router0", "command": "show ip route"},
                {"device": "Switch0", "command": "show vlan brief"}
            ]
        }
        diag = self.engine.diagnose_offline(case_info, self.checker.run_all_checks(healthy_full))
        self.assertEqual(diag["status"], "NO_CONFIRMED_ISSUE")

if __name__ == "__main__":
    unittest.main()
