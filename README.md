# NetSage AI — AI-Assisted Cisco Network Troubleshooting Assistant

**NetSage AI** is an intelligent, evidence-driven network troubleshooting system for Cisco Packet Tracer and enterprise lab networks. It combines a **Fact-based Deterministic Rule Engine**, an **Evidence-Driven Guided Diagnostic Planner**, and **AI-powered Diagnosis (Google Gemini)** with mandatory **Human-in-the-Loop Review** to diagnose, verify, and document network faults across 9 diagnostic domains.

---

## 🌟 Key Features

- 🧠 **Evidence-Driven Guided Diagnostic Planner (`DiagnosticPlanner`)**: Dynamically analyzes symptoms, active network inventory, and previously executed CLI commands to select device-aware next steps without relying on hardcoded command sequences.
- ⚙️ **Fact-Based Deterministic Rule Engine (`FactExtractor` & `RuleChecker`)**: Normalizes raw CLI output sections into structured fact objects with evidence provenance (`device`, `command`, `raw_snippet`) before rule evaluation.
- 🛡️ **Explicit Rule States & Dynamic Precedence**: Evaluates rules into 5 explicit states (`PASS`, `FAIL`, `NEED_MORE_EVIDENCE`, `NOT_APPLICABLE`, `SUPPRESSED`). Higher-priority physical and link-layer faults dynamically suppress lower-layer checks (e.g. host APIPA suppresses default gateway mismatch).
- 📊 **Minimum Evidence Thresholds**: Prevents false-positive confirmations by requiring minimum evidence pairs (e.g., trunk output from both switches, host `ipconfig` + router running-config) before declaring `ISSUE_CONFIRMED`.
- 👤 **Responsible AI & Human-in-the-Loop Logging**: Enforces human verification for all AI-assisted network fixes, logging engineer reviews (`Accept`, `Edit`, `Reject`) and tracking AI agreement rates.
- 💻 **Interactive Streamlit Dashboard**: Provides an intuitive UI for Case Exploration, Guided Multi-step Investigations, Analytics KPIs, and Fix Verification logs.
- 🎯 **35 Benchmark Test Cases**: Fully benchmarked across 35 realistic Cisco lab scenarios spanning 9 network domains.

---

## 🏛️ System Architecture

```text
                  ┌─────────────────────────────────┐
                  │          USER / ENGINEER        │
                  │   (Observes Network Symptom)    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    Guided Diagnostic Planner    │
                  │       (ai/diagnosis.py)         │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │  Evidence Normalization Layer   │
                  │    (checker/fact_extractor.py)  │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │  Fact-Based Prioritized Engine  │
                  │    (checker/rule_checker.py)    │
                  └────────┬───────────────┬────────┘
                           │               │
      Insufficient Evidence│               │Fault Confirmed (FAIL)
                           ▼               ▼
           ┌──────────────────────┐  ┌──────────────────────┐
           │  NEED_MORE_EVIDENCE  │  │   ISSUE_CONFIRMED    │
           │  Recommend Next Cmd  │  │  AI Diagnosis Engine │
           └──────────────────────┘  └──────────┬───────────┘
                                                │
                                                ▼
                                     ┌──────────────────────┐
                                     │ Human Review Logger  │
                                     │ (Accept/Edit/Reject) │
                                     └──────────┬───────────┘
                                                │
                                                ▼
                                     ┌──────────────────────┐
                                     │ Streamlit Dashboard  │
                                     │ Analytics & Verify   │
                                     └──────────────────────┘
```

---

## 📐 Rule Engine Hierarchy & Precedence

Rules are organized into 12 reusable modules across 6 evidence-aware priority tiers:

| Tier | Priority Level | Rule Module | Check Description | Suppression / Applicability Conditions |
| :--- | :---: | :--- | :--- | :--- |
| **Tier 1** | **Priority 1** | `InterfaceStatusRule` | Interface `err-disabled`, `secure-shutdown`, `admin down` | Physical / link status error overrides upper layers |
| **Tier 2** | **Priority 2** | `DHCPRelayRule` | APIPA `169.254.x.x` + missing `ip helper-address` | Requires host APIPA + router configuration evidence |
| **Tier 2** | **Priority 2** | `DHCPOptionAndPoolRule` | Missing gateway exclusions, 100% pool exhaustion, Option 43 | Minimum DHCP lease or pool evidence required |
| **Tier 3** | **Priority 3** | `NativeVlanMismatchRule` | CDP Native VLAN mismatch log or trunk mismatch | Requires trunk evidence from $\ge 2$ switches or CDP log |
| **Tier 3** | **Priority 3** | `VlanDatabaseRule` | Missing VLAN in database, access port misassignment, DTP | Requires switch `show vlan brief` / interface status |
| **Tier 4** | **Priority 4** | `SubnetMaskRule` | Subnet mask mismatch (e.g. host `/16` vs interface `/24`) | Compares host mask against router interface mask |
| **Tier 4** | **Priority 4** | `DuplicateIPRule` | Duplicate host IP assignments or ARP table conflicts | Requires evidence from $\ge 2$ hosts or ARP conflict |
| **Tier 4** | **Priority 4** | `GatewayMismatchRule` | Static default gateway IP mismatches, HSRP group errors | **Suppressed** when host uses APIPA or gateway `0.0.0.0` |
| **Tier 5** | **Priority 5** | `MissingRouteRule` | Missing default route / gateway of last resort | Requires `show ip route` evidence |
| **Tier 5** | **Priority 5** | `RoutingProtocolFaultRule` | OSPF timer mismatch, EIGRP AS mismatch, OSPF passive IF | Requires routing protocol evidence |
| **Tier 6** | **Priority 6** | `ACLFaultRule` | Wildcard mask errors (`0.0.0.255`), blocked ports, unbound ACLs | Requires access-list and interface binding output |
| **Tier 6** | **Priority 6** | `NATAndServicesRule` | Missing `ip nat inside/outside`, NAT ACL scope, DNS, WPA2 key | Requires NAT / DNS / Wireless service output |

