import os
import sys
import json
import argparse
import datetime
import pandas as pd
from typing import Dict, Any, List

# Import production backend modules (No modifications to production logic)
from dashboard.session_manager import SessionManager
from checker.rule_checker import RuleChecker
from ai.diagnosis import AIDiagnosisEngine
from tests.val_harness.validator import AIOutputValidator

CASES_CSV_PATH = os.path.join("data", "cases.csv")
FIXTURES_DIR = os.path.join("tests", "fixtures")
RESULTS_JSON_PATH = os.path.join("test_results", "backend_ai_validation_results.json")

def load_cases_dataset() -> pd.DataFrame:
    if not os.path.exists(CASES_CSV_PATH):
        print(f"ERROR: Dataset not found at {CASES_CSV_PATH}")
        sys.exit(1)
    df = pd.read_csv(CASES_CSV_PATH, dtype=str)
    df.fillna("", inplace=True)
    return df

def parse_fixture_file(filepath: str) -> Dict[str, str]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    device = "Device"
    command = "CLI Command"
    lines = content.splitlines()
    cli_lines = []

    for line in lines:
        if line.startswith("DEVICE:"):
            device = line.replace("DEVICE:", "").strip()
        elif line.startswith("COMMAND:"):
            command = line.replace("COMMAND:", "").strip()
        else:
            cli_lines.append(line)

    cli_output = "\n".join(cli_lines).strip()
    return {"device": device, "command": command, "cli_output": cli_output or content}

def run_case_benchmark(case_id: str, df_cases: pd.DataFrame) -> Dict[str, Any]:
    case_matches = df_cases[df_cases["case_id"] == case_id]
    if case_matches.empty:
        return {"case_id": case_id, "status": "SKIPPED_NO_FIXTURE", "reason": "Case ID not found in dataset"}

    case_row = case_matches.iloc[0].to_dict()
    case_fixture_dir = os.path.join(FIXTURES_DIR, case_id)

    if not os.path.exists(case_fixture_dir) or not os.path.isdir(case_fixture_dir):
        return {"case_id": case_id, "status": "SKIPPED_NO_FIXTURE", "reason": f"No fixture directory at {case_fixture_dir}"}

    fixture_files = sorted([
        f for f in os.listdir(case_fixture_dir)
        if f.endswith(".txt") and os.path.isfile(os.path.join(case_fixture_dir, f))
    ])

    if not fixture_files:
        return {"case_id": case_id, "status": "SKIPPED_NO_FIXTURE", "reason": "No .txt fixture files found"}

    session_mgr = SessionManager()
    session = session_mgr.create_session(
        symptom=case_row.get("symptom", "Benchmark test symptom"),
        topology=case_row.get("topology_note", ""),
        case_id=case_id
    )
    session_id = session["session_id"]

    print("=" * 60)
    print("NETSAGE AI AUTOMATED BACKEND + AI TEST")
    print("=" * 60)
    print(f"CASE: {case_id}")
    print(f"Category: {case_row.get('category')}")
    print(f"Concept: {case_row.get('concept')}")
    print(f"Expected Fault: {case_row.get('expected_fault')}")
    print("")

    step_results = []
    total_steps = len(fixture_files)
    final_diag = None
    final_rule_results = []
    backend_status = "UNKNOWN"

    for step_idx, fname in enumerate(fixture_files, start=1):
        fpath = os.path.join(case_fixture_dir, fname)
        parsed = parse_fixture_file(fpath)
        dev = parsed["device"]
        cmd = parsed["command"]
        cli_out = parsed["cli_output"]

        print(f"STEP {step_idx}")
        print("-" * 35)
        print("Submitted:")
        print(f"{dev} -> {cmd}")

        session_mgr.add_evidence(
            session_id=session_id,
            cli_output=cli_out,
            command=cmd,
            device=dev
        )

        accumulated_evidence = session_mgr.get_accumulated_evidence(session_id)
        checker = RuleChecker()
        rule_results = checker.run_all_checks(accumulated_evidence)

        engine = AIDiagnosisEngine()
        session_info = {
            "case_id": case_id,
            "category": case_row.get("category", "General"),
            "symptom": case_row.get("symptom", ""),
            "topology_note": case_row.get("topology_note", ""),
            "show_outputs": accumulated_evidence
        }
        diag = engine.diagnose(session_info, rule_results)
        final_diag = diag
        final_rule_results = rule_results
        backend_status = diag.get("status", "NO_CONFIRMED_ISSUE")

        print(f"\nBackend Status:\n{backend_status}")

        is_final_step = (step_idx == total_steps)
        if not is_final_step:
            progression_check = "PASS" if backend_status in ["NEED_MORE_EVIDENCE", "NO_CONFIRMED_ISSUE"] else "FAIL"
            print(f"\nProgression Check:\n{progression_check}\n")
            step_results.append({
                "step": step_idx,
                "device": dev,
                "command": cmd,
                "backend_status": backend_status,
                "progression_check": progression_check
            })
        else:
            det_root_cause = diag.get("root_cause", "None")
            print(f"\nDeterministic Finding:\n{det_root_cause}")
            
            # Ground Truth Validation (Used strictly inside test harness)
            exp_fault_lower = case_row.get("expected_fault", "").lower()
            concept_lower = case_row.get("concept", "").lower()
            det_lower = det_root_cause.lower()

            benchmark_pass = False
            if exp_fault_lower and any(w in det_lower for w in exp_fault_lower.split() if len(w) > 3):
                benchmark_pass = True
            elif concept_lower and any(w in det_lower for w in concept_lower.split() if len(w) > 3):
                benchmark_pass = True

            benchmark_val = "PASS" if (benchmark_pass and backend_status == "ISSUE_CONFIRMED") else "FAIL"
            print(f"\nBenchmark Validation:\n{benchmark_val}\n")
            
            step_results.append({
                "step": step_idx,
                "device": dev,
                "command": cmd,
                "backend_status": backend_status,
                "deterministic_finding": det_root_cause,
                "benchmark_validation": benchmark_val
            })

    # AI Output Validation Suite
    accumulated_evidence = session_mgr.get_accumulated_evidence(session_id)
    history = session_mgr.get_session(session_id).get("investigation_history", [])
    inventory = session_mgr.get_session(session_id).get("network_inventory", {})

    ai_val = AIOutputValidator.validate_ai_output(
        ai_diag=final_diag,
        rule_results=final_rule_results,
        submitted_evidence_text=accumulated_evidence,
        investigation_history=history,
        inventory=inventory,
        ground_truth=case_row
    )

    print("AI OUTPUT VALIDATION")
    print("-" * 35)
    print(f"Root Cause Consistency:       {ai_val['root_cause_consistency']}")
    print(f"Evidence Grounding:           {ai_val['evidence_grounding']}")
    print(f"Device Hallucination Check:   {ai_val['device_hallucination']}")
    print(f"Command Hallucination Check:  {ai_val['command_hallucination']}")
    print(f"Technical Value Check:        {ai_val['technical_value_check']}")
    print(f"Suggested Fix Relevance:      {ai_val['fix_relevance']}")
    print(f"\nAI VALIDATION RESULT: {ai_val['overall']}")

    last_step_val = step_results[-1].get("benchmark_validation", "FAIL") if step_results else "FAIL"
    if last_step_val == "PASS" and ai_val['overall'] == "PASS":
        final_case_result = "AUTOMATED_PASS"
    elif ai_val['overall'] == "REVIEW_REQUIRED":
        final_case_result = "REVIEW_REQUIRED"
    else:
        final_case_result = "AUTOMATED_FAIL"

    print(f"\nFINAL CASE RESULT: {final_case_result}")
    print("=" * 60 + "\n")

    return {
        "case_id": case_id,
        "category": case_row.get("category"),
        "concept": case_row.get("concept"),
        "timestamp": datetime.datetime.now().isoformat(),
        "evidence_steps": step_results,
        "backend_status": backend_status,
        "detected_fault": final_diag.get("root_cause"),
        "benchmark_result": last_step_val,
        "ai_output": final_diag,
        "ai_validation": ai_val,
        "final_result": final_case_result
    }

