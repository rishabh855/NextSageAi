import os
import json
import re
import datetime
from typing import Dict, Any, List, Optional

SESSIONS_BASE_DIR = os.path.join("data", "evidence", "sessions")

class SessionManager:
    """
    Manages interactive troubleshooting sessions, CLI evidence collection,
    network inventory, guided investigation step tracking, evidence persistence under
    data/evidence/sessions/<session_id>/, and accumulated evidence formatting.
    """

    def __init__(self, base_dir: str = SESSIONS_BASE_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    @staticmethod
    def detect_command(cli_output: str) -> str:
        """
        Auto-detects Cisco or host command from raw CLI output text if not explicitly provided.
        """
        if not cli_output:
            return "CLI Output"
        first_line = cli_output.strip().splitlines()[0]
        # Look for command prompt patterns like Switch# show interfaces trunk or C:\> ipconfig
        match = re.search(r"[#>\$]\s*([a-zA-Z0-9_\-\s/\|]+)", first_line)
        if match:
            return match.group(1).strip()
        
        lowered = cli_output.lower()
        if "show interfaces trunk" in lowered:
            return "show interfaces trunk"
        elif "show vlan brief" in lowered or "show vlan" in lowered:
            return "show vlan brief"
        elif "show ip route" in lowered:
            return "show ip route"
        elif "show access-lists" in lowered or "show ip access-lists" in lowered:
            return "show ip access-lists"
        elif "show ip interface brief" in lowered:
            return "show ip interface brief"
        elif "show ip nat translations" in lowered:
            return "show ip nat translations"
        elif "ipconfig" in lowered:
            return "ipconfig /all"
        elif "nslookup" in lowered:
            return "nslookup"
        
    @staticmethod
    def detect_device_and_command(cli_output: str) -> Dict[str, str]:
        """
        Detects both device hostname and command from raw CLI output text.
        """
        cmd = SessionManager.detect_command(cli_output)
        dev = "Device"
        if cli_output and cli_output.strip():
            first_line = cli_output.strip().splitlines()[0]
            match = re.search(r"([a-zA-Z0-9_\-]+)[#>\$]", first_line)
            if match:
                dev = match.group(1).strip()
        return {"device": dev, "command": cmd}

    def create_session(
        self,
        symptom: str,
        topology: str = "",
        case_id: Optional[str] = None,
        inventory: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates a new troubleshooting session with unique session_id, network inventory,
        and guided investigation state metadata.
        """
        now = datetime.datetime.now()
        session_id = f"SESSION-{now.strftime('%Y%m%d-%H%M%S')}"
        session_dir = os.path.join(self.base_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)

        # Dynamically infer device counts and names from topology text
        combo_text = f"{symptom} {topology}"
        has_router = bool(re.search(r"\b(Router|R1|R2|R3|L3SW|ISP|HQ|Branch)\b", combo_text, re.IGNORECASE))
        has_switch = bool(re.search(r"\b(Switch|SW1|SW2|L2SW)\b", combo_text, re.IGNORECASE))

        router_list = ["Router1"] if has_router else []
        switch_list = ["Switch1", "Switch2"] if has_switch or not has_router else ["Switch1"]

        default_inventory = {
            "end_devices_count": 2,
            "switches_count": len(switch_list),
            "routers_count": len(router_list),
            "wireless_count": 0,
            "end_devices": ["PC0", "PC1"],
            "switches": switch_list,
            "routers": router_list,
            "wireless": []
        }
        if inventory:
            default_inventory.update(inventory)

        init_dev = (default_inventory.get("routers")[0] if default_inventory.get("routers")
                    else (default_inventory.get("switches")[0] if default_inventory.get("switches") else "Switch1"))

        session_data = {
            "session_id": session_id,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "symptom": symptom.strip(),
            "topology": topology.strip(),
            "case_id": case_id.strip() if case_id else "",
            "network_inventory": default_inventory,
            "investigation_status": "ACTIVE",
            "current_step": 1,
            "investigation_state": "NO_CONFIRMED_ISSUE",
            "current_device": init_dev,
            "current_command": "show ip interface brief" if has_router else "show interfaces trunk",
            "reason_for_command": "First, verify interface operational status across network devices.",
            "evidence_list": [],
            "diagnosis_history": [],
            "investigation_history": []
        }

        json_path = os.path.join(session_dir, "session.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        return session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves session metadata and history by session_id with backward compatibility.
        """
        json_path = os.path.join(self.base_dir, session_id, "session.json")
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Ensure backward compatibility for older session files
            data.setdefault("network_inventory", {
                "end_devices_count": 2, "switches_count": 2, "routers_count": 1, "wireless_count": 0,
                "end_devices": ["PC0", "PC1"], "switches": ["Switch0", "Switch1"], "routers": ["Router0"], "wireless": []
            })
            data.setdefault("investigation_status", "ACTIVE")
            data.setdefault("current_step", max(1, len(data.get("evidence_list", []))))
            data.setdefault("investigation_state", "NO_CONFIRMED_ISSUE")
            data.setdefault("current_device", "Router0")
            data.setdefault("current_command", "show ip interface brief")
            data.setdefault("reason_for_command", "Inspect initial CLI outputs.")
            data.setdefault("investigation_history", [])
            return data
        except Exception:
            return None

    def add_evidence(
        self,
        session_id: str,
        cli_output: str,
        command: str = "",
        device: str = ""
    ) -> Dict[str, Any]:
        """
        Appends new CLI evidence to a session, saves evidence_xxx.txt, and updates session.json.
        """
        session_data = self.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session '{session_id}' not found.")

        if not cli_output or not cli_output.strip():
            raise ValueError("CLI output cannot be empty.")

        clean_output = cli_output.strip()
        detected_cmd = command.strip() if command and command.strip() else self.detect_command(clean_output)
        device_name = device.strip() if device and device.strip() else session_data.get("current_device", "Device")

        session_dir = os.path.join(self.base_dir, session_id)
        entry_index = len(session_data.get("evidence_list", [])) + 1
        evidence_filename = f"evidence_{entry_index:03d}.txt"
        file_path = os.path.join(session_dir, evidence_filename)

        header_text = f"--- [{device_name}] {detected_cmd} ---\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{header_text}{clean_output}\n")

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        evidence_entry = {
            "entry_id": f"EV-{entry_index:03d}",
            "timestamp": now,
            "command": detected_cmd,
            "device": device_name,
            "file_name": evidence_filename,
            "raw_output": clean_output
        }

        session_data.setdefault("evidence_list", []).append(evidence_entry)

        # Save updated session.json
        json_path = os.path.join(session_dir, "session.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        return session_data

    def update_investigation_state(
        self,
        session_id: str,
        state: str,
        next_device: str = "",
        next_command: str = "",
        reason_for_command: str = "",
        result_summary: str = "",
        investigation_status: str = "ACTIVE"
    ) -> Dict[str, Any]:
        """
        Updates the guided investigation state, records history step, and updates session.json.
        """
        session_data = self.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session '{session_id}' not found.")

        current_step = session_data.get("current_step", 1)
        prev_dev = session_data.get("current_device", "Device")
        prev_cmd = session_data.get("current_command", "Command")
        prev_reason = session_data.get("reason_for_command", "")

        step_history_entry = {
            "step": current_step,
            "device": prev_dev,
            "command": prev_cmd,
            "reason": prev_reason,
            "state": state,
            "result_summary": result_summary or f"State: {state}"
        }

        history = session_data.setdefault("investigation_history", [])
        # Prevent duplicate history entries for same step or same (device, command) pair
        history = [h for h in history if h.get("step") != current_step and (str(h.get("device")).lower(), str(h.get("command")).lower()) != (prev_dev.lower(), prev_cmd.lower())]
        history.append(step_history_entry)
        session_data["investigation_history"] = history

        session_data["investigation_state"] = state
        session_data["investigation_status"] = investigation_status

        if state == "ISSUE_CONFIRMED" or investigation_status == "STOPPED" or not next_command:
            session_data["investigation_status"] = "STOPPED"
            session_data["current_command"] = ""
            session_data["current_device"] = ""
            session_data["reason_for_command"] = reason_for_command or ("Issue confirmed." if state == "ISSUE_CONFIRMED" else "Standard diagnostic checks completed. No further commands remain. Manual review recommended.")
        else:
            session_data["current_step"] = current_step + 1
            if next_device:
                session_data["current_device"] = next_device
            if next_command:
                session_data["current_command"] = next_command
            if reason_for_command:
                session_data["reason_for_command"] = reason_for_command

        session_dir = os.path.join(self.base_dir, session_id)
        json_path = os.path.join(session_dir, "session.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        return session_data

    def get_accumulated_evidence(self, session_id: str) -> str:
        """
        Combines all evidence entries for a session into a unified CLI evidence string.
        """
        session_data = self.get_session(session_id)
        if not session_data or not session_data.get("evidence_list"):
            return ""

        sections = []
        for entry in session_data.get("evidence_list", []):
            dev = entry.get("device", "Device")
            cmd = entry.get("command", "CLI Output")
            raw = entry.get("raw_output", "")
            sections.append(f"--- [{dev}] {cmd} ---\n{raw}")

        return "\n\n".join(sections)

    def get_combined_evidence(self, session_id: str) -> str:
        """
        Alias for get_accumulated_evidence.
        """
        return self.get_accumulated_evidence(session_id)

    def get_evidence(self, session_id: str, entry_id: Optional[str] = None) -> Any:
        """
        Retrieves evidence list or specific evidence entry by entry_id.
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return [] if entry_id is None else None
        ev_list = session_data.get("evidence_list", [])
        if entry_id is None:
            return ev_list
        for ev in ev_list:
            if ev.get("entry_id") == entry_id:
                return ev
        return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Lists all saved troubleshooting sessions.
        """
        if not os.path.exists(self.base_dir):
            return []

        sessions = []
        for item in sorted(os.listdir(self.base_dir), reverse=True):
            item_path = os.path.join(self.base_dir, item)
            if os.path.isdir(item_path):
                sess = self.get_session(item)
                if sess:
                    sessions.append(sess)
        return sessions
