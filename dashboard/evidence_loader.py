import os
from typing import Optional

EVIDENCE_BASE_DIR = os.path.join("data", "evidence")

def load_case_evidence(case_id: str, default_show_outputs: str = "") -> str:
    """
    Dynamically loads real CLI evidence files from data/evidence/<case_id>/ if available.
    Falls back to default_show_outputs from cases.csv if no evidence directory exists.
    """
    case_evidence_dir = os.path.join(EVIDENCE_BASE_DIR, case_id)

    if os.path.exists(case_evidence_dir) and os.path.isdir(case_evidence_dir):
        txt_files = sorted([
            f for f in os.listdir(case_evidence_dir)
            if f.endswith(".txt") and os.path.isfile(os.path.join(case_evidence_dir, f))
        ])

        if txt_files:
            sections = []
            for fname in txt_files:
                fpath = os.path.join(case_evidence_dir, fname)
                header_name = fname.replace(".txt", "")
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        sections.append(f"--- {header_name} ---\n{content}")
                except Exception:
                    continue
            
            if sections:
                return "\n\n".join(sections)

    return default_show_outputs or ""
