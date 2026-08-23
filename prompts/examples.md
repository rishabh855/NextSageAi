# NetSage AI — Worked Diagnostic Examples

This file provides 3 worked reference examples demonstrating NetSage AI's structured diagnostic pipeline across Layer 2, Layer 3, and Layer 4-7 issues.

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
  "root_cause": "VLAN 10 traffic is blocked across the trunk link because VLAN 10 is missing from the allowed VLAN list on Switch2 interface GigabitEthernet0/1.",
  "confidence": "High",
  "evidence": [
    "Switch1 show interfaces trunk lists VLAN 10 under active VLANs on Gi0/1 (1,10,20)",
    "Switch2 show interfaces trunk lists allowed VLANs as 1,20,30 on Gi0/1, omitting VLAN 10"
  ],
  "next_command": "show interfaces trunk",
  "fix_steps": [
    "Access Switch2 command line in global configuration mode",
    "Navigate to interface GigabitEthernet0/1: 'interface GigabitEthernet0/1'",
    "Add VLAN 10 to allowed trunk list: 'switchport trunk allowed vlan add 10'"
  ],
  "osi_layer": "Layer 2",
  "concept": "VLAN Trunking / Pruning"
}
```

---

## Example 2: Layer 3 / Routing Issue (Missing Static Route)

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
  "root_cause": "Router1 lacks a routing table entry (static or dynamic route) for the destination network 10.0.30.0/24, causing packets sent to 10.0.30.50 to be dropped.",
  "confidence": "High",
  "evidence": [
    "Router1 show ip route displays 'Gateway of last resort is not set' and contains no route for 10.0.30.0/24",
    "Router1 show access-lists shows 'No access lists configured', ruling out packet filtering"
  ],
  "next_command": "show ip route",
  "fix_steps": [
    "Log into Router1 global configuration prompt",
    "Add static route to destination subnet via next-hop router: 'ip route 10.0.30.0 255.255.255.0 172.16.12.2'"
  ],
  "osi_layer": "Layer 3",
  "concept": "Missing Static Route"
}
```

---

## Example 3: Layer 4–7 / Security Issue (ACL Implicit Deny)

### Input
- **Case ID**: C022
- **Category**: ACL
- **Symptom**: PC-A (192.168.10.5) cannot access Web Server (10.0.0.100) on port 80.
- **Topology Note**: Router1 interface Gi0/1 outbound ACL named BLOCK_WEB.
- **Show Command Evidence**:
  ```text
  --- Router1 show ip access-lists BLOCK_WEB ---
  Extended IP access list BLOCK_WEB
      10 deny tcp host 192.168.10.5 host 10.0.0.100 eq 80
      (implicit deny ip any any at end of list)

  --- Router1 show ip interface Gi0/1 ---
  GigabitEthernet0/1 is up, line protocol is up
    Outbound access list is BLOCK_WEB
  ```
- **Rule Checker Result**:
  - `Interface Status Check`: PASS

### Structured AI Diagnosis Response
```json
{
  "root_cause": "Access list BLOCK_WEB contains a deny rule for port 80 traffic from host 192.168.10.5 to web server 10.0.0.100, and lacks an explicit permit statement, causing all other traffic to hit the implicit deny at the end of the ACL.",
  "confidence": "High",
  "evidence": [
    "show ip access-lists BLOCK_WEB contains rule '10 deny tcp host 192.168.10.5 host 10.0.0.100 eq 80'",
    "show ip interface Gi0/1 confirms outbound access list BLOCK_WEB is active"
  ],
  "next_command": "show access-lists BLOCK_WEB",
  "fix_steps": [
    "Enter Router1 global configuration mode: 'ip access-list extended BLOCK_WEB'",
    "If Web access should be permitted for other hosts/ports, add explicit permit rule: '20 permit ip any any'"
  ],
  "osi_layer": "Layer 4",
  "concept": "ACL Implicit Deny"
}
```
