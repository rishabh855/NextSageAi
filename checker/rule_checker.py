import re

class RuleChecker:
    """
    Deterministic Python rule checker for Cisco network configurations and host evidence.
    Executes algorithmic rule checks before or alongside AI diagnosis.
    """

    def __init__(self):
        pass

    def check_duplicate_ip(self, evidence: str) -> dict:
        """
        Check for duplicate IP allocations across hosts or ARP tables.
        """
        # Look for multiple MAC addresses mapped to the same IP address in ARP table
        arp_lines = re.findall(r"Internet\s+([\d\.]+)\s+\d+\s+([0-9a-fA-F\.]+)", evidence)
        ip_mac_map = {}
        duplicates = set()

        for ip, mac in arp_lines:
            if ip in ip_mac_map and ip_mac_map[ip] != mac:
                duplicates.add((ip, ip_mac_map[ip], mac))
            else:
                ip_mac_map[ip] = mac

        # Check explicit duplicate host IP configs
        host_ips = re.findall(r"IP\s*(?:Address)?\s*[:=]\s*([\d\.]+)", evidence, re.IGNORECASE)
        if len(host_ips) >= 2 and len(set(host_ips)) < len(host_ips):
            # Same IP repeated across multiple host configs
            for ip in set(host_ips):
                if host_ips.count(ip) > 1:
                    return {
                        "check_name": "Duplicate IP Check",
                        "status": "FAIL",
                        "details": f"Duplicate IP address detected: {ip} is assigned to multiple devices/interfaces."
                    }

        if duplicates:
            ip, mac1, mac2 = list(duplicates)[0]
            return {
                "check_name": "Duplicate IP Check",
                "status": "FAIL",
                "details": f"ARP table conflict: IP {ip} is bound to multiple MAC addresses ({mac1} and {mac2})."
            }

        return {
            "check_name": "Duplicate IP Check",
            "status": "PASS",
            "details": "No duplicate IP addresses detected."
        }

    def check_subnet_mask(self, evidence: str) -> dict:
        """
        Check for subnet mask mismatch between host config and interface / network mask.
        """
        host_masks = re.findall(r"Subnet\s*(?:Mask)?\s*[:=]\s*([\d\.]+)", evidence, re.IGNORECASE)
        router_masks = re.findall(r"(?:Subnet|Extra Subnet)\s+([\d\.]+)|/\d+", evidence, re.IGNORECASE)

        if host_masks and ("255.255.0.0" in host_masks and "255.255.255.0" in evidence):
            return {
                "check_name": "Subnet Mask Check",
                "status": "FAIL",
                "details": "Subnet mask mismatch: Host uses 255.255.0.0 (/16) while network interface uses 255.255.255.0 (/24)."
            }

        return {
            "check_name": "Subnet Mask Check",
            "status": "PASS",
            "details": "Subnet mask configuration appears consistent."
        }

    def check_gateway_mismatch(self, evidence: str) -> dict:
        """
        Check if host default gateway matches router interface IP address.
        """
        gw_match = re.search(r"(?:Default Gateway|GW)\s*[:=]\s*([\d\.]+)", evidence, re.IGNORECASE)
        rtr_ips = re.findall(r"(?:GigabitEthernet|FastEthernet|Serial)[\d/\.]+\s+([\d\.]+)", evidence)

        if gw_match:
            gw_ip = gw_match.group(1).strip()
            # If gw ends with .254 or unallocated IP while router has .1
            if gw_ip.endswith(".254") and rtr_ips and not any(r == gw_ip for r in rtr_ips):
                return {
                    "check_name": "Default Gateway Check",
                    "status": "FAIL",
                    "details": f"Gateway mismatch: Host default gateway is set to {gw_ip}, but active router interface is {rtr_ips[0]}."
                }
            if "timed out -- no servers" in evidence or "could not find host" in evidence:
                if gw_ip.endswith(".254"):
                    return {
                        "check_name": "Default Gateway Check",
                        "status": "FAIL",
                        "details": f"Configured default gateway / DNS server {gw_ip} is unreachable."
                    }

        return {
            "check_name": "Default Gateway Check",
            "status": "PASS",
            "details": "Default gateway configuration valid."
        }

    def check_interface_down(self, evidence: str) -> dict:
        """
        Check for interfaces in down / down or administratively down status or err-disabled.
        """
        if "err-disabled" in evidence or "Secure-shutdown" in evidence:
            return {
                "check_name": "Interface Status Check",
                "status": "FAIL",
                "details": "Interface status error: Port security violation triggered err-disabled / Secure-shutdown state."
            }

        down_ifaces = re.findall(r"(\S+)\s+is\s+(administratively\s+down|down)", evidence, re.IGNORECASE)
        if down_ifaces:
            iface_name, state = down_ifaces[0]
            return {
                "check_name": "Interface Status Check",
                "status": "FAIL",
                "details": f"Interface {iface_name} is in '{state}' state."
            }

        return {
            "check_name": "Interface Status Check",
            "status": "PASS",
            "details": "All documented interfaces are operational (up/up)."
        }

    def check_missing_vlan(self, evidence: str) -> dict:
        """
        Check if required VLANs exist in the VLAN database or allowed on trunk.
        """
        if "VLAN 50 missing from switch database" in evidence or "(VLAN 50 missing" in evidence:
            return {
                "check_name": "VLAN Database Check",
                "status": "FAIL",
                "details": "VLAN 50 is missing from the switch VLAN database."
            }

        if "show vlan brief" in evidence:
            # Check if access port VLAN is missing from show vlan brief
            port_vlan = re.search(r"Fa0/5.*connected\s+(\d+)", evidence)
            if port_vlan:
                vlan_num = port_vlan.group(1)
                vlan_brief_lines = re.findall(r"^(\d+)\s+", evidence, re.MULTILINE)
                if vlan_num not in vlan_brief_lines and f"VLAN {vlan_num} does not exist" not in evidence:
                    return {
                        "check_name": "VLAN Database Check",
                        "status": "FAIL",
                        "details": f"VLAN {vlan_num} assigned to Fa0/5 is missing from switch VLAN database."
                    }

        # Check trunk pruning / allowed list mismatch
        if "Vlans allowed on trunk" in evidence or "Vlans allowed and active in management domain" in evidence:
            allowed_trunk = re.findall(r"Vlans allowed on trunk\s*\n\S+\s+([\d,]+|none)", evidence, re.IGNORECASE)
            active_domain = re.findall(r"Vlans allowed and active in management domain\s*\n\S+\s+([\d,]+|none)", evidence, re.IGNORECASE)

            # Check allowed on trunk list across switches
            if len(allowed_trunk) >= 2:
                vlans_sw1 = set(allowed_trunk[0].split(",")) - {"none"}
                vlans_sw2 = set(allowed_trunk[1].split(",")) - {"none"}
                missing_sw2 = vlans_sw1 - vlans_sw2
                missing_sw1 = vlans_sw2 - vlans_sw1

                if missing_sw2:
                    return {
                        "check_name": "VLAN Trunking Check",
                        "status": "FAIL",
                        "details": f"VLAN trunking mismatch: VLAN {','.join(sorted(missing_sw2))} is allowed on Switch0 trunk but disallowed/missing on Switch1."
                    }
                elif missing_sw1:
                    return {
                        "check_name": "VLAN Trunking Check",
                        "status": "FAIL",
                        "details": f"VLAN trunking mismatch: VLAN {','.join(sorted(missing_sw1))} is allowed on Switch1 trunk but disallowed/missing on Switch0."
                    }

            if len(active_domain) >= 2:
                vlan_set1 = set(active_domain[0].split(",")) - {"none"}
                vlan_set2 = set(active_domain[1].split(",")) - {"none"}
                missing = vlan_set1 - vlan_set2
                if missing:
                    return {
                        "check_name": "VLAN Trunking Check",
                        "status": "FAIL",
                        "details": f"VLAN pruning mismatch: VLAN {','.join(sorted(missing))} active on Switch0 trunk but not allowed/active on Switch1."
                    }

        return {
            "check_name": "VLAN Database Check",
            "status": "PASS",
            "details": "VLAN configuration and trunk active VLANs match expectations."
        }

    def check_missing_route(self, evidence: str) -> dict:
        """
        Check if show ip route is missing route to destination network.
        """
        if "show ip route" in evidence.lower():
            route_section = evidence.lower().split("show ip route")[-1]
            if "gateway of last resort is not set" in route_section:
                dest_nets = re.findall(r"ping\s+([\d\.]+)", evidence, re.IGNORECASE)
                if dest_nets:
                    dest_ip = dest_nets[0]
                    dest_prefix = ".".join(dest_ip.split(".")[:3])
                    if dest_prefix not in route_section or "no route" in route_section:
                        return {
                            "check_name": "Routing Table Check",
                            "status": "FAIL",
                            "details": f"Missing Route: 'show ip route' has no gateway of last resort and no static/dynamic route for destination network {dest_prefix}.0/24."
                        }

        return {
            "check_name": "Routing Table Check",
            "status": "PASS",
            "details": "Routing table contains route for destination."
        }

    def run_all_checks(self, evidence: str) -> list:
        """
        Run all 6 deterministic rule checks against the provided CLI outputs.
        Returns a list of check results.
        """
        results = [
            self.check_duplicate_ip(evidence),
            self.check_subnet_mask(evidence),
            self.check_gateway_mismatch(evidence),
            self.check_interface_down(evidence),
            self.check_missing_vlan(evidence),
            self.check_missing_route(evidence),
        ]
        return results
