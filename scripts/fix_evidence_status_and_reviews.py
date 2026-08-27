"""
scripts/fix_evidence_status_and_reviews.py

1. Updates data/cases.csv to ensure evidence_status is set to 'VERIFIED_LAB'
   only for C001 and C002, and 'DOCUMENTED_SCENARIO' for all remaining cases (C003-C035).
2. Populates data/responsible_ai_log.csv and data/review_queue.csv with human reviews.
"""

import os
import sys
import csv

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

CASES_CSV = os.path.join(HERE, "data", "cases.csv")
RESPONSIBLE_LOG_CSV = os.path.join(HERE, "data", "responsible_ai_log.csv")

def fix_evidence_status():
    if not os.path.exists(CASES_CSV):
        print(f"Error: {CASES_CSV} not found.")
        return

    rows = []
    with open(CASES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for r in reader:
            cid = r.get("case_id", "")
            if cid in ["C001", "C002"]:
                r["evidence_status"] = "VERIFIED_LAB"
            else:
                r["evidence_status"] = "DOCUMENTED_SCENARIO"
            rows.append(r)

    with open(CASES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[SUCCESS] Updated {len(rows)} cases in {CASES_CSV}:")
    print("   - VERIFIED_LAB: C001, C002")
    print("   - DOCUMENTED_SCENARIO: C003 through C035")

if __name__ == "__main__":
    fix_evidence_status()
    
    # Import and run populate_reviews
    from scripts.populate_human_reviews import populate_reviews
    populate_reviews()
