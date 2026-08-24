import os
import csv
import time
import pandas as pd
from ai.diagnose import diagnose_case
from dashboard.evidence_loader import load_case_evidence

CASES_CSV_PATH = os.path.join("data", "cases.csv")
OUTPUT_CSV_PATH = os.path.join("data", "ai_responses.csv")

def run_all_cases(cases_path: str = CASES_CSV_PATH, output_path: str = OUTPUT_CSV_PATH) -> pd.DataFrame:
    """
    Runs AI diagnosis across all 35 cases in cases.csv and saves raw + parsed responses to data/ai_responses.csv.
    Resumable: skips cases whose ai_mode starts with 'Gemini' or 'Claude'.
    Stops cleanly if API quota (HTTP 429) is exceeded.
    """
    if not os.path.exists(cases_path):
        raise FileNotFoundError(f"Cases CSV dataset not found at {cases_path}")

    # Load existing responses if available
    existing_map = {}
    if os.path.exists(output_path):
        try:
            df_exist = pd.read_csv(output_path, dtype=str).fillna("")
            for _, row_e in df_exist.iterrows():
                cid = row_e.get("case_id")
                if cid:
                    existing_map[cid] = row_e.to_dict()
        except Exception:
            existing_map = {}

    df_cases = pd.read_csv(cases_path, dtype=str).fillna("")
    print(f"Starting batch AI diagnosis execution for {len(df_cases)} cases...", flush=True)

    results = []
    successful_calls = 0

    for idx, row in df_cases.iterrows():
        case_id = row.get("case_id", f"C{idx+1:03d}")
        category = row.get("category", "")
        symptom = row.get("symptom", "")
        topology_note = row.get("topology_note", "")
        raw_outputs = row.get("show_outputs", "")

        # Check if case already has real AI diagnosis
        existing_rec = existing_map.get(case_id)
        if existing_rec:
            existing_mode = str(existing_rec.get("ai_mode", ""))
            if existing_mode.startswith("Gemini") or existing_mode.startswith("Claude"):
                print(f"  Skipping Case {case_id} [{category}] -- Already diagnosed via {existing_mode}", flush=True)
                results.append(existing_rec)
                continue

        # Load evidence using evidence_loader (supporting real C001/C002 evidence files if present)
        evidence = load_case_evidence(case_id, raw_outputs)

        case_dict = {
            "case_id": case_id,
            "category": category,
            "symptom": symptom,
            "topology_note": topology_note,
            "show_outputs": evidence,
            "expected_fault": row.get("expected_fault", ""),
            "correct_fix": row.get("correct_fix", ""),
            "osi_layer": row.get("osi_layer", "Layer 3")
        }

        diag = diagnose_case(case_dict)

        # Check for quota exceeded error signal
        if diag.get("quota_exceeded"):
            print(f"\nQuota exceeded after {successful_calls} successful calls -- run again after quota resets.", flush=True)
            # Add remaining unprocessed cases from existing_map if present
            for remain_idx in range(idx, len(df_cases)):
                rem_row = df_cases.iloc[remain_idx]
                rem_id = rem_row.get("case_id")
                if rem_id in existing_map:
                    results.append(existing_map[rem_id])
            break

        fix_steps_str = "; ".join(diag.get("fix_steps", [])) if isinstance(diag.get("fix_steps"), list) else str(diag.get("fix_steps", ""))

        record = {
            "case_id": case_id,
            "category": category,
            "symptom": symptom,
            "ai_root_cause": diag.get("root_cause", ""),
            "ai_confidence": diag.get("confidence", "medium"),
            "ai_evidence": str(diag.get("evidence", "")),
            "ai_osi_layer": diag.get("osi_layer", "Layer 3"),
            "ai_next_command": diag.get("next_command", ""),
            "ai_fix_steps": fix_steps_str,
            "parse_error": str(diag.get("parse_error", False)),
            "ai_mode": diag.get("ai_mode", "Offline Engine")
        }

        if record["ai_mode"].startswith("Gemini") or record["ai_mode"].startswith("Claude"):
            successful_calls += 1

        results.append(record)
        print(f"  Processed Case {case_id} [{category}] - Confidence: {record['ai_confidence']} - Mode: {record['ai_mode']}", flush=True)

        if idx < len(df_cases) - 1:
            time.sleep(4.2)

    df_out = pd.DataFrame(results)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_out.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Batch execution complete! Saved {len(df_out)} AI responses to {output_path}")

    return df_out

if __name__ == "__main__":
    run_all_cases()
