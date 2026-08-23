import os
import sys
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from checker.rule_checker import RuleChecker
from ai.diagnose import diagnose_case
from checker.human_review import record_review, load_ai_responses
from dashboard.analytics import AnalyticsManager

CASES_CSV_PATH = os.path.join("data", "cases.csv")
AI_RESPONSES_PATH = os.path.join("data", "ai_responses.csv")
LOG_CSV_PATH = os.path.join("data", "verify_pipeline_test_log.csv")

def verify_pipeline() -> bool:
    """
    Executes end-to-end pipeline verification:
    Rule Checker -> AI Diagnose -> Human Review Logging -> Dashboard Data Integration.
    Prints PASS/FAIL per stage.
    """
    print("=" * 70)
    print("NetSage AI -- End-to-End Pipeline Verification")
    print("=" * 70)

    stage_pass = True

    # ----------------------------------------------------
    # STAGE 1: Dataset & Rule Checker Verification
    # ----------------------------------------------------
    print("\n[STAGE 1] Rule Checker Execution...")
    try:
        df_cases = pd.read_csv(CASES_CSV_PATH, dtype=str).fillna("")
        c001 = df_cases[df_cases["case_id"] == "C001"].iloc[0].to_dict()
        
        checker = RuleChecker()
        rule_results = checker.run_all_checks(c001.get("show_outputs", ""))
        
        if rule_results and len(rule_results) > 0:
            print("  [PASS] STAGE 1: Rule Checker executed successfully against C001 evidence.")
        else:
            print("  [FAIL] STAGE 1: Rule Checker produced empty results.")
            stage_pass = False
    except Exception as e:
        print(f"  [FAIL] STAGE 1: {e}")
        stage_pass = False

    # ----------------------------------------------------
    # STAGE 2: AI Diagnosis Engine Verification
    # ----------------------------------------------------
    print("\n[STAGE 2] AI Diagnosis Engine Execution...")
    try:
        diag_res = diagnose_case(c001)
        if diag_res and "root_cause" in diag_res and "confidence" in diag_res:
            print(f"  [PASS] STAGE 2: AI Diagnosis generated successfully (Mode: {diag_res.get('ai_mode')}, Confidence: {diag_res.get('confidence')}).")
        else:
            print("  [FAIL] STAGE 2: AI Diagnosis output invalid or missing required keys.")
            stage_pass = False
    except Exception as e:
        print(f"  [FAIL] STAGE 2: {e}")
        stage_pass = False

    # ----------------------------------------------------
    # STAGE 3: Human Review & Responsible AI Log Verification
    # ----------------------------------------------------
    print("\n[STAGE 3] Human Review Logging Verification...")
    try:
        record_review(
            case_id="VERIFY-001",
            ai_root_cause=diag_res.get("root_cause", "Test cause"),
            ai_confidence=diag_res.get("confidence", "high"),
            human_verdict="Edited",
            corrected_root_cause="Pipeline verification test correction.",
            reviewer_note="Pipeline verification test review note.",
            log_path=LOG_CSV_PATH
        )
        df_log = pd.read_csv(LOG_CSV_PATH, dtype=str).fillna("")
        test_row = df_log[df_log["case_id"] == "VERIFY-001"]
        if not test_row.empty:
            print("  [PASS] STAGE 3: Human review recorded and verified in temporary test log.")
        else:
            print("  [FAIL] STAGE 3: Human review record not found in temporary test log.")
            stage_pass = False
    except Exception as e:
        print(f"  [FAIL] STAGE 3: {e}")
        stage_pass = False

    # ----------------------------------------------------
    # STAGE 4: Dashboard Data Integration Verification
    # ----------------------------------------------------
    print("\n[STAGE 4] Dashboard Data Integration Verification...")
    try:
        df_ai = pd.read_csv(AI_RESPONSES_PATH, dtype=str).fillna("") if os.path.exists(AI_RESPONSES_PATH) else pd.DataFrame()
        df_reviews = pd.read_csv(LOG_CSV_PATH, dtype=str).fillna("") if os.path.exists(LOG_CSV_PATH) else pd.DataFrame()
        
        kpis = AnalyticsManager.get_kpis(df_cases, df_reviews)
        if kpis and kpis.get("total_cases", 0) >= 35 and kpis.get("agreement_rate") is not None:
            print(f"  [PASS] STAGE 4: Dashboard analytics computed cleanly (Total Cases: {kpis['total_cases']}, Test Reviews: {kpis['total_reviews']}, Agreement Rate: {kpis['agreement_rate']}%).")
        else:
            print("  [FAIL] STAGE 4: Dashboard analytics computation failed.")
            stage_pass = False
    except Exception as e:
        print(f"  [FAIL] STAGE 4: {e}")
        stage_pass = False

    # Cleanup temporary test log file
    if os.path.exists(LOG_CSV_PATH):
        try:
            os.remove(LOG_CSV_PATH)
        except Exception:
            pass

    print("\n" + "=" * 70)
    if stage_pass:
        print("END-TO-END PIPELINE VERIFICATION COMPLETE: ALL STAGES PASSED!")
    else:
        print("END-TO-END PIPELINE VERIFICATION FAILED: INSPECT LOGS ABOVE.")
    print("=" * 70)

    return stage_pass

if __name__ == "__main__":
    success = verify_pipeline()
    sys.exit(0 if success else 1)
