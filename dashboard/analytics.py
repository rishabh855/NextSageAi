import pandas as pd
from typing import Dict, Any, Optional

class AnalyticsManager:
    """
    Computes KPIs, dataset aggregations, and Responsible AI agreement metrics.
    Handles empty review logs and missing data safely without crashing.
    """

    @staticmethod
    def get_kpis(
        df_cases: pd.DataFrame,
        df_reviews: pd.DataFrame,
        df_verifications: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Computes high-level KPI metrics from cases, human reviews, and manual verifications.
        """
        total_cases = len(df_cases) if df_cases is not None else 0
        total_reviews = len(df_reviews) if df_reviews is not None and not df_reviews.empty else 0
        total_verifications = len(df_verifications) if df_verifications is not None and not df_verifications.empty else 0

        accepted_count = 0
        edited_count = 0
        rejected_count = 0
        agreement_rate = None
        resolved_count = 0

        if total_reviews > 0 and "human_decision" in df_reviews.columns:
            accepted_count = int((df_reviews["human_decision"] == "Accept").sum())
            edited_count = int((df_reviews["human_decision"] == "Edit").sum())
            rejected_count = int((df_reviews["human_decision"] == "Reject").sum())
            agreement_rate = round((accepted_count / total_reviews) * 100.0, 1)

        if total_verifications > 0 and "verification_result" in df_verifications.columns:
            resolved_count = int((df_verifications["verification_result"] == "RESOLVED").sum())

        corrections_count = edited_count + rejected_count

        return {
            "total_cases": total_cases,
            "total_reviews": total_reviews,
            "accepted_count": accepted_count,
            "edited_count": edited_count,
            "rejected_count": rejected_count,
            "corrections_count": corrections_count,
            "agreement_rate": agreement_rate,
            "total_verifications": total_verifications,
            "resolved_count": resolved_count
        }

    @staticmethod
    def get_category_counts(df_cases: pd.DataFrame) -> Dict[str, int]:
        if df_cases is None or df_cases.empty or "category" not in df_cases.columns:
            return {}
        return df_cases["category"].value_counts().to_dict()

    @staticmethod
    def get_severity_counts(df_cases: pd.DataFrame) -> Dict[str, int]:
        if df_cases is None or df_cases.empty or "severity" not in df_cases.columns:
            return {}
        return df_cases["severity"].value_counts().to_dict()

    @staticmethod
    def get_osi_layer_counts(df_cases: pd.DataFrame) -> Dict[str, int]:
        if df_cases is None or df_cases.empty or "osi_layer" not in df_cases.columns:
            return {}
        return df_cases["osi_layer"].value_counts().to_dict()

    @staticmethod
    def get_decision_counts(df_reviews: pd.DataFrame) -> Dict[str, int]:
        if df_reviews is None or df_reviews.empty or "human_decision" not in df_reviews.columns:
            return {"Accept": 0, "Edit": 0, "Reject": 0}
        counts = df_reviews["human_decision"].value_counts().to_dict()
        return {
            "Accept": counts.get("Accept", 0),
            "Edit": counts.get("Edit", 0),
            "Reject": counts.get("Reject", 0)
        }

    @staticmethod
    def get_confidence_counts(df_reviews: pd.DataFrame) -> Dict[str, int]:
        if df_reviews is None or df_reviews.empty or "ai_confidence" not in df_reviews.columns:
            return {"High": 0, "Medium": 0, "Low": 0}
        counts = df_reviews["ai_confidence"].value_counts().to_dict()
        return {
            "High": counts.get("High", 0),
            "Medium": counts.get("Medium", 0),
            "Low": counts.get("Low", 0)
        }
