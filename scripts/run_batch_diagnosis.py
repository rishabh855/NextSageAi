import os
import json
import pandas as pd
from typing import Dict, Any, List

from checker.rule_checker import RuleChecker
from ai.diagnosis import AIDiagnosisEngine
from dashboard.evidence_loader import load_case_evidence

CASES_CSV_PATH = os.path.join("data", "cases.csv")
OUTPUT_JSON_PATH = os.path.join("data", "ai_diagnosis_results.json")

def run_batch_diagnosis() -> List[Dict[str, Any]]:
    """
    Executes rule checker and AI Diagnosis Engine across all 35 cases in data/cases.csv.
    Saves the structured diagnostic results to data/ai_diagnosis_results.json.
    """
    if not os.path.exists(CASES_CSV_PATH):
        raise FileNotFoundError(f"Cases CSV dataset not found at {CASES_CSV_PATH}")

    df = pd.read_csv(CASES_CSV_PATH, dtype=str).fillna("")
    checker = RuleChecker()
    engine = AIDiagnosisEngine()

    batch_results = []

    print(f"🔄 Starting batch diagnosis execution for {len(df)} cases...")

    for idx, row in df.iterrows():
        case_id = row.get("case_id", f"C{idx+1:03d}")
        raw_outputs = row.get("show_outputs", "")
        evidence = load_case_evidence(case_id, raw_outputs)

        case_info = {
            "case_id": case_id,
            "category": row.get("category", ""),
            "symptom": row.get("symptom", ""),
            "topology_note": row.get("topology_note", ""),
            "show_outputs": evidence,
            "expected_fault": row.get("expected_fault", ""),
            "correct_fix": row.get("correct_fix", ""),
            "osi_layer": row.get("osi_layer", ""),
            "concept": row.get("concept", ""),
            "severity": row.get("severity", ""),
            "evidence_status": row.get("evidence_status", "")
        }

        # 1. Run Rule Checker
        rule_results = checker.run_all_checks(evidence)

        # 2. Run AI Engine
        diag_response = engine.diagnose(case_info, rule_results)

        case_record = {
            "case_id": case_id,
            "category": row.get("category"),
            "symptom": row.get("symptom"),
            "rule_checker_results": rule_results,
            "ai_diagnosis": diag_response
        }

        batch_results.append(case_record)
        print(f"  ✅ Executed Case {case_id} ({row.get('category')}) — AI Mode: {diag_response.get('ai_mode')} — Confidence: {diag_response.get('confidence_score')}")

    # Save all batch results to JSON
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(batch_results, f, indent=2)

    print(f"🎉 Batch diagnosis complete! Saved {len(batch_results)} case responses to {OUTPUT_JSON_PATH}")
    return batch_results

if __name__ == "__main__":
    run_batch_diagnosis()
