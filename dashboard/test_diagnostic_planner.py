import unittest
from ai.diagnosis import DiagnosticPlanner, AIDiagnosisEngine

class TestDiagnosticPlannerDomains(unittest.TestCase):
    def setUp(self):
        self.inventory = {
            "end_devices": ["PC0", "PC1"],
            "switches": ["Switch0", "Switch1"],
            "routers": ["Router0"],
            "wireless": ["WLC1"]
        }

    def test_vlan_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Trunk link down, VLAN 10 disallowed")
        self.assertIn("VLAN", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="VLAN 10 disallowed on trunk",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "Switch0")
        self.assertIn(cmd, ["show interfaces trunk", "show vlan brief"])

    def test_ip_gateway_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("PC0 unable to ping default gateway 10.0.1.1")
        self.assertIn("IP_GATEWAY", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="PC0 unable to ping default gateway",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "PC0")
        self.assertEqual(cmd, "ipconfig")

    def test_routing_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("OSPF neighbor adjacency down between routers")
        self.assertIn("ROUTING", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="OSPF neighbor adjacency down",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "Router0")
        self.assertEqual(cmd, "show ip route")

    def test_dhcp_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Host received 169.254 APIPA address, DHCP failure")
        self.assertIn("DHCP", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="Host received 169.254 APIPA address",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "PC0")
        self.assertEqual(cmd, "ipconfig /all")

    def test_dns_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Cannot resolve domain name example.com, DNS timeout")
        self.assertIn("DNS", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="DNS timeout when resolving server",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "PC0")
        self.assertEqual(cmd, "ipconfig /all")

    def test_acl_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Traffic blocked by access-list FILTER_VLAN")
        self.assertIn("ACL", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="Traffic blocked by access-list",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertIn(dev, ["PC0", "Router0", "Switch0"])
        self.assertIn(cmd, ["ipconfig", "show access-lists"])

    def test_nat_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Static NAT translation missing for internal server")
        self.assertIn("NAT", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="Static NAT translation missing",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertIn(dev, ["PC0", "Router0"])
        self.assertIn(cmd, ["ipconfig", "show ip nat translations"])

    def test_wireless_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Wireless host unable to authenticate, WPA2 PSK mismatch")
        self.assertIn("WIRELESS", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="Wireless host WPA2 PSK mismatch",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "PC0")
        self.assertEqual(cmd, "ipconfig /all")

    def test_interface_domain_planning(self):
        domains = DiagnosticPlanner.infer_diagnostic_domains("Port err-disabled due to port-security violation")
        self.assertIn("INTERFACE", domains)

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="Port err-disabled due to violation",
            show_outputs="",
            inventory=self.inventory
        )
        self.assertEqual(dev, "Switch0")
        self.assertEqual(cmd, "show interfaces status")

    def test_device_capabilities_enforcement(self):
        # PC should never be asked to run router/switch commands
        pc_cmd = DiagnosticPlanner.DEVICE_CAPABILITIES["END_DEVICE"]
        self.assertNotIn("show interfaces trunk", pc_cmd)
        self.assertNotIn("show ip route", pc_cmd)
        self.assertNotIn("show vlan brief", pc_cmd)

        # Router should never be asked to run switch-only commands
        rtr_cmd = DiagnosticPlanner.DEVICE_CAPABILITIES["ROUTER"]
        self.assertNotIn("show vlan brief", rtr_cmd)

    def test_no_repeated_commands(self):
        history = [
            {"device": "PC0", "command": "ipconfig"},
            {"device": "Router0", "command": "show ip interface brief"}
        ]
        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom="PC0 unable to ping gateway",
            show_outputs="",
            inventory=self.inventory,
            executed_history=history
        )
        # Should pick unexecuted PC1 ipconfig or Switch0 show vlan brief
        self.assertNotEqual((dev, cmd), ("PC0", "ipconfig"))
        self.assertNotEqual((dev, cmd), ("Router0", "show ip interface brief"))


class TestDHCPRelayAndAPIPAPrecedence(unittest.TestCase):
    def setUp(self):
        from checker.rule_checker import RuleChecker
        self.checker = RuleChecker()
        self.engine = AIDiagnosisEngine(api_key=None)
        self.inventory = {
            "end_devices": ["PC0"],
            "switches": ["Switch0"],
            "routers": ["Router0"]
        }

    def test_apipa_gateway_zero_not_gateway_mismatch(self):
        """a) APIPA + gateway 0.0.0.0 + active router interface MUST NOT return Gateway Mismatch."""
        evidence = """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 169.254.10.25
Subnet Mask . . . . . . . . . . . : 255.255.0.0
Default Gateway . . . . . . . . . : 0.0.0.0

--- [Router0] show ip interface brief ---
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.168.10.1    YES manual up                    up
"""
        results = self.checker.run_all_checks(evidence)
        failed_checks = [r for r in results if r["status"] == "FAIL"]
        gw_check = self.checker.check_gateway_mismatch(evidence)

        # Must not return gateway mismatch
        self.assertEqual(gw_check["status"], "PASS")
        self.assertFalse(any(r["check_name"] == "Default Gateway Check" for r in failed_checks))

    def test_apipa_evidence_keeps_dhcp_domain(self):
        """b) The same evidence should keep DHCP as an active diagnostic domain."""
        symptom = "PC0 unable to acquire IP address and cannot reach external network."
        evidence = """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 169.254.10.25
Subnet Mask . . . . . . . . . . . : 255.255.0.0
Default Gateway . . . . . . . . . : 0.0.0.0
"""
        domains = DiagnosticPlanner.infer_diagnostic_domains(symptom, show_outputs=evidence)
        self.assertIn("DHCP", domains)
        self.assertEqual(domains[0], "DHCP")

        dev, cmd, _ = DiagnosticPlanner.plan_next_action(
            symptom=symptom,
            show_outputs=evidence,
            inventory=self.inventory
        )
        self.assertEqual(dev, "Router0")
        self.assertIn(cmd, ["show ip interface brief", "show running-config"])

    def test_missing_ip_helper_address_returns_dhcp_relay_confirmed(self):
        """c) Missing ip helper-address in subsequent running-config MUST return ISSUE_CONFIRMED with DHCP Relay as root cause."""
        case_info = {
            "case_id": "C010",
            "symptom": "PC0 in VLAN 10 receives APIPA address 169.254.10.25 and cannot reach DHCP server.",
            "show_outputs": """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 169.254.10.25
Subnet Mask . . . . . . . . . . . : 255.255.0.0
Default Gateway . . . . . . . . . : 0.0.0.0

--- [Router0] show running-config ---
Building configuration...
interface GigabitEthernet0/0
 ip address 192.168.10.1 255.255.255.0
 duplex auto
 speed auto
"""
        }
        rule_results = self.checker.run_all_checks(case_info["show_outputs"])
        failed = [r for r in rule_results if r["status"] == "FAIL"]
        self.assertTrue(any("DHCP Relay" in r["check_name"] for r in failed))

        diag = self.engine.diagnose(case_info, rule_results)
        self.assertEqual(diag["status"], "ISSUE_CONFIRMED")
        self.assertEqual(diag["confidence"], "High")
        self.assertIn("DHCP Relay", diag["root_cause"])


if __name__ == "__main__":
    unittest.main()
