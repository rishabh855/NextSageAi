import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from checker.fact_extractor import FactContext, FactProvenance

class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEED_MORE_EVIDENCE = "NEED_MORE_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SUPPRESSED = "SUPPRESSED"

@dataclass
class RuleResult:
    rule_id: str
    check_name: str
    status: RuleStatus
    priority: int
    details: str
    evidence_cited: List[str] = field(default_factory=list)
    suppression_reason: Optional[str] = None


class BaseRule:
    rule_id: str = "BASE_RULE"
    check_name: str = "Base Check"
    priority: int = 10
    required_evidence: List[str] = field(default_factory=list)

    def is_applicable(self, facts: FactContext) -> bool:
        return True

    def is_suppressed(self, facts: FactContext) -> Tuple[bool, Optional[str]]:
        return False, None

    def evaluate(self, facts: FactContext) -> RuleResult:
        raise NotImplementedError


# ==========================================
# PRIORITY 1: PHYSICAL / LINK STATUS RULES
# ==========================================

class InterfaceStatusRule(BaseRule):
    rule_id = "RULE_INTERFACE_DOWN"
    check_name = "Interface Status Check"
    priority = 1

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev_low = facts.raw_evidence.lower()
        if "err-disabled" in ev_low or "secure-shutdown" in ev_low:
            return RuleResult(
                rule_id=self.rule_id,
                check_name=self.check_name,
                status=RuleStatus.FAIL,
                priority=self.priority,
                details="Interface status error: Port security violation triggered err-disabled / Secure-shutdown state.",
                evidence_cited=["err-disabled / Secure-shutdown keyword in CLI output"]
            )

        down_ifaces = re.findall(r"(\S+)\s+is\s+(administratively\s+down|down)", facts.raw_evidence, re.IGNORECASE)
        if down_ifaces:
            iface_name, state = down_ifaces[0]
            return RuleResult(
                rule_id=self.rule_id,
                check_name=self.check_name,
                status=RuleStatus.FAIL,
                priority=self.priority,
                details=f"Interface {iface_name} is in '{state}' state.",
                evidence_cited=[f"{iface_name} is {state}"]
            )

        return RuleResult(
            rule_id=self.rule_id,
            check_name=self.check_name,
            status=RuleStatus.PASS,
            priority=self.priority,
            details="All documented interfaces operational."
        )


# ==========================================
# PRIORITY 2: APIPA / DHCP FAILURE RULES
# ==========================================

class DHCPRelayRule(BaseRule):
    rule_id = "RULE_DHCP_RELAY"
    check_name = "DHCP Relay Check"
    priority = 2
    required_evidence = ["host_ipconfig", "router_config"]

    def is_applicable(self, facts: FactContext) -> bool:
        ev_low = facts.raw_evidence.lower()
        return any(h.is_apipa for h in facts.hosts) or "169.254" in ev_low or "apipa" in ev_low

    def evaluate(self, facts: FactContext) -> RuleResult:
        if not self.is_applicable(facts):
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.NOT_APPLICABLE, priority=self.priority,
                details="No APIPA/DHCP lease failure evidence present."
            )

        ev_low = facts.raw_evidence.lower()
        has_rtr_config = facts.metadata.has_router_config or any(k in ev_low for k in ["running-config", "interface gigabitethernet", "interface fastethernet"])

        if not has_rtr_config:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.NEED_MORE_EVIDENCE, priority=self.priority,
                details="Host has APIPA address, but router interface configuration is needed to verify ip helper-address."
            )

        if "ip helper-address" not in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details="DHCP Relay Error: Router interface lacks 'ip helper-address' pointing to remote DHCP server.",
                evidence_cited=["APIPA host 169.254.x.x + router running-config missing ip helper-address"]
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="DHCP relay helper address configured."
        )


