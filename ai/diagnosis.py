import os
import json
import re
import datetime
from typing import Dict, Any, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

if not os.environ.get("GEMINI_API_KEY") and os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass

_DEFAULT_API_KEY = object()

class DiagnosticPlanner:
    """
    Generic, Device-Aware, Evidence-Driven Diagnostic Planner.
    Classifies network troubleshooting symptoms into domain strategies,
    validates command capabilities per device type, and plans next steps.
    """
    DEVICE_CAPABILITIES = {
        "END_DEVICE": ["ipconfig", "ipconfig /all", "ping", "tracert", "nslookup"],
        "SWITCH": ["show interfaces status", "show vlan brief", "show interfaces trunk", "show mac address-table", "show running-config", "show access-lists"],
        "ROUTER": ["show ip interface brief", "show ip route", "show running-config", "show ip ospf neighbor", "show ip eigrp neighbors", "show ip nat translations", "show access-lists"],
        "WIRELESS": ["show vlan brief", "show running-config"]
    }

    DOMAINS = ["VLAN", "IP_GATEWAY", "ROUTING", "DHCP", "DNS", "ACL", "NAT", "WIRELESS", "INTERFACE"]

    @classmethod
    def classify_device_type(cls, dev_name: str, inventory: Optional[Dict[str, Any]] = None) -> str:
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

        if re.search(r"\b(pc|host|laptop|server|client)\b", dev_low):
            return "END_DEVICE"
        elif re.search(r"\b(switch|sw|l2sw)\b", dev_low):
            return "SWITCH"
        elif re.search(r"\b(router|r\d|l3sw|isp|hq|branch)\b", dev_low):
            return "ROUTER"
        elif re.search(r"\b(wlc|ap|lap|wireless)\b", dev_low):
            return "WIRELESS"
        
        return "SWITCH"

    @classmethod
    def infer_diagnostic_domains(
        cls,
        symptom: str,
        show_outputs: str = "",
        topology_note: str = "",
        category: str = ""
    ) -> List[str]:
        text = f"{symptom} {topology_note} {show_outputs} {category}".lower()
        matched = []

        is_apipa_dhcp = any(k in text for k in ["169.254", "apipa", "dhcp", "ip helper", "lease", "option 43"]) or ("0.0.0.0" in text and "gateway" in text)
        is_vlan_trunk = any(k in text for k in ["native vlan mismatch", "trunk mismatch", "vlan mismatch", "allowed vlan", "interfaces trunk", "pruning"])
        is_gateway = any(k in text for k in ["gateway", "default gateway", "subnet mask", "ip address mismatch", "ping gateway", "unable to ping gateway"])
        is_vlan = any(k in text for k in ["vlan", "switchport", "missing vlan"])

        # Prioritize DHCP if APIPA (169.254.x.x), 0.0.0.0 gateway, or explicit DHCP symptom
        if is_apipa_dhcp:
            matched.append("DHCP")
        if is_vlan_trunk and "VLAN" not in matched:
            matched.append("VLAN")
        if is_gateway and not ("169.254" in text or ("0.0.0.0" in text and "gateway" in text)) and "IP_GATEWAY" not in matched:
            matched.append("IP_GATEWAY")
        if is_vlan and "VLAN" not in matched:
            matched.append("VLAN")
        if is_gateway and "IP_GATEWAY" not in matched:
            matched.append("IP_GATEWAY")

        # 3. ROUTING
        if any(k in text for k in ["route", "routing", "ospf", "eigrp", "bgp", "neighbor", "autonomous system"]):
            matched.append("ROUTING")

        # 4. DHCP
        if any(k in text for k in ["dhcp", "ip helper", "apipa", "169.254", "lease", "option 43"]):
            matched.append("DHCP")

        # 5. DNS
        if any(k in text for k in ["dns", "domain", "name resolution", "nslookup"]):
            matched.append("DNS")

        # 6. ACL
        if any(k in text for k in ["acl", "access-list", "permit", "deny", "filter", "blocked port"]):
            matched.append("ACL")

        # 7. NAT
        if any(k in text for k in ["nat", "pat", "inside", "outside", "translation"]):
            matched.append("NAT")

        # 8. WIRELESS
        if any(k in text for k in ["wlan", "ssid", "wpa2", "psk", "wireless", "capwap"]):
            matched.append("WIRELESS")

        # 9. INTERFACE
        if any(k in text for k in ["err-disabled", "port-security", "shutdown", "duplex", "speed"]):
            matched.append("INTERFACE")

        # Fallbacks
        if not matched:
            if "ping" in text:
                matched.extend(["IP_GATEWAY", "ROUTING"])
            else:
                matched.extend(["IP_GATEWAY", "VLAN", "ROUTING"])

        return matched

    @classmethod
    def plan_next_action(
        cls,
        symptom: str,
        show_outputs: str,
        inventory: Optional[Dict[str, Any]] = None,
        topology_note: str = "",
        executed_history: Optional[List[Dict[str, Any]]] = None,
        category: str = ""
    ) -> tuple[str, str, str]:
        executed_pairs = set()
        if executed_history:
            for h in executed_history:
                d = str(h.get("device", "")).strip().lower()
                c = str(h.get("command", "")).strip().lower()
                if d and c:
                    executed_pairs.add((d, c))

        if show_outputs:
            hdr_matches = re.findall(r"(?:---|===)\s*\[?([a-zA-Z0-9_\-]{2,})\]?\s+([a-zA-Z0-9_/% \.\-]+?)\s*(?:---|===)", show_outputs)
            for d, c in hdr_matches:
                executed_pairs.add((d.strip().lower(), c.strip().lower()))

        devices_by_type = {"END_DEVICE": [], "SWITCH": [], "ROUTER": [], "WIRELESS": []}

        if inventory:
            for r in inventory.get("routers", []):
                if r and r not in devices_by_type["ROUTER"]: devices_by_type["ROUTER"].append(r)
            for s in inventory.get("switches", []):
                if s and s not in devices_by_type["SWITCH"]: devices_by_type["SWITCH"].append(s)
            for e in inventory.get("end_devices", []):
                if e and e not in devices_by_type["END_DEVICE"]: devices_by_type["END_DEVICE"].append(e)
            for w in inventory.get("wireless", []):
                if w and w not in devices_by_type["WIRELESS"]: devices_by_type["WIRELESS"].append(w)

        if not any(devices_by_type.values()):
            full_text = f"{symptom} {topology_note} {show_outputs} {category}"
            r_match = re.findall(r"\b(Router\d*|R\d+|L3SW\d*|ISP\d*|HQ\d*|Branch\d*)\b", full_text, re.IGNORECASE)
            sw_match = re.findall(r"\b(Switch\d*|SW\d+|L2SW\d*)\b", full_text, re.IGNORECASE)
            end_match = re.findall(r"\b(PC\d*|PC-[A-Z0-9]+|Host\d*|Laptop\d*|Server\d*)\b", full_text, re.IGNORECASE)

            for r in r_match:
                if r not in devices_by_type["ROUTER"]: devices_by_type["ROUTER"].append(r)
            for s in sw_match:
                if s not in devices_by_type["SWITCH"]: devices_by_type["SWITCH"].append(s)
            for e in end_match:
                if e not in devices_by_type["END_DEVICE"]: devices_by_type["END_DEVICE"].append(e)

        domains = cls.infer_diagnostic_domains(symptom, show_outputs, topology_note, category)
        candidate_checklist = []

        for domain in domains:
            if domain == "VLAN":
                # First check trunk configuration on ALL switches to compare link parameters
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show interfaces trunk", f"Inspect trunk link configuration and allowed/native VLANs on {sw}."))
                # Then check created VLAN databases across switches
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show vlan brief", f"Inspect created VLANs in the VLAN database on {sw}."))
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig", f"Verify host IP and VLAN assignment on {pc}."))
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show running-config", f"Inspect running configuration on {sw}."))

            elif domain == "IP_GATEWAY":
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig", f"Inspect IP, Subnet Mask, and Default Gateway configuration on {pc}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show ip interface brief", f"Verify router interface IP addresses and operational status on {rtr}."))
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show vlan brief", f"Check host port VLAN allocation on {sw}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show running-config", f"Inspect global running configuration on {rtr}."))

            elif domain == "ROUTING":
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show ip route", f"Verify routing table entries on {rtr}."))
                    candidate_checklist.append((rtr, "show ip interface brief", f"Verify router interface status on {rtr}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show running-config", f"Inspect routing protocol statements on {rtr}."))

            elif domain == "DHCP":
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig /all", f"Inspect detailed IP configuration, DHCP lease, and gateway on {pc}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show ip interface brief", f"Verify router helper interfaces on {rtr}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show running-config", f"Inspect DHCP pool and helper-address settings on {rtr}."))

            elif domain == "DNS":
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig /all", f"Inspect primary DNS server IP and domain suffix on {pc}."))
                    candidate_checklist.append((pc, "nslookup", f"Test DNS resolution on {pc}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show access-lists", f"Inspect ACL rules blocking DNS UDP 53 on {rtr}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show running-config", f"Inspect DNS server routing and ACLs on {rtr}."))

            elif domain == "ACL":
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig", f"Inspect host IP settings on {pc}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show access-lists", f"Inspect access-list rules and wildcard masks on {rtr}."))
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show access-lists", f"Inspect access-list rules on {sw}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show running-config", f"Inspect interface access-group bindings on {rtr}."))

            elif domain == "NAT":
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig", f"Inspect internal IP configuration on {pc}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show ip nat translations", f"Check active NAT translation table on {rtr}."))
                    candidate_checklist.append((rtr, "show ip interface brief", f"Verify NAT inside/outside interface status on {rtr}."))
                    candidate_checklist.append((rtr, "show running-config", f"Inspect NAT pool and ACL configuration on {rtr}."))

            elif domain == "WIRELESS":
                for pc in devices_by_type["END_DEVICE"]:
                    candidate_checklist.append((pc, "ipconfig /all", f"Inspect wireless host IP configuration on {pc}."))
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show vlan brief", f"Check WLAN VLAN database on {sw}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show running-config", f"Inspect wireless WLC and DHCP options on {rtr}."))

            elif domain == "INTERFACE":
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show interfaces status", f"Inspect physical port status and err-disabled states on {sw}."))
                for rtr in devices_by_type["ROUTER"]:
                    candidate_checklist.append((rtr, "show ip interface brief", f"Verify operational status of router interfaces on {rtr}."))
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show running-config", f"Inspect port security and interface config on {sw}."))

        for dev, cmd, reason in candidate_checklist:
            dev_type = cls.classify_device_type(dev, inventory)
            allowed_cmds = cls.DEVICE_CAPABILITIES.get(dev_type, [])

            if cmd not in allowed_cmds:
                continue

            dev_low = dev.lower().strip()
            cmd_low = cmd.lower().strip()

            if cmd_low in ["ipconfig", "ipconfig /all"]:
                if (dev_low, "ipconfig") in executed_pairs or (dev_low, "ipconfig /all") in executed_pairs:
                    continue

            if (dev_low, cmd_low) in executed_pairs:
                continue

            return (dev, cmd, reason)

        return ("", "", "")


