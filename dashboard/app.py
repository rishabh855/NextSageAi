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
    page_title="NetSage AI — AI-Assisted Network Troubleshooting",
    page_icon="🔌",
    layout="wide"
)

CASES_CSV_PATH = os.path.join("data", "cases.csv")
LOG_CSV_PATH = os.path.join("data", "responsible_ai_log.csv")
VERIF_CSV_PATH = os.path.join("data", "verification_log.csv")

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
    Renders the Guided Network Investigation workflow.
    """
    st.subheader("🔎 Guided Network Investigation")
    st.caption("Step-by-step assistant that selects target devices, recommends diagnostic commands, and analyzes CLI outputs.")

    existing_sessions = session_mgr.list_sessions()
    col_s1, col_s2 = st.columns([2, 1])

    with col_s2:
        st.markdown("#### Session History")
        if existing_sessions:
            session_opts = [f"{s['session_id']} ({s.get('timestamp', '')}) - {s.get('symptom', '')[:30]}..." for s in existing_sessions]
            selected_sess_opt = st.selectbox("Load Saved Session", ["Select a session..."] + session_opts)
            if selected_sess_opt != "Select a session...":
                selected_sess_id = selected_sess_opt.split(" ")[0]
                st.session_state["active_session_id"] = selected_sess_id
        else:
            st.info("No saved sessions found. Create one on the left.")

    with col_s1:
        st.markdown("#### Start Guided Investigation")
        symptom_input = st.text_input(
            "Describe the symptom (Required)",
            placeholder="e.g. PC0 has an IP address but cannot ping the server.",
            key="input_symptom"
        )
        topology_input = st.text_input(
            "Optional topology description",
            placeholder="e.g. PC0 → Switch0 → Switch1 → Router0 → Server",
            key="input_topology"
        )

        case_id_opts = ["None (Unlinked)"] + [c for c in df_cases["case_id"].unique() if c] if not df_cases.empty else ["None (Unlinked)"]
        selected_case_link = st.selectbox("Optional Link to Dataset Case ID", case_id_opts, key="input_case_link")

        # --- SECTION 1: NETWORK INVENTORY UI ---
        st.markdown("##### 🌐 Network Inventory")
        inv_col1, inv_col2, inv_col3, inv_col4 = st.columns(4)

        with inv_col1:
            ed_count = st.selectbox("End Devices", list(range(0, 21)), index=2, key="inv_ed_count")
            ed_names_str = st.text_input("End Device Names", value="PC0, PC1", key="inv_ed_names")
        with inv_col2:
            sw_count = st.selectbox("Switches", list(range(0, 21)), index=2, key="inv_sw_count")
            sw_names_str = st.text_input("Switch Names", value="Switch0, Switch1", key="inv_sw_names")
        with inv_col3:
            rt_count = st.selectbox("Routers", list(range(0, 21)), index=1, key="inv_rt_count")
            rt_names_str = st.text_input("Router Names", value="Router0", key="inv_rt_names")
        with inv_col4:
            wl_count = st.selectbox("Wireless Devices", list(range(0, 21)), index=0, key="inv_wl_count")
            wl_names_str = st.text_input("Wireless Names", value="", key="inv_wl_names")

        if st.button("🔎 Start Guided Investigation", type="primary", key="btn_start_guided_session"):
            if not symptom_input or not symptom_input.strip():
                st.error("Please enter a symptom description before starting an investigation.")
            else:
                linked_id = selected_case_link if selected_case_link != "None (Unlinked)" else None
                
                # Format inventory lists
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
                st.success(f"Started Guided Session **{sess['session_id']}**! Saved to `data/evidence/sessions/{sess['session_id']}/`")
                st.rerun()

    active_session_id = st.session_state.get("active_session_id")
    if not active_session_id:
        st.info("💡 Enter network inventory and symptom above, then click **🔎 Start Guided Investigation** to begin.")
        return

    session_data = session_mgr.get_session(active_session_id)
    if not session_data:
        st.error(f"Error loading active session `{active_session_id}`.")
        return

    st.markdown("---")

    # --- ACTIVE SESSION HEADER & INVENTORY SUMMARY ---
    st.subheader(f"📌 Active Session: `{session_data['session_id']}`")
    st.markdown(f"**Symptom:** {session_data.get('symptom')}")
    if session_data.get("topology"):
        st.markdown(f"**Topology:** `{session_data.get('topology')}`")
    
    inv = session_data.get("network_inventory", {})
    st.markdown(
        f"🌐 **Inventory:** `End Devices ({inv.get('end_devices_count', 0)}): {', '.join(inv.get('end_devices', []))}` | "
        f"`Switches ({inv.get('switches_count', 0)}): {', '.join(inv.get('switches', []))}` | "
        f"`Routers ({inv.get('routers_count', 0)}): {', '.join(inv.get('routers', []))}`"
    )

    evidence_list = session_data.get("evidence_list", [])
    investigation_status = session_data.get("investigation_status", "ACTIVE")
    current_step = session_data.get("current_step", 1)
    current_device = session_data.get("current_device", "Router0")
    current_command = session_data.get("current_command", "show ip interface brief")
    reason_for_command = session_data.get("reason_for_command", "Inspect interface status.")

    # --- SECTION 3: GUIDED COMMAND RECOMMENDATION BANNER ---
    if investigation_status == "ACTIVE":
        st.markdown("### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        st.markdown(f"### 🔎 Investigation Step {current_step}")
        st.markdown("### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        b_col1, b_col2 = st.columns([1, 2])
        with b_col1:
            st.info(f"📍 **Device to Open in Packet Tracer:**\n### `{current_device}`")
        with b_col2:
            st.success(f"▶️ **Run this exact command:**\n```text\n{current_command}\n```")
            st.caption(f"💡 **Reason:** {reason_for_command}")

        st.markdown("---")

        # --- SECTION 4: CLI EVIDENCE INPUT ---
        st.markdown("### 📄 Submit Command CLI Output")

        e_col1, e_col2 = st.columns(2)
        with e_col1:
            dev_input = st.text_input("Device Name", value=current_device, key=f"dev_in_{active_session_id}_{current_step}")
        with e_col2:
            cmd_input = st.text_input("Command Executed", value=current_command, key=f"cmd_in_{active_session_id}_{current_step}")

        cli_text_input = st.text_area(
            "Copy complete CLI output from Packet Tracer and paste below",
            placeholder="Paste output from Packet Tracer CLI here...",
            height=180,
            key=f"cli_in_{active_session_id}_{current_step}"
        )

        if st.button("➕ Submit Evidence & Continue Investigation", type="primary", key=f"btn_sub_ev_{active_session_id}_{current_step}"):
            if not cli_text_input or not cli_text_input.strip():
                st.error("Please paste the CLI output before submitting.")
            else:
                session_mgr.add_evidence(
                    session_id=active_session_id,
                    cli_output=cli_text_input,
                    command=cmd_input,
                    device=dev_input
                )

                # Re-analyze all accumulated evidence
                accumulated_evidence = session_mgr.get_accumulated_evidence(active_session_id)
                checker = RuleChecker()
                rule_res = checker.run_all_checks(accumulated_evidence)

                engine = AIDiagnosisEngine()
                session_case_info = {
                    "case_id": active_session_id,
                    "category": "General",
                    "symptom": session_data.get("symptom", ""),
                    "topology_note": session_data.get("topology", ""),
                    "network_inventory": inv,
                    "show_outputs": accumulated_evidence
                }
                diag = engine.diagnose(session_case_info, rule_res)
                st.session_state["session_rule_results"] = rule_res
                st.session_state["session_ai_diagnosis"] = diag

                diag_status = diag.get("status", "NO_CONFIRMED_ISSUE")

                if diag_status == "ISSUE_CONFIRMED":
                    session_mgr.update_investigation_state(
                        session_id=active_session_id,
                        state="ISSUE_CONFIRMED",
                        result_summary=f"🚨 Issue Confirmed: {diag.get('root_cause')}",
                        investigation_status="STOPPED"
                    )
                    st.success("🚨 Fault Confirmed! Investigation complete.")
                elif diag_status == "NEED_MORE_EVIDENCE":
                    session_mgr.update_investigation_state(
                        session_id=active_session_id,
                        state="NEED_MORE_EVIDENCE",
                        next_device=diag.get("next_device", current_device),
                        next_command=diag.get("next_command", "show running-config"),
                        reason_for_command=diag.get("reason_for_command", "Additional evidence required to confirm root cause."),
                        result_summary=f"🟡 Suspicion: {diag.get('root_cause')}"
                    )
                    st.warning("🟡 Possible issue detected — requesting follow-up evidence.")
                else:
                    session_mgr.update_investigation_state(
                        session_id=active_session_id,
                        state="NO_CONFIRMED_ISSUE",
                        next_device=diag.get("next_device", current_device),
                        next_command=diag.get("next_command", "show ip route"),
                        reason_for_command=diag.get("reason_for_command", "No issue detected in check. Moving to next diagnostic check."),
                        result_summary="✅ No issue detected in this check."
                    )
                    st.info("✅ No issue detected in check. Advancing to next diagnostic step.")
                
                st.rerun()

    else:
        st.success("🛑 **Investigation Complete — Issue Confirmed**")

    st.markdown("---")

    # --- SECTION 8: INVESTIGATION HISTORY TIMELINE ---
    inv_history = session_data.get("investigation_history", [])
    if inv_history:
        st.markdown("### 🔎 Investigation History Timeline")
        for h in inv_history:
            st.markdown(
                f"**Step {h.get('step')}** | 📍 `{h.get('device')}` | Command: `{h.get('command')}` | **Result:** {h.get('result_summary')}"
            )
        st.markdown("---")

    # --- SECTION 9 & 10: DIAGNOSIS & STOP CONDITION ---
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
            "network_inventory": inv,
            "show_outputs": accumulated_evidence
        }
        st.session_state["session_ai_diagnosis"] = engine.diagnose(session_case_info, rule_res)

    diag = st.session_state.get("session_ai_diagnosis")
    if diag:
        st.markdown("### 🤖 Diagnostic Analysis")
        
        diag_state = diag.get("status", "NO_CONFIRMED_ISSUE")
        if diag_state == "ISSUE_CONFIRMED":
            st.error("🚨 **ISSUE CONFIRMED — Root Cause Pinpointed**")
        elif diag_state == "NEED_MORE_EVIDENCE":
            st.warning("🟡 **NEED MORE EVIDENCE — Possible Anomaly Detected**")
        else:
            st.info("✅ **NO CONFIRMED ISSUE — Continuing Diagnostics**")

        conf = diag.get("confidence", "Medium")
        if conf == "High":
            st.markdown(f"**Confidence:** :green[{conf}]")
        elif conf == "Medium":
            st.markdown(f"**Confidence:** :orange[{conf}]")
        else:
            st.markdown(f"**Confidence:** :red[{conf}]")

        st.markdown(f"**Root Cause / Suspicion:** {diag.get('root_cause')}")

        st.markdown("**Cited Evidence:**")
        for ev in diag.get("evidence", []):
            st.markdown(f"- `{ev}`")

        st.markdown("**Suggested Fix Steps:**")
        for step in diag.get("fix_steps", []):
            st.markdown(f"1. {step}")

        st.markdown(f"**OSI Layer:** `{diag.get('osi_layer')}` | **Concept Tag:** `{diag.get('concept')}`")

        # --- SECTION 10 & 11: HUMAN REVIEW & FIX VERIFICATION ---
        st.markdown("---")
        st.subheader("👩‍💻 Human Reviewer Oversight & Decision")
        st.info("Inspect the AI diagnosis and cited evidence above, then record your decision.")

        existing_review = review_mgr.get_review_for_case(active_session_id)
        if existing_review:
            st.success(
                f"📋 **Existing Human Review Saved** [{existing_review.get('timestamp')}]\n\n"
                f"**Decision:** `{existing_review.get('human_decision')}` | "
                f"**Log ID:** `{existing_review.get('log_id')}`\n\n"
                f"**Corrected Diagnosis / Notes:** {existing_review.get('corrected_diagnosis')}\n\n"
                f"**Reason / Rationale:** {existing_review.get('reason_for_correction')}"
            )

        review_tab1, review_tab2, review_tab3 = st.tabs(["✅ Accept AI Diagnosis", "✏️ Edit Diagnosis", "❌ Reject Diagnosis"])

        with review_tab1:
            st.markdown("#### Accept Diagnosis")
            accept_comments = st.text_area("Optional Reviewer Comments / Verification Notes", key=f"guided_accept_notes_{active_session_id}")
            if st.button("Submit Decision: ACCEPT", type="primary", key=f"guided_btn_accept_{active_session_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=active_session_id,
                    category="General",
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Accept",
                    corrected_diagnosis=initial_diag_text,
                    reason_for_correction=accept_comments or "Accepted by reviewer after guided evidence inspection."
                )
                if res.get("success"):
                    st.success(f"✅ Decision recorded in `data/responsible_ai_log.csv` as **LOG ID: {res['record']['log_id']}**")
                    st.rerun()
                else:
                    st.error(res.get("error"))

        with review_tab2:
            st.markdown("#### Edit / Correct Diagnosis")
            default_edit_text = f"Root Cause: {diag.get('root_cause')}"
            edited_diag = st.text_area("Corrected Diagnosis (Required)", value=default_edit_text, key=f"guided_edit_text_{active_session_id}")
            edit_reason = st.text_area("Reason for Correction (Required)", placeholder="Explain why the AI diagnosis required correction...", key=f"guided_edit_reason_{active_session_id}")

            if st.button("Submit Decision: EDIT", type="primary", key=f"guided_btn_edit_{active_session_id}"):
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
                    st.success(f"✏️ Correction recorded in `data/responsible_ai_log.csv` as **LOG ID: {res['record']['log_id']}**")
                    st.rerun()
                else:
                    st.error(res.get("error"))

        with review_tab3:
            st.markdown("#### Reject Diagnosis")
            reject_reason = st.text_area("Rejection Reason (Required)", placeholder="Specify why this AI diagnosis is rejected...", key=f"guided_reject_reason_{active_session_id}")

            if st.button("Submit Decision: REJECT", type="primary", key=f"guided_btn_reject_{active_session_id}"):
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
                    st.error(f"❌ Rejection logged in `data/responsible_ai_log.csv` as **LOG ID: {res['record']['log_id']}**")
                    st.rerun()
                else:
                    st.error(res.get("error"))

        st.markdown("---")
        st.subheader("🔧 Fix & Verification Workflow")
        st.info("ℹ️ **NetSage does not control Cisco Packet Tracer. Apply the recommended fix manually in Packet Tracer.**")

        existing_verif = verif_mgr.get_verification_for_case(active_session_id)
        if existing_verif:
            st.success(
                f"📋 **Existing Verification Record** [{existing_verif.get('timestamp')}]\n\n"
                f"**Result:** `{existing_verif.get('verification_result')}` | "
                f"**Before:** `{existing_verif.get('before_status')}` ➔ **After:** `{existing_verif.get('after_status')}`\n\n"
                f"**Verification Notes:** {existing_verif.get('verification_notes')}"
            )

        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            before_status = st.selectbox("Before Fix Connectivity", ["FAIL", "PASS", "NOT_TESTED"], key=f"guided_v_before_{active_session_id}")
        with v_col2:
            after_status = st.selectbox("After Fix Connectivity", ["PASS", "FAIL", "NOT_TESTED"], key=f"guided_v_after_{active_session_id}")
        with v_col3:
            verif_result = st.selectbox("Final Verification Result", ["RESOLVED", "NOT_RESOLVED", "NOT_TESTED"], key=f"guided_v_res_{active_session_id}")

        verif_notes = st.text_area(
            "Verification Notes & Test Evidence (Required for RESOLVED / NOT_RESOLVED)",
            placeholder="Document manual ping results or CLI verification outputs from Packet Tracer...",
            key=f"guided_v_notes_{active_session_id}"
        )

        if st.button("Submit Fix Verification Record", type="primary", key=f"guided_btn_verif_{active_session_id}"):
            res_v = verif_mgr.record_verification(
                case_id=active_session_id,
                before_status=before_status,
                after_status=after_status,
                verification_result=verif_result,
                verification_notes=verif_notes
            )
            if res_v.get("success"):
                st.success(f"✅ Verification record saved in `data/verification_log.csv` as **LOG ID: {res_v['record']['log_id']}**")
                st.rerun()
            else:
                st.error(res_v.get("error"))

def render_case_explorer_workflow(
    df_cases: pd.DataFrame,
    review_mgr: ReviewManager,
    verif_mgr: VerificationManager
):
    st.sidebar.header("🔍 Case Explorer Filters")

    categories = ["All"] + sorted([c for c in df_cases["category"].unique() if c])
    severities = ["All"] + sorted([s for s in df_cases["severity"].unique() if s])
    osi_layers = ["All"] + sorted([l for l in df_cases["osi_layer"].unique() if l])
    statuses = ["All"] + sorted([st_val for st_val in df_cases["evidence_status"].unique() if st_val])

    sel_category = st.sidebar.selectbox("Category", categories)
    sel_severity = st.sidebar.selectbox("Severity", severities)
    sel_osi = st.sidebar.selectbox("OSI Layer", osi_layers)
    sel_status = st.sidebar.selectbox("Evidence Status", statuses)

    filtered_df = filter_cases(df_cases, sel_category, sel_severity, sel_osi, sel_status)

    st.sidebar.markdown(f"**Matching Cases:** `{len(filtered_df)}` / `{len(df_cases)}`")

    if filtered_df.empty:
        st.warning("No cases match the selected filters. Please adjust your criteria.")
        return

    case_options = [f"{row['case_id']} - {row['category']} - {row['symptom'][:40]}..." for _, row in filtered_df.iterrows()]
    selected_option = st.sidebar.selectbox("Select Case to Troubleshoot", case_options)

    selected_id = selected_option.split(" - ")[0]
    case_info = get_case_by_id(filtered_df, selected_id)

    if not case_info:
        st.error("Error loading selected case details.")
        return

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📌 Case {case_info.get('case_id')}: {case_info.get('category')} Fault")
        st.markdown(f"**Symptom:** {case_info.get('symptom')}")
        st.markdown(f"**Topology Note:** `{case_info.get('topology_note')}`")

    with col2:
        status_val = case_info.get("evidence_status", "DEMO_TEMPLATE")
        if status_val == "VERIFIED_LAB":
            st.success("🟢 **VERIFIED_LAB**\nConfirmed Packet Tracer CLI capture")
        else:
            st.info("🔵 **DEMO_TEMPLATE**\nDemo case template")

        st.markdown(f"**Severity:** `{case_info.get('severity')}`")
        st.markdown(f"**OSI Layer:** `{case_info.get('osi_layer')}`")
        st.markdown(f"**Concept Tag:** `{case_info.get('concept')}`")

    st.markdown("---")

    st.subheader("📄 Cisco `show` Command Evidence")
    raw_csv_outputs = case_info.get("show_outputs", "")
    show_output = load_case_evidence(selected_id, raw_csv_outputs)
    if show_output and show_output.strip():
        st.code(show_output, language="text")
    else:
        st.warning("⚠️ No show command output provided for this case.")

    st.markdown("---")

    if "current_case_id" not in st.session_state or st.session_state["current_case_id"] != selected_id:
        st.session_state["rule_results"] = None
        st.session_state["ai_diagnosis"] = None
        st.session_state["current_case_id"] = selected_id

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("⚙️ Run Deterministic Rule Checker", width="stretch"):
            checker = RuleChecker()
            st.session_state["rule_results"] = checker.run_all_checks(show_output)

    with col_btn2:
        if st.button("🤖 Run AI Diagnosis Engine", width="stretch"):
            with st.spinner("Analyzing case evidence with AI Engine..."):
                engine = AIDiagnosisEngine()
                st.session_state["ai_diagnosis"] = engine.diagnose(
                    case_info,
                    st.session_state.get("rule_results") or []
                )

    if st.session_state["rule_results"] is not None:
        st.subheader("⚙️ Rule Checker Results")
        for res in st.session_state["rule_results"]:
            status = res.get("status", "INFO")
            if status == "FAIL":
                st.error(f"❌ **{res.get('check_name')}**: {res.get('details')}")
            elif status == "WARN":
                st.warning(f"⚠️ **{res.get('check_name')}**: {res.get('details')}")
            else:
                st.success(f"✅ **{res.get('check_name')}**: {res.get('details')}")

    if st.session_state["ai_diagnosis"] is not None:
        diag = st.session_state["ai_diagnosis"]
        st.markdown("---")
        st.subheader("🤖 AI Recommendation")
        st.warning("⚠️ **AI Recommendation — Requires Human Review** (Do not auto-apply without human approval)")

        ai_mode = diag.get("ai_mode", "Offline Demo")
        if ai_mode == "Gemini LLM":
            st.caption("⚡ **AI Mode:** `Gemini LLM` (Live API Call)")
        else:
            st.caption("ℹ️ **AI Mode:** `Offline Demo` (Deterministic Fallback Engine)")

        conf = diag.get("confidence", "Medium")
        if conf == "High":
            st.markdown(f"**Confidence:** :green[{conf}]")
        elif conf == "Medium":
            st.markdown(f"**Confidence:** :orange[{conf}]")
        else:
            st.markdown(f"**Confidence:** :red[{conf}]")

        st.markdown(f"**Root Cause:** {diag.get('root_cause')}")

        st.markdown("**Cited Evidence:**")
        for ev in diag.get("evidence", []):
            st.markdown(f"- `{ev}`")

        st.markdown(f"**Recommended Next Command:** `{diag.get('next_command')}`")

        st.markdown("**Recommended Fix Steps:**")
        for step in diag.get("fix_steps", []):
            st.markdown(f"1. {step}")

        st.markdown(f"**OSI Layer:** `{diag.get('osi_layer')}` | **Concept:** `{diag.get('concept')}`")

        st.markdown("---")
        st.subheader("👩‍💻 Human Reviewer Oversight & Decision")
        st.info("As a human reviewer, inspect the AI diagnosis and cited evidence above, then select your decision below.")

        existing_review = review_mgr.get_review_for_case(selected_id)
        if existing_review:
            st.success(
                f"📋 **Existing Human Review Saved** [{existing_review.get('timestamp')}]\n\n"
                f"**Decision:** `{existing_review.get('human_decision')}` | "
                f"**Log ID:** `{existing_review.get('log_id')}`\n\n"
                f"**Corrected Diagnosis / Notes:** {existing_review.get('corrected_diagnosis')}\n\n"
                f"**Reason / Rationale:** {existing_review.get('reason_for_correction')}"
            )

        review_tab1, review_tab2, review_tab3 = st.tabs(["✅ Accept AI Diagnosis", "✏️ Edit Diagnosis", "❌ Reject Diagnosis"])

        with review_tab1:
            st.markdown("#### Accept Diagnosis")
            accept_comments = st.text_area("Optional Reviewer Comments / Verification Notes", key=f"accept_notes_{selected_id}")
            if st.button("Submit Decision: ACCEPT", type="primary", key=f"btn_accept_{selected_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=selected_id,
                    category=case_info.get("category", "General"),
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Accept",
                    corrected_diagnosis=initial_diag_text,
                    reason_for_correction=accept_comments or "Accepted by reviewer after evidence inspection."
                )
                if res.get("success"):
                    st.success(f"✅ Decision recorded in `data/responsible_ai_log.csv` as **LOG ID: {res['record']['log_id']}**")
                    st.rerun()
                else:
                    st.error(res.get("error"))

        with review_tab2:
            st.markdown("#### Edit / Correct Diagnosis")
            default_edit_text = f"Root Cause: {diag.get('root_cause')}"
            edited_diag = st.text_area("Corrected Diagnosis (Required)", value=default_edit_text, key=f"edit_text_{selected_id}")
            edit_reason = st.text_area("Reason for Correction (Required)", placeholder="Explain why the AI diagnosis required correction...", key=f"edit_reason_{selected_id}")

            if st.button("Submit Decision: EDIT", type="primary", key=f"btn_edit_{selected_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=selected_id,
                    category=case_info.get("category", "General"),
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Edit",
                    corrected_diagnosis=edited_diag,
                    reason_for_correction=edit_reason
                )
                if res.get("success"):
                    st.success(f"✏️ Correction recorded in `data/responsible_ai_log.csv` as **LOG ID: {res['record']['log_id']}**")
                    st.rerun()
                else:
                    st.error(res.get("error"))

        with review_tab3:
            st.markdown("#### Reject Diagnosis")
            reject_reason = st.text_area("Rejection Reason (Required)", placeholder="Specify why this AI diagnosis is rejected...", key=f"reject_reason_{selected_id}")

            if st.button("Submit Decision: REJECT", type="primary", key=f"btn_reject_{selected_id}"):
                initial_diag_text = f"Root Cause: {diag.get('root_cause')} | Fix: {'; '.join(diag.get('fix_steps', []))}"
                res = review_mgr.record_review(
                    case_id=selected_id,
                    category=case_info.get("category", "General"),
                    initial_ai_diagnosis=initial_diag_text,
                    ai_confidence=diag.get("confidence", "Medium"),
                    human_decision="Reject",
                    corrected_diagnosis="[REJECTED]",
                    reason_for_correction=reject_reason
                )
                if res.get("success"):
                    st.error(f"❌ Rejection logged in `data/responsible_ai_log.csv` as **LOG ID: {res['record']['log_id']}**")
                    st.rerun()
                else:
                    st.error(res.get("error"))

        st.markdown("---")
        st.subheader("🔧 Fix & Verification Workflow")
        st.code("1. AI Diagnosis ➔ 2. Human Review ➔ 3. Apply Fix in Packet Tracer ➔ 4. Verify Manually ➔ 5. Record Result", language="text")
        st.info("ℹ️ **Fix must be applied and verified manually in Packet Tracer.** (NetSage AI records your manual verification results, but does not control Packet Tracer directly).")

        existing_verif = verif_mgr.get_verification_for_case(selected_id)
        if existing_verif:
            st.success(
                f"📋 **Existing Verification Record** [{existing_verif.get('timestamp')}]\n\n"
                f"**Result:** `{existing_verif.get('verification_result')}` | "
                f"**Before:** `{existing_verif.get('before_status')}` ➔ **After:** `{existing_verif.get('after_status')}`\n\n"
                f"**Verification Notes:** {existing_verif.get('verification_notes')}"
            )

        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            before_status = st.selectbox("Before Fix Connectivity", ["FAIL", "PASS", "NOT_TESTED"], key=f"verif_before_{selected_id}")
        with v_col2:
            after_status = st.selectbox("After Fix Connectivity", ["PASS", "FAIL", "NOT_TESTED"], key=f"verif_after_{selected_id}")
        with v_col3:
            verif_result = st.selectbox("Final Verification Result", ["RESOLVED", "NOT_RESOLVED", "NOT_TESTED"], key=f"verif_res_{selected_id}")

        verif_notes = st.text_area(
            "Verification Notes & Test Evidence (Required for RESOLVED / NOT_RESOLVED)",
            placeholder="Document manual ping results or CLI verification outputs from Packet Tracer...",
            key=f"verif_notes_{selected_id}"
        )

        if st.button("Submit Fix Verification Record", type="primary", key=f"btn_verif_{selected_id}"):
            res_v = verif_mgr.record_verification(
                case_id=selected_id,
                before_status=before_status,
                after_status=after_status,
                verification_result=verif_result,
                verification_notes=verif_notes
            )
            if res_v.get("success"):
                st.success(f"✅ Verification record saved in `data/verification_log.csv` as **LOG ID: {res_v['record']['log_id']}**")
                st.rerun()
            else:
                st.error(res_v.get("error"))

def render_analytics_dashboard(df_cases: pd.DataFrame, df_reviews: pd.DataFrame, df_verifications: pd.DataFrame):
    st.subheader("📊 Responsible AI & Performance Analytics")
    st.caption("Real-time metrics calculated dynamically from case dataset, human review log, and verification log.")

    kpis = AnalyticsManager.get_kpis(df_cases, df_reviews, df_verifications)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5, col_kpi6 = st.columns(6)

    with col_kpi1:
        st.metric("Total Cases", kpis["total_cases"])
    with col_kpi2:
        st.metric("Diagnoses Reviewed", kpis["total_reviews"])
    with col_kpi3:
        st.metric("Accepted", kpis["accepted_count"])
    with col_kpi4:
        st.metric("Human Corrections", kpis["corrections_count"], help="Edited + Rejected diagnoses")
    with col_kpi5:
        if kpis["agreement_rate"] is not None:
            st.metric("AI Agreement Rate", f"{kpis['agreement_rate']}%")
        else:
            st.metric("AI Agreement Rate", "N/A", help="Requires at least 1 human review to calculate")
    with col_kpi6:
        st.metric("Verified Resolved", kpis.get("resolved_count", 0), help="Cases verified as RESOLVED in Packet Tracer")

    st.markdown("---")

    st.subheader("📈 Case Dataset Metrics")
    c_col1, c_col2, c_col3 = st.columns(3)

    cat_counts = AnalyticsManager.get_category_counts(df_cases)
    if cat_counts:
        df_cat = pd.DataFrame(list(cat_counts.items()), columns=["Category", "Cases"])
        fig_cat = px.bar(df_cat, x="Category", y="Cases", color="Category", title="Cases by Fault Category")
        c_col1.plotly_chart(fig_cat, width="stretch")

    sev_counts = AnalyticsManager.get_severity_counts(df_cases)
    if sev_counts:
        df_sev = pd.DataFrame(list(sev_counts.items()), columns=["Severity", "Cases"])
        fig_sev = px.pie(df_sev, names="Severity", values="Cases", title="Cases by Severity Level", hole=0.4)
        c_col2.plotly_chart(fig_sev, width="stretch")

    osi_counts = AnalyticsManager.get_osi_layer_counts(df_cases)
    if osi_counts:
        df_osi = pd.DataFrame(list(osi_counts.items()), columns=["OSI Layer", "Cases"])
        fig_osi = px.bar(df_osi, x="OSI Layer", y="Cases", color="OSI Layer", title="Cases by OSI Layer")
        c_col3.plotly_chart(fig_osi, width="stretch")

    st.markdown("---")

    st.subheader("👩‍💻 Responsible AI Human Review Metrics")

    if df_reviews.empty:
        st.info("ℹ️ **No human reviews recorded yet.** Submit reviews in the Troubleshooting Workspace tab to see AI agreement rates and correction distribution.")
    else:
        r_col1, r_col2 = st.columns(2)

        dec_counts = AnalyticsManager.get_decision_counts(df_reviews)
        df_dec = pd.DataFrame(list(dec_counts.items()), columns=["Decision", "Count"])
        fig_dec = px.bar(
            df_dec, x="Decision", y="Count", color="Decision",
            color_discrete_map={"Accept": "#2ecc71", "Edit": "#f39c12", "Reject": "#e74c3c"},
            title="Human Review Decision Breakdown (Accept vs Edit vs Reject)"
        )
        r_col1.plotly_chart(fig_dec, width="stretch")

        conf_counts = AnalyticsManager.get_confidence_counts(df_reviews)
        df_conf = pd.DataFrame(list(conf_counts.items()), columns=["AI Confidence", "Count"])
        fig_conf = px.pie(df_conf, names="AI Confidence", values="Count", title="AI Confidence Distribution on Reviewed Cases", hole=0.4)
        r_col2.plotly_chart(fig_conf, width="stretch")

    st.markdown("---")

    st.subheader("📋 Responsible AI Correction Audit Log")

    if df_reviews.empty:
        st.warning("No human review records present in `data/responsible_ai_log.csv`.")
    else:
        display_cols = [
            col for col in [
                "log_id", "case_id", "timestamp", "category",
                "human_decision", "ai_confidence", "initial_ai_diagnosis",
                "corrected_diagnosis", "reason_for_correction"
            ] if col in df_reviews.columns
        ]
        st.dataframe(df_reviews[display_cols], width="stretch")

    st.markdown("---")
    st.subheader("🔧 Fix Verification Log Table")
    if df_verifications.empty:
        st.info("No manual verification records present in `data/verification_log.csv`.")
    else:
        st.dataframe(df_verifications, width="stretch")

def main():
    st.title("NetSage AI — AI-Assisted Network Troubleshooting")
    st.caption("Packet Tracer & Cisco Lab Network Troubleshooting Helper")
    st.markdown("---")

    tab_new_session, tab_explorer, tab_analytics = st.tabs([
        "🔎 Guided Network Investigation",
        "🎯 Case Explorer",
        "📊 Responsible AI Analytics"
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
            st.error("⚠️ No cases dataset found in `data/cases.csv`. Please verify file existence.")
        else:
            render_case_explorer_workflow(df_cases, review_mgr, verif_mgr)

    with tab_analytics:
        render_analytics_dashboard(df_cases, df_reviews, df_verifications)

if __name__ == "__main__":
    main()
