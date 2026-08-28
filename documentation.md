# NetSage AI — Product Requirement Document (PRD) & Technical System Documentation

---

## 📄 Executive Summary

**NetSage AI** is an enterprise-grade, evidence-driven network troubleshooting system designed for Cisco Packet Tracer and lab networks. It combines a **Fact-Based Prioritized Rule Engine**, an **Evidence-Driven Guided Diagnostic Planner**, **AI-Powered Diagnosis (Google Gemini)**, and a **Responsible AI Human-in-the-Loop Workflow** to systematically diagnose, verify, and document network faults across 9 diagnostic domains.

This document serves as the **Complete Product Requirement Document (PRD)** and **Comprehensive Technical Architecture Reference**, detailing system specifications, file-by-file usage guidelines, operational run instructions, and complete benchmark mapping.

---

## 📌 Product Vision & Problem Statement

### The Problem
Traditional network troubleshooting in lab and enterprise environments relies heavily on manual CLI command execution across multiple devices. Engineers often face:
1. **Inefficient Command Sequences**: Running redundant or generic commands regardless of device role (e.g. running `show interfaces trunk` on a router or re-running `ipconfig` multiple times on a PC).
2. **Premature & False-Positive Diagnoses**: Rule engines that perform naive regex matching on partial CLI output often trigger false positives (e.g., mistaking an unconfigured DHCP APIPA address `169.254.x.x` with gateway `0.0.0.0` for a static default gateway mismatch).
3. **Black-Box AI Recommendations**: Pure LLM diagnostic tools often produce hallucinatory or unverified CLI commands without human oversight.

### The NetSage AI Solution
NetSage AI addresses these challenges through:
- **Evidence-Driven Guided Planning**: Recommending device-appropriate next CLI actions based on symptom context and active inventory.
- **Evidence Normalization & Fact Extraction**: Extracting structured `FactContext` models with provenance tracking (`device`, `command`, `raw_snippet`).
- **Prioritized 5-State Rule Engine**: Evaluating rules into 5 explicit states (`PASS`, `FAIL`, `NEED_MORE_EVIDENCE`, `NOT_APPLICABLE`, `SUPPRESSED`) with dynamic precedence.
- **Human-in-the-Loop Responsible AI Governance**: Requiring explicit engineer review (`ACCEPT`, `EDIT`, `REJECT`) before logging network fixes.

---

## 🎯 Target User Personas

1. **Network Engineers & Operators**: Accelerate root-cause identification in complex multi-device Cisco topologies.
2. **CCNA / CCNP Trainees & Students**: Interactively practice structured, evidence-driven troubleshooting workflows.
3. **Lab Instructors & Evaluators**: Benchmark automated diagnostic rule engines against physical Packet Tracer labs (`C001` - `C035`).

---

## 📐 Functional & Non-Functional Requirements (PRD)

### Functional Requirements (FR)

- **FR-1: Symptom & Inventory Ingestion**: The system shall parse network symptoms, user observations, and active inventory lists (`end_devices`, `switches`, `routers`).
- **FR-2: Device-Aware Command Planning**: The system shall restrict command selection strictly based on device role capabilities (`ipconfig`/`ping` for PCs; `show vlan brief`/`show interfaces trunk` for switches; `show ip route`/`show ip interface brief` for routers).
- **FR-3: Evidence Provenance & Normalization**: The system shall extract normalized facts (`HostFact`, `InterfaceFact`, `VLANFact`, etc.) and maintain explicit provenance (`device`, `command`, `raw_snippet`) for every extracted attribute.
- **FR-4: 5-State Rule Evaluation**: The rule engine shall evaluate checks into explicit states (`PASS`, `FAIL`, `NEED_MORE_EVIDENCE`, `NOT_APPLICABLE`, `SUPPRESSED`). Insufficient evidence must return `NEED_MORE_EVIDENCE` rather than false `PASS`.
- **FR-5: Dynamic Rule Precedence & Suppression**: Higher-priority physical and link-layer faults shall dynamically suppress lower-tier checks (e.g., APIPA address suppresses static Default Gateway mismatch).
- **FR-6: Minimum Evidence Threshold Enforcement**: The engine shall require minimum evidence pairs (e.g. trunk output from both switches, host `ipconfig` + router running-config) before declaring `ISSUE_CONFIRMED`.
- **FR-7: Primary & Secondary Findings Selection**: The engine shall return a single `primary_failure` (highest priority failure) along with a list of `secondary_findings`.
- **FR-8: Human-in-the-Loop Review Governance**: All AI diagnostic outputs must present interactive review options (`ACCEPT`, `EDIT`, `REJECT`) with mandatory notes for edits/rejections.
- **FR-9: Lab Fix Verification Logging**: The system shall allow engineers to record lab verification status (`RESOLVED`, `NOT_RESOLVED`) with mandatory lab notes.
- **FR-10: Benchmark Ground-Truth Isolation**: Benchmark fields (`expected_fault`, `correct_fix`) from `cases.csv` shall NEVER be passed into production diagnostic paths.

