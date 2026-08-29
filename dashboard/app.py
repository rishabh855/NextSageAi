import os
import pandas as pd
import streamlit as st
import plotly.express as px
from typing import Dict, Any, Optional

# Import core modules
from checker.rule_checker import RuleChecker
from ai.diagnosis import AIDiagnosisEngine
from dashboard.review_manager import ReviewManager
from dashboard.verification_manager import VerificationManager
from dashboard.analytics import AnalyticsManager
from dashboard.evidence_loader import load_case_evidence
from dashboard.session_manager import SessionManager

# Set Page Configuration
st.set_page_config(
    page_title="NetSage AI — Network Diagnostic Console",
    page_icon="🔌",
    layout="wide"
)

CASES_CSV_PATH = os.path.join("data", "cases.csv")
LOG_CSV_PATH = os.path.join("data", "responsible_ai_log.csv")
VERIF_CSV_PATH = os.path.join("data", "verification_log.csv")

def inject_custom_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

code, kbd, pre, samp, textarea {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Base Canvas & Palette */
.stApp {
    background-color: #0a0e17;
    color: #f8fafc;
}

/* Sidebar Styling */
section[data-testid="stSidebar"] {
    background-color: #0f172a !important;
    border-right: 1px solid #1e293b !important;
}

section[data-testid="stSidebar"] * {
    color: #f8fafc !important;
}

/* Header & Container Width */
header[data-testid="stHeader"] {
    background: transparent !important;
}

.block-container {
    max-width: 1150px !important;
    padding-top: 3.5rem !important;
    padding-bottom: 2rem !important;
}

/* Technical Ops Console Header */
.netsage-console-header {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-left: 4px solid #38bdf8;
    border-radius: 6px;
    padding: 0.85rem 1.25rem;
    margin-bottom: 1rem;
}

.netsage-console-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #38bdf8;
    margin: 0;
    text-transform: uppercase;
}

.netsage-console-subtitle {
    font-family: 'IBM Plex Sans', sans-serif;
    color: #94a3b8;
    font-size: 0.825rem;
    font-weight: 400;
    margin-top: 0.2rem;
}

.sys-tag {
    font-family: 'JetBrains Mono', monospace;
    display: inline-block;
    padding: 0.15rem 0.5rem;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border-radius: 4px;
    background: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
    margin-right: 0.4rem;
}

.sys-tag-active {
    background: rgba(56, 189, 248, 0.1);
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.3);
}

/* Persistent Priority-Tier Rail */
.priority-rail-container {
    display: flex;
    gap: 6px;
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 0.65rem 0.85rem;
    margin-bottom: 1.25rem;
}

.priority-tier-box {
    flex: 1;
    background: #162032;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 0.4rem 0.5rem;
    text-align: center;
    transition: all 0.2s ease;
}

.priority-tier-box.active-tier {
    border-color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
}

.priority-tier-box.active-tier-fail {
    border-color: #f87171;
    background: rgba(248, 113, 113, 0.12);
}

.priority-tier-code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    color: #cbd5e1;
}

.priority-tier-box.active-tier .priority-tier-code {
    color: #38bdf8;
}

.priority-tier-box.active-tier-fail .priority-tier-code {
    color: #f87171;
}

.priority-tier-name {
    font-size: 0.65rem;
    color: #64748b;
    font-weight: 500;
    margin-top: 0.1rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Technical Panels */
.ops-panel {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 1.15rem 1.35rem;
    margin-bottom: 1rem;
}

.ops-panel-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.875rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #f8fafc;
    text-transform: uppercase;
    margin-bottom: 0.85rem;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 0.4rem;
}

/* Terminal Log View */
.terminal-window {
    background: #030712;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #cbd5e1;
    line-height: 1.45;
    height: 340px;
    overflow-y: auto;
    white-space: pre-wrap;
}

.terminal-line-prompt {
    color: #38bdf8;
    font-weight: 600;
}

.terminal-line-result {
    color: #94a3b8;
}

/* Status Vocabulary Boxes */
.status-vocab {
    font-family: 'JetBrains Mono', monospace;
    display: inline-block;
    padding: 0.2rem 0.55rem;
    font-size: 0.725rem;
    font-weight: 700;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.status-vocab-fail {
    background: rgba(248, 113, 113, 0.12);
    color: #f87171;
    border: 1px solid rgba(248, 113, 113, 0.3);
}

.status-vocab-pass {
    background: rgba(52, 211, 153, 0.12);
    color: #34d399;
    border: 1px solid rgba(52, 211, 153, 0.3);
}

.status-vocab-evidence {
    background: rgba(251, 191, 36, 0.12);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
}

.status-vocab-na {
    background: rgba(100, 116, 139, 0.12);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.3);
}

