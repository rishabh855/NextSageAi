import os
import csv
import tempfile
import unittest
from dashboard.verification_manager import VerificationManager

class TestVerificationManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        self.temp_file.close()
        self.log_path = self.temp_file.name
        self.mgr = VerificationManager(log_path=self.log_path)

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_empty_verification_log(self):
        records = self.mgr.load_verifications()
        self.assertEqual(records, [])
        v = self.mgr.get_verification_for_case("C001")
        self.assertIsNone(v)

    def test_create_verification_record_resolved(self):
        res = self.mgr.record_verification(
            case_id="C001",
            before_status="FAIL",
            after_status="PASS",
            verification_result="RESOLVED",
            verification_notes="Applied switchport trunk allowed vlan add 10 in Packet Tracer. Ping now succeeds."
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["record"]["verification_result"], "RESOLVED")
        self.assertEqual(res["record"]["before_status"], "FAIL")
        self.assertEqual(res["record"]["after_status"], "PASS")
        self.assertEqual(res["record"]["log_id"], "VERIF-001")

    def test_create_verification_record_not_resolved(self):
        res = self.mgr.record_verification(
            case_id="C002",
            before_status="FAIL",
            after_status="FAIL",
            verification_result="NOT_RESOLVED",
            verification_notes="Fix applied but ping still fails due to additional routing fault."
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["record"]["verification_result"], "NOT_RESOLVED")

    def test_required_verification_notes_validation(self):
        res = self.mgr.record_verification(
            case_id="C003",
            before_status="FAIL",
            after_status="PASS",
            verification_result="RESOLVED",
            verification_notes=""  # Missing notes
        )
        self.assertFalse(res["success"])
        self.assertIn("notes are required", res["error"].lower())

    def test_invalid_verification_data(self):
        res = self.mgr.record_verification(
            case_id="C004",
            before_status="INVALID_STATUS",
            after_status="PASS",
            verification_result="RESOLVED",
            verification_notes="Notes provided"
        )
        self.assertFalse(res["success"])
        self.assertIn("invalid before_status", res["error"].lower())

    def test_reloading_saved_verification_records(self):
        self.mgr.record_verification("C001", "FAIL", "PASS", "RESOLVED", "Ping PASS after fix")
        self.mgr.record_verification("C002", "FAIL", "FAIL", "NOT_RESOLVED", "Ping FAIL")

        new_mgr = VerificationManager(log_path=self.log_path)
        v1 = new_mgr.get_verification_for_case("C001")
        self.assertIsNotNone(v1)
        self.assertEqual(v1["verification_result"], "RESOLVED")

        v2 = new_mgr.get_verification_for_case("C002")
        self.assertIsNotNone(v2)
        self.assertEqual(v2["verification_result"], "NOT_RESOLVED")

if __name__ == "__main__":
    unittest.main()