### Non-Functional Requirements (NFR)

- **NFR-1: Performance**: Offline deterministic rule evaluation shall complete within 100 milliseconds per case.
- **NFR-2: Robustness**: The `FactExtractor` shall gracefully handle partial, truncated, or malformed CLI command outputs without throwing exceptions.
- **NFR-3: Determinism**: 100% deterministic diagnostic accuracy across all 35 benchmark cases in `data/cases.csv`.
- **NFR-4: Reproducibility**: 100% automated test coverage with 90/90 passing unit and integration tests.

---

## 🏛️ System Architecture & Data Flow

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

## 📁 File-by-File Technical Directory Reference

### 1. `ai/` — Diagnostic Engine & Planning

- **`ai/diagnosis.py`**:
  - `AIDiagnosisEngine`: Main entry point for offline/online LLM diagnosis. Formats prompt, queries Google Gemini (`gemini-2.5-flash` / `gemini-flash-latest`), parses JSON response, and falls back to offline deterministic synthesis when offline.
  - `DiagnosticPlanner`: Device-aware diagnostic planner. Infers active diagnostic domains (`DHCP`, `VLAN`, `IP_GATEWAY`, `ROUTING`, `ACL`, `NAT`, `DNS`, `WIRELESS`, `INTERFACE`), enforces `DEVICE_CAPABILITIES`, tracks `executed_pairs`, and selects next recommended CLI actions.
- **`ai/run_all_cases.py`**: Batch execution script that iterates through all 35 cases in `data/cases.csv`, executes diagnosis, and caches output to `data/ai_responses.csv`.
- **`ai/test_diagnosis.py`**: Unit tests for prompt building, LLM parsing, domain inference, and offline fallback diagnosis.

### 2. `checker/` — Fact Extraction, Rule Engine, & Responsible AI Logging

- **`checker/fact_extractor.py`**:
  - `FactExtractor`: Normalizes raw CLI evidence sections (`--- [Device] command ---`) into structured dataclasses (`HostFact`, `InterfaceFact`, `VLANFact`, `RoutingFact`, `DHCPFact`, `ACLFact`, `NATFact`, `EvidenceMetadata`).
  - `FactProvenance`: Stores source `device`, `command`, and up to 300 characters of `raw_snippet`.
- **`checker/rule_contracts.py`**:
  - `RuleStatus` Enum: Defines explicit states (`PASS`, `FAIL`, `NEED_MORE_EVIDENCE`, `NOT_APPLICABLE`, `SUPPRESSED`).
  - `RuleResult`: Data structure containing `rule_id`, `check_name`, `status`, `priority`, `details`, `evidence_cited`, and `suppression_reason`.
  - Prioritized `BaseRule` implementations across Priority Tiers 1 through 6.
- **`checker/rule_checker.py`**:
  - `RuleChecker`: Instantiates the 12 rule classes, delegates extraction to `FactExtractor`, evaluates rules, sorts failures by priority, and returns `primary_failure`, `secondary_findings`, `pending_evidence_rules`, and `suppressed_rules`.
  - Provides backward-compatible `run_all_checks(evidence)` interface for test suites.
- **`checker/human_review.py`**:
  - `HumanReviewLogger`: Appends engineer review decisions (`ACCEPT`, `EDIT`, `REJECT`) with timestamps and notes to `data/responsible_ai_log.csv`.
- **`checker/test_rule_checker.py`**: Unit test suite for individual rule checks.
- **`checker/test_systematic_rule_audit.py`**: Systematic audit suite verifying 35 positive benchmark cases and 7 negative/false-positive prevention tests.
- **`checker/test_coverage_all_cases.py`**: Coverage validation test ensuring 100% deterministic rule coverage.

