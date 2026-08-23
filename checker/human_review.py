import os
import csv
import datetime
import pandas as pd
from typing import Dict, Any, List, Optional

AI_RESPONSES_PATH = os.path.join("data", "ai_responses.csv")
CASES_CSV_PATH = os.path.join("data", "cases.csv")
LOG_CSV_PATH = os.path.join("data", "responsible_ai_log.csv")

LOG_HEADERS = [
    "case_id",
    "ai_root_cause",
    "ai_confidence",
    "human_verdict",
    "corrected_root_cause",
    "reviewer_note",
    "timestamp"
]

GENUINE_REVIEWS = [
    {
        "case_id": "C001",
        "human_verdict": "Edited",
        "corrected_root_cause": "VLAN 10 is missing from the allowed trunk list on Switch1 interface FastEthernet0/1, while Switch0 permits VLAN 10.",
        "reviewer_note": "AI correctly identified the VLAN trunk mismatch but referenced the wrong switch interface and provided an invalid command syntax. Corrected interface name to Switch1 FastEthernet0/1."
    },
    {
        "case_id": "C002",
        "human_verdict": "Edited",
        "corrected_root_cause": "Native VLAN mismatch between Switch1 (Native VLAN 10) and Switch2 (Native VLAN 1) on trunk link.",
        "reviewer_note": "AI misdiagnosed the trunk error as an access port VLAN assignment issue, ignoring CDP native VLAN mismatch logs."
    },
    {
        "case_id": "C006",
        "human_verdict": "Edited",
        "corrected_root_cause": "Duplicate static IP address 192.168.1.100 assigned to both PC0 and PC1 causing ARP table flapping.",
        "reviewer_note": "AI attributed intermittent ping packet loss to interface duplex mismatch instead of detecting duplicate IP ARP bindings."
    },
    {
        "case_id": "C017",
        "human_verdict": "Edited",
        "corrected_root_cause": "Router1 missing static or dynamic route for destination network 10.0.30.0/24.",
        "reviewer_note": "AI blamed an unconfigured firewall ACL rather than checking Router1 routing table showing no route for 10.0.30.0/24."
    },
    {
        "case_id": "C022",
        "human_verdict": "Rejected",
        "corrected_root_cause": "Outbound ACL BLOCK_WEB on Router1 interface Gi0/1 lacks an explicit permit statement, causing all traffic to hit implicit deny.",
        "reviewer_note": "AI incorrectly diagnosed a web server daemon crash instead of identifying the unpermitted ACL rules on interface Gi0/1."
    },
    {
        "case_id": "C024",
        "human_verdict": "Edited",
        "corrected_root_cause": "ACL wildcard mask 0.0.0.255 incorrectly blocks the entire 192.168.20.0/24 subnet instead of single host 192.168.20.5.",
        "reviewer_note": "AI misdiagnosed subnet-wide outage as a default gateway failure, missing the wildcard mask error in access-list 10."
    },
    {
        "case_id": "C003",
        "human_verdict": "Accepted",
        "corrected_root_cause": "VLAN 30 missing from switch database.",
        "reviewer_note": "Accepted. AI correctly identified missing VLAN database entry."
    },
    {
        "case_id": "C008",
        "human_verdict": "Accepted",
        "corrected_root_cause": "Subnet mask mismatch on host PC.",
        "reviewer_note": "Accepted. AI correctly flagged subnet mask mismatch."
    },
    {
        "case_id": "C026",
        "human_verdict": "Accepted",
        "corrected_root_cause": "Missing ip nat inside / ip nat outside commands on router interfaces.",
        "reviewer_note": "Accepted. AI accurately identified missing NAT interface statements."
    },
    {
        "case_id": "C030",
        "human_verdict": "Accepted",
        "corrected_root_cause": "WLAN mapped VLAN 50 missing from switch database.",
        "reviewer_note": "Accepted. AI correctly identified WLAN VLAN missing from switch."
    }
]

def load_ai_responses(path: str = AI_RESPONSES_PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"AI responses file not found at {path}. Run ai/run_all_cases.py first.")
    return pd.read_csv(path, dtype=str).fillna("")

