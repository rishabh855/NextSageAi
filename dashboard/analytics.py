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
        total_cases = len(df_cases) if df_cases is not None else 0
        total_reviews = len(df_reviews) if df_reviews is not None and not df_reviews.empty else 0
        total_verifications = len(df_verifications) if df_verifications is not None and not df_verifications.empty else 0

        accepted_count = 0
        edited_count = 0
        rejected_count = 0
        agreement_rate = None
        resolved_count = 0

        verdict_col = None
        if df_reviews is not None and not df_reviews.empty:
            if "human_verdict" in df_reviews.columns:
                verdict_col = "human_verdict"
            elif "human_decision" in df_reviews.columns:
                verdict_col = "human_decision"

        if total_reviews > 0 and verdict_col:
            v_series = df_reviews[verdict_col].astype(str).str.strip().str.lower()
            accepted_count = int((v_series.isin(["accept", "accepted"])).sum())
            edited_count = int((v_series.isin(["edit", "edited"])).sum())
            rejected_count = int((v_series.isin(["reject", "rejected"])).sum())
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
        if df_reviews is None or df_reviews.empty:
            return {"Accept": 0, "Accepted": 0, "Edit": 0, "Edited": 0, "Reject": 0, "Rejected": 0}
        
        verdict_col = "human_verdict" if "human_verdict" in df_reviews.columns else ("human_decision" if "human_decision" in df_reviews.columns else None)
        if not verdict_col:
            return {"Accept": 0, "Accepted": 0, "Edit": 0, "Edited": 0, "Reject": 0, "Rejected": 0}

        v_series = df_reviews[verdict_col].astype(str).str.strip().str.capitalize()
        counts = v_series.value_counts().to_dict()
        
        acc = counts.get("Accepted", 0) + counts.get("Accept", 0)
        edi = counts.get("Edited", 0) + counts.get("Edit", 0)
        rej = counts.get("Rejected", 0) + counts.get("Reject", 0)

        return {
            "Accept": acc,
            "Accepted": acc,
            "Edit": edi,
            "Edited": edi,
            "Reject": rej,
            "Rejected": rej
        }

    @staticmethod
    def get_confidence_counts(df_reviews: pd.DataFrame) -> Dict[str, int]:
        if df_reviews is None or df_reviews.empty:
            return {"High": 0, "Medium": 0, "Low": 0}
        
        col = "ai_confidence" if "ai_confidence" in df_reviews.columns else None
        if not col:
            return {"High": 0, "Medium": 0, "Low": 0}

        v_series = df_reviews[col].astype(str).str.strip().str.capitalize()
        counts = v_series.value_counts().to_dict()
        return {
            "High": counts.get("High", 0),
            "Medium": counts.get("Medium", 0),
            "Low": counts.get("Low", 0)
        }
