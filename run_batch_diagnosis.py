"""
run_batch_diagnosis.py

Batch-runs every case in data/cases.csv through the NetSage AI diagnosis
engine, saves each raw AI response, and prepares a review queue for
human Accept / Edit / Reject decisions.

Drop this file in your project root (same level as data/, ai/, checker/).

WHAT THIS DOES
--------------
1. Reads every row of data/cases.csv (no .pkt files needed — it uses the
   show_outputs column that's already in the CSV, same as evidence_loader.py
   does when there's no real evidence/<case_id>/ folder).
2. If a real evidence/<case_id>/ folder exists (like C001, C002), it uses
   that instead — same fallback logic your dashboard already relies on.
3. Calls your existing diagnose() / diagnose_case() function from ai/ for each case.
4. Saves every AI response to data/ai_responses.csv (one row per case) —
   this is your audit trail, separate from cases.csv's known-correct answers.
5. Also runs the deterministic rule checker on each case and records
   agreement/disagreement between rule checker and AI, which feeds
   straight into your dashboard's "AI vs human agreement" panel.
6. Produces data/review_queue.csv — one row per case with AI's answer
   next to the expected answer, and a blank decision column for you to
   fill in as you do human review (Accept / Edit / Reject + notes).
"""

import argparse
import csv
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.getcwd())

AI_AVAILABLE = False
CHECKER_AVAILABLE = False

try:
    from ai.diagnose import diagnose_case as _real_diagnose_case
    from ai.diagnosis import AIDiagnosisEngine
    AI_AVAILABLE = True
except Exception:
    _real_diagnose_case = None

try:
    from checker.rule_checker import RuleChecker
    _rule_checker_instance = RuleChecker()
    CHECKER_AVAILABLE = True
except Exception:
    _rule_checker_instance = None


def call_ai_diagnosis(symptom, topology_note, show_outputs, case_id):
    """
    Wraps NetSage AI diagnosis engine call.
    """
    if AI_AVAILABLE:
        try:
            case_dict = {
                "case_id": case_id,
                "symptom": symptom,
                "topology_note": topology_note,
                "show_outputs": show_outputs,
                "show_output": show_outputs
            }
            if _real_diagnose_case:
                result = _real_diagnose_case(case_dict)
            else:
                engine = AIDiagnosisEngine()
                rule_results = _rule_checker_instance.run_all_checks(show_outputs) if _rule_checker_instance else []
                result = engine.diagnose(case_dict, rule_results)

            if isinstance(result, str):
                result = json.loads(result)
            return result, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"
    else:
        return {
            "root_cause": "STUB: ai module not importable -- wire in real call",
            "confidence": "N/A",
            "evidence": [],
            "next_command": "",
            "fix_steps": [],
            "osi_layer": "",
            "concept": "",
        }, "ai module not found -- using stub output"


def call_rule_checker(show_outputs, case_id):
    """
    Wraps real checker/rule_checker.py RuleChecker call.
    """
    if CHECKER_AVAILABLE and _rule_checker_instance:
        try:
            results = _rule_checker_instance.run_all_checks(show_outputs)
            failed_checks = [r.get("check_name") for r in results if isinstance(r, dict) and r.get("status") == "FAIL"]
            return failed_checks, None
        except Exception as e:
            return [], f"{type(e).__name__}: {e}"
    else:
        return [], "checker.rule_checker module not found -- skipped"


def load_evidence(case_id, csv_show_outputs, evidence_dir="data/evidence"):
    """
    Prefer real captured evidence/<case_id>/*.txt if it exists (C001, C002),
    otherwise fall back to the show_outputs column already in cases.csv.
    Mirrors dashboard/evidence_loader.py fallback logic.
    """
    case_folder = os.path.join(evidence_dir, case_id)
    if os.path.isdir(case_folder):
        txt_files = sorted(f for f in os.listdir(case_folder) if f.endswith(".txt"))
        if txt_files:
            combined = []
            for fname in txt_files:
                with open(os.path.join(case_folder, fname), "r", encoding="utf-8") as f:
                    combined.append(f"--- {fname} ---\n{f.read()}")
            return "\n\n".join(combined), "real_evidence_folder"
    return csv_show_outputs, "csv_show_outputs_column"


