# NetSage AI — AI-Assisted Cisco Network Troubleshooting Assistant

**NetSage AI** is an enterprise-grade, evidence-driven network troubleshooting assistant designed for Cisco Packet Tracer and enterprise lab networks. It integrates a **Fact-Based Prioritized Rule Engine**, an **Evidence-Driven Guided Diagnostic Planner**, **AI-Powered Diagnosis (Google Gemini)**, and a **Responsible AI Human-in-the-Loop Workflow** to systematically diagnose, verify, and document network faults across 9 diagnostic domains.

---

## 📋 Table of Contents

- [🌟 Key System Capabilities](#-key-system-capabilities)
- [🏛️ Architectural Overview](#️-architectural-overview)
- [🧬 Deep Dive: Evidence Normalization & Fact Layer (`FactExtractor`)](#-deep-dive-evidence-normalization--fact-layer-factextractor)
- [⚙️ Deep Dive: Prioritized Rule Engine (`RuleChecker`)](#️-deep-dive-prioritized-rule-engine-rulechecker)
  - [5 Explicit Rule States](#5-explicit-rule-states)
  - [12 Reusable Deterministic Rule Modules](#12-reusable-deterministic-rule-modules)
  - [Evidence-Aware Rule Precedence & Suppression](#evidence-aware-rule-precedence--suppression)
- [🧠 Deep Dive: Device-Aware Guided Diagnostic Planner (`DiagnosticPlanner`)](#-deep-dive-device-aware-guided-diagnostic-planner-diagnosticplanner)
- [👤 Responsible AI & Human Review Workflow](#-responsible-ai--human-review-workflow)
- [💻 Streamlit Interactive Dashboard Guide](#-streamlit-interactive-dashboard-guide)
- [💾 Data Schemas & Persistence Formats](#-data-schemas--persistence-formats)
- [🐍 Python API Usage & Integration Examples](#-python-api-usage--integration-examples)
- [🚀 Installation & Quickstart Guide](#-installation--quickstart-guide)
- [🧪 Automated Test Suite & Systematic Audit](#-automated-test-suite--systematic-audit)
- [📊 Master 35-Case Benchmark Reference Matrix](#-master-35-case-benchmark-reference-matrix)
- [📜 License](#-license)

---

## 🌟 Key System Capabilities

- 🧠 **Device-Aware Diagnostic Planner**: Dynamically infers diagnostic domains from symptoms and collected CLI evidence, recommending device-appropriate commands (`ipconfig` for PCs, `show vlan brief` for switches, `show ip route` for routers).
- ⚙️ **Fact Extraction & Provenance Tracking**: Normalizes unstructured CLI evidence into structured `FactContext` models while preserving exact evidence provenance (`device`, `command`, `raw_snippet`).
- 🛡️ **Explicit 5-State Rule Contract**: Replaces binary pass/fail checks with explicit states (`PASS`, `FAIL`, `NEED_MORE_EVIDENCE`, `NOT_APPLICABLE`, `SUPPRESSED`), eliminating false positives due to missing CLI evidence.
- 🚦 **Dynamic Priority & Suppression Hierarchy**: Enforces a 6-tier precedence system where physical/link status and APIPA lease failures dynamically suppress lower-layer checks (e.g. host APIPA suppresses default gateway mismatch).
- 📊 **Minimum Evidence Threshold Enforcement**: Requires minimum evidence pairs (e.g., trunk output from both switches, host `ipconfig` + router running-config) before declaring `ISSUE_CONFIRMED`.
- 👤 **Responsible AI Governance**: Enforces mandatory human-in-the-loop review for all AI-assisted diagnostic recommendations (`Accept`, `Edit`, `Reject`), tracking agreement rates and audit logs.
- 🎯 **100% Deterministic Rule Coverage**: Audited and verified against all 35 benchmark cases in `data/cases.csv` with zero reliance on hardcoded case rules.

---

## 🏛️ Architectural Overview

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

## 🧬 Deep Dive: Evidence Normalization & Fact Layer (`FactExtractor`)

Rather than running regex matches against raw string blobs, NetSage AI passes all CLI evidence through **`FactExtractor.extract(evidence: str)`** in [`checker/fact_extractor.py`](file:///c:/Users/Rishabh/NetSage%20AI/checker/fact_extractor.py).

`FactExtractor` parses raw section headers (`--- [Device] command ---`), normalizes commands and parameters, and instantiates structured dataclasses:

### Fact Context Structure

- **`HostFact`**: Contains `ipv4_address`, `subnet_mask`, `default_gateway`, `dns_servers`, `dns_suffix`, `mac_address`, `is_apipa`, `has_valid_ip`, `has_valid_gateway`.
- **`InterfaceFact`**: Contains `interface_name`, `status`, `protocol`, `ip_address`, `subnet_mask`, `mode` (`access` | `trunk`), `access_vlan`, `native_vlan`, `allowed_vlans`, `helper_address`, `nat_role` (`inside` | `outside`).
- **`VLANFact`**: Contains `vlan_database` (Set of VLAN IDs present in database).
- **`RoutingFact`**: Contains `has_default_route`, `gateway_of_last_resort`, `routes`, `ospf_hello`, `ospf_dead`, `ospf_passive_interfaces`, `eigrp_as`, `bgp_as`, `bgp_remote_as`.
- **`DHCPFact`**: Contains `pools`, `excluded_addresses`, `active_bindings`, `utilization_pct`, `option_43_present`.
- **`ACLFact`**: Contains `acl_rules`, `interface_bindings`, `has_implicit_deny`, `has_permit_any_any`.
- **`NATFact`**: Contains `inside_interfaces`, `outside_interfaces`, `nat_acl_id`, `static_mappings`.
- **`EvidenceMetadata`**: Contains `devices_inspected`, `commands_executed`, `has_host_config`, `has_switch_config`, `has_router_config`, `raw_sections_count`.

### Provenance Tracking
Every fact maintains a **`FactProvenance`** object capturing:
- `device`: Device name (e.g. `Router0`, `Switch1`, `PC0`).
- `command`: CLI command executed (e.g. `show ip interface brief`, `ipconfig`).
- `raw_snippet`: Up to 300 characters of raw CLI output section.

---

## ⚙️ Deep Dive: Prioritized Rule Engine (`RuleChecker`)

### 5 Explicit Rule States

1. **`FAIL`**: Minimum evidence threshold met AND explicit configuration fault verified.
2. **`PASS`**: Component inspected and verified operational.
3. **`NEED_MORE_EVIDENCE`**: Potential anomaly detected, but required evidence pair is incomplete (e.g. APIPA host present, but router running-config not yet gathered).
4. **`NOT_APPLICABLE`**: Rule scope does not match collected CLI command evidence (e.g. OSPF timer check when inspecting a switch).
5. **`SUPPRESSED`**: Rule applicability satisfied, but higher-priority fault suppresses lower-tier rules (e.g. APIPA suppresses Gateway Mismatch).

---

### 12 Reusable Deterministic Rule Modules

#### Priority 1 — Physical / Link Status
- **`InterfaceStatusRule`**: Scans for `err-disabled`, `secure-shutdown`, `administratively down`, or physical link state failures.

#### Priority 2 — APIPA / DHCP Failure
- **`DHCPRelayRule`**: Detects host APIPA (`169.254.0.0/16`) combined with missing `ip helper-address` on client-facing router interfaces.
- **`DHCPOptionAndPoolRule`**: Identifies unexcluded gateway IPs, 100% pool exhaustion, scope network mismatches, missing Option 43 (CAPWAP/WLC discovery), and invalid option IPs.

#### Priority 3 — Layer 2 VLAN & Trunking
- **`NativeVlanMismatchRule`**: Identifies Native VLAN mismatches from CDP log entries (`%CDP-4-NATIVE_VLAN_MISMATCH`) or multi-switch trunk comparisons.
- **`VlanDatabaseRule`**: Identifies missing VLANs in switch database, access port misassignments, trunk allowed/pruning list mismatches, missing dot1q subinterfaces, and DTP negotiation failures (`dynamic auto`).

#### Priority 4 — Layer 3 Addressing & Gateway
- **`SubnetMaskRule`**: Identifies subnet mask discrepancies (e.g. host `/16` vs interface `/24`).
- **`DuplicateIPRule`**: Identifies ARP table conflict entries and identical IP assignments across multiple hosts.
- **`GatewayMismatchRule`**: Identifies static gateway IP mismatches, missing SVI IP addresses, and HSRP standby group discrepancies. *(Suppressed when host is APIPA or gateway is 0.0.0.0)*.

#### Priority 5 — Routing Protocols & Routes
- **`MissingRouteRule`**: Identifies missing default routes (`gateway of last resort is not set`) and missing destination subnets in `show ip route`.
- **`RoutingProtocolFaultRule`**: Identifies OSPF hello/dead timer mismatches, EIGRP AS mismatches, OSPF passive interfaces on WAN links, and BGP remote-AS mismatches.

#### Priority 6 — Services & Security
- **`ACLFaultRule`**: Identifies incorrect wildcard masks (`0.0.0.255` vs host `/32`), blocked service ports (Telnet 23 vs SSH 22), missing interface bindings, and missing `permit ip any any` rules.
- **`NATAndServicesRule`**: Identifies missing `ip nat inside/outside` interface roles, NAT ACL scope omissions, invalid static NAT mappings, unreachable DNS servers, missing DNS domain suffixes, blocked UDP 53 DNS queries, and WPA2 security key mismatches.

---

### Evidence-Aware Rule Precedence & Suppression

```text
Priority 1: Physical / Link Status (err-disabled, admin down)
     │
     ▼
Priority 2: APIPA / DHCP Lease Failure (DHCP Relay, DHCP Options, Pool Exhaustion)
     │
     ▼
Priority 3: Layer 2 VLAN & Trunking (Native VLAN Mismatch, Missing VLAN, Pruning, DTP)
     │
     ▼
Priority 4: Layer 3 Addressing & Gateway (Subnet Mask, Duplicate IP, Gateway Mismatch)
     │
     ▼
Priority 5: Routing Protocols (Missing Route, OSPF Timers, EIGRP AS, BGP AS)
     │
     ▼
Priority 6: Services & Security (ACL Rules, NAT Roles/Scope, DNS, Wireless Key)
```

#### Rule Output Structure

```json
{
    "primary_failure": {
        "rule_id": "RULE_DHCP_RELAY",
        "check_name": "DHCP Relay Check",
        "status": "FAIL",
        "priority": 2,
        "details": "DHCP Relay Error: Router interface lacks 'ip helper-address' pointing to remote DHCP server."
    },
    "secondary_findings": [],
    "pending_evidence_rules": [],
    "suppressed_rules": [
        {
            "rule_id": "RULE_GATEWAY_MISMATCH",
            "check_name": "Default Gateway Check",
            "status": "SUPPRESSED",
            "priority": 4,
            "suppression_reason": "Suppressed because host is using APIPA (169.254.0.0/16); gateway 0.0.0.0 is a consequence of DHCP lease failure."
        }
    ]
}
```

---

## 🧠 Deep Dive: Device-Aware Guided Diagnostic Planner (`DiagnosticPlanner`)

The **`DiagnosticPlanner`** class in [`ai/diagnosis.py`](file:///c:/Users/Rishabh/NetSage%20AI/ai/diagnosis.py) governs the step-by-step guided troubleshooting experience.

### 1. Domain Inference
`DiagnosticPlanner.infer_diagnostic_domains(symptom, inventory, evidence)` inspects symptom text and collected CLI outputs to classify active diagnostic domains:
- `DHCP`: Triggered by APIPA (`169.254.x.x`), gateway `0.0.0.0`, or keywords `dhcp`, `ipconfig`.
- `VLAN`: Triggered by keywords `vlan`, `trunk`, `native`, `subinterface`.
- `IP_GATEWAY`: Triggered by keywords `ping`, `gateway`, `subnet`, `hsrp`.
- `ROUTING`: Triggered by keywords `route`, `ospf`, `eigrp`, `bgp`.
- `ACL`: Triggered by keywords `acl`, `access-list`, `blocked`, `firewall`.
- `NAT`: Triggered by keywords `nat`, `pat`, `translation`.
- `DNS`: Triggered by keywords `dns`, `nslookup`, `domain`.
- `WIRELESS`: Triggered by keywords `wifi`, `wpa2`, `wlc`, `ap`.
- `INTERFACE`: Triggered by keywords `interface`, `port`, `duplex`, `err-disabled`.

### 2. Device Capabilities Matrix

`DiagnosticPlanner` enforces strict device role capabilities:

| Device Type | Allowed Commands |
| :--- | :--- |
| **`END_DEVICE`** (PC/Host) | `ipconfig`, `ipconfig /all`, `ping`, `tracert`, `nslookup` |
| **`SWITCH`** | `show interfaces status`, `show vlan brief`, `show interfaces trunk`, `show mac address-table`, `show running-config` |
| **`ROUTER`** | `show ip interface brief`, `show ip route`, `show running-config`, `show access-lists`, `show ip nat translations`, `show standby brief` |
| **`WIRELESS`** (AP/WLC) | `show running-config`, `show ip interface brief` |

### 3. Duplicate Command Prevention & Equivalence
`plan_next_action()` tracks `executed_pairs = {(device.lower(), command.lower())}`. It treats `ipconfig` and `ipconfig /all` as equivalent for executed host checks, preventing re-prompting loops.

---

## 👤 Responsible AI & Human Review Workflow

NetSage AI treats AI diagnoses as **advisory suggestions** requiring mandatory human review before implementation.

```text
[ AI Diagnosis Generated ] ──► [ Human Review Modal ] ──┬──► [ ACCEPT ] ──► Logged to responsible_ai_log.csv
                                                       ├──► [ EDIT ]   ──► Required Correction Notes
                                                       └──► [ REJECT ] ──► Required Rejection Reason
```

### Governance Metrics Tracked
- **AI Agreement Rate**: Percentage of AI recommendations accepted by engineers without modification.
- **Correction Categories**: Human edit rationale classification.
- **Audit Logging**: Timestamped persistence in `data/responsible_ai_log.csv`.

---

## 💻 Streamlit Interactive Dashboard Guide

Launch the dashboard:
```bash
python -m streamlit run dashboard/app.py
```

### Dashboard Tabs

1. 🔍 **Case Explorer**:
   - Filter all 35 lab cases by Category (`VLAN`, `DHCP`, `Routing`, etc.) or Evidence Status (`VERIFIED_LAB`).
   - View topology notes, active inventory, and raw show command evidence.
   - Run AI / Deterministic Diagnosis on demand.

2. 🕵️ **Guided Investigation Assistant**:
   - Interactive multi-step troubleshooting wizard.
   - Select next recommended device and CLI command from `DiagnosticPlanner`.
   - Submit new CLI outputs and observe real-time state updates (`NEED_MORE_EVIDENCE` vs `ISSUE_CONFIRMED`).

3. 📈 **Responsible AI Analytics**:
   - Displays system KPIs: Total Reviews, AI Acceptance Rate %, Edit Rate %, Rejection Rate %.
   - Interactive charts of review decisions across diagnostic domains.

4. ✅ **Fix Verification Manager**:
   - Document Packet Tracer lab fixes applied in physical/virtual environments.
   - Record verification status (`RESOLVED` / `NOT_RESOLVED`) with mandatory engineer verification notes.

---

## 💾 Data Schemas & Persistence Formats

### 1. `data/cases.csv` (Benchmark Specification)
| Field | Type | Description |
| :--- | :--- | :--- |
| `case_id` | String | Unique case ID (e.g. `C001`, `C010`) |
| `category` | String | Diagnostic domain category (`VLAN`, `DHCP`, etc.) |
| `symptom` | String | User-observed network problem description |
| `network_inventory` | JSON String | Dict of devices (`end_devices`, `switches`, `routers`) |
| `show_outputs` | String | Raw CLI command evidence captured from devices |
| `expected_fault` | String | Benchmark ground-truth fault |
| `correct_fix` | String | Benchmark ground-truth remediation |
| `evidence_status` | String | Evidence validation status (`VERIFIED_LAB`) |

### 2. `data/responsible_ai_log.csv` (Engineer Review Log)
| Field | Type | Description |
| :--- | :--- | :--- |
| `case_id` | String | Reference case ID |
| `review_status` | String | Engineer decision (`ACCEPT`, `EDIT`, `REJECT`) |
| `correction_reason` | String | Required notes if decision is `EDIT` |
| `rejection_reason` | String | Required notes if decision is `REJECT` |
| `timestamp` | String | ISO-8601 review timestamp |

### 3. `data/verification_log.csv` (Lab Verification Log)
| Field | Type | Description |
| :--- | :--- | :--- |
| `case_id` | String | Reference case ID |
| `verification_status`| String | Verification status (`RESOLVED`, `NOT_RESOLVED`) |
| `verification_notes` | String | Mandatory engineer lab notes |
| `timestamp` | String | ISO-8601 verification timestamp |

---

## 🐍 Python API Usage & Integration Examples

### Programmatic Fact Extraction & Rule Check

```python
from checker.fact_extractor import FactExtractor
from checker.rule_checker import RuleChecker

evidence = """
--- [PC0] ipconfig ---
IPv4 Address. . . . . . . . . . . : 169.254.10.25
Subnet Mask . . . . . . . . . . . : 255.255.0.0
Default Gateway . . . . . . . . . : 0.0.0.0

--- [Router0] show running-config ---
interface GigabitEthernet0/0
 ip address 192.168.10.1 255.255.255.0
"""

# Extract normalized facts
facts = FactExtractor.extract(evidence)
print("Hosts Extracted:", [h.ipv4_address for h in facts.hosts])
print("Is APIPA:", any(h.is_apipa for h in facts.hosts))

# Run prioritized rule engine
checker = RuleChecker()
res = checker.evaluate_all_rules(evidence)

if res["primary_failure"]:
    print(f"Primary Failure: {res['primary_failure'].check_name}")
    print(f"Details: {res['primary_failure'].details}")

for suppressed in res["suppressed_rules"]:
    print(f"Suppressed Check: {suppressed.check_name} -> {suppressed.suppression_reason}")
```

### Guided Diagnostic Planning

```python
from ai.diagnosis import DiagnosticPlanner

symptom = "PC0 cannot reach remote server"
inventory = {"end_devices": ["PC0"], "switches": ["Switch0"], "routers": ["Router0"]}
executed_pairs = [("PC0", "ipconfig")]
evidence = "--- [PC0] ipconfig ---\nIPv4 Address: 169.254.10.25"

next_dev, next_cmd, reason = DiagnosticPlanner.plan_next_action(
    symptom=symptom,
    inventory=inventory,
    executed_pairs=executed_pairs,
    show_outputs=evidence
)

print(f"Recommended Next Action: {next_dev} -> {next_cmd}")
print(f"Reason: {reason}")
# Output: Router0 -> show ip interface brief
```

---

## 🚀 Installation & Quickstart Guide

### 1. Prerequisites
- Python 3.10 or higher
- `pip` package manager

### 2. Installation
```bash
git clone https://github.com/rishabh855/NextSageAi.git
cd NextSageAi
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)
Create `.env` in project root for live Gemini AI diagnosis:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

---

## 🧪 Automated Test Suite & Systematic Audit

NetSage AI maintains a robust test suite of **90 unit and integration tests**.

```bash
# Run all 90 unit and integration tests
python -m unittest discover -s . -v

# Run systematic 35-case positive and negative rule audit
python -m unittest checker/test_systematic_rule_audit.py -v

# Run end-to-end pipeline verification
python -m scripts.verify_pipeline
```

---

## 📊 Master 35-Case Benchmark Reference Matrix

| Case ID | Category | Topology / Problem Summary | Primary Rule Module | Diagnosis Result |
| :--- | :--- | :--- | :--- | :--- |
| **C001** | VLAN | Trunk allowed VLAN list mismatch between Switch1 & Switch2 | `VlanDatabaseRule` | **ISSUE_CONFIRMED** |
| **C002** | VLAN | Native VLAN mismatch (VLAN 10 vs VLAN 1) on trunk link | `NativeVlanMismatchRule` | **ISSUE_CONFIRMED** |
| **C003** | VLAN | VLAN 30 missing from Switch1 VLAN database | `VlanDatabaseRule` | **ISSUE_CONFIRMED** |
| **C004** | VLAN | Router Gi0/0 missing dot1q subinterfaces for inter-VLAN routing | `VlanDatabaseRule` | **ISSUE_CONFIRMED** |
| **C005** | VLAN | Switchport assigned to default VLAN 1 instead of target VLAN | `VlanDatabaseRule` | **ISSUE_CONFIRMED** |
| **C006** | VLAN | Both trunk ports set to DTP `dynamic auto` failing negotiation | `VlanDatabaseRule` | **ISSUE_CONFIRMED** |
| **C007** | IP_GATEWAY | Host configured with incorrect default gateway `10.0.1.254` | `GatewayMismatchRule` | **ISSUE_CONFIRMED** |
| **C008** | IP_GATEWAY | Host configured with `/16` subnet mask instead of `/24` | `SubnetMaskRule` | **ISSUE_CONFIRMED** |
| **C009** | IP_GATEWAY | HSRP group mismatch (Group 1 vs Group 2) between routers | `GatewayMismatchRule` | **ISSUE_CONFIRMED** |
| **C010** | DHCP | Router client interface missing `ip helper-address` for DHCP relay | `DHCPRelayRule` | **ISSUE_CONFIRMED** |
| **C011** | DHCP | DHCP pool missing `ip dhcp excluded-address` for gateway IP | `DHCPOptionAndPoolRule` | **ISSUE_CONFIRMED** |
| **C012** | DHCP | DHCP pool 100% address capacity exhaustion | `DHCPOptionAndPoolRule` | **ISSUE_CONFIRMED** |
| **C013** | DHCP | DHCP pool missing Option 43 for CAPWAP WLC discovery | `DHCPOptionAndPoolRule` | **ISSUE_CONFIRMED** |
| **C014** | ROUTING | Router missing default route / gateway of last resort | `MissingRouteRule` | **ISSUE_CONFIRMED** |
| **C015** | ROUTING | OSPF hello/dead timer mismatch between neighbors | `RoutingProtocolFaultRule` | **ISSUE_CONFIRMED** |
| **C016** | ROUTING | EIGRP AS number mismatch between routers | `RoutingProtocolFaultRule` | **ISSUE_CONFIRMED** |
| **C017** | ROUTING | OSPF passive-interface configured on active WAN link | `RoutingProtocolFaultRule` | **ISSUE_CONFIRMED** |
| **C018** | ROUTING | BGP neighbor remote-as mismatch | `RoutingProtocolFaultRule` | **ISSUE_CONFIRMED** |
| **C019** | ACL | ACL wildcard mask `0.0.0.255` blocks entire `/24` subnet | `ACLFaultRule` | **ISSUE_CONFIRMED** |
| **C020** | ACL | ACL denies Telnet port 23 instead of SSH port 22 | `ACLFaultRule` | **ISSUE_CONFIRMED** |
| **C021** | ACL | Guest interface missing `ip access-group` binding | `ACLFaultRule` | **ISSUE_CONFIRMED** |
| **C022** | ACL | ACL missing trailing `permit ip any any`, implicit deny drops all | `ACLFaultRule` | **ISSUE_CONFIRMED** |
| **C023** | NAT | Interfaces missing `ip nat inside` / `ip nat outside` roles | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C024** | NAT | NAT access-list does not permit new LAN subnet | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C025** | NAT | Static NAT mapping configured with incorrect internal IP | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C026** | DNS | Primary DNS server IP unreachable from client host | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C027** | DNS | Host missing primary DNS domain suffix | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C028** | DNS | ACL permits TCP port 53 but blocks standard UDP 53 DNS | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C029** | WIRELESS | Laptop WPA2 pre-shared key does not match AP key | `NATAndServicesRule` | **ISSUE_CONFIRMED** |
| **C030** | INTERFACE | Port security violation triggered `err-disabled` port state | `InterfaceStatusRule` | **ISSUE_CONFIRMED** |
| **C031** | INTERFACE | Duplicate IP address conflict assigned to multiple hosts | `DuplicateIPRule` | **ISSUE_CONFIRMED** |
| **C032** | IP_GATEWAY | Default Gateway SVI interface missing assigned IP address | `GatewayMismatchRule` | **ISSUE_CONFIRMED** |
| **C033** | VLAN | Switchport assigned to incorrect access VLAN 20 | `VlanDatabaseRule` | **ISSUE_CONFIRMED** |
| **C034** | DHCP | DHCP pool network subnet mismatched with target VLAN | `DHCPOptionAndPoolRule` | **ISSUE_CONFIRMED** |
| **C035** | DHCP | DHCP pool specifies invalid default-router / DNS IP | `DHCPOptionAndPoolRule` | **ISSUE_CONFIRMED** |

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