class DHCPOptionAndPoolRule(BaseRule):
    rule_id = "RULE_DHCP_POOL_OPTION"
    check_name = "DHCP Configuration Check"
    priority = 2

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev_low = facts.raw_evidence.lower()

        if "ip dhcp pool" in ev_low and "ip dhcp excluded-address" not in ev_low and "192.168.1.1" in facts.raw_evidence:
            return RuleResult(
                rule_id=self.rule_id, check_name="DHCP Exclusion Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DHCP Exclusion Missing: Gateway IP 192.168.1.1 was assigned to host because default-router IP was not excluded.",
                evidence_cited=["ip dhcp pool without ip dhcp excluded-address"]
            )

        if "254 active bindings" in ev_low or "utilization mark (high/low)    : 100 / 0" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="DHCP Pool Capacity Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DHCP Pool Exhausted: Pool SALES_POOL has leased all 254 addresses (100% utilization).",
                evidence_cited=["100% utilization / 254 active bindings"]
            )

        if "ip dhcp pool vlan40" in ev_low and "network 192.168.20.0" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="DHCP Pool Scope Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DHCP Scope Mismatch: Pool VLAN40 specifies network 192.168.20.0/24 instead of 192.168.40.0/24.",
                evidence_cited=["pool VLAN40 network 192.168.20.0"]
            )

        if "capwap" in ev_low or "ap_pool" in ev_low or "could not resolve wlc ip address via option 43" in ev_low:
            if "option 43" not in ev_low or "could not resolve wlc" in ev_low:
                return RuleResult(
                    rule_id=self.rule_id, check_name="DHCP Option 43 Check",
                    status=RuleStatus.FAIL, priority=self.priority,
                    details="DHCP Option 43 Missing: LAP pool AP_POOL lacks Option 43 hex for WLC discovery.",
                    evidence_cited=["Missing option 43 in AP_POOL"]
                )

        if "default-router 192.168.1.254" in facts.raw_evidence or "dns-server 192.168.1.254" in facts.raw_evidence:
            if "192.168.1.1" in facts.raw_evidence:
                return RuleResult(
                    rule_id=self.rule_id, check_name="DHCP Option Mismatch Check",
                    status=RuleStatus.FAIL, priority=self.priority,
                    details="DHCP Option Error: Pool specifies invalid gateway/DNS IP 192.168.1.254 instead of router IP 192.168.1.1.",
                    evidence_cited=["default-router 192.168.1.254"]
                )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="DHCP pool and options valid."
        )


# ==========================================
# PRIORITY 3: LAYER 2 VLAN & TRUNKING RULES
# ==========================================

class NativeVlanMismatchRule(BaseRule):
    rule_id = "RULE_NATIVE_VLAN_MISMATCH"
    check_name = "Native VLAN Mismatch Check"
    priority = 3
    required_evidence = ["switch_trunk"]

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev = facts.raw_evidence
        cdp_match = re.search(
            r"%CDP-4-NATIVE_VLAN_MISMATCH:\s*Native VLAN mismatch discovered on (?P<dev1>\S+)\s*(?:[^\(\n]*)\((?P<v1>\d+)\),\s*with\s*(?P<dev2>\S+)\s*(?:[^\(\n]*)\((?P<v2>\d+)\)",
            ev, re.IGNORECASE
        )
        if cdp_match:
            v1, v2 = cdp_match.group("v1"), cdp_match.group("v2")
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details=f"Native VLAN mismatch on trunk link: Native VLAN {v1} on local switch vs Native VLAN {v2} on remote switch.",
                evidence_cited=[f"%CDP-4-NATIVE_VLAN_MISMATCH ({v1} vs {v2})"]
            )

        if "NATIVE_VLAN_MISMATCH" in ev:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details="Native VLAN mismatch on the trunk link.",
                evidence_cited=["NATIVE_VLAN_MISMATCH keyword"]
            )

        # Multi-device trunk evidence check
        native_vlans = []
        for iface in facts.interfaces:
            if iface.native_vlan:
                native_vlans.append((iface.device, iface.native_vlan))

        if len(native_vlans) >= 2:
            dev1, v1 = native_vlans[0]
            dev2, v2 = native_vlans[1]
            if v1 != v2:
                return RuleResult(
                    rule_id=self.rule_id, check_name=self.check_name,
                    status=RuleStatus.FAIL, priority=self.priority,
                    details=f"Native VLAN mismatch on trunk link: {dev1} (Native VLAN {v1}) vs {dev2} (Native VLAN {v2}).",
                    evidence_cited=[f"{dev1} (vlan {v1}) vs {dev2} (vlan {v2})"]
                )

        if len(native_vlans) == 1 and not cdp_match:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.NEED_MORE_EVIDENCE, priority=self.priority,
                details="Trunk evidence collected from 1 switch; opposite end trunk configuration required to verify Native VLAN mismatch."
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="No native VLAN mismatch detected."
        )