def main():
    parser = argparse.ArgumentParser(description="Batch-run AI diagnosis across all cases.")
    parser.add_argument("--cases", default="data/cases.csv", help="Path to cases.csv")
    parser.add_argument("--evidence-dir", default="data/evidence", help="Path to evidence folders")
    parser.add_argument("--out-responses", default="data/ai_responses.csv", help="Where to save raw AI responses")
    parser.add_argument("--out-queue", default="data/review_queue.csv", help="Where to save the human review queue")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N rows (useful for testing)")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between AI calls (rate limiting)")
    args = parser.parse_args()

    if not os.path.exists(args.cases):
        print(f"ERROR: {args.cases} not found. Run this from your project root.")
        sys.exit(1)

    with open(args.cases, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if args.limit:
        rows = rows[: args.limit]

    print(f"Loaded {len(rows)} cases from {args.cases}", flush=True)
    if not AI_AVAILABLE:
        print("WARNING: ai.diagnosis not importable -- running in STUB mode.", flush=True)
    if not CHECKER_AVAILABLE:
        print("WARNING: checker.rule_checker not importable -- rule checker columns will be blank.", flush=True)

    response_rows = []
    queue_rows = []

    for i, row in enumerate(rows, 1):
        case_id = row.get("case_id", f"UNKNOWN_{i}")
        symptom = row.get("symptom", "")
        topology_note = row.get("topology_note", "")
        csv_show_outputs = row.get("show_outputs", "")
        expected_fault = row.get("expected_fault", "")
        correct_fix = row.get("correct_fix", "")

        show_outputs, evidence_source = load_evidence(case_id, csv_show_outputs, args.evidence_dir)

        print(f"[{i}/{len(rows)}] {case_id} -- evidence source: {evidence_source}", flush=True)

        ai_result, ai_error = call_ai_diagnosis(symptom, topology_note, show_outputs, case_id)
        rule_flags, rule_error = call_rule_checker(show_outputs, case_id)

        ai_result = ai_result or {}
        response_rows.append({
            "case_id": case_id,
            "evidence_source": evidence_source,
            "ai_root_cause": ai_result.get("root_cause", ""),
            "ai_confidence": ai_result.get("confidence", ""),
            "ai_evidence": json.dumps(ai_result.get("evidence", [])),
            "ai_next_command": ai_result.get("next_command", ""),
            "ai_fix_steps": json.dumps(ai_result.get("fix_steps", [])),
            "ai_osi_layer": ai_result.get("osi_layer", ""),
            "ai_concept": ai_result.get("concept", ""),
            "rule_checker_flags": json.dumps(rule_flags),
            "ai_error": ai_error or "",
            "rule_checker_error": rule_error or "",
        })

        queue_rows.append({
            "case_id": case_id,
            "expected_fault": expected_fault,
            "ai_root_cause": ai_result.get("root_cause", ""),
            "ai_confidence": ai_result.get("confidence", ""),
            "correct_fix": correct_fix,
            "ai_fix_steps": json.dumps(ai_result.get("fix_steps", [])),
            "rule_checker_flags": json.dumps(rule_flags),
            "human_decision": "",     # fill in: Accept / Edit / Reject
            "corrected_diagnosis": "",  # fill in only if Edit or Reject
            "reason": "",              # fill in only if Edit or Reject
        })

        if args.sleep and AI_AVAILABLE:
            time.sleep(args.sleep)

    os.makedirs(os.path.dirname(args.out_responses) or ".", exist_ok=True)

    with open(args.out_responses, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(response_rows[0].keys()))
        writer.writeheader()
        writer.writerows(response_rows)

    with open(args.out_queue, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(queue_rows[0].keys()))
        writer.writeheader()
        writer.writerows(queue_rows)

    print(f"\nDone. Wrote {len(response_rows)} AI responses to {args.out_responses}")
    print(f"Wrote review queue ({len(queue_rows)} rows) to {args.out_queue}")


if __name__ == "__main__":
    main()
