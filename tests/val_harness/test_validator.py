import unittest
from tests.val_harness.validator import AIOutputValidator

class TestAIOutputValidator(unittest.TestCase):
    """
    Unit tests for AIOutputValidator verifying that it correctly flags
    incorrect AI responses, unsupported evidence claims, device hallucinations,
    interface-role errors, IP hallucinations, unsupported CLI flags, and
    device-aware command guards.
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

        self.c010_ground_truth = {
            "case_id": "C010",
            "category": "DHCP",
            "concept": "DHCP Relay",
            "topology_note": "Router0 G0/0 = client-facing interface (192.168.10.1). Router0 G0/1 = inter-router link. Server0 = 192.168.20.10.",
            "expected_fault": "Missing ip helper-address on client-facing Router0 G0/0 pointing to DHCP Server0 (192.168.20.10)."
        }
        self.c010_submitted_evidence = """
--- Router0 show running-config ---
interface GigabitEthernet0/0
 ip address 192.168.10.1 255.255.255.0
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
--- Server0 ipconfig ---
IP Address: 192.168.20.10
        """
        self.c010_inventory = {
            "end_devices": ["PC0", "Server0 (192.168.20.10)"],
            "switches": ["Switch0"],
            "routers": ["Router0"]
        }

    def test_deliberately_incorrect_ai_root_cause(self):
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
            investigation_history=self.c007_history,
            inventory=self.c007_inventory,
            ground_truth=self.c007_ground_truth
        )

        self.assertEqual(val_res["evidence_grounding"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_ambiguous_response(self):
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

        self.assertEqual(val_res["overall"], "PASS")

    def test_dhcp_server_ip_hallucination(self):
        """
        Negative Test: AI outputs ip helper-address 10.1.1.100 when evidence/inventory says server is 192.168.20.10.
        Validator MUST return FAIL.
        """
        bad_dhcp_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "Missing ip helper-address on Router0 interface GigabitEthernet0/0.",
            "evidence": ["DHCP relay check failure"],
            "fix_steps": ["interface GigabitEthernet0/0", "ip helper-address 10.1.1.100"]
        }
        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=bad_dhcp_diag,
            rule_results=[{"check_name": "DHCP Relay Check", "status": "FAIL", "details": "Missing helper-address"}],
            submitted_evidence_text=self.c010_submitted_evidence,
            investigation_history=[],
            inventory=self.c010_inventory,
            ground_truth=self.c010_ground_truth
        )
        self.assertEqual(val_res["technical_value_check"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_wrong_interface_selection(self):
        """
        Negative Test: AI outputs ip helper-address on G0/1 (inter-router link) when client network is on G0/0.
        Validator MUST return FAIL.
        """
        bad_if_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "Missing ip helper-address on Router0.",
            "evidence": ["DHCP relay check failure"],
            "fix_steps": ["interface GigabitEthernet0/1", "ip helper-address 192.168.20.10"]
        }
        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=bad_if_diag,
            rule_results=[{"check_name": "DHCP Relay Check", "status": "FAIL", "details": "Missing helper-address"}],
            submitted_evidence_text=self.c010_submitted_evidence,
            investigation_history=[],
            inventory=self.c010_inventory,
            ground_truth=self.c010_ground_truth
        )
        self.assertEqual(val_res["interface_role_validation"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_unconfirmed_subnet_mask_fix(self):
        """
        Negative Test: AI introduces subnet mask fix when only DHCP relay failed.
        Validator MUST return FAIL.
        """
        unconfirmed_fix_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "Missing ip helper-address on Router0.",
            "evidence": ["DHCP relay check failure"],
            "fix_steps": ["interface GigabitEthernet0/0", "ip helper-address 192.168.20.10", "Reconfigure host subnet mask 255.255.255.0"]
        }
        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=unconfirmed_fix_diag,
            rule_results=[{"check_name": "DHCP Relay Check", "status": "FAIL", "details": "Missing helper-address"}],
            submitted_evidence_text=self.c010_submitted_evidence,
            investigation_history=[],
            inventory=self.c010_inventory,
            ground_truth=self.c010_ground_truth
        )
        self.assertEqual(val_res["fix_relevance"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_unsupported_packet_tracer_command(self):
        """
        Negative Test: AI recommends ipconfig /setmask 255.255.255.0 (unsupported on Packet Tracer PC).
        Validator MUST return FAIL.
        """
        bad_cmd_diag = {
            "status": "ISSUE_CONFIRMED",
            "root_cause": "Subnet mask mismatch on host.",
            "evidence": ["Subnet mask mismatch"],
            "fix_steps": ["ipconfig /setmask 255.255.255.0"]
        }
        val_res = AIOutputValidator.validate_ai_output(
            ai_diag=bad_cmd_diag,
            rule_results=[{"check_name": "Subnet Mask Check", "status": "FAIL", "details": "Subnet mask mismatch"}],
            submitted_evidence_text=self.c007_submitted_evidence,
            investigation_history=[],
            inventory=self.c007_inventory,
            ground_truth=self.c007_ground_truth
        )
        self.assertEqual(val_res["command_compatibility"], "FAIL")
        self.assertEqual(val_res["overall"], "FAIL")

    def test_guided_command_guards(self):
        """
        Unit tests for Guided Command Compatibility Guard across device types.
        """
        # show interfaces trunk on Router -> BLOCKED
        is_val, status = AIOutputValidator.validate_device_command("Router0", "show interfaces trunk")
        self.assertFalse(is_val)
        self.assertEqual(status, "BLOCKED")

        # show ip interface brief on Router -> PASS
        is_val, status = AIOutputValidator.validate_device_command("Router0", "show ip interface brief")
        self.assertTrue(is_val)
        self.assertEqual(status, "PASS")

        # show vlan brief on Switch -> PASS
        is_val, status = AIOutputValidator.validate_device_command("Switch0", "show vlan brief")
        self.assertTrue(is_val)
        self.assertEqual(status, "PASS")

        # ipconfig on PC -> PASS
        is_val, status = AIOutputValidator.validate_device_command("PC0", "ipconfig")
        self.assertTrue(is_val)
        self.assertEqual(status, "PASS")

        # Unknown device -> REVIEW_REQUIRED
        is_val, status = AIOutputValidator.validate_device_command("UnknownDevice", "show running-config")
        self.assertFalse(is_val)
        self.assertEqual(status, "REVIEW_REQUIRED")

if __name__ == "__main__":
    unittest.main()