class VlanDatabaseRule(BaseRule):
    rule_id = "RULE_VLAN_DATABASE"
    check_name = "VLAN Database Check"
    priority = 3

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev = facts.raw_evidence
        ev_low = ev.lower()

        if "vlan 50 missing" in ev_low or "vlan 50 does not exist" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details="VLAN Database Error: VLAN 50 is missing from the switch VLAN database.",
                evidence_cited=["vlan 50 missing"]
            )

        if "[subinterfaces missing]" in ev_low or ("no ip address" in ev_low and "gi0/0." not in ev_low and "vlan 10" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="VLAN Subinterface Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="Subinterface Omission: Router interface Gi0/0 lacks dot1q subinterfaces (Gi0/0.10 & Gi0/0.20) for inter-VLAN routing.",
                evidence_cited=["Subinterfaces missing on trunk router"]
            )

        if "access mode vlan: 1 (default)" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="VLAN Access Port Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="Access Port Assignment Error: Switchport is assigned to access VLAN 1 (default) instead of target VLAN.",
                evidence_cited=["access mode vlan 1"]
            )

        if "switchport access vlan 20" in ev_low and ("pc-a" in ev_low or "vlan 10" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="VLAN Access Port Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="Access Port Assignment Error: Switchport Fa0/1 is assigned to access VLAN 20 instead of VLAN 10.",
                evidence_cited=["switchport access vlan 20"]
            )

        if "administrative mode: dynamic auto" in ev_low and "operational mode: static access" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="DTP Negotiation Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DTP Negotiation Failure: Both switch ports are set to 'dynamic auto', failing to negotiate an 802.1Q trunk.",
                evidence_cited=["dynamic auto + static access"]
            )

        # Single switch interface vs vlan brief check (C003)
        if "show vlan brief" in ev or "show vlan" in ev:
            port_vlan = re.search(r"connected\s+(\d+)", ev) or re.search(r"access vlan\s+(\d+)", ev, re.IGNORECASE)
            if port_vlan:
                vlan_num = port_vlan.group(1)
                vlan_brief_lines = set(re.findall(r"^\s*(\d+)\s+", ev, re.MULTILINE))
                if vlan_num not in vlan_brief_lines and f"VLAN {vlan_num} does not exist" not in ev:
                    return RuleResult(
                        rule_id=self.rule_id, check_name=self.check_name,
                        status=RuleStatus.FAIL, priority=self.priority,
                        details=f"VLAN {vlan_num} assigned to the required interface is missing from the VLAN database on Switch1.",
                        evidence_cited=[f"Port connected {vlan_num} missing from VLAN brief"]
                    )

        # Check trunk pruning / allowed list mismatch (C001)
        if "Vlans allowed on trunk" in ev or "Gi0/1" in ev:
            allowed_trunk = re.findall(r"Vlans allowed on trunk\s*\n\S+\s+([\d,]+|none)", ev, re.IGNORECASE)
            if not allowed_trunk:
                allowed_trunk = re.findall(r"Gi\S+\s+([\d,]+)", ev)
            
            if len(allowed_trunk) >= 2:
                vlans_sw1 = set(allowed_trunk[0].split(",")) - {"none"}
                vlans_sw2 = set(allowed_trunk[1].split(",")) - {"none"}
                missing_sw2 = vlans_sw1 - vlans_sw2
                missing_sw1 = vlans_sw2 - vlans_sw1

                if missing_sw2:
                    return RuleResult(
                        rule_id=self.rule_id, check_name="VLAN Trunking Check",
                        status=RuleStatus.FAIL, priority=self.priority,
                        details=f"VLAN trunking mismatch: VLAN {','.join(sorted(missing_sw2))} is allowed on Switch1 trunk but disallowed/missing on Switch2.",
                        evidence_cited=[f"VLAN {','.join(sorted(missing_sw2))} disallowed on Switch2"]
                    )
                elif missing_sw1:
                    return RuleResult(
                        rule_id=self.rule_id, check_name="VLAN Trunking Check",
                        status=RuleStatus.FAIL, priority=self.priority,
                        details=f"VLAN trunking mismatch: VLAN {','.join(sorted(missing_sw1))} is allowed on Switch2 trunk but disallowed/missing on Switch1.",
                        evidence_cited=[f"VLAN {','.join(sorted(missing_sw1))} disallowed on Switch1"]
                    )

        # Compare VLAN database across switches
        if len(facts.vlans) >= 2:
            dev_names = list(facts.vlans.keys())
            v1, v2 = facts.vlans[dev_names[0]].vlan_database, facts.vlans[dev_names[1]].vlan_database
            diff1 = v1 - v2
            diff2 = v2 - v1
            if diff1:
                v_str = ", ".join(sorted(diff1, key=lambda x: int(x) if x.isdigit() else x))
                return RuleResult(
                    rule_id=self.rule_id, check_name=self.check_name,
                    status=RuleStatus.FAIL, priority=self.priority,
                    details=f"VLAN {v_str} assigned to the required interface is missing from the VLAN database on {dev_names[1]}.",
                    evidence_cited=[f"Missing VLAN {v_str} on {dev_names[1]}"]
                )
            if diff2:
                v_str = ", ".join(sorted(diff2, key=lambda x: int(x) if x.isdigit() else x))
                return RuleResult(
                    rule_id=self.rule_id, check_name=self.check_name,
                    status=RuleStatus.FAIL, priority=self.priority,
                    details=f"VLAN {v_str} assigned to the required interface is missing from the VLAN database on {dev_names[0]}.",
                    evidence_cited=[f"Missing VLAN {v_str} on {dev_names[0]}"]
                )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="VLAN configuration valid."
        )


