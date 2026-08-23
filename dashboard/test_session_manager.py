import os
import json
import shutil
import tempfile
import unittest

from dashboard.session_manager import SessionManager
from dashboard.evidence_loader import load_case_evidence
from dashboard.review_manager import ReviewManager
from dashboard.verification_manager import VerificationManager
from checker.rule_checker import RuleChecker
from ai.diagnosis import AIDiagnosisEngine

class TestGuidedInvestigation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sm = SessionManager(base_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Network inventory storage
    def test_1_network_inventory_storage(self):
        inventory = {
            "end_devices_count": 4,
            "switches_count": 3,
            "routers_count": 2,
            "wireless_count": 1,
            "end_devices": ["PC0", "PC1", "PC2", "Server0"],
            "switches": ["Switch0", "Switch1", "Switch2"],
            "routers": ["Router0", "Router1"],
            "wireless": ["AP0"]
        }
        sess = self.sm.create_session(
            symptom="PC0 cannot reach Server0",
            inventory=inventory
        )
        self.assertIn("network_inventory", sess)
        inv = sess["network_inventory"]
        self.assertEqual(inv["end_devices_count"], 4)
        self.assertEqual(inv["switches_count"], 3)
        self.assertEqual(inv["routers_count"], 2)
        self.assertEqual(inv["wireless_count"], 1)
        self.assertEqual(inv["routers"], ["Router0", "Router1"])

    # 2. Starting guided investigation
    def test_2_starting_guided_investigation(self):
        sess = self.sm.create_session(symptom="Inter-VLAN ping timeout")
        self.assertEqual(sess["investigation_status"], "ACTIVE")
        self.assertEqual(sess["current_step"], 1)
        self.assertIsNotNone(sess["current_device"])
        self.assertIsNotNone(sess["current_command"])

    # 3. Investigation step creation & step incrementing
    def test_3_investigation_step_creation(self):
        sess = self.sm.create_session(symptom="IP conflict")
        session_id = sess["session_id"]
        
        self.sm.update_investigation_state(
            session_id=session_id,
            state="NO_CONFIRMED_ISSUE",
            next_device="Switch0",
            next_command="show vlan brief",
            reason_for_command="Check VLAN database.",
            result_summary="No interface errors."
        )
        updated = self.sm.get_session(session_id)
        self.assertEqual(updated["current_step"], 2)
        self.assertEqual(updated["current_device"], "Switch0")
        self.assertEqual(updated["current_command"], "show vlan brief")

    # 4 & 5. Command and device recommendation
    def test_4_and_5_command_and_device_recommendation(self):
        engine = AIDiagnosisEngine(api_key=None)
        case_info = {
            "case_id": "TEST",
            "symptom": "PC0 cannot reach remote subnet server",
            "show_outputs": "",
            "network_inventory": {"routers_count": 1, "routers": ["Router0"], "switches_count": 1, "switches": ["Switch0"]}
        }
        diag = engine.diagnose(case_info, [])
        self.assertEqual(diag["next_device"], "Router0")
        self.assertIn(diag["next_command"], ["show ip route", "show ip interface brief"])
        self.assertIsNotNone(diag["reason_for_command"])

    def test_zero_routers_inventory_validation(self):
        engine = AIDiagnosisEngine(api_key=None)
        case_info = {
            "case_id": "TEST_ZERO_ROUTERS",
            "symptom": "PC0 cannot reach PC1 in VLAN 10",
            "show_outputs": "",
            "network_inventory": {
                "routers_count": 0,
                "routers": [],
                "switches_count": 2,
                "switches": ["Switch0", "Switch1"],
                "end_devices_count": 2,
                "end_devices": ["PC0", "PC1"]
            }
        }
        diag = engine.diagnose(case_info, [])
        self.assertNotEqual(diag["next_device"], "Router0")
        self.assertIn(diag["next_device"], ["Switch0", "Switch1", "PC0", "PC1"])
        self.assertIn(diag["next_command"], ["show interfaces trunk", "show vlan brief", "show running-config"])

    # 6. Evidence submission
    def test_6_evidence_submission(self):
        sess = self.sm.create_session(symptom="Port down")
        session_id = sess["session_id"]

        cli_output = "GigabitEthernet0/0 is up, line protocol is up"
        res = self.sm.add_evidence(session_id, cli_output, "show ip interface brief", "Router0")
        self.assertEqual(len(res["evidence_list"]), 1)
        self.assertEqual(res["evidence_list"][0]["device"], "Router0")
        self.assertEqual(res["evidence_list"][0]["command"], "show ip interface brief")

    # 7. NO_CONFIRMED_ISSUE state
    def test_7_no_confirmed_issue_state(self):
        engine = AIDiagnosisEngine(api_key=None)
        case_info = {
            "case_id": "TEST",
            "symptom": "PC0 cannot reach server",
            "show_outputs": "--- [Router0] show ip interface brief ---\nGigabitEthernet0/0 192.168.1.1 YES manual up up\nGigabitEthernet0/1 10.0.0.1 YES manual up up"
        }
        diag = engine.diagnose(case_info, [])
        self.assertEqual(diag["status"], "NO_CONFIRMED_ISSUE")
        self.assertEqual(diag["confidence"], "Low")

    # 8. NEED_MORE_EVIDENCE state
    def test_8_need_more_evidence_state(self):
        engine = AIDiagnosisEngine(api_key=None)
        case_info = {
            "case_id": "TEST",
            "symptom": "PC0 ping Request timed out to 10.0.30.50",
            "show_outputs": "--- [PC0] ping 10.0.30.50 ---\nRequest timed out.\nRequest timed out."
        }
        diag = engine.diagnose(case_info, [])
        self.assertEqual(diag["status"], "NEED_MORE_EVIDENCE")
        self.assertEqual(diag["confidence"], "Medium")

    # 9 & 10. ISSUE_CONFIRMED state and stopping investigation
    def test_9_and_10_issue_confirmed_state_and_stopping(self):
        sess = self.sm.create_session(symptom="Trunk mismatch")
        session_id = sess["session_id"]

        cli_sw0 = "Vlans allowed on trunk\nFa0/2 10"
        cli_sw1 = "Vlans allowed on trunk\nFa0/1 20"
        self.sm.add_evidence(session_id, cli_sw0, "show interfaces trunk", "Switch0")
        self.sm.add_evidence(session_id, cli_sw1, "show interfaces trunk", "Switch1")

        accumulated = self.sm.get_accumulated_evidence(session_id)
        checker = RuleChecker()
        rule_res = checker.run_all_checks(accumulated)

        engine = AIDiagnosisEngine(api_key=None)
        case_info = {"case_id": session_id, "symptom": sess["symptom"], "show_outputs": accumulated}
        diag = engine.diagnose(case_info, rule_res)

        self.assertEqual(diag["status"], "ISSUE_CONFIRMED")
        self.assertEqual(diag["confidence"], "High")

        # Update investigation state to stopped
        updated_sess = self.sm.update_investigation_state(
            session_id=session_id,
            state="ISSUE_CONFIRMED",
            result_summary=diag["root_cause"],
            investigation_status="STOPPED"
        )
        self.assertEqual(updated_sess["investigation_status"], "STOPPED")

    # 11. Investigation history persistence
    def test_11_investigation_history_persistence(self):
        sess = self.sm.create_session(symptom="Ping timeout")
        session_id = sess["session_id"]

        self.sm.update_investigation_state(session_id, "NO_CONFIRMED_ISSUE", "Router0", "show ip interface brief", "Check interfaces", "All UP/UP")
        self.sm.update_investigation_state(session_id, "NEED_MORE_EVIDENCE", "Router0", "show ip route", "Check route table", "Missing route 10.0.30.0")

        json_file = os.path.join(self.temp_dir, session_id, "session.json")
        with open(json_file, "r", encoding="utf-8") as f:
            saved = json.load(f)

        hist = saved.get("investigation_history", [])
        self.assertTrue(len(hist) >= 2)
        self.assertEqual(hist[0]["step"], 1)
        self.assertEqual(hist[1]["step"], 2)

    # 12. All accumulated evidence passed to AI
    def test_12_all_accumulated_evidence_passed_to_ai(self):
        sess = self.sm.create_session(symptom="Route issue")
        session_id = sess["session_id"]

        self.sm.add_evidence(session_id, "Gi0/0 192.168.1.1 up up", "show ip interface brief", "Router0")
        self.sm.add_evidence(session_id, "Gateway of last resort is not set", "show ip route", "Router0")

        accumulated = self.sm.get_accumulated_evidence(session_id)
        self.assertIn("--- [Router0] show ip interface brief ---", accumulated)
        self.assertIn("--- [Router0] show ip route ---", accumulated)

    # 13. Human Review compatibility
    def test_13_human_review_compatibility(self):
        temp_log = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_log.close()
        try:
            rm = ReviewManager(log_path=temp_log.name)
            res = rm.record_review(
                case_id="SESSION-TEST",
                category="General",
                initial_ai_diagnosis="Diag",
                ai_confidence="High",
                human_decision="Accept",
                reason_for_correction="Confirmed"
            )
            self.assertTrue(res["success"])
            saved = rm.load_reviews()
            self.assertEqual(len(saved), 1)
        finally:
            if os.path.exists(temp_log.name):
                os.remove(temp_log.name)

    # 14. Verification compatibility
    def test_14_verification_compatibility(self):
        temp_verif = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_verif.close()
        try:
            vm = VerificationManager(log_path=temp_verif.name)
            res = vm.record_verification(
                case_id="SESSION-TEST",
                before_status="FAIL",
                after_status="PASS",
                verification_result="RESOLVED",
                verification_notes="Ping passed"
            )
            self.assertTrue(res["success"])
            saved = vm.load_verifications()
            self.assertEqual(len(saved), 1)
        finally:
            if os.path.exists(temp_verif.name):
                os.remove(temp_verif.name)

    # 15 & 16. Existing C001 & C002 evidence loading compatibility
    def test_15_and_16_c001_c002_evidence_compatibility(self):
        c001_ev = load_case_evidence("C001", default_show_outputs="CSV")
        self.assertIn("show_interfaces_trunk_Switch0", c001_ev)
        
        c002_ev = load_case_evidence("C002", default_show_outputs="CSV Fallback")
        self.assertIsNotNone(c002_ev)

    # 17. Existing session file backward compatibility
    def test_17_existing_session_file_backward_compatibility(self):
        sess_dir = os.path.join(self.temp_dir, "SESSION-OLD")
        os.makedirs(sess_dir, exist_ok=True)
        old_json = {
            "session_id": "SESSION-OLD",
            "symptom": "Old symptom",
            "topology": "Old topology",
            "evidence_list": []
        }
        with open(os.path.join(sess_dir, "session.json"), "w", encoding="utf-8") as f:
            json.dump(old_json, f)

        loaded = self.sm.get_session("SESSION-OLD")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["investigation_status"], "ACTIVE")
        self.assertEqual(loaded["current_step"], 1)

if __name__ == "__main__":
    unittest.main()