class AIDiagnosisEngine:
    """
    NetSage AI Diagnosis Engine.
    Executes grounded network troubleshooting analysis using LLM API (Google Gemini)
    or a deterministic offline fallback engine when API credentials are absent.
    """

    REQUIRED_SCHEMA_KEYS = {
        "root_cause", "confidence", "evidence",
        "next_command", "fix_steps", "osi_layer", "concept"
    }

    def __init__(self, api_key: Any = _DEFAULT_API_KEY):
        if api_key is _DEFAULT_API_KEY:
            self.api_key = os.environ.get("GEMINI_API_KEY")
        else:
            self.api_key = api_key

    @staticmethod
    def normalize_keys(data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data
        
        normalized = dict(data)
        if "likely_root_cause" in normalized and "root_cause" not in normalized:
            normalized["root_cause"] = normalized["likely_root_cause"]
        if "root_cause" in normalized and "likely_root_cause" not in normalized:
            normalized["likely_root_cause"] = normalized["root_cause"]

        if "confidence_score" in normalized and "confidence" not in normalized:
            normalized["confidence"] = normalized["confidence_score"]
        if "confidence" in normalized and "confidence_score" not in normalized:
            normalized["confidence_score"] = normalized["confidence"]

        if "evidence_cited" in normalized and "evidence" not in normalized:
            normalized["evidence"] = normalized["evidence_cited"]
        if "evidence" in normalized and "evidence_cited" not in normalized:
            normalized["evidence_cited"] = normalized["evidence"]

        if "recommended_next_command" in normalized and "next_command" not in normalized:
            normalized["next_command"] = normalized["recommended_next_command"]
        if "next_command" in normalized and "recommended_next_command" not in normalized:
            normalized["recommended_next_command"] = normalized["next_command"]

        if "suggested_fix" in normalized and "fix_steps" not in normalized:
            fix = normalized["suggested_fix"]
            normalized["fix_steps"] = fix if isinstance(fix, list) else [str(fix)]
        if "fix_steps" in normalized and "suggested_fix" not in normalized:
            normalized["suggested_fix"] = normalized["fix_steps"]

        return normalized

    def build_prompt(self, case_info: Dict[str, Any], rule_results: List[Dict[str, Any]]) -> str:
        rule_summary = ""
        if rule_results:
            rule_summary = "\n".join(
                f"- {r.get('check_name')}: [{r.get('status')}] {r.get('details')}"
                for r in rule_results
            )
        else:
            rule_summary = "No rule checker results available."

        prompt = f"""You are NetSage AI, a network troubleshooting assistant for Cisco-style lab networks (Packet Tracer). You suggest diagnoses and fixes for human review.

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

=== CRITICAL GROUNDING & RESPONSE RULES ===
1. Only reference devices that are explicitly named in the topology note or appear in the show-command evidence provided. Do not invent, assume, or default to placeholder device names.
2. Base your root cause strictly on the evidence given.
3. Cross-check configs line by line.

Output MUST be a single, valid JSON object with keys:
"root_cause", "confidence", "evidence", "osi_layer", "concept", "next_command", "fix_steps".
"""
        return prompt

    def validate_schema(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False

        normalized = self.normalize_keys(data)

        if not self.REQUIRED_SCHEMA_KEYS.issubset(normalized.keys()):
            return False

        if normalized.get("confidence") not in {"High", "Medium", "Low"}:
            return False

        if not isinstance(normalized.get("evidence"), list):
            return False

        if not isinstance(normalized.get("fix_steps"), list):
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
                normalized = self.normalize_keys(parsed)
                normalized.setdefault("status", "ISSUE_CONFIRMED" if normalized.get("confidence") == "High" else "NEED_MORE_EVIDENCE")
                normalized.setdefault("next_device", "Switch1")
                normalized.setdefault("reason_for_command", "Verify device configuration.")
                return normalized
        except (json.JSONDecodeError, TypeError):
            pass

        return None

    def select_next_device_and_command(
        self,
        symptom: str,
        show_outputs: str,
        inventory: Optional[Dict[str, Any]] = None,
        topology_note: str = "",
        executed_history: Optional[List[Dict[str, Any]]] = None,
        category: str = ""
    ) -> tuple[str, str, str]:
        return DiagnosticPlanner.plan_next_action(
            symptom=symptom,
            show_outputs=show_outputs,
            inventory=inventory,
            topology_note=topology_note,
            executed_history=executed_history,
            category=category
        )

    def diagnose_offline(self, case_info: Dict[str, Any], rule_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        failed_rules = [r for r in rule_results if r.get("status") == "FAIL"]
        show_outputs = case_info.get("show_outputs", "")
        symptom = case_info.get("symptom", "")
        inventory = case_info.get("network_inventory")
        topology_note = case_info.get("topology_note", "")
        executed_history = case_info.get("investigation_history", [])

        is_empty_or_minimal = not show_outputs or len(show_outputs.strip()) < 20 or "insufficient" in show_outputs.lower()
        category = case_info.get("category", "")
        next_dev, next_cmd, reason_cmd = self.select_next_device_and_command(
            symptom, show_outputs, inventory, topology_note, executed_history, category
        )

        has_native_mismatch = (
            "NATIVE_VLAN_MISMATCH" in show_outputs
            or "native vlan mismatch" in show_outputs.lower()
        )

        if failed_rules or has_native_mismatch:
            confidence = "High"
            status = "ISSUE_CONFIRMED"
            if failed_rules:
                first_fail = failed_rules[0]
                root_cause = f"Rule check failure: {first_fail.get('details')}"
                evidence = [f"Deterministic Check [{first_fail.get('check_name')}]: {first_fail.get('details')}"]
            else:
                root_cause = "Native VLAN mismatch on the trunk link between switches."
                evidence = ["CDP or trunk configuration evidence indicates Native VLAN mismatch across link."]
            next_cmd = ""
            next_dev = ""
            reason_cmd = "Fault has been confirmed by CLI evidence."
        elif is_empty_or_minimal:
            confidence = "Low"
            status = "NO_CONFIRMED_ISSUE"
            root_cause = "Insufficient CLI show command evidence supplied to pinpoint root cause."
            evidence = ["Initial diagnostic CLI output needed to begin investigation."]
        elif "request timed out" in show_outputs.lower() or "unreachable" in show_outputs.lower():
            confidence = "Medium"
            status = "NEED_MORE_EVIDENCE"
            root_cause = f"Observed ping timeout / reachability error in CLI output. Further evidence required on {next_dev if next_dev else 'network devices'}."
            evidence = ["Observed ping timeouts or suspicious CLI status in collected evidence."]
        elif not next_cmd:
            confidence = "Low"
            status = "NO_CONFIRMED_ISSUE"
            root_cause = "Standard diagnostic checks completed. No further commands remain. Manual review recommended."
            evidence = ["All standard diagnostic checks for this symptom category have been completed."]
            next_dev = ""
            next_cmd = ""
            reason_cmd = "Standard diagnostic checks completed. No further commands remain. Manual review recommended."
        else:
            confidence = "Low"
            status = "NO_CONFIRMED_ISSUE"
            root_cause = "No issue detected in current CLI output. Continuing diagnostic checks."
            evidence = ["Current command evidence shows normal operation for inspected component."]

        if failed_rules:
            first_fail = failed_rules[0]
            fix_steps = [f"Fix identified issue: {first_fail.get('details')}"]
        else:
            fix_steps = ["Review device configuration in Cisco Packet Tracer."]

        diagnosis = {
            "status": status,
            "root_cause": root_cause,
            "likely_root_cause": root_cause,
            "confidence": confidence,
            "confidence_score": confidence,
            "evidence": evidence,
            "evidence_cited": evidence,
            "next_device": next_dev,
            "next_command": next_cmd,
            "recommended_next_command": next_cmd,
            "reason_for_command": reason_cmd,
            "fix_steps": fix_steps,
            "suggested_fix": fix_steps,
            "osi_layer": case_info.get("osi_layer", "Layer 2" if "vlan" in symptom.lower() or "trunk" in symptom.lower() else "Layer 3"),
            "concept": case_info.get("concept", "Native VLAN Mismatch" if has_native_mismatch else "General Network Fault"),
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
            
            for m_name in ["gemini-flash-latest", "gemini-2.5-flash"]:
                try:
                    response = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                    )
                    if response and hasattr(response, "text") and response.text:
                        parsed = self.parse_llm_response(response.text)
                        if parsed:
                            parsed["ai_mode"] = f"Gemini ({m_name})"
                            return parsed
                except Exception:
                    continue
        except Exception:
            pass

        return self.diagnose_offline(case_info, rule_results)
