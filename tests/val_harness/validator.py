import re
from typing import Dict, Any, List

STOP_WORDS = {
    "with", "from", "that", "this", "have", "been", "were", "where",
    "when", "what", "than", "then", "into", "over", "under", "interface",
    "device", "configured", "check", "issue", "failure", "error", "problem"
}

class AIOutputValidator:
    """
    Validates AI-generated diagnosis responses for consistency, evidence grounding,
    hallucination of devices/commands/values, and fix relevance.
    """

    @staticmethod
    def extract_ips(text: str) -> List[str]:
        return re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)

    @staticmethod
    def extract_vlans(text: str) -> List[str]:
        return re.findall(r"\bVLAN\s*(\d+)\b", text, re.IGNORECASE)

    @staticmethod
    def extract_devices(text: str) -> List[str]:
        return re.findall(r"\b(PC\d*|Switch\d*|Router\d*|R\d+|SW\d+|Server|Host)\b", text, re.IGNORECASE)

    @staticmethod
    def validate_ai_output(
        ai_diag: Dict[str, Any],
        rule_results: List[Dict[str, Any]],
        submitted_evidence_text: str,
        investigation_history: List[Dict[str, Any]],
        inventory: Dict[str, Any],
        ground_truth: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes 6 explicit AI validation checks:
        1. Root Cause Consistency
        2. Evidence Grounding
        3. Device Hallucination Check
        4. Command Hallucination Check
        5. Technical Value Check
        6. Suggested Fix Relevance
        """
        checks = {}
        ai_root_cause = str(ai_diag.get("root_cause", "") or ai_diag.get("likely_root_cause", ""))
        ai_evidence_list = ai_diag.get("evidence", []) or ai_diag.get("evidence_cited", [])
        ai_fix_steps = ai_diag.get("fix_steps", []) or ai_diag.get("suggested_fix", [])
        evidence_lower = submitted_evidence_text.lower()

        # --- 1. Root Cause Consistency ---
        expected_fault = ground_truth.get("expected_fault", "").lower()
        concept = ground_truth.get("concept", "").lower()
        det_failures = [r for r in rule_results if r.get("status") == "FAIL"]
        det_text = " ".join([f.get("details", "").lower() for f in det_failures])

        ai_rc_low = ai_root_cause.lower()

        exp_keywords = [w for w in re.findall(r"\b[a-z0-9_\-]{4,}\b", expected_fault) if w not in STOP_WORDS]
        concept_keywords = [w for w in re.findall(r"\b[a-z0-9_\-]{4,}\b", concept) if w not in STOP_WORDS]
        det_keywords = [w for w in re.findall(r"\b[a-z0-9_\-]{4,}\b", det_text) if w not in STOP_WORDS]

        consistent = False
        if exp_keywords and any(kw in ai_rc_low for kw in exp_keywords):
            consistent = True
        elif concept_keywords and any(kw in ai_rc_low for kw in concept_keywords):
            consistent = True
        elif det_keywords and any(kw in ai_rc_low for kw in det_keywords):
            consistent = True
        
        # Explicit check for domain contradictions
        if "ospf" in ai_rc_low and "ospf" not in concept and "ospf" not in det_text:
            consistent = False
        if "vlan" in ai_rc_low and "vlan" not in concept and "vlan" not in det_text and "trunk" not in concept:
            consistent = False

        checks["root_cause_consistency"] = "PASS" if consistent else ("FAIL" if ("ospf" in ai_rc_low or "bgp" in ai_rc_low or "eigrp" in ai_rc_low) else "REVIEW_REQUIRED")

        # --- 2. Evidence Grounding ---
        grounded = True
        grounding_reason = ""
        for ev in ai_evidence_list:
            ev_str = str(ev).lower()
            if "running-config" in ev_str and "running-config" not in evidence_lower:
                grounded = False
                grounding_reason = "Unsupported Evidence Claim: Cites running-config when unsubmitted."
                break
            if "show interfaces trunk" in ev_str and "trunk" not in evidence_lower:
                grounded = False
                grounding_reason = "Unsupported Evidence Claim: Cites show interfaces trunk when unsubmitted."
                break

        checks["evidence_grounding"] = "PASS" if grounded else "FAIL"

        # --- 3. Device Hallucination Check ---
        known_devices = set([d.lower() for d in inventory.get("end_devices", []) + inventory.get("switches", []) + inventory.get("routers", [])])
        for h in investigation_history:
            if h.get("device"):
                known_devices.add(h.get("device").lower())
        
        generic_terms = {"pc", "router", "switch", "server", "host", "device", "gateway", "client", "laptop", "ap"}

        mentioned_devices = AIOutputValidator.extract_devices(ai_root_cause + " " + " ".join(ai_fix_steps))
        hallucinated_devs = []
        for d in set(mentioned_devices):
            d_low = d.lower()
            if d_low not in known_devices and d_low not in generic_terms:
                hallucinated_devs.append(d)

        checks["device_hallucination"] = "PASS" if not hallucinated_devs else "FAIL"

        # --- 4. Command Hallucination Check ---
        submitted_cmds = set([h.get("command", "").lower() for h in investigation_history if h.get("command")])
        cmd_hallucinated = False
        for ev in ai_evidence_list:
            if "show " in str(ev).lower() or "ipconfig" in str(ev).lower():
                ev_cmd = re.search(r"(show [a-z0-9_\-\s]+|ipconfig[a-z0-9_\-\s/]*)", str(ev), re.IGNORECASE)
                if ev_cmd:
                    matched_c = ev_cmd.group(1).strip().lower()
                    if submitted_cmds and not any(sc in matched_c or matched_c in sc for sc in submitted_cmds):
                        cmd_hallucinated = True
                        break
        
        checks["command_hallucination"] = "FAIL" if cmd_hallucinated else "PASS"

        # --- 5. Technical Value Check ---
        submitted_ips = set(AIOutputValidator.extract_ips(submitted_evidence_text))
        ai_ips = set(AIOutputValidator.extract_ips(ai_root_cause + " " + " ".join(ai_evidence_list)))
        
        common_masks = {"255.255.255.0", "255.255.0.0", "255.0.0.0", "0.0.0.0", "127.0.0.1", "8.8.8.8", "8.8.4.4"}
        unsupported_ips = [ip for ip in ai_ips if ip not in submitted_ips and ip not in common_masks]

        checks["technical_value_check"] = "PASS" if not unsupported_ips else "REVIEW_REQUIRED"

        # --- 6. Suggested Fix Relevance ---
        fix_text = " ".join(ai_fix_steps).lower()
        fix_relevant = False
        
        if "gateway" in concept or "gateway" in det_text:
            fix_relevant = any(w in fix_text for w in ["gateway", "ip", "address", "default-router", "reconfigure"])
        elif "dhcp" in concept or "dhcp" in det_text:
            fix_relevant = any(w in fix_text for w in ["dhcp", "helper", "ipconfig", "lease", "binding", "pool"])
        elif "vlan" in concept or "vlan" in det_text:
            fix_relevant = any(w in fix_text for w in ["vlan", "switchport", "trunk", "allowed", "native"])
        elif "routing" in concept or "route" in det_text:
            fix_relevant = any(w in fix_text for w in ["route", "router", "network", "ospf", "eigrp", "static"])
        else:
            fix_relevant = True

        checks["fix_relevance"] = "PASS" if fix_relevant else "REVIEW_REQUIRED"

        # Overall Status Determination
        if any(v == "FAIL" for v in checks.values()):
            overall = "FAIL"
        elif any(v == "REVIEW_REQUIRED" for v in checks.values()):
            overall = "REVIEW_REQUIRED"
        else:
            overall = "PASS"

        checks["overall"] = overall
        if grounding_reason:
            checks["failure_reason"] = grounding_reason

        return checks