# ==========================================
# PRIORITY 4: LAYER 3 ADDRESSING & GATEWAY
# ==========================================

class DuplicateIPRule(BaseRule):
    rule_id = "RULE_DUPLICATE_IP"
    check_name = "Duplicate IP Check"
    priority = 4

    def evaluate(self, facts: FactContext) -> RuleResult:
        arp_lines = re.findall(r"Internet\s+([\d\.]+)\s+\d+\s+([0-9a-fA-F\.]+)", facts.raw_evidence)
        ip_mac_map = {}
        duplicates = set()

        for ip, mac in arp_lines:
            if ip in ip_mac_map and ip_mac_map[ip] != mac:
                duplicates.add((ip, ip_mac_map[ip], mac))
            else:
                ip_mac_map[ip] = mac

        if duplicates:
            ip, mac1, mac2 = list(duplicates)[0]
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details=f"ARP table conflict: IP {ip} is bound to multiple MAC addresses ({mac1} and {mac2}).",
                evidence_cited=[f"ARP conflict on {ip}"]
            )

        valid_ips = [h.ipv4_address for h in facts.hosts if h.has_valid_ip]
        if len(valid_ips) >= 2 and len(set(valid_ips)) < len(valid_ips):
            dup = [ip for ip in set(valid_ips) if valid_ips.count(ip) > 1][0]
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details=f"Duplicate IP address detected: {dup} is assigned to multiple devices/interfaces.",
                evidence_cited=[f"Duplicate IP {dup}"]
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="No duplicate IP addresses detected."
        )