.status-vocab-suppressed {
    background: rgba(71, 85, 105, 0.12);
    color: #64748b;
    border: 1px solid rgba(71, 85, 105, 0.3);
    text-decoration: line-through;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 0.75rem 0.9rem;
}

div[data-testid="stMetricLabel"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    color: #64748b !important;
    text-transform: uppercase;
}

div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #f8fafc !important;
}

/* Minimal Tab Bar */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: transparent;
    padding: 0 0 4px 0;
    border-bottom: 1px solid #1e293b;
    margin-bottom: 1rem;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace;
    height: 36px;
    border-radius: 0px;
    color: #64748b;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0 12px;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
}

.stTabs [aria-selected="true"] {
    color: #38bdf8 !important;
    border-bottom: 2px solid #38bdf8 !important;
}

/* Inputs & Form Control */
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-family: 'IBM Plex Sans', sans-serif;
    color: #cbd5e1 !important;
    font-weight: 600 !important;
    font-size: 0.825rem !important;
}

.stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
    border-radius: 4px !important;
    border: 1px solid #1e293b !important;
    background-color: #030712 !important;
    color: #f8fafc !important;
    font-size: 0.85rem !important;
}

.stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
    border-color: #38bdf8 !important;
    box-shadow: 0 0 0 1px #38bdf8 !important;
}

/* Buttons */
.stButton>button {
    font-family: 'JetBrains Mono', monospace;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.825rem;
    letter-spacing: 0.02em;
    border: 1px solid #1e293b;
}

.stButton>button[kind="primary"] {
    background: #0284c7;
    color: #ffffff !important;
    border: 1px solid #0369a1;
}

