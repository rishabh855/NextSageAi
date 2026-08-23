import unittest
from checker.rule_checker import RuleChecker

class TestRuleChecker(unittest.TestCase):
    def setUp(self):
        self.checker = RuleChecker()

    def test_check_duplicate_ip(self):
        evidence = """
        --- Router1 show ip arp ---
        Internet  192.168.1.100           0   0001.AAAA.1111  ARPA   Gi0/0
        Internet  192.168.1.100           0   0002.BBBB.2222  ARPA   Gi0/0
        """
        res = self.checker.check_duplicate_ip(evidence)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("Duplicate IP", res["check_name"])

    def test_check_subnet_mask(self):
        evidence = """
        --- Host config ---
        Subnet Mask: 255.255.0.0
        --- Router config ---
        Internet Address is 172.16.10.1/24, Extra Subnet 255.255.255.0
        """
        res = self.checker.check_subnet_mask(evidence)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("255.255.0.0", res["details"])

    def test_check_gateway_mismatch(self):
        evidence = """
        --- Host config ---
        Default Gateway: 10.0.1.254
        --- Router show ip interface brief ---
        GigabitEthernet0/0         10.0.1.1        YES manual up                    up
        """
        res = self.checker.check_gateway_mismatch(evidence)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("10.0.1.254", res["details"])

    def test_check_interface_down(self):
        evidence = """
        --- Switch1 show interfaces Fa0/1 ---
        FastEthernet0/1 is up, line protocol is down (err-disabled)
        Port security violation count: 1
        """
        res = self.checker.check_interface_down(evidence)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("err-disabled", res["details"])

    def test_check_missing_vlan(self):
        evidence = """
        --- Switch1 show interface Fa0/5 status ---
        Fa0/5                        connected    30         a-full  a-100 10/100BaseTX
        --- Switch1 show vlan brief ---
        1    default                          active    Fa0/1
        10   Sales                            active    Fa0/6
        """
        res = self.checker.check_missing_vlan(evidence)
        self.assertEqual(res["status"], "FAIL")

    def test_check_missing_route(self):
        evidence = """
        --- PC-A ping 10.0.30.50 ---
        Request timed out.
        --- Router1 show ip route ---
        Gateway of last resort is not set
        C    192.168.10.0/24 is directly connected, GigabitEthernet0/0
        """
        res = self.checker.check_missing_route(evidence)
        self.assertEqual(res["status"], "FAIL")

    def test_run_all_checks_passing(self):
        clean_evidence = """
        Host IP: 192.168.1.10, Mask: 255.255.255.0, GW: 192.168.1.1
        Router Gi0/0: 192.168.1.1/24 up/up
        VLAN 10 active
        """
        results = self.checker.run_all_checks(clean_evidence)
        self.assertEqual(len(results), 6)

if __name__ == "__main__":
    unittest.main()