### 3. `dashboard/` — Streamlit Web Interface & Analytics

- **`dashboard/app.py`**: Streamlit multi-tab web application (Case Explorer, Guided Assistant, Responsible AI Analytics, Fix Verification Manager).
- **`dashboard/session_manager.py`**: Manages interactive guided investigation sessions, accumulating CLI evidence step-by-step and persisting session history.
- **`dashboard/analytics.py`**: Computes KPI metrics (Acceptance Rate %, Edit Rate %, Rejection Rate %) and generates interactive visualizations.
- **`dashboard/review_manager.py`**: Manages reading and updating engineer review records in `data/responsible_ai_log.csv`.
- **`dashboard/test_diagnostic_planner.py`**: Regression tests for domain planning, APIPA precedence, and device capability enforcement.
- **`dashboard/test_evidence_loader.py`**: Unit tests for loading evidence from CSV and disk.
- **`dashboard/test_session_manager.py`**: Integration tests for guided investigation sessions.

### 4. `data/` — Benchmark Datasets & Persistent Logs

- **`data/cases.csv`**: Benchmark specification containing 35 Cisco Packet Tracer lab cases across 9 categories.
- **`data/ai_responses.csv`**: Cached AI diagnostic outputs generated for benchmark cases.
- **`data/responsible_ai_log.csv`**: Engineer review audit log (`case_id`, `review_status`, `correction_reason`, `rejection_reason`, `timestamp`).
- **`data/verification_log.csv`**: Physical/virtual lab fix verification log (`case_id`, `verification_status`, `verification_notes`, `timestamp`).

### 5. `prompts/` — Prompt Specifications

- **`prompts/diagnose_prompt.md`**: System prompt template for Google Gemini AI with JSON response formatting rules.
- **`prompts/examples.md`**: Few-shot reference examples demonstrating structured JSON output formatting across VLAN, ACL, and Routing cases.

### 6. `scripts/` — Helper & Batch Utilities

- **`scripts/run_batch_diagnosis.py`**: Batch execution runner for evaluating all 35 cases.
- **`scripts/verify_pipeline.py`**: End-to-end pipeline verification test script.
- **`scripts/populate_human_reviews.py`**: Benchmark review populator for synthetic baseline logs.

### 7. `packet_tracer/` — Packet Tracer Lab Topology Files

- **`packet_tracer/cases/`**: Contains original Cisco Packet Tracer topology files (`.pkt`) for physical lab verification.

---

## ⚙️ Prioritized Rule Engine Reference Table

Rules are executed according to a strict 6-tier evidence-aware priority hierarchy:

| Priority | Rule Module | Description | Required Evidence | Suppression Condition |
| :---: | :--- | :--- | :--- | :--- |
| **P1** | `InterfaceStatusRule` | Detects `err-disabled`, `secure-shutdown`, `admin down` | Physical interface status | Overrides all upper-layer rules |
| **P2** | `DHCPRelayRule` | Detects APIPA `169.254.x.x` + missing `ip helper-address` | Host APIPA + Router running-config | Suppressed if host has valid IP |
| **P2** | `DHCPOptionAndPoolRule` | Detects missing gateway exclusions, 100% pool exhaustion, Option 43 | DHCP pool / option output | None |
| **P3** | `NativeVlanMismatchRule` | Detects Native VLAN mismatch on trunk link or CDP log | Trunk output from $\ge 2$ switches or CDP log | Requires trunk output from both link ends |
| **P3** | `VlanDatabaseRule` | Detects missing VLANs in DB, access port errors, trunk pruning, DTP | Switch `show vlan brief` / interface status | Suppressed if interface link is down |
| **P4** | `SubnetMaskRule` | Detects subnet mask mismatch (host `/16` vs interface `/24`) | Host mask + Router interface mask | None |
| **P4** | `DuplicateIPRule` | Detects duplicate host IP assignments or ARP conflicts | $\ge 2$ host ipconfigs or ARP conflict | None |
| **P4** | `GatewayMismatchRule` | Detects static gateway IP mismatch, missing SVI IP, HSRP mismatch | Host `ipconfig` + Router interface status | **Suppressed** when host uses APIPA or gateway `0.0.0.0` |
| **P5** | `MissingRouteRule` | Detects missing default route / gateway of last resort | `show ip route` output | Suppressed if interface is down |
| **P5** | `RoutingProtocolFaultRule` | Detects OSPF timer mismatch, EIGRP AS mismatch, OSPF passive IF | Routing protocol CLI output | None |
| **P6** | `ACLFaultRule` | Detects wildcard errors (`0.0.0.255`), blocked ports, unbound ACLs | `show access-lists` + interface config | None |
| **P6** | `NATAndServicesRule` | Detects missing NAT roles, NAT ACL scope, static NAT, DNS, WPA2 key | NAT / DNS / Wireless CLI output | None |

