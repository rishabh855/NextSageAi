import os
import csv
import datetime
from typing import Dict, Any, List, Optional

LOG_FILE_PATH = os.path.join("data", "responsible_ai_log.csv")

class ReviewManager:
    """
    Manages loading, validating, and persisting human review decisions
    (Accept, Edit, Reject) into data/responsible_ai_log.csv.
    """

    CSV_HEADERS = [
        "log_id",
        "case_id",
        "timestamp",
        "category",
        "initial_ai_diagnosis",
        "ai_confidence",
        "human_decision",
        "corrected_diagnosis",
        "reason_for_correction"
    ]

    def __init__(self, log_path: str = LOG_FILE_PATH):
        self.log_path = log_path
        self.ensure_log_file()

    def ensure_log_file(self):
        """
        Ensures the CSV file exists with the required headers.
        """
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
            return

        # Check existing headers
        with open(self.log_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            first_row = next(reader, None)

        if first_row and "ai_confidence" not in first_row:
            # Upgrade header if missing ai_confidence
            with open(self.log_path, "r", encoding="utf-8") as rf:
                records = list(csv.DictReader(rf))

            with open(self.log_path, "w", newline="", encoding="utf-8") as wf:
                writer = csv.DictWriter(wf, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                for r in records:
                    new_rec = {k: r.get(k, "") for k in self.CSV_HEADERS}
                    new_rec["ai_confidence"] = r.get("ai_confidence", "Unknown")
                    writer.writerow(new_rec)

    def load_reviews(self) -> List[Dict[str, str]]:
        """
        Loads all saved human review records from CSV.
        """
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return [dict(row) for row in reader]
        except Exception:
            return []

    def get_review_for_case(self, case_id: str) -> Optional[Dict[str, str]]:
        """
        Returns the latest review record for a given case_id if present.
        """
        reviews = self.load_reviews()
        case_reviews = [r for r in reviews if r.get("case_id") == case_id]
        if case_reviews:
            return case_reviews[-1]
        return None

    def record_review(
        self,
        case_id: str,
        category: str,
        initial_ai_diagnosis: str,
        ai_confidence: str,
        human_decision: str,
        corrected_diagnosis: str = "",
        reason_for_correction: str = ""
    ) -> Dict[str, Any]:
        """
        Validates and records a human review decision (Accept, Edit, Reject).
        Returns a result dictionary with status and message.
        """
        decision = human_decision.capitalize()

        if decision not in {"Accept", "Edit", "Reject"}:
            return {"success": False, "error": f"Invalid decision '{human_decision}'. Must be Accept, Edit, or Reject."}

        # Validation rules
        if decision == "Edit":
            if not corrected_diagnosis or not corrected_diagnosis.strip():
                return {"success": False, "error": "Corrected diagnosis is required when editing a diagnosis."}
            if not reason_for_correction or not reason_for_correction.strip():
                return {"success": False, "error": "A correction reason is required when editing a diagnosis."}

        if decision == "Reject":
            if not reason_for_correction or not reason_for_correction.strip():
                return {"success": False, "error": "A rejection reason is required when rejecting a diagnosis."}
            corrected_diagnosis = "[REJECTED BY HUMAN REVIEWER]"

        if decision == "Accept" and not corrected_diagnosis:
            corrected_diagnosis = initial_ai_diagnosis

        reviews = self.load_reviews()
        log_id = f"LOG-{len(reviews) + 1:03d}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = {
            "log_id": log_id,
            "case_id": case_id,
            "timestamp": timestamp,
            "category": category,
            "initial_ai_diagnosis": initial_ai_diagnosis,
            "ai_confidence": ai_confidence,
            "human_decision": decision,
            "corrected_diagnosis": corrected_diagnosis,
            "reason_for_correction": reason_for_correction
        }

        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
            writer.writerow(record)

        return {"success": True, "record": record}