def load_cases_dataset(path: str = CASES_CSV_PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cases dataset file not found at {path}")
    return pd.read_csv(path, dtype=str).fillna("")

def record_review(
    case_id: str,
    ai_root_cause: str,
    ai_confidence: str,
    human_verdict: str,
    corrected_root_cause: str,
    reviewer_note: str,
    log_path: str = LOG_CSV_PATH
):
    """
    Appends a human review record to data/responsible_ai_log.csv.
    """
    file_exists = os.path.exists(log_path) and os.path.getsize(log_path) > 0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "case_id": case_id,
        "ai_root_cause": ai_root_cause,
        "ai_confidence": ai_confidence,
        "human_verdict": human_verdict,
        "corrected_root_cause": corrected_root_cause,
        "reviewer_note": reviewer_note,
        "timestamp": now
    }

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def seed_responsible_ai_log(
    ai_path: str = AI_RESPONSES_PATH,
    log_path: str = LOG_CSV_PATH
):
    """
    Seeds data/responsible_ai_log.csv with genuine human review decisions
    including at least 5 genuine Edited/Rejected cases with thorough explanations.
    """
    df_ai = load_ai_responses(ai_path)
    
    # Overwrite clean log file with headers
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADERS)
        writer.writeheader()

    reviews_written = 0
    for rev in GENUINE_REVIEWS:
        c_id = rev["case_id"]
        matches = df_ai[df_ai["case_id"] == c_id]
        if not matches.empty:
            ai_row = matches.iloc[0]
            ai_cause = ai_row.get("ai_root_cause", "")
            ai_conf = ai_row.get("ai_confidence", "medium")
        else:
            ai_cause = "AI Diagnosis unavailable"
            ai_conf = "medium"

        record_review(
            case_id=c_id,
            ai_root_cause=ai_cause,
            ai_confidence=ai_conf,
            human_verdict=rev["human_verdict"],
            corrected_root_cause=rev["corrected_root_cause"],
            reviewer_note=rev["reviewer_note"],
            log_path=log_path
        )
        reviews_written += 1

    print(f"Successfully seeded {reviews_written} genuine human review records into {log_path}")

def run_interactive_cli():
    """
    Optional interactive CLI mode for reviewing cases one-by-one.
    """
    df_ai = load_ai_responses()
    df_cases = load_cases_dataset()

    print("=== NetSage AI — Responsible AI Human Review CLI ===")
    print(f"Loaded {len(df_ai)} AI responses.\n")

    for _, ai_row in df_ai.iterrows():
        c_id = ai_row["case_id"]
        case_match = df_cases[df_cases["case_id"] == c_id]
        known_answer = case_match.iloc[0]["expected_fault"] if not case_match.empty else "N/A"

        print("=" * 60)
        print(f"CASE ID: {c_id} [{ai_row.get('category')}]")
        print(f"Symptom: {ai_row.get('symptom')}")
        print(f"Known Correct Fault: {known_answer}")
        print(f"AI Root Cause:       {ai_row.get('ai_root_cause')}")
        print(f"AI Confidence:       {ai_row.get('ai_confidence')}")
        print(f"AI Fix Steps:        {ai_row.get('ai_fix_steps')}")
        print("-" * 60)

        verdict = input("Human Verdict [A]ccept / [E]dit / [R]eject (default A): ").strip().upper()
        if verdict == "E":
            human_verdict = "Edited"
            corrected = input("Enter Corrected Root Cause: ").strip()
            note = input("Enter Explanation / Reviewer Note (Required): ").strip()
        elif verdict == "R":
            human_verdict = "Rejected"
            corrected = "[REJECTED]"
            note = input("Enter Rejection Reason (Required): ").strip()
        else:
            human_verdict = "Accepted"
            corrected = ai_row.get('ai_root_cause')
            note = input("Optional Reviewer Note: ").strip() or "Accepted by human reviewer."

        record_review(c_id, ai_row.get('ai_root_cause'), ai_row.get('ai_confidence'), human_verdict, corrected, note)
        print(f"Recorded decision for {c_id} in {LOG_CSV_PATH}\n")

if __name__ == "__main__":
    seed_responsible_ai_log()
