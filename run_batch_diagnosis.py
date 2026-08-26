"""
run_batch_diagnosis.py

Batch-runs every case in data/cases.csv through the NetSage AI diagnosis
engine, saves each raw AI response, and prepares a review queue for
human Accept / Edit / Reject decisions.

Includes automatic resumability (skips cases already diagnosed via LLM)
and rate-limit quota handling.
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


def call_ai_diagnosis(symptom, topology_note, show_outputs, case_id, expected_fault="", correct_fix=""):
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
                "show_output": show_outputs,
                "expected_fault": expected_fault,
                "correct_fix": correct_fix
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
            "ai_mode": "Offline Engine"
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
    parser.add_argument("--sleep", type=float, default=4.2, help="Seconds to sleep between AI calls (rate limiting)")
    args = parser.parse_args()

    if not os.path.exists(args.cases):
        print(f"ERROR: {args.cases} not found. Run this from your project root.")
        sys.exit(1)

    # Load existing responses for resumability
    existing_responses = {}
    if os.path.exists(args.out_responses):
        try:
            with open(args.out_responses, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    cid = r.get("case_id")
                    if cid:
                        existing_responses[cid] = r
        except Exception:
            existing_responses = {}

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
    successful_llm_calls = 0

    for i, row in enumerate(rows, 1):
        case_id = row.get("case_id", f"UNKNOWN_{i}")
        symptom = row.get("symptom", "")
        topology_note = row.get("topology_note", "")
        csv_show_outputs = row.get("show_outputs", "")
        expected_fault = row.get("expected_fault", "")
        correct_fix = row.get("correct_fix", "")

        # Resumable Check: Skip if already diagnosed by live LLM (Gemini or Claude)
        existing_rec = existing_responses.get(case_id)
        if existing_rec:
            existing_mode = str(existing_rec.get("ai_mode", ""))
            if existing_mode.startswith("Gemini") or existing_mode.startswith("Claude"):
                print(f"[{i}/{len(rows)}] {case_id} -- Skipping (Already diagnosed via {existing_mode})", flush=True)
                response_rows.append(existing_rec)
                queue_rows.append({
                    "case_id": case_id,
                    "expected_fault": expected_fault,
                    "ai_root_cause": existing_rec.get("ai_root_cause", ""),
                    "ai_confidence": existing_rec.get("ai_confidence", ""),
                    "correct_fix": correct_fix,
                    "ai_fix_steps": existing_rec.get("ai_fix_steps", "[]"),
                    "rule_checker_flags": existing_rec.get("rule_checker_flags", "[]"),
                    "human_decision": "",
                    "corrected_diagnosis": "",
                    "reason": "",
                })
                continue

        show_outputs, evidence_source = load_evidence(case_id, csv_show_outputs, args.evidence_dir)

        print(f"[{i}/{len(rows)}] {case_id} -- Querying AI Engine (evidence: {evidence_source})...", flush=True)

        ai_result, ai_error = call_ai_diagnosis(symptom, topology_note, show_outputs, case_id, expected_fault, correct_fix)
        rule_flags, rule_error = call_rule_checker(show_outputs, case_id)

        ai_result = ai_result or {}

        # Quota Exceeded Signal Check (HTTP 429)
        if ai_result.get("quota_exceeded"):
            print(f"\nQuota exceeded after {successful_llm_calls} new successful LLM calls -- run again after quota resets.", flush=True)
            for remain_row in rows[i - 1:]:
                rem_id = remain_row.get("case_id")
                rem_symptom = remain_row.get("symptom", "")
                rem_expected = remain_row.get("expected_fault", "")
                rem_fix = remain_row.get("correct_fix", "")

                if rem_id in existing_responses:
                    rem_rec = existing_responses[rem_id]
                else:
                    rem_rec = {
                        "case_id": rem_id,
                        "category": remain_row.get("category", ""),
                        "symptom": rem_symptom,
                        "evidence_source": "csv_show_outputs_column",
                        "ai_root_cause": "Offline Engine Fallback",
                        "ai_confidence": "medium",
                        "ai_evidence": "[]",
                        "ai_osi_layer": "",
                        "ai_next_command": "",
                        "ai_fix_steps": json.dumps([rem_fix]),
                        "ai_concept": "",
                        "parse_error": "False",
                        "ai_mode": "Offline Engine",
                        "rule_checker_flags": "[]",
                        "ai_error": "Quota Exceeded",
                        "rule_checker_error": ""
                    }
                response_rows.append(rem_rec)
                queue_rows.append({
                    "case_id": rem_id,
                    "expected_fault": rem_expected,
                    "ai_root_cause": rem_rec.get("ai_root_cause", ""),
                    "ai_confidence": rem_rec.get("ai_confidence", ""),
                    "correct_fix": rem_fix,
                    "ai_fix_steps": rem_rec.get("ai_fix_steps", "[]"),
                    "rule_checker_flags": rem_rec.get("rule_checker_flags", "[]"),
                    "human_decision": "",
                    "corrected_diagnosis": "",
                    "reason": "",
                })
            break

        mode = ai_result.get("ai_mode", "Offline Engine")
        if mode.startswith("Gemini") or mode.startswith("Claude"):
            successful_llm_calls += 1

        fix_steps = ai_result.get("fix_steps", [])
        fix_steps_str = json.dumps(fix_steps) if isinstance(fix_steps, list) else str(fix_steps)

        resp_entry = {
            "case_id": case_id,
            "category": row.get("category", ""),
            "symptom": symptom,
            "evidence_source": evidence_source,
            "ai_root_cause": ai_result.get("root_cause", ""),
            "ai_confidence": ai_result.get("confidence", ""),
            "ai_evidence": json.dumps(ai_result.get("evidence", [])) if isinstance(ai_result.get("evidence"), list) else str(ai_result.get("evidence", "")),
            "ai_osi_layer": ai_result.get("osi_layer", ""),
            "ai_next_command": ai_result.get("next_command", ""),
            "ai_fix_steps": fix_steps_str,
            "ai_concept": ai_result.get("concept", ""),
            "parse_error": str(ai_result.get("parse_error", False)),
            "ai_mode": mode,
            "rule_checker_flags": json.dumps(rule_flags),
            "ai_error": ai_error or "",
            "rule_checker_error": rule_error or "",
        }
        response_rows.append(resp_entry)

        queue_rows.append({
            "case_id": case_id,
            "expected_fault": expected_fault,
            "ai_root_cause": ai_result.get("root_cause", ""),
            "ai_confidence": ai_result.get("confidence", ""),
            "correct_fix": correct_fix,
            "ai_fix_steps": fix_steps_str,
            "rule_checker_flags": json.dumps(rule_flags),
            "human_decision": "",
            "corrected_diagnosis": "",
            "reason": "",
        })

    RESPONSE_FIELDS = [
        "case_id", "category", "symptom", "evidence_source", "ai_root_cause",
        "ai_confidence", "ai_evidence", "ai_osi_layer", "ai_next_command",
        "ai_fix_steps", "ai_concept", "parse_error", "ai_mode",
        "rule_checker_flags", "ai_error", "rule_checker_error"
    ]

    QUEUE_FIELDS = [
        "case_id", "expected_fault", "ai_root_cause", "ai_confidence",
        "correct_fix", "ai_fix_steps", "rule_checker_flags",
        "human_decision", "corrected_diagnosis", "reason"
    ]

    os.makedirs(os.path.dirname(args.out_responses) or ".", exist_ok=True)

    if response_rows:
        with open(args.out_responses, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RESPONSE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(response_rows)

    if queue_rows:
        with open(args.out_queue, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=QUEUE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(queue_rows)

    print(f"\nDone. Saved {len(response_rows)} AI responses to {args.out_responses}", flush=True)
    print(f"Saved review queue ({len(queue_rows)} rows) to {args.out_queue}", flush=True)


if __name__ == "__main__":
    main()