---

## 🚀 How to Run & Operational Guide

### 1. Environment Setup

```bash
# Clone repository
git clone https://github.com/rishabh855/NextSageAi.git
cd NextSageAi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Optional Gemini API Key
Create a `.env` file in the root directory if you wish to run live Gemini AI diagnosis:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```
*(Note: NetSage AI automatically uses its offline deterministic rule engine if no API key is present.)*

---

### 3. Launching the Streamlit Web Application

To launch the web interface:
```bash
python -m streamlit run dashboard/app.py
```
Open `http://localhost:8501` in your browser.

#### Using Dashboard Features:
- **Case Explorer**: Select any of the 35 benchmark cases from the dropdown, inspect symptoms and CLI evidence, and click **Run Diagnosis**.
- **Guided Assistant**: Start an interactive guided investigation. Click **Recommend Next Command**, copy the command to Packet Tracer, paste output, and click **Submit Evidence**.
- **Responsible AI Analytics**: Review live KPIs (Acceptance %, Edit %, Rejection %) and interactive bar charts.
- **Fix Verification Manager**: Select a case, choose `RESOLVED` or `NOT_RESOLVED`, enter mandatory verification notes, and save.

---

### 4. Running the Automated Test Suite

NetSage AI includes **90 automated unit and integration tests**.

```bash
# Run complete test suite (90 tests)
python -m unittest discover -s . -v

# Run systematic rule audit suite (35 positive benchmark tests + 7 negative tests)
python -m unittest checker/test_systematic_rule_audit.py -v

# Run pipeline verification script
python -m scripts.verify_pipeline
```

---

### 5. Running Batch Diagnosis

To run diagnosis across all 35 cases in `data/cases.csv` and populate `data/ai_responses.csv`:

```bash
python -m scripts.run_batch_diagnosis
```

---

## 📊 Master 35-Case Benchmark Specification