.stButton>button[kind="primary"]:hover {
    background: #0369a1;
    border-color: #075985;
}
</style>
""", unsafe_allow_html=True)

def render_priority_rail(active_tier: str = "P1"):
    """
    Renders the signature persistent priority-tier rail across the diagnostic console.
    """
    tiers = [
        ("P1", "PHYSICAL / INTERFACE"),
        ("P2", "TRUNKING / NATIVE VLAN"),
        ("P3", "ACCESS VLAN / DATABASE"),
        ("P4", "IP SUBNET / GATEWAY"),
        ("P5", "ROUTING PROTOCOL"),
        ("P6", "SERVICES / DHCP / ACL")
    ]
    
    rail_html = '<div class="priority-rail-container">'
    for code, name in tiers:
        is_active = (code == active_tier)
        css_class = "priority-tier-box active-tier-fail" if is_active else "priority-tier-box"
        rail_html += f'<div class="{css_class}"><div class="priority-tier-code">{code}</div><div class="priority-tier-name">{name}</div></div>'
    rail_html += '</div>'
    st.markdown(rail_html, unsafe_allow_html=True)


@st.cache_data
def load_cases(csv_path: str = CASES_CSV_PATH) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, dtype=str)
        df.fillna("", inplace=True)
        return df
    except Exception as e:
        st.error(f"Error reading cases dataset: {e}")
        return pd.DataFrame()

def load_reviews(csv_path: str = LOG_CSV_PATH) -> pd.DataFrame:
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, dtype=str)
        df.fillna("", inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def load_verifications(csv_path: str = VERIF_CSV_PATH) -> pd.DataFrame:
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, dtype=str)
        df.fillna("", inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def filter_cases(
    df: pd.DataFrame,
    category: str = "All",
    severity: str = "All",
    osi_layer: str = "All",
    evidence_status: str = "All"
) -> pd.DataFrame:
    filtered = df.copy()
    if category != "All" and "category" in filtered.columns:
        filtered = filtered[filtered["category"] == category]
    if severity != "All" and "severity" in filtered.columns:
        filtered = filtered[filtered["severity"] == severity]
    if osi_layer != "All" and "osi_layer" in filtered.columns:
        filtered = filtered[filtered["osi_layer"] == osi_layer]
    if evidence_status != "All" and "evidence_status" in filtered.columns:
        filtered = filtered[filtered["evidence_status"] == evidence_status]
    return filtered

def get_case_by_id(df: pd.DataFrame, case_id: str) -> Optional[Dict[str, Any]]:
    if df.empty or "case_id" not in df.columns:
        return None
    matches = df[df["case_id"] == case_id]
    if not matches.empty:
        return matches.iloc[0].to_dict()
    return None

def render_new_session_workflow(
    session_mgr: SessionManager,
    review_mgr: ReviewManager,
    verif_mgr: VerificationManager,
    df_cases: pd.DataFrame
):
    """
    Renders the Guided Network Investigation workflow in a 2-pane terminal console layout.
    """
    existing_sessions = session_mgr.list_sessions()

    # --- STEP 1 & INVENTORY SETUP CONTROL BLOCK ---
    st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ops-panel-header">CONSOLE // START GUIDED DIAGNOSTIC SESSION</div>', unsafe_allow_html=True)
    
    col_inp1, col_inp2 = st.columns(2)
    with col_inp1:
        symptom_input = st.text_input(
            "SYMPTOM DESCRIPTION (REQUIRED)",
            placeholder="e.g. PC0 has an IP address but cannot ping the server.",
            key="input_symptom"
        )
        topology_input = st.text_input(
            "TOPOLOGY PATH (OPTIONAL)",
            placeholder="e.g. PC0 -> Switch0 -> Switch1 -> Router0 -> Server",
            key="input_topology"
        )
    with col_inp2:
        case_id_opts = ["None (Unlinked)"] + [c for c in df_cases["case_id"].unique() if c] if not df_cases.empty else ["None (Unlinked)"]
        selected_case_link = st.selectbox("LINK BENCHMARK CASE ID", case_id_opts, key="input_case_link")
        
        if existing_sessions:
            session_opts = [f"{s['session_id']} - {s.get('symptom', '')[:30]}..." for s in existing_sessions]
            selected_sess_opt = st.selectbox("LOAD RECENT SESSION", ["None (New Session)"] + session_opts, key="select_saved_session_dd")
            if selected_sess_opt != "None (New Session)":
                selected_sess_id = selected_sess_opt.split(" - ")[0]
                if st.session_state.get("active_session_id") != selected_sess_id:
                    st.session_state["active_session_id"] = selected_sess_id
                    st.session_state["session_rule_results"] = None
                    st.session_state["session_ai_diagnosis"] = None
                    st.rerun()

    st.markdown('<div style="margin-top: 0.5rem; font-family: \'JetBrains Mono\', monospace; font-size: 0.75rem; color: #94a3b8;">NETWORK INVENTORY COUNTS & HOSTNAMES</div>', unsafe_allow_html=True)
    
    inv_col1, inv_col2, inv_col3, inv_col4 = st.columns(4)
    with inv_col1:
        ed_count = st.selectbox("END DEVICES", list(range(0, 21)), index=2, key="inv_ed_count")
        ed_names_str = st.text_input("HOSTNAMES", value="PC0, PC1", key="inv_ed_names")
    with inv_col2:
        sw_count = st.selectbox("SWITCHES", list(range(0, 21)), index=2, key="inv_sw_count")
        sw_names_str = st.text_input("SWITCH NAMES", value="Switch0, Switch1", key="inv_sw_names")
    with inv_col3:
        rt_count = st.selectbox("ROUTERS", list(range(0, 21)), index=1, key="inv_rt_count")
        rt_names_str = st.text_input("ROUTER NAMES", value="Router0", key="inv_rt_names")
    with inv_col4:
        wl_count = st.selectbox("WIRELESS", list(range(0, 21)), index=0, key="inv_wl_count")
        wl_names_str = st.text_input("AP NAMES", value="", key="inv_wl_names")

    st.markdown('<div style="margin-top: 0.75rem;"></div>', unsafe_allow_html=True)

    if st.button("INITIALIZE DIAGNOSTIC SESSION", type="primary", key="btn_start_guided_session", use_container_width=True):
        if not symptom_input or not symptom_input.strip():
            st.error("Symptom description is required to initialize session.")
        else:
            linked_id = selected_case_link if selected_case_link != "None (Unlinked)" else None
            inventory_data = {
                "end_devices_count": ed_count,
                "switches_count": sw_count,
                "routers_count": rt_count,
                "wireless_count": wl_count,
                "end_devices": [x.strip() for x in ed_names_str.split(",") if x.strip()] or [f"PC{i}" for i in range(ed_count)],
                "switches": [x.strip() for x in sw_names_str.split(",") if x.strip()] or [f"Switch{i}" for i in range(sw_count)],
                "routers": [x.strip() for x in rt_names_str.split(",") if x.strip()] or [f"Router{i}" for i in range(rt_count)],
                "wireless": [x.strip() for x in wl_names_str.split(",") if x.strip()] or [f"AP{i}" for i in range(wl_count)]
            }

            sess = session_mgr.create_session(
                symptom=symptom_input,
                topology=topology_input,
                case_id=linked_id,
                inventory=inventory_data
            )
            st.session_state["active_session_id"] = sess["session_id"]
            st.session_state["session_rule_results"] = None
            st.session_state["session_ai_diagnosis"] = None
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    active_session_id = st.session_state.get("active_session_id")
    if not active_session_id:
        return

    session_data = session_mgr.get_session(active_session_id)
    if not session_data:
        st.error(f"Error loading session `{active_session_id}`.")
        return

    st.markdown("---")

    # --- TWO-PANE TERMINAL CONSOLE WORKSPACE ---
    investigation_status = session_data.get("investigation_status", "ACTIVE")
    current_step = session_data.get("current_step", 1)
    current_device = session_data.get("current_device", "Router0")
    current_command = session_data.get("current_command", "show ip interface brief")
    reason_for_command = session_data.get("reason_for_command", "Inspect interface status.")

    pane_left, pane_right = st.columns([1, 1])

    # --- LEFT PANE: ACCUMULATED TERMINAL EVIDENCE LOG ---
    with pane_left:
        st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
        st.markdown(f'<div class="ops-panel-header">TERMINAL EVIDENCE LOG // SESSION {active_session_id}</div>', unsafe_allow_html=True)

        inv_history = session_data.get("investigation_history", [])
        term_text = f"// NETSAGE DIAGNOSTIC CONSOLE v2.0\n// SESSION: {active_session_id}\n// SYMPTOM: {session_data.get('symptom')}\n\n"
        
        if inv_history:
            for h in inv_history:
                term_text += f"[STEP {h.get('step')}] DEVICE: {h.get('device')} | CMD: {h.get('command')}\n"
                term_text += f"RESULT: {h.get('result_summary')}\n----------------------------------------\n"
        else:
            term_text += "[SYSTEM] Session initialized. Awaiting Step 1 CLI output submission...\n"

        st.markdown(f'<div class="terminal-window">{term_text}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- RIGHT PANE: TARGET COMMAND & EVIDENCE SUBMISSION ---
    with pane_right:
        st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
        st.markdown(f'<div class="ops-panel-header">STEP {current_step} // TARGET COMMAND & SUBMISSION</div>', unsafe_allow_html=True)

        if investigation_status == "ACTIVE":
            st.markdown(
                f'<div style="font-family: \'JetBrains Mono\', monospace; font-size: 0.8rem; margin-bottom: 0.5rem;">'
                f'TARGET DEVICE: <span style="color: #38bdf8; font-weight: 700;">{current_device}</span><br>'
                f'RECOMMENDED COMMAND: <span style="color: #34d399; font-weight: 700;">{current_command}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.caption(f"REASON: {reason_for_command}")

            dev_input = st.text_input("EXECUTING DEVICE", value=current_device, key=f"dev_in_{active_session_id}_{current_step}")
            cmd_input = st.text_input("EXECUTED COMMAND", value=current_command, key=f"cmd_in_{active_session_id}_{current_step}")

            cli_text_input = st.text_area(
                "PASTE CLI SHOW OUTPUT FROM PACKET TRACER",
                placeholder="Copy CLI terminal output from Packet Tracer and paste here...",
                height=140,
                key=f"cli_in_{active_session_id}_{current_step}"
            )

            if st.button("SUBMIT CLI EVIDENCE & EVALUATE", type="primary", key=f"btn_sub_ev_{active_session_id}_{current_step}", use_container_width=True):
                if not cli_text_input or not cli_text_input.strip():
                    st.error("CLI output payload is empty.")
                else:
                    session_mgr.add_evidence(
                        session_id=active_session_id,
                        cli_output=cli_text_input,
                        command=cmd_input,
                        device=dev_input
                    )

                    accumulated_evidence = session_mgr.get_accumulated_evidence(active_session_id)
                    checker = RuleChecker()
                    rule_res = checker.run_all_checks(accumulated_evidence)

                    engine = AIDiagnosisEngine()
                    session_case_info = {
                        "case_id": active_session_id,
                        "category": "General",
                        "symptom": session_data.get("symptom", ""),
                        "topology_note": session_data.get("topology", ""),
                        "network_inventory": session_data.get("network_inventory", {}),
                        "show_outputs": accumulated_evidence,
                        "investigation_history": session_data.get("investigation_history", [])
                    }
                    diag = engine.diagnose(session_case_info, rule_res)
                    st.session_state["session_rule_results"] = rule_res
                    st.session_state["session_ai_diagnosis"] = diag

                    diag_status = diag.get("status", "NO_CONFIRMED_ISSUE")

                    if diag_status == "ISSUE_CONFIRMED":
                        session_mgr.update_investigation_state(
                            session_id=active_session_id,
                            state="ISSUE_CONFIRMED",
                            result_summary=f"CONFIRMED FAULT: {diag.get('root_cause')}",
                            investigation_status="STOPPED"
                        )
                    elif diag_status == "NEED_MORE_EVIDENCE":
                        session_mgr.update_investigation_state(
                            session_id=active_session_id,
                            state="NEED_MORE_EVIDENCE",
                            next_device=diag.get("next_device", current_device),
                            next_command=diag.get("next_command", "show running-config"),
                            reason_for_command=diag.get("reason_for_command", "Follow-up evidence required."),
                            result_summary=f"SUSPICION: {diag.get('root_cause')}"
                        )
                    else:
                        next_cmd = diag.get("next_command", "")
                        next_dev = diag.get("next_device", "")
                        if not next_cmd:
                            session_mgr.update_investigation_state(
                                session_id=active_session_id,
                                state="NO_CONFIRMED_ISSUE",
                                next_device="",
                                next_command="",
                                reason_for_command="Standard diagnostic checks complete.",
                                result_summary="NO FAULT CONFIRMED in standard checks.",
                                investigation_status="STOPPED"
                            )
                        else:
                            session_mgr.update_investigation_state(
                                session_id=active_session_id,
                                state="NO_CONFIRMED_ISSUE",
                                next_device=next_dev,
                                next_command=next_cmd,
                                reason_for_command=diag.get("reason_for_command", "No issue in current check."),
                                result_summary="PASS: No issue detected in current check."
                            )
                    st.rerun()
        else:
            st.markdown('<div class="status-vocab status-vocab-pass">SESSION COMPLETE - INVESTIGATION CONCLUDED</div>', unsafe_allow_html=True)
            st.caption("Standard diagnostic checks completed or fault pinpointed.")


        st.markdown('</div>', unsafe_allow_html=True)

    # --- SECTION 3: DIAGNOSTIC ANALYSIS & CITATIONS ---
    accumulated_evidence = session_mgr.get_accumulated_evidence(active_session_id)
    if st.session_state.get("session_ai_diagnosis") is None and accumulated_evidence:
        checker = RuleChecker()
        rule_res = checker.run_all_checks(accumulated_evidence)
        st.session_state["session_rule_results"] = rule_res

        engine = AIDiagnosisEngine()
        session_case_info = {
            "case_id": active_session_id,
            "category": "General",
            "symptom": session_data.get("symptom", ""),
            "topology_note": session_data.get("topology", ""),
            "network_inventory": session_data.get("network_inventory", {}),
            "show_outputs": accumulated_evidence
        }
        st.session_state["session_ai_diagnosis"] = engine.diagnose(session_case_info, rule_res)

    diag = st.session_state.get("session_ai_diagnosis")
    if diag:
        st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ops-panel-header">DIAGNOSTIC ANALYSIS // DETERMINISTIC FINDINGS</div>', unsafe_allow_html=True)

        # Highlight Tier on Persistent Rail
        osi_val = str(diag.get("osi_layer") or "Layer 2")
        root_cause_str = str(diag.get("root_cause") or "")
        tier_code = "P1"
        if "3" in osi_val or "Network" in osi_val:
            tier_code = "P4"
        elif "VLAN" in root_cause_str or "Trunk" in root_cause_str:
            tier_code = "P2"
        elif "Routing" in root_cause_str:
            tier_code = "P5"
        elif "DHCP" in root_cause_str or "ACL" in root_cause_str:
            tier_code = "P6"

        render_priority_rail(tier_code)

        diag_state = diag.get("status", "NO_CONFIRMED_ISSUE")
        if diag_state == "ISSUE_CONFIRMED":
            st.markdown(f'<div class="status-vocab status-vocab-fail">CONFIRMED FAULT [{tier_code}]</div>', unsafe_allow_html=True)
        elif diag_state == "NEED_MORE_EVIDENCE":
            st.markdown(f'<div class="status-vocab status-vocab-evidence">NEED MORE EVIDENCE [{tier_code}]</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="status-vocab status-vocab-pass">CLEAR / NO FAULT CONFIRMED</div>', unsafe_allow_html=True)

        st.markdown(f"**PRIMARY FAILURE CLAIM:** {diag.get('root_cause')}")
        
        # Evidence Citations DIRECTLY UNDER Claim
        st.markdown("**EVIDENCE CITATIONS:**")
        for ev in diag.get("evidence", []):
            st.markdown(f"↳ <span style='color: #38bdf8; font-family: monospace;'>{ev}</span>", unsafe_allow_html=True)

        st.markdown("**RECOMMENDED FIX PROCEDURE:**")
        for idx, step in enumerate(diag.get("fix_steps", []), 1):
            st.markdown(f"{idx}. {step}")

        ios_cmds = diag.get("ios_commands", [])
        if ios_cmds:
            st.markdown("**CISCO IOS CONFIGURATION COMMANDS:**")
            st.code("\n".join(ios_cmds), language="cisco")

        verif_cmds = diag.get("verification_commands", [])
        if verif_cmds:
            st.markdown("**VERIFICATION COMMANDS:**")
            st.code("\n".join(verif_cmds), language="cisco")

        st.markdown('</div>', unsafe_allow_html=True)


        # --- SECTION 4: RESPONSIBLE AI REVIEW & OVERSIGHT ---
        st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ops-panel-header">HUMAN REVIEWER OVERSIGHT // DECISION CONTROL</div>', unsafe_allow_html=True)

        existing_review = review_mgr.get_review_for_case(active_session_id)
        if existing_review:
            st.markdown(
                f'<div class="status-vocab status-vocab-pass">RECORDED DECISION: {existing_review.get("human_decision")}</div> '
                f'<span style="font-family: monospace; font-size: 0.8rem; color: #94a3b8;">LOG ID: {existing_review.get("log_id")}</span>',
                unsafe_allow_html=True
            )
            st.markdown(f"**NOTES:** {existing_review.get('reason_for_correction')}")

        st.markdown("Select Decision Mode:")
        rev_mode = st.radio("Review Mode", ["ACCEPT DIAGNOSIS", "EDIT DIAGNOSIS", "REJECT DIAGNOSIS"], horizontal=True, key=f"rev_mode_radio_{active_session_id}")

        if rev_mode == "ACCEPT DIAGNOSIS":
            accept_notes = st.text_area("OPTIONAL REVIEWER VERIFICATION COMMENTS", key=f"guided_acc_notes_{active_session_id}")
            if st.button("RECORD ACCEPT DECISION", type="primary", key=f"guided_btn_acc_{active_session_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=active_session_id,
                    category="General",
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Accept",
                    corrected_diagnosis=initial_diag_text,
                    reason_for_correction=accept_notes or "Accepted by reviewer after evidence inspection."
                )
                if res.get("success"):
                    st.rerun()

        elif rev_mode == "EDIT DIAGNOSIS":
            default_edit_text = f"Root Cause: {diag.get('root_cause')}"
            edited_diag = st.text_area("CORRECTED DIAGNOSIS (REQUIRED)", value=default_edit_text, key=f"guided_edit_text_{active_session_id}")
            edit_reason = st.text_area("REASON FOR CORRECTION (REQUIRED)", placeholder="Explain rationale...", key=f"guided_edit_reason_{active_session_id}")
            if st.button("RECORD EDIT DECISION", type="primary", key=f"guided_btn_edt_{active_session_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=active_session_id,
                    category="General",
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Edit",
                    corrected_diagnosis=edited_diag,
                    reason_for_correction=edit_reason
                )
                if res.get("success"):
                    st.rerun()

        else:
            reject_reason = st.text_area("REJECTION REASON (REQUIRED)", placeholder="Explain why rejected...", key=f"guided_reject_reason_{active_session_id}")
            if st.button("RECORD REJECT DECISION", type="primary", key=f"guided_btn_rej_{active_session_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=active_session_id,
                    category="General",
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Reject",
                    corrected_diagnosis="[REJECTED]",
                    reason_for_correction=reject_reason
                )
                if res.get("success"):
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

def render_case_explorer_workflow(
    df_cases: pd.DataFrame,
    review_mgr: ReviewManager,
    verif_mgr: VerificationManager
):
    """
    Renders the Case Explorer screen as a scannable technical table of 35 benchmark cases.
    """
    st.sidebar.markdown('<div style="font-family: \'JetBrains Mono\', monospace; font-weight: 700; font-size: 0.85rem; color: #38bdf8; margin-bottom: 0.5rem;">FILTER BENCHMARK DATASET</div>', unsafe_allow_html=True)

    categories = ["All"] + sorted([c for c in df_cases["category"].unique() if c])
    severities = ["All"] + sorted([s for s in df_cases["severity"].unique() if s])
    osi_layers = ["All"] + sorted([l for l in df_cases["osi_layer"].unique() if l])
    statuses = ["All"] + sorted([st_val for st_val in df_cases["evidence_status"].unique() if st_val])

    sel_category = st.sidebar.selectbox("CATEGORY", categories)
    sel_severity = st.sidebar.selectbox("SEVERITY", severities)
    sel_osi = st.sidebar.selectbox("OSI LAYER", osi_layers)
    sel_status = st.sidebar.selectbox("EVIDENCE STATUS", statuses)

    filtered_df = filter_cases(df_cases, sel_category, sel_severity, sel_osi, sel_status)
    st.sidebar.markdown(f"**MATCHING RECORD COUNT:** `{len(filtered_df)}` / `{len(df_cases)}`")

    st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ops-panel-header">CASE EXPLORER // BENCHMARK LAB DATASET (35 CASES)</div>', unsafe_allow_html=True)

    if filtered_df.empty:
        st.warning("No benchmark cases match the specified filters.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # SCANNABLE DATASET TABLE
    display_df = filtered_df[["case_id", "category", "severity", "osi_layer", "concept", "evidence_status"]].copy()
    st.dataframe(display_df, use_container_width=True, height=240)

    case_options = [f"{row['case_id']} - {row['category']} - {row['symptom'][:45]}..." for _, row in filtered_df.iterrows()]
    selected_option = st.selectbox("SELECT CASE RECORD TO INSPECT", case_options, key="explorer_case_select")

    selected_id = selected_option.split(" - ")[0]
    case_info = get_case_by_id(filtered_df, selected_id)

    if case_info:
        st.markdown("---")
        st.markdown(f"### CASE RECORD: `{case_info.get('case_id')}` [{case_info.get('category')}]")
        st.markdown(f"**SYMPTOM:** {case_info.get('symptom')}")
        st.markdown(f"**TOPOLOGY NOTE:** `{case_info.get('topology_note')}`")

        # Persistent Rail Link
        osi_val = str(case_info.get("osi_layer") or "Layer 2")
        cat_str = str(case_info.get("category") or "")
        tier_code = "P1"
        if "3" in osi_val or "Network" in osi_val:
            tier_code = "P4"
        elif "VLAN" in cat_str:
            tier_code = "P2"
        elif "Routing" in cat_str:
            tier_code = "P5"
        elif "DHCP" in cat_str or "ACL" in cat_str:
            tier_code = "P6"

        render_priority_rail(tier_code)

        raw_csv_outputs = case_info.get("show_outputs", "")
        show_output = load_case_evidence(selected_id, raw_csv_outputs)
        st.markdown("#### CISCO CLI SHOW EVIDENCE OUTPUT")
        st.code(show_output or "// No show command output provided", language="text")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("RUN DETERMINISTIC RULE CHECKER", type="primary", key="btn_explorer_rules", use_container_width=True):
                checker = RuleChecker()
                st.session_state["rule_results"] = checker.run_all_checks(show_output)

        with col_btn2:
            if st.button("RUN AI DIAGNOSIS ENGINE", type="primary", key="btn_explorer_ai", use_container_width=True):
                checker = RuleChecker()
                rule_res = checker.run_all_checks(show_output)
                engine = AIDiagnosisEngine()
                st.session_state["ai_diagnosis"] = engine.diagnose(case_info, rule_res)

        if st.session_state.get("rule_results"):
            st.markdown("#### DETERMINISTIC RULE EVALUATION STATES")
            for res in st.session_state["rule_results"]:
                status = res.get("status", "INFO")
                if status == "FAIL":
                    st.markdown(f'<div class="status-vocab status-vocab-fail">FAIL</div> <b>{res.get("check_name")}</b>: {res.get("details")}', unsafe_allow_html=True)
                elif status == "NEED_MORE_EVIDENCE":
                    st.markdown(f'<div class="status-vocab status-vocab-evidence">NEED_MORE_EVIDENCE</div> <b>{res.get("check_name")}</b>: {res.get("details")}', unsafe_allow_html=True)
                elif status == "SUPPRESSED":
                    st.markdown(f'<div class="status-vocab status-vocab-suppressed">SUPPRESSED</div> <b>{res.get("check_name")}</b>: {res.get("details")}', unsafe_allow_html=True)
                elif status == "NOT_APPLICABLE":
                    st.markdown(f'<div class="status-vocab status-vocab-na">NOT_APPLICABLE</div> <b>{res.get("check_name")}</b>: {res.get("details")}', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="status-vocab status-vocab-pass">PASS</div> <b>{res.get("check_name")}</b>: {res.get("details")}', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

def render_analytics_dashboard(df_cases: pd.DataFrame, df_reviews: pd.DataFrame, df_verifications: pd.DataFrame):
    st.markdown('<div class="ops-panel">', unsafe_allow_html=True)
    st.markdown('<div class="ops-panel-header">RESPONSIBLE AI & PERFORMANCE METRICS</div>', unsafe_allow_html=True)

    kpis = AnalyticsManager.get_kpis(df_cases, df_reviews, df_verifications)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5, col_kpi6 = st.columns(6)
    with col_kpi1:
        st.metric("TOTAL CASES", kpis["total_cases"])
    with col_kpi2:
        st.metric("REVIEWS LOGGED", kpis["total_reviews"])
    with col_kpi3:
        st.metric("ACCEPTED", kpis["accepted_count"])
    with col_kpi4:
        st.metric("CORRECTIONS", kpis["corrections_count"])
    with col_kpi5:
        st.metric("AGREEMENT RATE", f"{kpis['agreement_rate']}%" if kpis['agreement_rate'] is not None else "N/A")
    with col_kpi6:
        st.metric("VERIFIED FIXED", kpis.get("resolved_count", 0))

    st.markdown("---")

    c_col1, c_col2 = st.columns(2)
    cat_counts = AnalyticsManager.get_category_counts(df_cases)
    if cat_counts:
        df_cat = pd.DataFrame(list(cat_counts.items()), columns=["Category", "Cases"])
        fig_cat = px.bar(df_cat, x="Category", y="Cases", color="Category", title="Cases by Category", template="plotly_dark")
        fig_cat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        c_col1.plotly_chart(fig_cat, use_container_width=True)

    if not df_reviews.empty:
        dec_counts = AnalyticsManager.get_decision_counts(df_reviews)
        df_dec = pd.DataFrame(list(dec_counts.items()), columns=["Decision", "Count"])
        fig_dec = px.bar(
            df_dec, x="Decision", y="Count", color="Decision",
            color_discrete_map={"Accept": "#34d399", "Edit": "#fbbf24", "Reject": "#f87171"},
            title="Human Review Decision Breakdown",
            template="plotly_dark"
        )
        fig_dec.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        c_col2.plotly_chart(fig_dec, use_container_width=True)

    st.markdown("---")
    st.markdown("#### RESPONSIBLE AI AUDIT LOG TABLE")
    if not df_reviews.empty:
        st.dataframe(df_reviews, use_container_width=True)
    else:
        st.info("No review records logged in `data/responsible_ai_log.csv`.")

    st.markdown('</div>', unsafe_allow_html=True)

def main():
    inject_custom_css()

    st.markdown("""
    <div class="netsage-console-header">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
                <span class="sys-tag sys-tag-active">NETSAGE_AI // v2.0</span>
                <span class="sys-tag">ENGINE: FACT_BASED_V2</span>
                <span class="sys-tag">RULES: 12_CONTRACTS</span>
                <h1 class="netsage-console-title">Cisco Network Diagnostic Console</h1>
                <div class="netsage-console-subtitle">Deterministic Rule Evaluation & AI-Assisted Troubleshooting Console</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_new_session, tab_explorer, tab_analytics = st.tabs([
        "01 // GUIDED ASSISTANT",
        "02 // CASE EXPLORER",
        "03 // RESPONSIBLE AI ANALYTICS"
    ])

    df_cases = load_cases()
    session_mgr = SessionManager()
    review_mgr = ReviewManager(LOG_CSV_PATH)
    verif_mgr = VerificationManager(VERIF_CSV_PATH)
    df_reviews = load_reviews(LOG_CSV_PATH)
    df_verifications = load_verifications(VERIF_CSV_PATH)

    with tab_new_session:
        render_new_session_workflow(session_mgr, review_mgr, verif_mgr, df_cases)

    with tab_explorer:
        if df_cases.empty:
            st.error("No cases dataset found in `data/cases.csv`.")
        else:
            render_case_explorer_workflow(df_cases, review_mgr, verif_mgr)

    with tab_analytics:
        render_analytics_dashboard(df_cases, df_reviews, df_verifications)

if __name__ == "__main__":
    main()
