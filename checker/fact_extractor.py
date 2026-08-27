import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any, Tuple

@dataclass
class FactProvenance:
    device: str = "UNKNOWN"
    command: str = "UNKNOWN"
    raw_snippet: str = ""

@dataclass
class HostFact:
    device: str
    command: str
    ipv4_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    default_gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)
    dns_suffix: Optional[str] = None
    mac_address: Optional[str] = None
    is_apipa: bool = False
    has_valid_ip: bool = False
    has_valid_gateway: bool = False
    provenance: Optional[FactProvenance] = None

@dataclass
class InterfaceFact:
    device: str
    command: str
    interface_name: str
    status: str = "UNKNOWN"
    protocol: str = "UNKNOWN"
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    mode: Optional[str] = None
    access_vlan: Optional[str] = None
    native_vlan: Optional[str] = None
    allowed_vlans: List[str] = field(default_factory=list)
    active_vlans: List[str] = field(default_factory=list)
    helper_address: Optional[str] = None
    nat_role: Optional[str] = None
    provenance: Optional[FactProvenance] = None

@dataclass
class VLANFact:
    device: str
    command: str
    vlan_database: Set[str] = field(default_factory=set)
    provenance: Optional[FactProvenance] = None

@dataclass
class RoutingFact:
    device: str
    command: str
    has_default_route: bool = False
    gateway_of_last_resort: Optional[str] = None
    routes: List[Dict[str, str]] = field(default_factory=list)
    ospf_hello: Optional[str] = None
    ospf_dead: Optional[str] = None
    ospf_passive_interfaces: List[str] = field(default_factory=list)
    eigrp_as: Optional[str] = None
    bgp_as: Optional[str] = None
    bgp_remote_as: Optional[str] = None
    provenance: Optional[FactProvenance] = None

@dataclass
class DHCPFact:
    device: str
    command: str
    pools: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    excluded_addresses: List[str] = field(default_factory=list)
    active_bindings: int = 0
    utilization_pct: int = 0
    option_43_present: bool = False
    provenance: Optional[FactProvenance] = None

@dataclass
class ACLFact:
    device: str
    command: str
    acl_rules: List[Dict[str, Any]] = field(default_factory=list)
    interface_bindings: Dict[str, str] = field(default_factory=dict)
    has_implicit_deny: bool = False
    has_permit_any_any: bool = False
    provenance: Optional[FactProvenance] = None

@dataclass
class NATFact:
    device: str
    command: str
    inside_interfaces: List[str] = field(default_factory=list)
    outside_interfaces: List[str] = field(default_factory=list)
    nat_acl_id: Optional[str] = None
    static_mappings: List[Dict[str, str]] = field(default_factory=list)
    provenance: Optional[FactProvenance] = None

@dataclass
class EvidenceMetadata:
    devices_inspected: Set[str] = field(default_factory=set)
    commands_executed: Set[Tuple[str, str]] = field(default_factory=set)
    has_host_config: bool = False
    has_switch_config: bool = False
    has_router_config: bool = False
    raw_sections_count: int = 0

@dataclass
class FactContext:
    hosts: List[HostFact] = field(default_factory=list)
    interfaces: List[InterfaceFact] = field(default_factory=list)
    vlans: Dict[str, VLANFact] = field(default_factory=dict)
    routing: Dict[str, RoutingFact] = field(default_factory=dict)
    dhcp: Dict[str, DHCPFact] = field(default_factory=dict)
    acls: Dict[str, ACLFact] = field(default_factory=dict)
    nat: Dict[str, NATFact] = field(default_factory=dict)
    metadata: EvidenceMetadata = field(default_factory=EvidenceMetadata)
    raw_evidence: str = ""

    def has_evidence_type(self, evidence_type: str) -> bool:
        et = evidence_type.lower()
        if et in ["host", "host_ipconfig", "ipconfig"]:
            return self.metadata.has_host_config or len(self.hosts) > 0
        if et in ["router_if", "router_interface", "show_ip_interface_brief"]:
            return any(i for i in self.interfaces if i.device.lower().startswith("router") or i.device.lower().startswith("r"))
        if et in ["router_config", "running_config", "show_running_config"]:
            return self.metadata.has_router_config
        if et in ["switch_config", "switch_trunk", "show_interfaces_trunk"]:
            return self.metadata.has_switch_config or any(i.mode == "trunk" or i.native_vlan for i in self.interfaces)
        if et in ["vlan_brief", "vlan_database"]:
            return len(self.vlans) > 0
        return False


