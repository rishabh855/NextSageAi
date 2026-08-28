import unittest
from tests.val_harness.validator import AIOutputValidator

class TestAIOutputValidator(unittest.TestCase):
    """
    Unit tests for AIOutputValidator verifying that it correctly flags
    incorrect AI responses, unsupported evidence claims, device hallucinations,
    and ambiguous outputs.
    """

    def setUp(self):
        self.c007_ground_truth = {
            "case_id": "C007",
            "category": "Gateway/IP",
            "concept": "Default Gateway Mismatch",
            "expected_fault": "PC-1 is configured with an invalid default gateway address (10.0.1.254 instead of 10.0.1.1)."
        }
        self.c007_submitted_evidence = """
--- PC0 ipconfig ---
IP Address. . . . . . . . . . . . : 10.0.1.50
Subnet Mask . . . . . . . . . . . : 255.255.255.0
Default Gateway . . . . . . . . . : 10.0.1.254

--- Router0 show ip interface brief ---
Interface                  IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0         10.0.1.1        YES manual up                    up
        """
        self.c007_history = [
            {"device": "PC0", "command": "ipconfig"},
            {"device": "Router0", "command": "show ip interface brief"}
        ]
        self.c007_inventory = {
            "end_devices": ["PC0"],
            "switches": ["Switch0"],
            "routers": ["Router0"]
        }

    def test_deliberately_incorrect_ai_root_cause(self):
        """
        Test 1: Deliberately incorrect AI response (claiming OSPF routing failure on Router2 for C007).
        Validator MUST return FAIL.
        """
        bad_ai_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "The issue is an OSPF routing failure on Router2.",
            "evidence": ["OSPF neighbor state down"],
            "fix_steps": ["Reconfigure OSPF area 0 on Router2."]
        }
        rule_results = [{
            "check_name": "Default Gateway Check",
            "status": "FAIL",
            "details": "Gateway Mismatch: Host default gateway is set to 10.0.1.254, but active router interface is 10.0.1.1."
        }]

        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=bad_ai_diag,
            rule_results=rule_results,
            submitted_evidence_text=self.c007_submitted_evidence,
            investigation_history=self.c007_history,
            inventory=self.c007_inventory,
            ground_truth=self.c007_ground_truth
        )

        self.assertEqual(val_res["root_cause_consistency"], "FAIL")
        self.assertEqual(val_res["device_hallucination"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_unsupported_evidence_claim(self):
        """
        Test 2: Unsupported evidence claim (AI claims show running-config evidence when unsubmitted).
        Validator MUST return FAIL.
        """
        hallucinated_evidence_ai_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "Gateway Mismatch: Host default gateway is set to 10.0.1.254 instead of 10.0.1.1.",
            "evidence": ["show running-config confirms default gateway mismatch on host."],
            "fix_steps": ["Change host default gateway to 10.0.1.1."]
        }
        rule_results = [{
            "check_name": "Default Gateway Check",
            "status": "FAIL",
            "details": "Gateway Mismatch: Host default gateway is set to 10.0.1.254, but active router interface is 10.0.1.1."
        }]

        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=hallucinated_evidence_ai_diag,
            rule_results=rule_results,
            submitted_evidence_text=self.c007_submitted_evidence,
            investigation_history=self.c007_history, # running-config NOT in history
            inventory=self.c007_inventory,
            ground_truth=self.c007_ground_truth
        )

        self.assertEqual(val_res["evidence_grounding"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_ambiguous_response(self):
        """
        Test 3: Ambiguous AI response (vague text lacking domain keywords).
        Validator MUST return REVIEW_REQUIRED (not automatic PASS).
        """
        ambiguous_ai_diag = {
            "status": "NEED_MORE_EVIDENCE",
            "root_cause": "Some network components require further observation.",
            "evidence": ["Check network status"],
            "fix_steps": ["Inspect network."]
        }
        rule_results = []

        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=ambiguous_ai_diag,
            rule_results=rule_results,
            submitted_evidence_text=self.c007_submitted_evidence,
            investigation_history=self.c007_history,
            inventory=self.c007_inventory,
            ground_truth=self.c007_ground_truth
        )

        self.assertEqual(val_res["root_cause_consistency"], "REVIEW_REQUIRED")
        self.assertEqual(val_res["overall"], "REVIEW_REQUIRED")

    def test_valid_grounded_ai_response(self):
        """
        Test 4: Correct, evidence-grounded AI diagnosis.
        Validator MUST return PASS.
        """
        valid_ai_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "Host PC0 default gateway is configured as 10.0.1.254, which does not match Router0 interface IP 10.0.1.1.",
            "evidence": ["Deterministic Check [Default Gateway Check]: Host GW 10.0.1.254 vs Router IP 10.0.1.1"],
            "fix_steps": ["Reconfigure PC0 default gateway address to 10.0.1.1."]
        }
        rule_results = [{
            "check_name": "Default Gateway Check",
            "status": "FAIL",
            "details": "Gateway Mismatch: Host default gateway is set to 10.0.1.254, but active router interface is 10.0.1.1."
        }]

        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=valid_ai_diag,
            rule_results=rule_results,
            submitted_evidence_text=self.c007_submitted_evidence,
            investigation_history=self.c007_history,
            inventory=self.c007_inventory,
            ground_truth=self.c007_ground_truth
        )

        self.assertEqual(val_res["root_cause_consistency"], "PASS")
        self.assertEqual(val_res["evidence_grounding"], "PASS")
        self.assertEqual(val_res["device_hallucination"], "PASS")
        self.assertEqual(val_res["command_hallucination"], "PASS")
        self.assertEqual(val_res["technical_value_check"], "PASS")
        self.assertEqual(val_res["fix_relevance"], "PASS")
        self.assertEqual(val_res["overall"], "PASS")

if __name__ == "__main__":
    unittest.main()