def main():
    parser = argparse.ArgumentParser(description="NetSage AI — Automated Backend + AI Output Validation Harness")
    parser.add_argument("--case", type=str, help="Single case ID to benchmark (e.g. C007)")
    parser.add_argument("--cases", nargs="+", help="Multiple case IDs to benchmark (e.g. C007 C010)")
    args = parser.parse_args()

    df_cases = load_cases_dataset()
    target_cases = []

    if args.case:
        target_cases = [args.case.upper()]
    elif args.cases:
        target_cases = [c.upper() for c in args.cases]
    else:
        # Run all cases that have a fixture directory in tests/fixtures/
        if os.path.exists(FIXTURES_DIR):
            target_cases = sorted([
                d for d in os.listdir(FIXTURES_DIR)
                if os.path.isdir(os.path.join(FIXTURES_DIR, d)) and d.startswith("C")
            ])

    if not target_cases:
        print(f"No test cases or fixtures found in {FIXTURES_DIR}. Please specify --case C007 or add fixtures.")
        sys.exit(1)

    results_summary = []
    executed_count = 0
    passed_count = 0
    failed_count = 0
    review_req_count = 0
    skipped_count = 0

    for cid in target_cases:
        res = run_case_benchmark(cid, df_cases)
        results_summary.append(res)
        
        status = res.get("final_result", res.get("status"))
        if status == "AUTOMATED_PASS":
            passed_count += 1
            executed_count += 1
        elif status == "AUTOMATED_FAIL":
            failed_count += 1
            executed_count += 1
        elif status == "REVIEW_REQUIRED":
            review_req_count += 1
            executed_count += 1
        elif status == "SKIPPED_NO_FIXTURE":
            skipped_count += 1

    os.makedirs(os.path.dirname(RESULTS_JSON_PATH), exist_ok=True)
    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)

    print("=" * 60)
    print("BENCHMARK EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Cases Requested:  {len(target_cases)}")
    print(f"Cases Executed:   {executed_count}")
    print(f"Automated Pass:   {passed_count}")
    print(f"Automated Fail:   {failed_count}")
    print(f"Review Required:  {review_req_count}")
    print(f"Skipped (No Fixture): {skipped_count}")
    print(f"\nDetailed JSON report saved to: {RESULTS_JSON_PATH}")
    print("=" * 60)

if __name__ == "__main__":
    main()