class FactExtractor:
    """
    Normalizes raw CLI output sections into a structured FactContext.
    Preserves exact evidence provenance (device, command, snippet).
    Tolerates partial and malformed CLI output; missing values remain None/UNKNOWN.
    """

    @classmethod
    def extract(cls, evidence: str) -> FactContext:
        ctx = FactContext(raw_evidence=evidence)
        sections = cls._parse_device_sections(evidence)

        if not sections and evidence.strip():
            sections = [("Global", "raw_output", evidence)]

        ctx.metadata.raw_sections_count = len(sections)

        for dev_name, cmd_name, content in sections:
            prov = FactProvenance(device=dev_name, command=cmd_name, raw_snippet=content[:300])
            dev_clean = dev_name.strip()
            cmd_clean = cmd_name.strip()

            ctx.metadata.devices_inspected.add(dev_clean)
            ctx.metadata.commands_executed.add((dev_clean.lower(), cmd_clean.lower()))

            dev_low = dev_clean.lower()
            cmd_low = cmd_clean.lower()

            if "pc" in dev_low or "host" in dev_low or "ipconfig" in cmd_low:
                ctx.metadata.has_host_config = True
                cls._extract_host_facts(ctx, dev_clean, cmd_clean, content, prov)
            elif "router" in dev_low or "r1" in dev_low or "r2" in dev_low or "r3" in dev_low or "rtr" in dev_low:
                ctx.metadata.has_router_config = True
            elif "switch" in dev_low or "sw" in dev_low or "l2sw" in dev_low:
                ctx.metadata.has_switch_config = True

            cls._extract_interface_facts(ctx, dev_clean, cmd_clean, content, prov)
            cls._extract_vlan_facts(ctx, dev_clean, cmd_clean, content, prov)
            cls._extract_routing_facts(ctx, dev_clean, cmd_clean, content, prov)
            cls._extract_dhcp_facts(ctx, dev_clean, cmd_clean, content, prov)
            cls._extract_acl_facts(ctx, dev_clean, cmd_clean, content, prov)
            cls._extract_nat_facts(ctx, dev_clean, cmd_clean, content, prov)

        return ctx

    @classmethod
    def _parse_device_sections(cls, evidence: str) -> List[Tuple[str, str, str]]:
        pattern = r"^\s*(?:---|===)\s*\[?([a-zA-Z0-9_\-]{2,})\]?\s+([a-zA-Z0-9_/% \.\-]+?)\s*(?:---|===)\s*$"
        matches = list(re.finditer(pattern, evidence, re.MULTILINE))

        sections = []
        for i in range(len(matches)):
            dev_name = matches[i].group(1)
            cmd_name = matches[i].group(2)
            start_pos = matches[i].end()
            end_pos = matches[i+1].start() if i+1 < len(matches) else len(evidence)
            content = evidence[start_pos:end_pos]
            sections.append((dev_name, cmd_name, content))

        return sections

    @classmethod
    def _extract_host_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        ip_m = re.search(r"(?:IPv4 Address|IP Address)[\s\.]*[:=]\s*([\d\.]+)", text, re.IGNORECASE)
        mask_m = re.search(r"Subnet Mask[\s\.]*[:=]\s*([\d\.]+)", text, re.IGNORECASE)
        gw_m = re.search(r"(?:Default Gateway|GW)[\s\.]*[:=]\s*([\d\.]+)", text, re.IGNORECASE)
        dns_suffix_m = re.search(r"Connection-specific DNS Suffix[\s\.]*[:=]\s*(\S+)", text, re.IGNORECASE)
        mac_m = re.search(r"(?:Physical Address|MAC)[\s\.]*[:=]\s*([0-9a-fA-F\.\-]+)", text, re.IGNORECASE)

        ip_val = ip_m.group(1).strip() if ip_m else None
        mask_val = mask_m.group(1).strip() if mask_m else None
        gw_val = gw_m.group(1).strip() if gw_m else None
        dns_suffix_val = dns_suffix_m.group(1).strip() if dns_suffix_m else None
        mac_val = mac_m.group(1).strip() if mac_m else None

        is_apipa = bool(ip_val and ip_val.startswith("169.254.")) or "169.254." in text
        has_valid_ip = bool(ip_val and not is_apipa and ip_val != "0.0.0.0")
        has_valid_gw = bool(gw_val and gw_val != "0.0.0.0")

        host_fact = HostFact(
            device=dev,
            command=cmd,
            ipv4_address=ip_val,
            subnet_mask=mask_val,
            default_gateway=gw_val,
            dns_suffix=dns_suffix_val,
            mac_address=mac_val,
            is_apipa=is_apipa,
            has_valid_ip=has_valid_ip,
            has_valid_gateway=has_valid_gw,
            provenance=prov
        )
        ctx.hosts.append(host_fact)

    @classmethod
    def _extract_interface_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        # Parse show ip interface brief
        ip_ifaces = re.findall(r"^(\S+)\s+([\d\.]+|unassigned)\s+YES\s+\S+\s+(up|down|administratively down)\s+(up|down)", text, re.MULTILINE | re.IGNORECASE)
        for if_name, ip_addr, status, proto in ip_ifaces:
            fact = InterfaceFact(
                device=dev,
                command=cmd,
                interface_name=if_name,
                status=status.lower(),
                protocol=proto.lower(),
                ip_address=ip_addr if ip_addr.lower() != "unassigned" else None,
                provenance=prov
            )
            ctx.interfaces.append(fact)

        # Parse table rows from show interfaces trunk
        trunk_tbl_rows = re.findall(r"^\s*(\S+)\s+(?:on|auto|desirable|off)\s+\S+\s+(?:trunking|not-trunking)\s+(\d+)", text, re.MULTILINE | re.IGNORECASE)
        for if_name, n_vlan in trunk_tbl_rows:
            ctx.interfaces.append(InterfaceFact(
                device=dev,
                command=cmd,
                interface_name=if_name,
                mode="trunk",
                native_vlan=n_vlan,
                provenance=prov
            ))

        # Parse Trunking Native VLAN from show interfaces switchport
        native_m = re.findall(r"Trunking Native (?:Mode )?VLAN:\s*(\d+)", text, re.IGNORECASE)
        for n_vlan in native_m:
            ctx.interfaces.append(InterfaceFact(
                device=dev,
                command=cmd,
                interface_name="Trunk",
                mode="trunk",
                native_vlan=n_vlan,
                provenance=prov
            ))

        # Parse access VLAN from show interface status / switchport
        access_m = re.search(r"connected\s+(\d+)", text) or re.search(r"access vlan\s+(\d+)", text, re.IGNORECASE)
        if access_m:
            ctx.interfaces.append(InterfaceFact(
                device=dev,
                command=cmd,
                interface_name="AccessPort",
                mode="access",
                access_vlan=access_m.group(1),
                provenance=prov
            ))

        # Parse helper-address
        helper_m = re.search(r"ip helper-address\s+([\d\.]+)", text, re.IGNORECASE)
        if helper_m:
            ctx.interfaces.append(InterfaceFact(
                device=dev,
                command=cmd,
                interface_name="RoutedInterface",
                helper_address=helper_m.group(1),
                provenance=prov
            ))

    @classmethod
    def _extract_vlan_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        if "vlan" in cmd.lower() or "show vlan" in text.lower():
            vlans = set(re.findall(r"^\s*(\d+)\s+", text, re.MULTILINE))
            if dev in ctx.vlans:
                ctx.vlans[dev].vlan_database.update(vlans)
            else:
                ctx.vlans[dev] = VLANFact(device=dev, command=cmd, vlan_database=vlans, provenance=prov)

    @classmethod
    def _extract_routing_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        if "route" in cmd.lower() or "show ip route" in text.lower():
            has_gw_lr = "gateway of last resort is not set" not in text.lower() and "gateway of last resort is" in text.lower()
            fact = RoutingFact(device=dev, command=cmd, has_default_route=has_gw_lr, provenance=prov)
            ctx.routing[dev] = fact

        # OSPF timers
        hello_timers = re.findall(r"Hello\s+(\d+),\s*Dead\s+(\d+)", text)
        if hello_timers:
            h, d = hello_timers[0]
            if dev not in ctx.routing:
                ctx.routing[dev] = RoutingFact(device=dev, command=cmd, provenance=prov)
            ctx.routing[dev].ospf_hello = h
            ctx.routing[dev].ospf_dead = d

        # EIGRP AS
        eigrp_as = re.findall(r"(?:AS\((\d+)\)|router eigrp\s+(\d+))", text, re.IGNORECASE)
        flattened = [a for pair in eigrp_as for a in pair if a]
        if flattened:
            if dev not in ctx.routing:
                ctx.routing[dev] = RoutingFact(device=dev, command=cmd, provenance=prov)
            ctx.routing[dev].eigrp_as = flattened[0]

    @classmethod
    def _extract_dhcp_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        if "dhcp" in text.lower() or "169.254" in text:
            fact = DHCPFact(
                device=dev,
                command=cmd,
                option_43_present="option 43" in text.lower(),
                provenance=prov
            )
            ctx.dhcp[dev] = fact

    @classmethod
    def _extract_acl_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        if "access-list" in text.lower() or "access-group" in text.lower():
            fact = ACLFact(
                device=dev,
                command=cmd,
                has_implicit_deny="implicit deny" in text.lower(),
                has_permit_any_any="permit ip any any" in text.lower(),
                provenance=prov
            )
            ctx.acls[dev] = fact

    @classmethod
    def _extract_nat_facts(cls, ctx: FactContext, dev: str, cmd: str, text: str, prov: FactProvenance):
        if "nat" in text.lower():
            fact = NATFact(
                device=dev,
                command=cmd,
                provenance=prov
            )
            ctx.nat[dev] = fact
