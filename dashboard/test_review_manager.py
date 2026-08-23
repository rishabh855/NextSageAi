import os
import csv
import tempfile
import unittest
from dashboard.review_manager import ReviewManager

class TestReviewManager(unittest.TestCase):
    def setUp(self):
        # Use temporary file for review log testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        self.temp_file.close()
        self.log_path = self.temp_file.name
        self.mgr = ReviewManager(log_path=self.log_path)

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_csv_creation_and_headers(self):
        self.assertTrue(os.path.exists(self.log_path))
        with open(self.log_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertIn("log_id", headers)
            self.assertIn("human_decision", headers)
            self.assertIn("ai_confidence", headers)

    def test_record_accept(self):
        res = self.mgr.record_review(
            case_id="C001",
            category="VLAN",
            initial_ai_diagnosis="VLAN 10 pruned",
            ai_confidence="High",
            human_decision="Accept",
            reason_for_correction="Confirmed via show interfaces trunk"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["record"]["human_decision"], "Accept")
        self.assertEqual(res["record"]["log_id"], "LOG-001")

        # Test CSV persistence & reloading
        saved_reviews = self.mgr.load_reviews()
        self.assertEqual(len(saved_reviews), 1)
        self.assertEqual(saved_reviews[0]["case_id"], "C001")
        self.assertEqual(saved_reviews[0]["human_decision"], "Accept")

    def test_record_edit_valid(self):
        res = self.mgr.record_review(
            case_id="C002",
            category="VLAN",
            initial_ai_diagnosis="Cable issue",
            ai_confidence="Medium",
            human_decision="Edit",
            corrected_diagnosis="Native VLAN mismatch",
            reason_for_correction="CDP log clearly shows native VLAN mismatch on Gi0/1"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["record"]["human_decision"], "Edit")
        self.assertEqual(res["record"]["corrected_diagnosis"], "Native VLAN mismatch")

    def test_record_edit_missing_correction_reason(self):
        res = self.mgr.record_review(
            case_id="C002",
            category="VLAN",
            initial_ai_diagnosis="Cable issue",
            ai_confidence="Medium",
            human_decision="Edit",
            corrected_diagnosis="Native VLAN mismatch",
            reason_for_correction=""  # Missing reason
        )
        self.assertFalse(res["success"])
        self.assertIn("reason is required", res["error"].lower())

    def test_record_reject_valid(self):
        res = self.mgr.record_review(
            case_id="C003",
            category="ACL",
            initial_ai_diagnosis="Routing error",
            ai_confidence="Low",
            human_decision="Reject",
            reason_for_correction="AI hallucinated routing issue when ACL is dropping traffic"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["record"]["human_decision"], "Reject")

    def test_record_reject_missing_rejection_reason(self):
        res = self.mgr.record_review(
            case_id="C003",
            category="ACL",
            initial_ai_diagnosis="Routing error",
            ai_confidence="Low",
            human_decision="Reject",
            reason_for_correction=""  # Missing reason
        )
        self.assertFalse(res["success"])
        self.assertIn("reason is required", res["error"].lower())

    def test_reloading_previously_saved_review_data(self):
        # Save two reviews
        self.mgr.record_review("C001", "VLAN", "Diag1", "High", "Accept")
        self.mgr.record_review("C002", "ACL", "Diag2", "Low", "Reject", reason_for_correction="Wrong")

        # Create new manager pointing to same log file
        new_mgr = ReviewManager(log_path=self.log_path)
        c002_review = new_mgr.get_review_for_case("C002")

        self.assertIsNotNone(c002_review)
        self.assertEqual(c002_review["human_decision"], "Reject")
        self.assertEqual(c002_review["reason_for_correction"], "Wrong")

if __name__ == "__main__":
    unittest.main()