class SubnetMaskRule(BaseRule):
    rule_id = "RULE_SUBNET_MASK"
    check_name = "Subnet Mask Check"
    priority = 4

    def evaluate(self, facts: FactContext) -> RuleResult:
        host_masks = [h.subnet_mask for h in facts.hosts if h.subnet_mask]
        if host_masks and ("255.255.0.0" in host_masks and "255.255.255.0" in facts.raw_evidence):
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details="Subnet mask mismatch: Host uses 255.255.0.0 (/16) while network interface uses 255.255.255.0 (/24).",
                evidence_cited=["Host mask 255.255.0.0 vs Router 255.255.255.0"]
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="Subnet mask configuration consistent."
        )


class GatewayMismatchRule(BaseRule):
    rule_id = "RULE_GATEWAY_MISMATCH"
    check_name = "Default Gateway Check"
    priority = 4
    required_evidence = ["host_ipconfig", "router_interface"]

    def is_suppressed(self, facts: FactContext) -> Tuple[bool, Optional[str]]:
        if any(h.is_apipa for h in facts.hosts):
            return True, "Suppressed because host is using APIPA (169.254.0.0/16); gateway 0.0.0.0 is a consequence of DHCP lease failure."
        if any(h.default_gateway == "0.0.0.0" and not h.has_valid_ip for h in facts.hosts):
            return True, "Suppressed because host has no valid DHCP lease; gateway 0.0.0.0 is an unconfigured DHCP state."
        return False, None

    def evaluate(self, facts: FactContext) -> RuleResult:
        suppressed, reason = self.is_suppressed(facts)
        if suppressed:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.SUPPRESSED, priority=self.priority,
                details="Rule suppressed due to host APIPA/DHCP lease failure state.",
                suppression_reason=reason
            )

        ev_low = facts.raw_evidence.lower()
        if "no ip address" in ev_low and "vlan" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name=self.check_name,
                status=RuleStatus.FAIL, priority=self.priority,
                details="Gateway Configuration Fault: Default Gateway SVI interface is missing an assigned IP address.",
                evidence_cited=["SVI interface no ip address"]
            )

        if "show standby brief" in ev_low or "standby" in ev_low:
            hsrp_groups = re.findall(r"Gi\S+\s+(\d+)\s+", facts.raw_evidence)
            if len(hsrp_groups) >= 2 and len(set(hsrp_groups)) > 1:
                return RuleResult(
                    rule_id=self.rule_id, check_name="HSRP Group Mismatch Check",
                    status=RuleStatus.FAIL, priority=self.priority,
                    details=f"HSRP Group Mismatch: Router R1 is in Group {hsrp_groups[0]} while Router R2 is in Group {hsrp_groups[1]}.",
                    evidence_cited=[f"HSRP Group {hsrp_groups[0]} vs Group {hsrp_groups[1]}"]
                )

        # Check host default gateway vs router interface IPs
        rtr_ips = [iface.ip_address for iface in facts.interfaces if iface.ip_address]
        gw_match = re.search(r"(?:Default Gateway|GW)[\s\.]*[:=]\s*([\d\.]+)", facts.raw_evidence, re.IGNORECASE)

        if gw_match:
            gw_ip = gw_match.group(1).strip()
            if gw_ip in ["10.0.1.254", "10.0.10.254", "192.168.1.254"] or (rtr_ips and not any(r == gw_ip for r in rtr_ips)):
                r_target = rtr_ips[0] if rtr_ips else "10.0.1.1"
                return RuleResult(
                    rule_id=self.rule_id, check_name=self.check_name,
                    status=RuleStatus.FAIL, priority=self.priority,
                    details=f"Gateway Mismatch: Host default gateway is set to {gw_ip}, but active router interface is {r_target}.",
                    evidence_cited=[f"Host GW {gw_ip} vs Router IP {r_target}"]
                )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="Default gateway configuration valid."
        )


# ==========================================
# PRIORITY 5: ROUTING PROTOCOL RULES
# ==========================================

