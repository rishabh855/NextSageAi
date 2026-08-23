import unittest
import pandas as pd
from dashboard.analytics import AnalyticsManager

class TestAnalyticsManager(unittest.TestCase):
    def setUp(self):
        self.sample_cases = pd.DataFrame([
            {"case_id": "C001", "category": "VLAN", "severity": "High", "osi_layer": "Layer 2"},
            {"case_id": "C002", "category": "VLAN", "severity": "Medium", "osi_layer": "Layer 2"},
            {"case_id": "C003", "category": "Routing", "severity": "High", "osi_layer": "Layer 3"},
            {"case_id": "C004", "category": "ACL", "severity": "High", "osi_layer": "Layer 4"},
        ])

        self.sample_reviews = pd.DataFrame([
            {"log_id": "LOG-001", "case_id": "C001", "human_decision": "Accept", "ai_confidence": "High"},
            {"log_id": "LOG-002", "case_id": "C002", "human_decision": "Edit", "ai_confidence": "Medium"},
            {"log_id": "LOG-003", "case_id": "C003", "human_decision": "Accept", "ai_confidence": "High"},
            {"log_id": "LOG-004", "case_id": "C004", "human_decision": "Reject", "ai_confidence": "Low"},
        ])

    def test_empty_review_log(self):
        empty_reviews = pd.DataFrame()
        kpis = AnalyticsManager.get_kpis(self.sample_cases, empty_reviews)
        self.assertEqual(kpis["total_cases"], 4)
        self.assertEqual(kpis["total_reviews"], 0)
        self.assertEqual(kpis["accepted_count"], 0)
        self.assertIsNone(kpis["agreement_rate"])

    def test_review_statistics(self):
        kpis = AnalyticsManager.get_kpis(self.sample_cases, self.sample_reviews)
        self.assertEqual(kpis["total_cases"], 4)
        self.assertEqual(kpis["total_reviews"], 4)
        self.assertEqual(kpis["accepted_count"], 2)
        self.assertEqual(kpis["edited_count"], 1)
        self.assertEqual(kpis["rejected_count"], 1)
        self.assertEqual(kpis["corrections_count"], 2)

    def test_agreement_rate_calculation(self):
        # 2 Accept out of 4 total reviews = 50.0%
        kpis = AnalyticsManager.get_kpis(self.sample_cases, self.sample_reviews)
        self.assertEqual(kpis["agreement_rate"], 50.0)

        # 100% agreement test
        all_accept = pd.DataFrame([
            {"human_decision": "Accept"},
            {"human_decision": "Accept"}
        ])
        kpis_100 = AnalyticsManager.get_kpis(self.sample_cases, all_accept)
        self.assertEqual(kpis_100["agreement_rate"], 100.0)

    def test_category_aggregation(self):
        cat_counts = AnalyticsManager.get_category_counts(self.sample_cases)
        self.assertEqual(cat_counts.get("VLAN"), 2)
        self.assertEqual(cat_counts.get("Routing"), 1)
        self.assertEqual(cat_counts.get("ACL"), 1)

    def test_decision_aggregation(self):
        dec_counts = AnalyticsManager.get_decision_counts(self.sample_reviews)
        self.assertEqual(dec_counts["Accept"], 2)
        self.assertEqual(dec_counts["Edit"], 1)
        self.assertEqual(dec_counts["Reject"], 1)

    def test_missing_and_invalid_data_handling(self):
        invalid_cases = pd.DataFrame()
        invalid_reviews = None
        kpis = AnalyticsManager.get_kpis(invalid_cases, invalid_reviews)
        self.assertEqual(kpis["total_cases"], 0)
        self.assertEqual(kpis["total_reviews"], 0)
        self.assertIsNone(kpis["agreement_rate"])

        cat_counts = AnalyticsManager.get_category_counts(None)
        self.assertEqual(cat_counts, {})

if __name__ == "__main__":
    unittest.main()
