import re
from typing import Dict, Any, List, Optional

STOP_WORDS = {
    "with", "from", "that", "this", "have", "been", "were", "where",
    "when", "what", "than", "then", "into", "over", "under", "interface",
    "device", "configured", "check", "issue", "failure", "error", "problem"
}

UNSUPPORTED_CLI_COMMANDS = {
    "ipconfig /setmask",
    "ipconfig /setgateway",
    "ipconfig /setip"
}

DEVICE_COMMAND_REGISTRY = {
    "ROUTER": {
        "show ip interface brief", "show ip route", "show running-config",
        "show ip ospf neighbor", "show ip eigrp neighbors", "show ip nat translations", "show access-lists"
    },
    "SWITCH": {
        "show interfaces status", "show vlan brief", "show interfaces trunk",
        "show mac address-table", "show running-config", "show access-lists"
    },
    "END_DEVICE": {
        "ipconfig", "ipconfig /all", "ping", "tracert", "nslookup"
    },
    "WIRELESS": {
        "show vlan brief", "show running-config"
    }
}

class AIOutputValidator:
    """
    Validates AI-generated diagnosis responses for consistency, evidence grounding,
    hallucination of devices/commands/values, interface-role alignment,
    Packet Tracer CLI compatibility, and fix relevance.
    Standardized Status Vocabulary: PASS, FAIL, REVIEW_REQUIRED, BLOCKED.
    """

    @staticmethod
    def extract_ips(text: str) -> List[str]:
        return re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)

    @staticmethod
    def extract_vlans(text: str) -> List[str]:
        return re.findall(r"\bVLAN\s*(\d+)\b", text, re.IGNORECASE)

    @staticmethod
    def extract_devices(text: str) -> List[str]:
        return re.findall(r"\b(PC\d*|Switch\d*|Router\d*|R\d+|SW\d+|Server\d*|Host\d*)\b", text, re.IGNORECASE)

    @staticmethod
    def classify_device_type(dev_name: str, inventory: Optional[Dict[str, Any]] = None) -> str:
        if not dev_name:
            return "UNKNOWN"
        dev_low = dev_name.lower().strip()
        if inventory:
            for d in inventory.get("routers", []):
                if d and d.lower().strip() == dev_low: return "ROUTER"
            for d in inventory.get("switches", []):
                if d and d.lower().strip() == dev_low: return "SWITCH"
            for d in inventory.get("end_devices", []):
                if d and d.lower().strip() == dev_low: return "END_DEVICE"
            for d in inventory.get("wireless", []):
                if d and d.lower().strip() == dev_low: return "WIRELESS"

        if re.search(r"^(pc|host|laptop|server|client)\d*$", dev_low) or dev_low.startswith("pc") or dev_low.startswith("host") or dev_low.startswith("server"):
            return "END_DEVICE"
        elif re.search(r"^(switch|sw|l2sw)\d*$", dev_low) or dev_low.startswith("switch") or dev_low.startswith("sw"):
            return "SWITCH"
        elif re.search(r"^(router|r|l3sw|isp|hq|branch)\d*$", dev_low) or dev_low.startswith("router") or dev_low.startswith("r"):
            return "ROUTER"
        elif re.search(r"^(wlc|ap|lap|wireless)\d*$", dev_low) or dev_low.startswith("wlc") or dev_low.startswith("ap"):
            return "WIRELESS"
        
        return "UNKNOWN"

    @classmethod
    def validate_device_command(cls, dev_name: str, command: str, inventory: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
        """
        Validates whether a command is supported on the target device type.
        Returns (is_valid, status) where status is PASS, BLOCKED, or REVIEW_REQUIRED.
        """
        if not dev_name or not command:
            return False, "REVIEW_REQUIRED"
        
        dev_type = cls.classify_device_type(dev_name, inventory)
        if dev_type == "UNKNOWN" or dev_type not in DEVICE_COMMAND_REGISTRY:
            return False, "REVIEW_REQUIRED"
        
        allowed_cmds = DEVICE_COMMAND_REGISTRY[dev_type]
        cmd_clean = command.strip().lower()

        # Match base command name (e.g. "show running-config interface Gi0/0" matches "show running-config")
        is_valid = any(cmd_clean == ac or cmd_clean.startswith(ac + " ") for ac in allowed_cmds)

        if is_valid:
            return True, "PASS"
        else:
            return False, "BLOCKED"

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
        Executes strict AI validation checks using standardized status vocabulary:
        PASS, FAIL, REVIEW_REQUIRED, BLOCKED.
        """
        checks = {}
        ai_root_cause = str(ai_diag.get("root_cause", "") or ai_diag.get("likely_root_cause", ""))
        ai_evidence_list = ai_diag.get("evidence", []) or ai_diag.get("evidence_cited", [])
        ai_fix_steps = ai_diag.get("fix_steps", []) or ai_diag.get("suggested_fix", [])
        fix_text = " ".join(ai_fix_steps).lower() if isinstance(ai_fix_steps, list) else str(ai_fix_steps).lower()
        evidence_lower = submitted_evidence_text.lower()
        topology_note = str(ground_truth.get("topology_note", "") or "").lower()

        # --- 1. Unsupported CLI Command Check ---
        unsupported_found = [cmd for cmd in UNSUPPORTED_CLI_COMMANDS if cmd in fix_text or cmd in ai_root_cause.lower()]
        if unsupported_found:
            checks["command_compatibility"] = "FAIL"
            checks["failure_reason"] = f"Unsupported Packet Tracer Command: '{unsupported_found[0]}'. Use GUI PC -> Desktop -> IP Configuration."
            checks["overall"] = "FAIL"
            return checks
        else:
            checks["command_compatibility"] = "PASS"

        # --- 2. Device-Aware Guided Command Check ---
        next_dev = str(ai_diag.get("next_device", "") or "")
        next_cmd = str(ai_diag.get("next_command", "") or "")
        if next_dev and next_cmd:
            is_valid_cmd, cmd_status = AIOutputValidator.validate_device_command(next_dev, next_cmd, inventory)
            if not is_valid_cmd and cmd_status == "BLOCKED":
                checks["next_command_guard"] = "BLOCKED"
                checks["failure_reason"] = f"Incompatible command '{next_cmd}' on device '{next_dev}' of type '{AIOutputValidator.classify_device_type(next_dev, inventory)}'."
                checks["overall"] = "BLOCKED"
                return checks
            else:
                checks["next_command_guard"] = cmd_status

        # --- 3. Technical Value / IP Hallucination Check ---
        submitted_ips = set(AIOutputValidator.extract_ips(submitted_evidence_text + " " + topology_note))
        if inventory:
            for dlist in inventory.values():
                if isinstance(dlist, list):
                    for item in dlist:
                        submitted_ips.update(AIOutputValidator.extract_ips(str(item)))

        det_failures = [r for r in rule_results if r.get("status") == "FAIL"]
        det_text = " ".join([f.get("details", "").lower() for f in det_failures])
        submitted_ips.update(AIOutputValidator.extract_ips(det_text))

        ai_ips = set(AIOutputValidator.extract_ips(ai_root_cause + " " + fix_text))
        common_masks = {"255.255.255.0", "255.255.0.0", "255.0.0.0", "0.0.0.0", "127.0.0.1", "8.8.8.8", "8.8.4.4"}
        unsupported_ips = [ip for ip in ai_ips if ip not in submitted_ips and ip not in common_masks]

        if unsupported_ips:
            checks["technical_value_check"] = "FAIL"
            checks["failure_reason"] = f"IP Address Hallucination: '{unsupported_ips[0]}' does not exist in submitted evidence or inventory."
            checks["overall"] = "FAIL"
            return checks
        else:
            checks["technical_value_check"] = "PASS"

        # --- 4. Interface-Role & DHCP Relay Validation ---
        if "ip helper-address" in fix_text or "dhcp relay" in det_text or "dhcp relay" in ai_root_cause.lower():
            if "g0/1" in fix_text or "gigabitethernet0/1" in fix_text:
                if "client" in topology_note and ("g0/0" in topology_note or "gigabitethernet0/0" in topology_note):
                    checks["interface_role_validation"] = "FAIL"
                    checks["failure_reason"] = "Interface Selection Error: ip helper-address applied to inter-router link (G0/1) instead of client-facing interface (G0/0)."
                    checks["overall"] = "FAIL"
                    return checks
            checks["interface_role_validation"] = "PASS"

        # --- 5. Unconfirmed Fix Injection Check ---
        if "subnet mask" in fix_text and "subnet" not in det_text and "subnet" not in topology_note and "subnet" not in ai_root_cause.lower():
            checks["fix_relevance"] = "FAIL"
            checks["failure_reason"] = "Unconfirmed Fix Injection: Subnet mask fix generated without confirmed subnet mask fault."
            checks["overall"] = "FAIL"
            return checks

        # --- 6. Root Cause Consistency ---
        expected_fault = ground_truth.get("expected_fault", "").lower()
        concept = ground_truth.get("concept", "").lower()
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
        
        if "ospf" in ai_rc_low and "ospf" not in concept and "ospf" not in det_text:
            consistent = False
        if "vlan" in ai_rc_low and "vlan" not in concept and "vlan" not in det_text and "trunk" not in concept:
            consistent = False

        checks["root_cause_consistency"] = "PASS" if consistent else ("FAIL" if ("ospf" in ai_rc_low or "bgp" in ai_rc_low or "eigrp" in ai_rc_low) else "REVIEW_REQUIRED")

        # --- 7. Evidence Grounding ---
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

        # --- 8. Device Hallucination Check ---
        known_devices = set([d.lower() for d in inventory.get("end_devices", []) + inventory.get("switches", []) + inventory.get("routers", [])])
        for h in investigation_history:
            if h.get("device"):
                known_devices.add(h.get("device").lower())
        
        generic_terms = {"pc", "router", "switch", "server", "host", "device", "gateway", "client", "laptop", "ap"}
        mentioned_devices = AIOutputValidator.extract_devices(ai_root_cause + " " + fix_text)
        hallucinated_devs = [d for d in set(mentioned_devices) if d.lower() not in known_devices and d.lower() not in generic_terms]

        checks["device_hallucination"] = "PASS" if not hallucinated_devs else "FAIL"

        # --- Overall Status Determination ---
        if any(v == "FAIL" for v in checks.values()):
            overall = "FAIL"
        elif any(v == "BLOCKED" for v in checks.values()):
            overall = "BLOCKED"
        elif any(v == "REVIEW_REQUIRED" for v in checks.values()):
            overall = "REVIEW_REQUIRED"
        else:
            overall = "PASS"

        checks["overall"] = overall
        if grounding_reason and "failure_reason" not in checks:
            checks["failure_reason"] = grounding_reason

        return checks