| Case ID | Category | Topology / Problem Summary | Expected Root Cause | Deterministic Rule Module |
| :--- | :--- | :--- | :--- | :--- |
| **C001** | VLAN | Trunk allowed VLAN list mismatch between Switch1 & Switch2 | VLAN 10 disallowed on Switch2 trunk | `VlanDatabaseRule` |
| **C002** | VLAN | Native VLAN mismatch (VLAN 10 vs VLAN 1) on trunk link | Native VLAN mismatch on trunk link | `NativeVlanMismatchRule` |
| **C003** | VLAN | VLAN 30 missing from Switch1 VLAN database | VLAN 30 missing from switch database | `VlanDatabaseRule` |
| **C004** | VLAN | Router Gi0/0 missing dot1q subinterfaces for inter-VLAN routing | Subinterfaces missing on trunk router | `VlanDatabaseRule` |
| **C005** | VLAN | Switchport assigned to default VLAN 1 instead of target VLAN | Switchport assigned to default VLAN 1 | `VlanDatabaseRule` |
| **C006** | VLAN | Both trunk ports set to DTP `dynamic auto` failing negotiation | DTP negotiation failure (dynamic auto) | `VlanDatabaseRule` |
| **C007** | IP_GATEWAY | Host configured with incorrect default gateway `10.0.1.254` | Default gateway mismatch (`10.0.1.254` vs `10.0.1.1`) | `GatewayMismatchRule` |
| **C008** | IP_GATEWAY | Host configured with `/16` subnet mask instead of `/24` | Subnet mask mismatch (`255.255.0.0` vs `/24`) | `SubnetMaskRule` |
| **C009** | IP_GATEWAY | HSRP group mismatch (Group 1 vs Group 2) between routers | HSRP group mismatch (Group 1 vs Group 2) | `GatewayMismatchRule` |
| **C010** | DHCP | Router client interface missing `ip helper-address` for DHCP relay | DHCP Relay Error (missing helper-address) | `DHCPRelayRule` |
| **C011** | DHCP | DHCP pool missing `ip dhcp excluded-address` for gateway IP | DHCP Exclusion missing for gateway IP | `DHCPOptionAndPoolRule` |
| **C012** | DHCP | DHCP pool 100% address capacity exhaustion | DHCP pool capacity exhausted (100%) | `DHCPOptionAndPoolRule` |
| **C013** | DHCP | DHCP pool missing Option 43 for CAPWAP WLC discovery | DHCP Option 43 missing for WLC discovery | `DHCPOptionAndPoolRule` |
| **C014** | ROUTING | Router missing default route / gateway of last resort | Missing default route / gateway of last resort | `MissingRouteRule` |
| **C015** | ROUTING | OSPF hello/dead timer mismatch between neighbors | OSPF hello/dead timer mismatch | `RoutingProtocolFaultRule` |
| **C016** | ROUTING | EIGRP AS number mismatch between routers | EIGRP AS number mismatch | `RoutingProtocolFaultRule` |
| **C017** | ROUTING | OSPF passive-interface configured on active WAN link | OSPF passive-interface on WAN link | `RoutingProtocolFaultRule` |
| **C018** | ROUTING | BGP neighbor remote-as mismatch | BGP remote-as mismatch | `RoutingProtocolFaultRule` |
| **C019** | ACL | ACL wildcard mask `0.0.0.255` blocks entire `/24` subnet | ACL wildcard mask error (`0.0.0.255` vs host) | `ACLFaultRule` |
| **C020** | ACL | ACL denies Telnet port 23 instead of SSH port 22 | ACL blocked wrong port (Telnet 23 vs 22) | `ACLFaultRule` |
| **C021** | ACL | Guest interface missing `ip access-group` binding | Guest interface missing access-group binding | `ACLFaultRule` |
| **C022** | ACL | ACL missing trailing `permit ip any any`, implicit deny drops all | ACL missing trailing permit ip any any | `ACLFaultRule` |
| **C023** | NAT | Interfaces missing `ip nat inside` / `ip nat outside` roles | NAT inside/outside interface roles missing | `NATAndServicesRule` |
| **C024** | NAT | NAT access-list does not permit new LAN subnet | NAT ACL scope missing new LAN subnet | `NATAndServicesRule` |
| **C025** | NAT | Static NAT mapping configured with incorrect internal IP | Static NAT mapping configured with wrong internal IP | `NATAndServicesRule` |
| **C026** | DNS | Primary DNS server IP unreachable from client host | Primary DNS server IP unreachable | `NATAndServicesRule` |
| **C027** | DNS | Host missing primary DNS domain suffix | Host missing primary DNS domain suffix | `NATAndServicesRule` |
| **C028** | DNS | ACL permits TCP port 53 but blocks standard UDP 53 DNS | ACL permits TCP 53 but blocks UDP 53 DNS | `NATAndServicesRule` |
| **C029** | WIRELESS | Laptop WPA2 pre-shared key does not match AP key | WPA2 pre-shared key mismatch | `NATAndServicesRule` |
| **C030** | INTERFACE | Port security violation triggered `err-disabled` port state | Port security violation (err-disabled state) | `InterfaceStatusRule` |
| **C031** | INTERFACE | Duplicate IP address conflict assigned to multiple hosts | Duplicate IP address assigned to multiple hosts | `DuplicateIPRule` |
| **C032** | IP_GATEWAY | Default Gateway SVI interface missing assigned IP address | Gateway SVI interface missing IP address | `GatewayMismatchRule` |
| **C033** | VLAN | Switchport assigned to incorrect access VLAN 20 | Switchport assigned to incorrect access VLAN 20 | `VlanDatabaseRule` |
| **C034** | DHCP | DHCP pool network subnet mismatched with target VLAN | DHCP pool network subnet mismatch | `DHCPOptionAndPoolRule` |
| **C035** | DHCP | DHCP pool specifies invalid default-router / DNS IP | DHCP pool specifies invalid gateway/DNS IP | `DHCPOptionAndPoolRule` |

---

## 📜 License

This project is released under the **MIT License**.
