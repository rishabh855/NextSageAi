# NetSage AI — Worked Diagnostic Examples

This file provides reference worked examples demonstrating NetSage AI's structured diagnostic pipeline across Layer 2 VLAN/Trunking, Guest Wi-Fi Isolation, and Layer 3 Routing issues.

---

## Example 1: Layer 2 / VLAN Issue (Trunk Allowed List Pruning)

### Input
- **Case ID**: C001
- **Category**: VLAN
- **Symptom**: PC-A in VLAN 10 cannot ping PC-B in VLAN 10 connected to Switch 2.
- **Topology Note**: PC-A (192.168.10.10/24) -> Switch1 (Fa0/1 access VLAN 10, Gi0/1 trunk) -> Switch2 (Gi0/1 trunk, Fa0/2 access VLAN 10) -> PC-B (192.168.10.20/24).
- **Show Command Evidence**:
  ```text
  --- Switch1 show interfaces trunk ---
  Gi0/1       on           802.1q         trunking      1
  Port        Vlans allowed and active in management domain
  Gi0/1       1,10,20

  --- Switch2 show interfaces trunk ---
  Gi0/1       on           802.1q         trunking      1
  Port        Vlans allowed on trunk
  Gi0/1       1,20,30
  Port        Vlans allowed and active in management domain
  Gi0/1       1,20,30
  ```
- **Rule Checker Result**:
  - `VLAN Trunking Check`: FAIL — VLAN pruning mismatch: VLAN 10 active on Switch1 trunk but not allowed/active on Switch2.

### Structured AI Diagnosis Response
```json
{
  "likely_root_cause": "VLAN 10 traffic is blocked across the trunk link because VLAN 10 is missing from the allowed VLAN list on Switch2 interface GigabitEthernet0/1.",
  "confidence_score": "High",
  "evidence_cited": [
    "Switch1 show interfaces trunk lists VLAN 10 under active VLANs on Gi0/1 (1,10,20)",
    "Switch2 show interfaces trunk lists allowed VLANs as 1,20,30 on Gi0/1, omitting VLAN 10"
  ],
  "recommended_next_command": "show interfaces trunk",
  "suggested_fix": [
    "Access Switch2 command line in global configuration mode",
    "Navigate to interface GigabitEthernet0/1: 'interface GigabitEthernet0/1'",
    "Add VLAN 10 to allowed trunk list: 'switchport trunk allowed vlan add 10'"
  ],
  "osi_layer": "Layer 2",
  "concept": "VLAN Trunking / Pruning"
}
```

---

## Example 2: Wireless & Guest Wi-Fi Isolation (Missing Access List on Subinterface)

### Input
- **Case ID**: C032
- **Category**: Wireless
- **Symptom**: Guest Wi-Fi laptop in VLAN 99 can access internal corporate database server 10.0.0.50 on port 3306.
- **Topology Note**: Guest Laptop -> AP1 -> Switch1 (Gi0/1) -> Router1 subinterface Gi0/0.99 (192.168.99.1/24) -> Corporate Server (10.0.0.50).
- **Show Command Evidence**:
  ```text
  --- Router1 show running-config interface Gi0/0.99 ---
  interface GigabitEthernet0/0.99
   encapsulation dot1Q 99
   ip address 192.168.99.1 255.255.255.0

  --- Router1 show ip access-lists GUEST_ISOLATION ---
  Extended IP access list GUEST_ISOLATION
      10 deny ip 192.168.99.0 0.0.0.255 10.0.0.0 0.255.255.255
      20 permit ip any any
  ```
- **Rule Checker Result**:
  - `Interface Status Check`: PASS

### Structured AI Diagnosis Response
```json
{
  "likely_root_cause": "Subinterface GigabitEthernet0/0.99 lacks an in-bound access group binding, leaving access list GUEST_ISOLATION unapplied and allowing guest Wi-Fi clients to reach corporate internal servers.",
  "confidence_score": "High",
  "evidence_cited": [
    "show running-config interface Gi0/0.99 shows no 'ip access-group GUEST_ISOLATION in' statement",
    "show ip access-lists GUEST_ISOLATION confirms isolation rule exists but is not bound to the subinterface"
  ],
  "recommended_next_command": "show running-config interface Gi0/0.99",
  "suggested_fix": [
    "Enter Router1 global configuration mode: 'interface GigabitEthernet0/0.99'",
    "Bind isolation access list to subinterface: 'ip access-group GUEST_ISOLATION in'"
  ],
  "osi_layer": "Layer 3",
  "concept": "Wireless Guest Isolation ACL"
}
```

---

## Example 3: Layer 3 / Routing Issue (Missing Static Route)

### Input
- **Case ID**: C017
- **Category**: Routing
- **Symptom**: PC-A (192.168.10.10) receives IP address and gateway ping works, but cannot reach Server in VLAN 30 (10.0.30.50).
- **Topology Note**: PC-A -> Router1 -> Router2 -> Server (10.0.30.50). Gateway ping succeeds.
- **Show Command Evidence**:
  ```text
  --- PC-A ping 10.0.30.50 ---
  Request timed out.

  --- Router1 show ip route ---
  Codes: C - connected, S - static, R - RIP, M - mobile, B - BGP
  Gateway of last resort is not set
  C    192.168.10.0/24 is directly connected, GigabitEthernet0/0
  C    172.16.12.0/30 is directly connected, GigabitEthernet0/1

  --- Router1 show access-lists ---
  No access lists configured.
  ```
- **Rule Checker Result**:
  - `Routing Table Check`: FAIL — Missing Route: 'show ip route' has no gateway of last resort and no static/dynamic route for destination network 10.0.30.0/24.

### Structured AI Diagnosis Response
```json
{
  "likely_root_cause": "Router1 lacks a routing table entry (static or dynamic route) for the destination network 10.0.30.0/24, causing packets sent to 10.0.30.50 to be dropped.",
  "confidence_score": "High",
  "evidence_cited": [
    "Router1 show ip route displays 'Gateway of last resort is not set' and contains no route for 10.0.30.0/24",
    "Router1 show access-lists shows 'No access lists configured', ruling out packet filtering"
  ],
  "recommended_next_command": "show ip route",
  "suggested_fix": [
    "Log into Router1 global configuration prompt",
    "Add static route to destination subnet via next-hop router: 'ip route 10.0.30.0 255.255.255.0 172.16.12.2'"
  ],
  "osi_layer": "Layer 3",
  "concept": "Missing Static Route"
}
```