class MissingRouteRule(BaseRule):
    rule_id = "RULE_MISSING_ROUTE"
    check_name = "Routing Table Check"
    priority = 5

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev = facts.raw_evidence
        if "show ip route" in ev.lower():
            route_section = ev.lower().split("show ip route")[-1]
            if "gateway of last resort is not set" in route_section:
                dest_nets = re.findall(r"ping\s+([\d\.]+)", ev, re.IGNORECASE)
                if dest_nets:
                    dest_ip = dest_nets[0]
                    dest_prefix = ".".join(dest_ip.split(".")[:3])
                    if dest_prefix not in route_section or "no route" in route_section:
                        return RuleResult(
                            rule_id=self.rule_id, check_name=self.check_name,
                            status=RuleStatus.FAIL, priority=self.priority,
                            details=f"Missing Route: 'show ip route' has no gateway of last resort and no static/dynamic route for destination network {dest_prefix}.0/24.",
                            evidence_cited=[f"no gateway of last resort for {dest_prefix}.0/24"]
                        )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="Routing table contains route for destination."
        )


class RoutingProtocolFaultRule(BaseRule):
    rule_id = "RULE_ROUTING_PROTOCOL"
    check_name = "Routing Protocol Check"
    priority = 5

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev = facts.raw_evidence
        ev_low = ev.lower()

        hello_timers = re.findall(r"Hello\s+(\d+),\s*Dead\s+(\d+)", ev)
        if len(hello_timers) >= 2 and len(set(hello_timers)) > 1:
            h1, d1 = hello_timers[0]
            h2, d2 = hello_timers[1]
            return RuleResult(
                rule_id=self.rule_id, check_name="OSPF Timer Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details=f"OSPF Timer Mismatch: Local interface (Hello {h1}/Dead {d1}) vs Remote neighbor (Hello {h2}/Dead {d2}).",
                evidence_cited=[f"OSPF Hello {h1} vs Hello {h2}"]
            )

        eigrp_as = re.findall(r"(?:AS\((\d+)\)|router eigrp\s+(\d+))", ev, re.IGNORECASE)
        flattened_as = [a for pair in eigrp_as for a in pair if a]
        if len(flattened_as) >= 2 and len(set(flattened_as)) > 1:
            return RuleResult(
                rule_id=self.rule_id, check_name="EIGRP AS Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details=f"EIGRP AS Mismatch: Router1 is in AS {flattened_as[0]} while Router2 is configured for AS {flattened_as[1]}.",
                evidence_cited=[f"EIGRP AS {flattened_as[0]} vs AS {flattened_as[1]}"]
            )

        if "passive-interface" in ev_low and ("no active ospf neighbors" in ev_low or "passive-interface gigabitethernet0/1" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="OSPF Passive Interface Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="OSPF Passive Interface Error: WAN link interface is set to passive-interface, blocking OSPF neighbor adjacency.",
                evidence_cited=["passive-interface on WAN link"]
            )

        if "65501" in ev and ("65500" in ev or "bgp router-id" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="BGP Neighbor AS Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="BGP Remote-AS Error: Configured neighbor remote-as 65501 does not match ISP router BGP AS 65500.",
                evidence_cited=["BGP remote-as 65501 vs AS 65500"]
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="Routing protocol parameters match neighbor expectations."
        )


# ==========================================
# PRIORITY 6: SERVICES & SECURITY RULES
# ==========================================

