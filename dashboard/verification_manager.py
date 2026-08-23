import os
import csv
import datetime
from typing import Dict, Any, List, Optional

VERIFICATION_LOG_PATH = os.path.join("data", "verification_log.csv")

class VerificationManager:
    """
    Manages loading, validating, and persisting manual fix verification records
    into data/verification_log.csv.
    """

    CSV_HEADERS = [
        "log_id",
        "case_id",
        "timestamp",
        "before_status",
        "after_status",
        "verification_result",
        "verification_notes"
    ]

    VALID_STATUSES = {"PASS", "FAIL", "NOT_TESTED"}
    VALID_RESULTS = {"RESOLVED", "NOT_RESOLVED", "NOT_TESTED"}

    def __init__(self, log_path: str = VERIFICATION_LOG_PATH):
        self.log_path = log_path
        self.ensure_log_file()

    def ensure_log_file(self):
        """
        Ensures the verification CSV file exists with proper headers.
        """
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

    def load_verifications(self) -> List[Dict[str, str]]:
        """
        Loads all saved verification records from CSV.
        """
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return [dict(row) for row in reader]
        except Exception:
            return []

    def get_verification_for_case(self, case_id: str) -> Optional[Dict[str, str]]:
        """
        Returns the latest verification record for a given case_id if present.
        """
        records = self.load_verifications()
        case_records = [r for r in records if r.get("case_id") == case_id]
        if case_records:
            return case_records[-1]
        return None

    def record_verification(
        self,
        case_id: str,
        before_status: str,
        after_status: str,
        verification_result: str,
        verification_notes: str
    ) -> Dict[str, Any]:
        """
        Validates and records a manual fix verification entry.
        Returns a result dictionary with status and message.
        """
        before = before_status.upper().strip()
        after = after_status.upper().strip()
        result = verification_result.upper().strip()

        if before not in self.VALID_STATUSES:
            return {"success": False, "error": f"Invalid before_status '{before_status}'. Must be PASS, FAIL, or NOT_TESTED."}

        if after not in self.VALID_STATUSES:
            return {"success": False, "error": f"Invalid after_status '{after_status}'. Must be PASS, FAIL, or NOT_TESTED."}

        if result not in self.VALID_RESULTS:
            return {"success": False, "error": f"Invalid verification_result '{verification_result}'. Must be RESOLVED, NOT_RESOLVED, or NOT_TESTED."}

        # Validation: Verification notes required when result is RESOLVED or NOT_RESOLVED
        if result in {"RESOLVED", "NOT_RESOLVED"}:
            if not verification_notes or not verification_notes.strip():
                return {"success": False, "error": f"Verification notes are required when marking a case as {result}."}

        records = self.load_verifications()
        log_id = f"VERIF-{len(records) + 1:03d}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = {
            "log_id": log_id,
            "case_id": case_id,
            "timestamp": timestamp,
            "before_status": before,
            "after_status": after,
            "verification_result": result,
            "verification_notes": verification_notes.strip()
        }

        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
            writer.writerow(record)

        return {"success": True, "record": record}
