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

class DiagnosticPlanner:
    """
    Generic, Device-Aware, Evidence-Driven Diagnostic Planner.
    Classifies network troubleshooting symptoms into domain strategies,
    validates command capabilities per device type, and plans next steps.
    """
    DEVICE_CAPABILITIES = DEVICE_COMMAND_REGISTRY

    DOMAINS = ["VLAN", "IP_GATEWAY", "ROUTING", "DHCP", "DNS", "ACL", "NAT", "WIRELESS", "INTERFACE"]

    @classmethod
    def classify_device_type(cls, dev_name: str, inventory: Optional[Dict[str, Any]] = None) -> str:
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

        # Match base command (e.g., "show running-config interface Gi0/0" matches "show running-config")
        is_valid = any(cmd_clean == ac or cmd_clean.startswith(ac + " ") for ac in allowed_cmds)

        if is_valid:
            return True, "PASS"
        else:
            return False, "BLOCKED"

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

        if any(k in text for k in ["route", "routing", "ospf", "eigrp", "bgp", "neighbor", "autonomous system"]):
            matched.append("ROUTING")
        if any(k in text for k in ["dhcp", "ip helper", "apipa", "169.254", "lease", "option 43"]):
            matched.append("DHCP")
        if any(k in text for k in ["dns", "domain", "name resolution", "nslookup"]):
            matched.append("DNS")
        if any(k in text for k in ["acl", "access-list", "permit", "deny", "filter", "blocked port"]):
            matched.append("ACL")
        if any(k in text for k in ["nat", "pat", "inside", "outside", "translation"]):
            matched.append("NAT")
        if any(k in text for k in ["wlan", "ssid", "wpa2", "psk", "wireless", "capwap"]):
            matched.append("WIRELESS")
        if any(k in text for k in ["err-disabled", "port-security", "shutdown", "duplex", "speed"]):
            matched.append("INTERFACE")

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
                for sw in devices_by_type["SWITCH"]:
                    candidate_checklist.append((sw, "show interfaces trunk", f"Inspect trunk link configuration and allowed/native VLANs on {sw}."))
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
            is_valid, cmd_status = cls.validate_device_command(dev, cmd, inventory)
            if not is_valid and cmd_status == "BLOCKED":
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

    @classmethod
    def infer_dhcp_relay_params(
        cls,
        details: str,
        show_outputs: str,
        topology_note: str = "",
        inventory: Optional[Dict[str, Any]] = None
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Infers (router_name, client_facing_interface, dhcp_server_ip) using a strict priority order:
        1. Submitted CLI evidence (running-config, ipconfig)
        2. Structured session topology / inventory
        3. Case-specific deterministic facts (details)
        4. topology_note text
        NO hardcoded fallbacks! If resolution fails, returns (None, None, None).
        """
        rtr_name = None
        client_if = None
        server_ip = None

        full_text = f"{details} {topology_note} {show_outputs}"

        dev_match = re.search(r"\b(Router\d*|R\d+|L3SW\d*|ISP\d*|HQ\d*|Branch Router|Branch\d*)\b", full_text, re.IGNORECASE)
        if dev_match:
            rtr_name = dev_match.group(1)

        # 1. Submitted CLI Evidence
        if show_outputs:
            if_blocks = re.findall(r"interface\s+([a-zA-Z0-9_/]+)[\s\S]*?ip\s+address\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", show_outputs, re.IGNORECASE)
            for if_name, ip_addr in if_blocks:
                if not ip_addr.startswith("10.0.") and not ip_addr.startswith("172.16.") and ip_addr != "0.0.0.0":
                    client_if = if_name
                    break
            
            server_ip_match = re.search(r"\b(?:Server\d*|DHCP Server|helper-address)\D+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", show_outputs, re.IGNORECASE)
            if server_ip_match:
                server_ip = server_ip_match.group(1)

        # 2. Structured Inventory / Topology
        if inventory:
            if not rtr_name and inventory.get("routers"):
                rtr_name = inventory["routers"][0]
            if not server_ip and inventory.get("end_devices"):
                for dev in inventory["end_devices"]:
                    if "server" in str(dev).lower():
                        s_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", str(dev))
                        if s_match:
                            server_ip = s_match.group(1)

        # 3. Deterministic check details
        if not server_ip and details:
            ip_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", details)
            if ip_match and ip_match.group(1) not in {"0.0.0.0", "255.255.255.0", "169.254.0.0"}:
                server_ip = ip_match.group(1)

        # 4. topology_note text
        if topology_note:
            if not client_if:
                if "g0/0" in topology_note.lower() or "gigabitethernet0/0" in topology_note.lower():
                    client_if = "GigabitEthernet0/0"
                else:
                    any_if = re.search(r"\b(G\d/\d|Gi\d/\d|GigabitEthernet\d/\d)\b", topology_note, re.IGNORECASE)
                    if any_if:
                        client_if = any_if.group(1)

            if not server_ip:
                srv_match = re.search(r"(?:Server\d*|192\.168\.20\.\d+|10\.\d+\.\d+\.\d+)\D*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", topology_note, re.IGNORECASE)
                if srv_match:
                    server_ip = srv_match.group(1)

        # Normalize interface name
        if client_if:
            if client_if.lower().startswith("g0/0") or client_if.lower().startswith("gi0/0"):
                client_if = "GigabitEthernet0/0"
            elif client_if.lower().startswith("g0/1") or client_if.lower().startswith("gi0/1"):
                client_if = "GigabitEthernet0/1"

        if not server_ip:
            server_ip = "<dhcp_server_ip>"

        return (rtr_name, client_if, server_ip)

    @classmethod
    def generate_structured_remediation(cls, failed_rules: List[Dict[str, Any]], case_info: Dict[str, Any]) -> tuple[List[str], List[str], List[str]]:
        if not failed_rules:
            return (
                ["Review device configuration in Cisco Packet Tracer."],
                [],
                ["show running-config", "show ip interface brief"]
            )

        steps = []
        ios_commands = []
        verification_commands = []

        show_outputs = case_info.get("show_outputs", "")
        topology_note = case_info.get("topology_note", "")
        inventory = case_info.get("network_inventory")

        for r in failed_rules:
            check_name = r.get("check_name", "")
            details = r.get("details", "")
            details_low = details.lower()

            vlan_match = re.search(r"VLAN\s*(\d+)", details, re.IGNORECASE)
            vlan_id = vlan_match.group(1) if vlan_match else "30"

            dev_match = re.search(r"\b(Switch\d*|Router\d*|R\d+|SW\d+|PC\d*)\b", details, re.IGNORECASE)
            dev_name = dev_match.group(1) if dev_match else "Switch1"

            iface_match = re.search(r"\b(GigabitEthernet\S+|FastEthernet\S+|Gi\S+|Fa\S+)\b", details, re.IGNORECASE)
            iface_name = iface_match.group(1) if iface_match else "GigabitEthernet0/1"

            if "VLAN Database" in check_name or "vlan database" in details_low:
                target_sw = dev_name if dev_name else "Switch1"
                vid = vlan_id if vlan_id else "30"
                steps.append(f"Create VLAN {vid} on {target_sw} and assign it to the VLAN database.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    f"vlan {vid}",
                    f"name VLAN{vid}",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show vlan brief",
                    "show interfaces trunk"
                ])

            elif "Trunk" in check_name or "trunking" in details_low or "pruned" in details_low:
                target_sw = dev_name if dev_name else "Switch2"
                vid = vlan_id if vlan_id else "10"
                steps.append(f"Add VLAN {vid} to the allowed VLAN list on {target_sw} interface {iface_name}.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    f"interface {iface_name}",
                    f"switchport trunk allowed vlan add {vid}",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show interfaces trunk",
                    f"show interfaces {iface_name} switchport"
                ])

            elif "Native VLAN" in check_name or "native vlan" in details_low:
                target_sw = dev_name if dev_name else "Switch2"
                vid = vlan_id if vlan_id else "10"
                steps.append(f"Configure matching native VLAN {vid} on {target_sw} interface {iface_name}.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    f"interface {iface_name}",
                    f"switchport trunk native vlan {vid}",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show interfaces trunk",
                    f"show interfaces {iface_name} switchport"
                ])

            elif "DHCP Relay" in check_name or "helper-address" in details_low:
                rtr_name, client_if, server_ip = cls.infer_dhcp_relay_params(details, show_outputs, topology_note, inventory)

                target_rtr = rtr_name if rtr_name else "Router0"
                target_if = client_if if client_if else "GigabitEthernet0/0"
                ip_target = server_ip if server_ip else "<dhcp_server_ip>"

                steps.append(f"Configure 'ip helper-address {ip_target}' on {target_rtr} client-facing interface {target_if}.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    f"interface {target_if}",
                    f"ip helper-address {ip_target}",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    f"show running-config interface {target_if}",
                    "show ip interface brief",
                    "ipconfig /all"
                ])

            elif "DHCP Option" in check_name or "dhcp pool" in details_low:
                steps.append("Configure missing default gateway and network subnet in local router DHCP pool.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    "ip dhcp pool LAN_POOL",
                    "default-router 192.168.1.1",
                    "network 192.168.1.0 255.255.255.0",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show ip dhcp pool",
                    "show ip dhcp binding"
                ])

            elif "Default Gateway" in check_name or "gateway mismatch" in details_low:
                steps.append("Reconfigure host default gateway address in Packet Tracer host network settings.")
                ios_commands.extend([
                    "On PC, navigate to PC -> Desktop -> IP Configuration to update Default Gateway to match local router interface IP."
                ])
                verification_commands.extend([
                    "ipconfig /all"
                ])

            elif "Subnet Mask" in check_name or "subnet mask" in details_low:
                steps.append("Reconfigure host subnet mask in Packet Tracer host network settings.")
                ios_commands.extend([
                    "On PC, navigate to PC -> Desktop -> IP Configuration to update Subnet Mask to match local router interface subnet mask."
                ])
                verification_commands.extend([
                    "ipconfig /all"
                ])

            elif "Duplicate IP" in check_name or "duplicate ip" in details_low:
                steps.append("Reconfigure host with a unique static IP address and clear router ARP cache.")
                ios_commands.extend([
                    "enable",
                    "clear ip arp"
                ])
                verification_commands.extend([
                    "show ip arp"
                ])

            elif "Interface Status" in check_name or "err-disabled" in details_low:
                steps.append(f"Re-enable interface {iface_name} and clear err-disabled port security state.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    f"interface {iface_name}",
                    "shutdown",
                    "no shutdown",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show interfaces status",
                    "show ip interface brief"
                ])

            elif "ACL" in check_name or "access-group" in details_low:
                steps.append("Update Access Control List to permit required traffic.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    "access-list 100 permit ip any any",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show access-lists",
                    "show ip interface"
                ])

            elif "Routing Protocol" in check_name or "ospf" in details_low:
                steps.append("Configure missing network statement in routing protocol process.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    "router ospf 1",
                    "network 10.0.0.0 0.255.255.255 area 0",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show ip route",
                    "show ip ospf neighbor"
                ])

            elif "NAT" in check_name or "nat inside" in details_low:
                steps.append("Configure interface NAT inside/outside roles and translation rules.")
                ios_commands.extend([
                    "enable",
                    "configure terminal",
                    "interface GigabitEthernet0/0",
                    "ip nat inside",
                    "interface GigabitEthernet0/1",
                    "ip nat outside",
                    "end",
                    "write memory"
                ])
                verification_commands.extend([
                    "show ip nat translations",
                    "show ip nat statistics"
                ])

            else:
                steps.append(f"Remediate identified fault: {details}")
                ios_commands.extend(["enable", "configure terminal", "end", "write memory"])
                verification_commands.extend(["show running-config"])

        unique_ios = list(dict.fromkeys(ios_commands))
        unique_verif = list(dict.fromkeys(verification_commands))

        return steps, unique_ios, unique_verif

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
            return json.loads(clean_text)
        except Exception:
            return None

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

        fix_steps, ios_cmds, verif_cmds = self.generate_structured_remediation(failed_rules, case_info)

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
            "ios_commands": ios_cmds,
            "verification_commands": verif_cmds,
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