---

## 📁 Repository Structure

```text
NetSage-AI/
├── ai/
│   ├── diagnosis.py             # AIDiagnosisEngine & DiagnosticPlanner (Device-aware next steps)
│   ├── run_all_cases.py         # Batch evaluation script for cases.csv
│   └── test_diagnosis.py        # Diagnosis engine unit tests
├── checker/
│   ├── fact_extractor.py        # FactExtractor & FactContext normalization layer
│   ├── rule_contracts.py        # Prioritized Rule classes & explicit RuleStatus Enum
│   ├── rule_checker.py          # RuleChecker engine implementation
│   ├── human_review.py          # Responsible AI human review logging module
│   ├── test_rule_checker.py     # Rule engine unit test suite
│   └── test_systematic_rule_audit.py # Audit suite for 35 positive cases & 7 negative tests
├── dashboard/
│   ├── app.py                   # Streamlit web application (Case Explorer, Assistant, Analytics)
│   ├── session_manager.py       # Guided investigation state & evidence accumulator
│   ├── analytics.py             # KPI metrics aggregator & visualization provider
│   ├── review_manager.py        # Human review manager for Accept/Edit/Reject
│   ├── test_diagnostic_planner.py# Domain planning & APIPA precedence tests
│   ├── test_evidence_loader.py  # Evidence parsing unit tests
│   └── test_session_manager.py  # Interactive session unit tests
├── data/
│   ├── cases.csv                # Benchmark specification (35 test cases across 9 domains)
│   ├── ai_responses.csv         # Cached AI diagnostic outputs
│   ├── responsible_ai_log.csv   # Engineer review log (Accept, Edit, Reject)
│   └── verification_log.csv    # Fixed lab verification records
├── packet_tracer/
│   └── cases/                   # Cisco Packet Tracer lab files (.pkt)
├── prompts/
│   ├── diagnose_prompt.md       # Structured Gemini system prompt
│   └── examples.md              # Few-shot diagnostic examples
├── scripts/
│   ├── run_batch_diagnosis.py   # Batch execution runner
│   ├── verify_pipeline.py       # End-to-end pipeline verification
│   └── populate_human_reviews.py# Benchmark review generator
├── requirements.txt             # Project dependencies
└── README.md                    # System documentation
```

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.10+
- `pip` package manager

### 2. Install Dependencies
```bash
git clone https://github.com/rishabh855/NextSageAi.git
cd NextSageAi
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional for Live Gemini AI)
Create a `.env` file in the root directory if you wish to run live Gemini AI diagnosis:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```
*(Note: NetSage AI automatically falls back to an offline deterministic diagnosis engine if no API key is set.)*

---

## 🧪 Testing & Verification

NetSage AI includes a comprehensive test suite of **90 automated unit and integration tests**.

### Run Complete Test Suite
```bash
python -m unittest discover -s . -v
```

### Run Systematic Rule Audit Suite (35 Benchmark Cases & Negative Tests)
```bash
python -m unittest checker/test_systematic_rule_audit.py -v
```

### Run End-to-End Pipeline Verification
```bash
python -m scripts.verify_pipeline
```

---

## 💻 Running the Streamlit Dashboard

To launch the web interface:

```bash
python -m streamlit run dashboard/app.py
```

Open your browser at `http://localhost:8501` to access:
1. 🔍 **Case Explorer**: Browse all 35 lab cases, view CLI evidence, and trigger AI/deterministic diagnosis.
2. 🕵️ **Guided Investigation Assistant**: Interactively troubleshoot lab issues step-by-step with real-time command recommendations.
3. 📈 **Responsible AI Analytics**: View agreement metrics, review distributions (Accept/Edit/Reject), and confidence breakdowns.
4. ✅ **Fix Verification Manager**: Log manual Packet Tracer lab verification steps and track resolution status.

---

## 📊 Benchmark Dataset (35 Cases Across 9 Domains)

NetSage AI is benchmarked against 35 standard Cisco Packet Tracer lab cases:

- 🟢 **VLAN & Trunking (6 Cases)**: `C001`, `C002`, `C003`, `C004`, `C005`, `C006`, `C033`
- 🔵 **IP & Gateway (4 Cases)**: `C007`, `C008`, `C009`, `C032`
- 🟡 **DHCP (7 Cases)**: `C010`, `C011`, `C012`, `C013`, `C034`, `C035`
- 🔴 **Routing Protocols (5 Cases)**: `C014`, `C015`, `C016`, `C017`, `C018`
- 🟣 **Access Control Lists (4 Cases)**: `C019`, `C020`, `C021`, `C022`
- 🟠 **NAT & Port Forwarding (3 Cases)**: `C023`, `C024`, `C025`
- 🟤 **DNS Services (3 Cases)**: `C026`, `C027`, `C028`
- ⚪ **Wireless LAN (1 Case)**: `C029`
- 🔴 **Physical / Interface Security (2 Cases)**: `C030`, `C031`

---

## 📜 License

This project is released under the **MIT License**.
