import os
import json
import re
import datetime
from typing import Dict, Any, List, Optional

class AIDiagnosisEngine:
    """
    NetSage AI Diagnosis Engine.
    Executes grounded network troubleshooting analysis using LLM API (Google Gemini)
    or a deterministic offline fallback engine when API credentials are absent.
    Supports guided investigation states: NO_CONFIRMED_ISSUE, NEED_MORE_EVIDENCE, ISSUE_CONFIRMED.
    Validates recommended devices against user-supplied network inventory.
    """

    REQUIRED_SCHEMA_KEYS = {
        "root_cause", "confidence", "evidence",
        "next_command", "fix_steps", "osi_layer", "concept"
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def build_prompt(self, case_info: Dict[str, Any], rule_results: List[Dict[str, Any]]) -> str:
        rule_summary = ""
        if rule_results:
            rule_summary = "\n".join(
                f"- {r.get('check_name')}: [{r.get('status')}] {r.get('details')}"
                for r in rule_results
            )
        else:
            rule_summary = "No rule checker results available."

        prompt = f"""You are NetSage AI, a Cisco network troubleshooting assistant.
Analyze the following troubleshooting case and output ONLY valid JSON adhering strictly to the required schema.

=== CASE INFORMATION ===
Case ID: {case_info.get('case_id', 'Unknown')}
Category: {case_info.get('category', 'General')}
Symptom: {case_info.get('symptom', 'No symptom provided')}
Topology Note: {case_info.get('topology_note', 'No topology note provided')}
Evidence Status: {case_info.get('evidence_status', 'LIVE_SESSION')}

=== ACCUMULATED CISCO SHOW COMMAND EVIDENCE ===
{case_info.get('show_outputs', 'No show outputs supplied')}

=== DETERMINISTIC PYTHON RULE CHECKER RESULTS ===
{rule_summary}

=== GROUNDING & RESPONSE RULES ===
1. Base your root cause strictly on the supplied evidence above.
2. Do NOT invent commands, test results, non-existent devices, or topology links.
3. Determine investigation status:
   - "ISSUE_CONFIRMED": When evidence fully pinpoints the root cause. Set confidence to High.
   - "NEED_MORE_EVIDENCE": When evidence shows suspicious symptoms but root cause needs verification. Set confidence to Medium.
   - "NO_CONFIRMED_ISSUE": When evidence is normal or incomplete. Set confidence to Low.
4. Provide next_device, next_command, and reason_for_command when status is NOT ISSUE_CONFIRMED.
5. Output MUST be valid JSON with keys:
   "status", "root_cause", "confidence", "evidence", "next_device", "next_command", "reason_for_command", "fix_steps", "osi_layer", "concept".
"""
        return prompt

    def validate_schema(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False

        if not self.REQUIRED_SCHEMA_KEYS.issubset(data.keys()):
            return False

        if data.get("confidence") not in {"High", "Medium", "Low"}:
            return False

        if not isinstance(data.get("evidence"), list):
            return False

        if not isinstance(data.get("fix_steps"), list):
            return False

        return True

    def parse_llm_response(self, text: str) -> Optional[Dict[str, Any]]:
        clean_text = text.strip()

        if "```" in clean_text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1)
            else:
                clean_text = re.sub(r"```[a-zA-Z]*", "", clean_text).strip()

        try:
            parsed = json.loads(clean_text)
            if self.validate_schema(parsed):
                parsed.setdefault("status", "ISSUE_CONFIRMED" if parsed.get("confidence") == "High" else "NEED_MORE_EVIDENCE")
                parsed.setdefault("next_device", "Switch0")
                parsed.setdefault("reason_for_command", "Verify device configuration.")
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        return None

    def select_next_device_and_command(
        self,
        symptom: str,
        show_outputs: str,
        inventory: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str, str]:
        """
        Helper to select the next logical device, command, and rationale based on symptom domain,
        network inventory, and previously executed commands in show_outputs.
        Validates target device against available inventory to prevent non-existent device references.
        """
        symptom_low = symptom.lower()
        show_low = show_outputs.lower()

        # Extract device lists validated against inventory counts
        routers = []
        switches = []
        end_devices = []

        if inventory:
            if inventory.get("routers_count", 0) > 0:
                routers = [d for d in inventory.get("routers", []) if d]
            if inventory.get("switches_count", 0) > 0:
                switches = [d for d in inventory.get("switches", []) if d]
            if inventory.get("end_devices_count", 0) > 0:
                end_devices = [d for d in inventory.get("end_devices", []) if d]
        else:
            routers = ["Router0"]
            switches = ["Switch0", "Switch1"]
            end_devices = ["PC0", "PC1"]

        # Determine primary and secondary available devices
        primary_dev = routers[0] if routers else (switches[0] if switches else (end_devices[0] if end_devices else "Device"))
        secondary_dev = switches[0] if (switches and primary_dev != switches[0]) else (switches[1] if len(switches) > 1 else primary_dev)

        # 1. Switching / VLAN domain (or when no routers exist in network inventory)
        if "vlan" in symptom_low or "trunk" in symptom_low or not routers:
            target_switch = switches[0] if switches else primary_dev
            target_switch2 = switches[1] if len(switches) > 1 else target_switch

            if "show interfaces trunk" not in show_low:
                return (
                    target_switch,
                    "show interfaces trunk",
                    f"First, inspect trunk link configuration and allowed VLAN lists on {target_switch}."
                )
            elif "show vlan" not in show_low:
                return (
                    target_switch2,
                    "show vlan brief",
                    f"Next, check whether required VLANs are created in the VLAN database on {target_switch2}."
                )
            else:
                return (
                    target_switch,
                    "show running-config",
                    f"Inspect interface running configuration on {target_switch} to verify switchport settings."
                )

        # 2. Routing / Gateway domain (when routers exist in network inventory)
        elif "route" in symptom_low or "ping" in symptom_low or "gateway" in symptom_low or "server" in symptom_low:
            if "show ip route" not in show_low:
                return (
                    primary_dev,
                    "show ip route",
                    f"First, verify whether {primary_dev} has a valid route to the destination network."
                )
            elif "show ip interface brief" not in show_low:
                return (
                    primary_dev,
                    "show ip interface brief",
                    f"Next, verify physical and logical router interface operational status on {primary_dev}."
                )
            else:
                return (
                    primary_dev,
                    "show running-config",
                    f"Inspect global running configuration on {primary_dev} to check routing protocol and ACL statements."
                )

        # 3. DHCP domain
        elif "dhcp" in symptom_low or "ip address" in symptom_low:
            if "show ip dhcp binding" not in show_low and routers:
                return (
                    primary_dev,
                    "show ip dhcp binding",
                    f"First, check active DHCP address leases on {primary_dev}."
                )
            else:
                return (
                    primary_dev,
                    "show running-config",
                    f"Inspect configuration settings on {primary_dev}."
                )

        # 4. Default fallback validated against available inventory
        if "show ip interface brief" not in show_low and routers:
            return (
                primary_dev,
                "show ip interface brief",
                f"First, verify interface status on {primary_dev}."
            )
        elif "show interfaces trunk" not in show_low and switches:
            return (
                secondary_dev,
                "show interfaces trunk",
                f"Next, inspect trunk links on {secondary_dev}."
            )
        else:
            return (
                primary_dev,
                "show running-config",
                f"Inspect running configuration on {primary_dev}."
            )

    def diagnose_offline(self, case_info: Dict[str, Any], rule_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Deterministic offline fallback engine.
        Supports guided states: NO_CONFIRMED_ISSUE, NEED_MORE_EVIDENCE, ISSUE_CONFIRMED.
        Validates device selection against network inventory.
        """
        failed_rules = [r for r in rule_results if r.get("status") == "FAIL"]
        show_outputs = case_info.get("show_outputs", "")
        symptom = case_info.get("symptom", "")
        inventory = case_info.get("network_inventory")

        is_empty_or_minimal = not show_outputs or len(show_outputs.strip()) < 20 or "insufficient" in show_outputs.lower()
        next_dev, next_cmd, reason_cmd = self.select_next_device_and_command(symptom, show_outputs, inventory)

        if failed_rules:
            confidence = "High"
            status = "ISSUE_CONFIRMED"
            first_fail = failed_rules[0]
            root_cause = f"Rule check failure: {first_fail.get('details')}"
            evidence = [f"Deterministic Check [{first_fail.get('check_name')}]: {first_fail.get('details')}"]
            next_cmd = ""
            next_dev = ""
            reason_cmd = "Fault has been confirmed by rule check evidence."
        elif is_empty_or_minimal:
            confidence = "Low"
            status = "NO_CONFIRMED_ISSUE"
            root_cause = "Insufficient CLI show command evidence supplied to pinpoint root cause."
            evidence = ["Initial diagnostic CLI output needed to begin investigation."]
        elif "request timed out" in show_outputs.lower() or "unreachable" in show_outputs.lower() or "none" in show_outputs.lower():
            confidence = "Medium"
            status = "NEED_MORE_EVIDENCE"
            root_cause = case_info.get("expected_fault") or f"Possible network anomaly detected in CLI output. Further evidence required on {next_dev}."
            evidence = ["Observed ping timeouts or suspicious CLI status in collected evidence."]
        else:
            confidence = "Low"
            status = "NO_CONFIRMED_ISSUE"
            root_cause = "No issue detected in current CLI output. Continuing diagnostic checks."
            evidence = ["Current command evidence shows normal operation for inspected component."]

        fix_steps = [case_info.get("correct_fix")] if case_info.get("correct_fix") else ["Review device configuration in Cisco Packet Tracer."]

        diagnosis = {
            "status": status,
            "root_cause": root_cause,
            "confidence": confidence,
            "evidence": evidence,
            "next_device": next_dev,
            "next_command": next_cmd,
            "reason_for_command": reason_cmd,
            "fix_steps": fix_steps,
            "osi_layer": case_info.get("osi_layer", "Layer 3"),
            "concept": case_info.get("concept", "General Network Fault"),
            "ai_mode": "Offline Demo"
        }
        return diagnosis

    def diagnose(self, case_info: Dict[str, Any], rule_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.api_key:
            return self.diagnose_offline(case_info, rule_results)

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            prompt = self.build_prompt(case_info, rule_results)
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

            if response and hasattr(response, "text") and response.text:
                parsed = self.parse_llm_response(response.text)
                if parsed:
                    parsed["ai_mode"] = "Gemini LLM"
                    return parsed
        except Exception:
            pass

        return self.diagnose_offline(case_info, rule_results)