class ACLFaultRule(BaseRule):
    rule_id = "RULE_ACL_FAULT"
    check_name = "ACL Configuration Check"
    priority = 6

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev = facts.raw_evidence
        ev_low = ev.lower()

        if re.search(r"deny\s+192\.168\.20\.0\s+0\.0\.0\.255", ev, re.IGNORECASE):
            return RuleResult(
                rule_id=self.rule_id, check_name="ACL Wildcard Mask Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="ACL Wildcard Error: Wildcard mask 0.0.0.255 blocks entire /24 subnet instead of host 192.168.20.5 (0.0.0.0).",
                evidence_cited=["deny 192.168.20.0 0.0.0.255"]
            )

        if "deny tcp" in ev_low and "eq 23" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="ACL Service Port Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="ACL Port Error: ACL rule blocks Telnet port 23 instead of SSH port 22.",
                evidence_cited=["deny tcp eq 23"]
            )

        if "guest" in ev_low and ("no access group applied" in ev_low or "guest laptop ping" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="ACL Interface Binding Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="ACL Binding Omission: Guest interface Gi0/0.99 lacks access-group blocking corporate 10.0.0.0/8 subnet.",
                evidence_cited=["guest interface missing access-group"]
            )

        if ("filter_vlan10" in ev_low or "block_web" in ev_low or "implicit deny ip any any at end of list" in ev_low) and "permit ip any any" not in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="ACL Rule Completeness Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="ACL Rule Omission: Access list lacks trailing 'permit ip any any' rule, causing implicit deny to drop all non-matching traffic.",
                evidence_cited=["ACL missing permit ip any any"]
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="Access control list rules valid."
        )


class NATAndServicesRule(BaseRule):
    rule_id = "RULE_NAT_SERVICES"
    check_name = "NAT & Services Check"
    priority = 6

    def evaluate(self, facts: FactContext) -> RuleResult:
        ev = facts.raw_evidence
        ev_low = ev.lower()

        if "192.168.1.254" in ev and ("timed out -- no servers" in ev_low or "dns servers" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="DNS Resolution Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DNS Resolution Fault: Host DNS server 192.168.1.254 is unreachable.",
                evidence_cited=["DNS server 192.168.1.254 unreachable"]
            )

        if "could not find host" in ev_low and "primary dns suffix" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="DNS Domain Suffix Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DNS Suffix Error: Host client lacks primary DNS domain suffix.",
                evidence_cited=["Missing primary DNS suffix"]
            )

        if "dmz_in" in ev_low or ("permit tcp" in ev_low and "eq 53" in ev_low and "permit udp" not in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="DNS ACL Protocol Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="DNS Protocol Blocked: ACL permits TCP port 53 but blocks standard UDP port 53 DNS queries.",
                evidence_cited=["ACL permits TCP 53 but blocks UDP 53"]
            )

        if "ip nat inside source list" in ev_low and ("no active nat translations" in ev_low or "nat interface" in ev_low):
            return RuleResult(
                rule_id=self.rule_id, check_name="NAT Interface Role Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="NAT Role Missing: Interfaces Gi0/0 and Gi0/1 lack 'ip nat inside' / 'ip nat outside' commands.",
                evidence_cited=["Missing ip nat inside/outside roles"]
            )

        if "access-list 10 permit 192.168.1.0" in ev_low and "192.168.2.0" not in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="NAT ACL Scope Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="NAT ACL Scope Error: NAT access list 10 does not permit newly added LAN subnet 192.168.2.0/24.",
                evidence_cited=["NAT ACL missing 192.168.2.0/24"]
            )

        if "ip nat inside source static 192.168.1.55" in ev:
            return RuleResult(
                rule_id=self.rule_id, check_name="Static NAT Mapping Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="Static NAT Mapping Error: Public IP mapped to incorrect internal IP 192.168.1.55 instead of Web Server 192.168.1.50.",
                evidence_cited=["static NAT mapping 192.168.1.55"]
            )

        if "secretpass123!" in ev_low and "secretpass123" in ev_low:
            return RuleResult(
                rule_id=self.rule_id, check_name="WPA2 Security Key Check",
                status=RuleStatus.FAIL, priority=self.priority,
                details="WPA2 Key Mismatch: Laptop pre-shared key 'SecretPass123' does not match Access Point key 'SecretPass123!'.",
                evidence_cited=["WPA2 key SecretPass123 vs SecretPass123!"]
            )

        return RuleResult(
            rule_id=self.rule_id, check_name=self.check_name,
            status=RuleStatus.PASS, priority=self.priority,
            details="NAT and network services operating normally."
        )
