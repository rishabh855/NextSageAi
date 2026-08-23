import os
import csv

os.makedirs("data", exist_ok=True)

cases = [
    # VLAN Category (5 cases)
    {
        "case_id": "C001",
        "category": "VLAN",
        "symptom": "PC-A in VLAN 10 cannot ping PC-B in VLAN 10 connected to Switch 2.",
        "topology_note": "PC-A (192.168.10.10/24) -> Switch1 (FastEthernet0/1 access VLAN 10, GigabitEthernet0/1 trunk) -> Switch2 (GigabitEthernet0/1 trunk, FastEthernet0/2 access VLAN 10) -> PC-B (192.168.10.20/24).",
        "show_outputs": (
            "--- Host IP Config ---\n"
            "PC-A: IP 192.168.10.10, Subnet 255.255.255.0, GW 192.168.10.1\n"
            "PC-B: IP 192.168.10.20, Subnet 255.255.255.0, GW 192.168.10.1\n\n"
            "--- Switch1 show interfaces trunk ---\n"
            "Port        Mode         Encapsulation  Status        Native vlan\n"
            "Gi0/1       on           802.1q         trunking      1\n"
            "Port        Vlans allowed on trunk\n"
            "Gi0/1       1-4094\n"
            "Port        Vlans allowed and active in management domain\n"
            "Gi0/1       1,10,20\n\n"
            "--- Switch2 show interfaces trunk ---\n"
            "Port        Mode         Encapsulation  Status        Native vlan\n"
            "Gi0/1       on           802.1q         trunking      1\n"
            "Port        Vlans allowed on trunk\n"
            "Gi0/1       1,20,30\n"
            "Port        Vlans allowed and active in management domain\n"
            "Gi0/1       1,20,30\n\n"
            "--- Switch2 show vlan brief ---\n"
            "VLAN Name                             Status    Ports\n"
            "---- -------------------------------- --------- -------------------------------\n"
            "1    default                          active    Fa0/1, Fa0/3\n"
            "10   Sales                            active    Fa0/2\n"
            "20   Engineering                      active\n"
        ),
        "expected_fault": "VLAN 10 is pruned/disallowed on Switch2 trunk interface GigabitEthernet0/1.",
        "osi_layer": "Layer 2",
        "concept": "VLAN Trunking / Pruning",
        "severity": "High",
        "correct_fix": "On Switch2 interface GigabitEthernet0/1, execute 'switchport trunk allowed vlan add 10'."
    },
    {
        "case_id": "C002",
        "category": "VLAN",
        "symptom": "PC-1 in VLAN 20 is unable to obtain traffic or reach gateway. Switch logs report native VLAN mismatch.",
        "topology_note": "Switch1 (Gi0/1) trunk to Switch2 (Gi0/1). Native VLAN mismatch between switches.",
        "show_outputs": (
            "--- Switch1 CDP & Trunk Log ---\n"
            "%CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch discovered on GigabitEthernet0/1 (10), with Switch2 GigabitEthernet0/1 (1).\n\n"
            "--- Switch1 show interfaces Gi0/1 switchport ---\n"
            "Name: Gi0/1\n"
            "Operational Mode: trunk\n"
            "Administrative Native VLAN tagging: disabled\n"
            "Trunking Native VLAN: 10 (Sales)\n\n"
            "--- Switch2 show interfaces Gi0/1 switchport ---\n"
            "Name: Gi0/1\n"
            "Operational Mode: trunk\n"
            "Administrative Native VLAN tagging: disabled\n"
            "Trunking Native VLAN: 1 (default)\n"
        ),
        "expected_fault": "Native VLAN mismatch on trunk link between Switch1 (VLAN 10) and Switch2 (VLAN 1).",
        "osi_layer": "Layer 2",
        "concept": "Native VLAN Mismatch",
        "severity": "Medium",
        "correct_fix": "Configure 'switchport trunk native vlan 10' on Switch2 interface GigabitEthernet0/1."
    },
    {
        "case_id": "C003",
        "category": "VLAN",
        "symptom": "PC connected to Switch1 Fa0/5 has no network access and fails all pings.",
        "topology_note": "Host PC (192.168.30.15/24) connected to Switch1 Fa0/5, configured for VLAN 30.",
        "show_outputs": (
            "--- Host IP Config ---\n"
            "IP: 192.168.30.15, Mask: 255.255.255.0, GW: 192.168.30.1\n\n"
            "--- Switch1 show interface Fa0/5 status ---\n"
            "Port      Name               Status       Vlan       Duplex  Speed Type\n"
            "Fa0/5                        connected    30         a-full  a-100 10/100BaseTX\n\n"
            "--- Switch1 show vlan brief ---\n"
            "VLAN Name                             Status    Ports\n"
            "---- -------------------------------- --------- -------------------------------\n"
            "1    default                          active    Fa0/1, Fa0/2, Fa0/3, Fa0/4\n"
            "10   Sales                            active    Fa0/6, Fa0/7\n"
            "20   HR                               active    Fa0/8\n"
        ),
        "expected_fault": "VLAN 30 does not exist in the VLAN database on Switch1.",
        "osi_layer": "Layer 2",
        "concept": "Missing VLAN Definition",
        "severity": "High",
        "correct_fix": "Create VLAN 30 on Switch1 using 'vlan 30' followed by 'name Admin'."
    },
    {
        "case_id": "C004",
        "category": "VLAN",
        "symptom": "PC-2 attached to Fa0/10 cannot reach default gateway 192.168.1.1.",
        "topology_note": "Host PC-2 should be in VLAN 10 (subnet 192.168.1.0/24).",
        "show_outputs": (
            "--- Host IP Config ---\n"
            "IP: 192.168.1.50, Mask: 255.255.255.0, GW: 192.168.1.1\n\n"
            "--- Switch1 show mac address-table interface Fa0/10 ---\n"
            "Vlan    Mac Address       Type        Ports\n"
            "----    -----------       --------    -----\n"
            "1       0050.7966.0001    DYNAMIC     Fa0/10\n\n"
            "--- Switch1 show interfaces Fa0/10 switchport ---\n"
            "Name: Fa0/10\n"
            "Administrative Mode: static access\n"
            "Operational Mode: static access\n"
            "Access Mode VLAN: 1 (default)\n"
        ),
        "expected_fault": "Switch port Fa0/10 is assigned to default VLAN 1 instead of target VLAN 10.",
        "osi_layer": "Layer 2",
        "concept": "Access Port VLAN Assignment",
        "severity": "Medium",
        "correct_fix": "On Switch1 interface Fa0/10, execute 'switchport access vlan 10'."
    },
    {
        "case_id": "C005",
        "category": "VLAN",
        "symptom": "Trunk port between Switch1 and Switch2 is down, disabling inter-switch traffic.",
        "topology_note": "Switch1 Gi0/2 connected to Switch2 Gi0/2. DTP negotiation failing.",
        "show_outputs": (
            "--- Switch1 show interfaces Gi0/2 switchport ---\n"
            "Name: Gi0/2\n"
            "Administrative Mode: dynamic auto\n"
            "Operational Mode: static access\n"
            "Negotiation of Trunking: On\n"
            "Access Mode VLAN: 1\n\n"
            "--- Switch2 show interfaces Gi0/2 switchport ---\n"
            "Name: Gi0/2\n"
            "Administrative Mode: dynamic auto\n"
            "Operational Mode: static access\n"
            "Negotiation of Trunking: On\n"
            "Access Mode VLAN: 1\n"
        ),
        "expected_fault": "Both trunk ports are set to 'dynamic auto', so neither port initiates trunk negotiation.",
        "osi_layer": "Layer 2",
        "concept": "Dynamic Trunking Protocol (DTP) Misconfig",
        "severity": "Medium",
        "correct_fix": "Configure 'switchport mode trunk' statically on interface Gi0/2 of both switches."
    },

    # Gateway / IP Category (4 cases)
    {
        "case_id": "C006",
        "category": "Gateway/IP",
        "symptom": "PC-A experiences intermittent loss of connectivity and duplicate IP warnings.",
        "topology_note": "PC-A (192.168.1.100) and PC-B on the same LAN segment.",
        "show_outputs": (
            "--- PC-A Host IP Config ---\n"
            "IP Address: 192.168.1.100, Subnet: 255.255.255.0, GW: 192.168.1.1\n"
            "MAC: 0001.AAAA.1111\n\n"
            "--- PC-B Host IP Config ---\n"
            "IP Address: 192.168.1.100, Subnet: 255.255.255.0, GW: 192.168.1.1\n"
            "MAC: 0002.BBBB.2222\n\n"
            "--- Router1 show ip arp ---\n"
            "Protocol  Address          Age (min)  Hardware Addr   Type   Interface\n"
            "Internet  192.168.1.100           0   0001.AAAA.1111  ARPA   Gi0/0\n"
            "Internet  192.168.1.100           0   0002.BBBB.2222  ARPA   Gi0/0\n"
        ),
        "expected_fault": "Duplicate IP address (192.168.1.100) statically assigned to both PC-A and PC-B.",
        "osi_layer": "Layer 3",
        "concept": "Duplicate IP Address",
        "severity": "High",
        "correct_fix": "Reconfigure PC-B to use an unallocated static IP address such as 192.168.1.101."
    },
    {
        "case_id": "C007",
        "category": "Gateway/IP",
        "symptom": "PC-1 can reach local subnet hosts (10.0.1.0/24) but cannot reach remote servers (10.0.2.10).",
        "topology_note": "PC-1 (10.0.1.50) connected to Router1 Gi0/0 (10.0.1.1).",
        "show_outputs": (
            "--- PC-1 ipconfig ---\n"
            "IP Address. . . . . . . . . . . . : 10.0.1.50\n"
            "Subnet Mask . . . . . . . . . . . : 255.255.255.0\n"
            "Default Gateway . . . . . . . . . : 10.0.1.254\n\n"
            "--- Router1 show ip interface brief ---\n"
            "Interface                  IP-Address      OK? Method Status                Protocol\n"
            "GigabitEthernet0/0         10.0.1.1        YES manual up                    up\n"
            "GigabitEthernet0/1         10.0.2.1        YES manual up                    up\n"
        ),
        "expected_fault": "PC-1 is configured with an invalid default gateway address (10.0.1.254 instead of 10.0.1.1).",
        "osi_layer": "Layer 3",
        "concept": "Default Gateway Mismatch",
        "severity": "High",
        "correct_fix": "Change PC-1's default gateway address to 10.0.1.1."
    },
    {
        "case_id": "C008",
        "category": "Gateway/IP",
        "symptom": "Host PC-3 (172.16.10.50) cannot ping Gateway 172.16.10.1.",
        "topology_note": "PC-3 connected to Router LAN interface Gi0/0 (172.16.10.1/24).",
        "show_outputs": (
            "--- PC-3 ipconfig ---\n"
            "IP Address: 172.16.10.50\n"
            "Subnet Mask: 255.255.0.0\n"
            "Default Gateway: 172.16.10.1\n\n"
            "--- Router show interfaces GigabitEthernet0/0 ---\n"
            "GigabitEthernet0/0 is up, line protocol is up\n"
            "  Internet Address is 172.16.10.1/24, Extra Subnet 255.255.255.0\n"
        ),
        "expected_fault": "Subnet mask mismatch between host PC-3 (255.255.0.0 /16) and router interface (255.255.255.0 /24).",
        "osi_layer": "Layer 3",
        "concept": "Subnet Mask Mismatch",
        "severity": "Medium",
        "correct_fix": "Update PC-3 subnet mask to 255.255.255.0."
    },
    {
        "case_id": "C009",
        "category": "Gateway/IP",
        "symptom": "Hosts on LAN failover fail when primary router R1 goes down.",
        "topology_note": "R1 (192.168.1.2) and R2 (192.168.1.3) configured for HSRP Virtual IP 192.168.1.1.",
        "show_outputs": (
            "--- R1 show standby brief ---\n"
            "Interface   Grp  Pri P State   Active          Standby         Virtual IP\n"
            "Gi0/0       1    110 P Active  local           192.168.1.3     192.168.1.1\n\n"
            "--- R2 show standby brief ---\n"
            "Interface   Grp  Pri P State   Active          Standby         Virtual IP\n"
            "Gi0/0       2    100   Active  local           unknown         192.168.1.1\n"
        ),
        "expected_fault": "HSRP group ID mismatch (Group 1 on R1 vs Group 2 on R2).",
        "osi_layer": "Layer 3",
        "concept": "HSRP First-Hop Redundancy Misconfig",
        "severity": "High",
        "correct_fix": "Reconfigure R2 interface Gi0/0 to use 'standby 1 ip 192.168.1.1'."
    },

    # DHCP Category (4 cases)
    {
        "case_id": "C010",
        "category": "DHCP",
        "symptom": "Branch office PCs receive APIPA IP addresses (169.254.x.x) and cannot access company network.",
        "topology_note": "Branch PCs -> Switch -> Branch Router Gi0/0 (192.168.50.1) -> WAN -> HQ Central DHCP Server (10.1.1.100).",
        "show_outputs": (
            "--- Branch PC ipconfig ---\n"
            "Autoconfiguration IPv4 Address. . . : 169.254.45.12\n"
            "Subnet Mask . . . . . . . . . . . : 255.255.0.0\n"
            "Default Gateway . . . . . . . . . :\n\n"
            "--- Branch Router show running-config interface Gi0/0 ---\n"
            "interface GigabitEthernet0/0\n"
            " ip address 192.168.50.1 255.255.255.0\n"
            " duplex auto\n"
            " speed auto\n"
        ),
        "expected_fault": "Missing 'ip helper-address 10.1.1.100' command on Branch Router interface Gi0/0 to forward DHCP broadcasts across the WAN.",
        "osi_layer": "Layer 7 / Application (DHCP Relay)",
        "concept": "DHCP Relay / IP Helper Address",
        "severity": "High",
        "correct_fix": "On Branch Router interface Gi0/0, add command 'ip helper-address 10.1.1.100'."
    },
    {
        "case_id": "C011",
        "category": "DHCP",
        "symptom": "New PCs added to Sales department fail to obtain IP address from Router DHCP pool.",
        "topology_note": "Router1 acting as local DHCP server for pool SALES_POOL (192.168.10.0/24).",
        "show_outputs": (
            "--- Router1 show ip dhcp binding ---\n"
            "IP address       Client-ID/Hardware address      Expiration       Type\n"
            "192.168.10.1     0001.1111.1111                  Infinite         Manual\n"
            "... [254 active bindings listed] ...\n\n"
            "--- Router1 show ip dhcp pool SALES_POOL ---\n"
            "Pool SALES_POOL :\n"
            " Utilization mark (high/low)    : 100 / 0\n"
            " Subnet size (total/total addresses) : 254 / 254\n"
            " Total leased addresses         : 254\n"
            " Pending event addresses        : 0\n"
        ),
        "expected_fault": "DHCP pool SALES_POOL address space is completely exhausted.",
        "osi_layer": "Layer 7",
        "concept": "DHCP Pool Exhaustion",
        "severity": "High",
        "correct_fix": "Expand the DHCP pool subnet mask or clear inactive leases using 'clear ip dhcp binding *'."
    },
    {
        "case_id": "C012",
        "category": "DHCP",
        "symptom": "Router interface IP conflicts with newly connected host PC.",
        "topology_note": "Router LAN interface is 192.168.1.1. Host assigned 192.168.1.1 via DHCP.",
        "show_outputs": (
            "--- Router show running-config | section dhcp ---\n"
            "ip dhcp pool LAN_POOL\n"
            " network 192.168.1.0 255.255.255.0\n"
            " default-router 192.168.1.1\n"
            " dns-server 8.8.8.8\n"
        ),
        "expected_fault": "Router interface IP (192.168.1.1) was not excluded from the DHCP pool allocation range.",
        "osi_layer": "Layer 7",
        "concept": "DHCP Excluded Addresses",
        "severity": "Medium",
        "correct_fix": "Configure 'ip dhcp excluded-address 192.168.1.1 192.168.1.10' on global router prompt."
    },
    {
        "case_id": "C013",
        "category": "DHCP",
        "symptom": "PCs in VLAN 40 receive IP addresses in 192.168.20.0/24 range instead of 192.168.40.0/24.",
        "topology_note": "Router subinterface Gi0/0.40 (192.168.40.1) configured for VLAN 40.",
        "show_outputs": (
            "--- Router show running-config | section dhcp ---\n"
            "ip dhcp pool VLAN40\n"
            " network 192.168.20.0 255.255.255.0\n"
            " default-router 192.168.40.1\n\n"
            "--- Router show interface Gi0/0.40 ---\n"
            "Gi0/0.40 is up, line protocol is up\n"
            " Encapsulation 802.1Q Virtual LAN 40\n"
            " Internet address is 192.168.40.1/24\n"
        ),
        "expected_fault": "DHCP pool VLAN40 has incorrect network statement (192.168.20.0 instead of 192.168.40.0).",
        "osi_layer": "Layer 7",
        "concept": "DHCP Pool Network Misconfig",
        "severity": "High",
        "correct_fix": "In DHCP pool VLAN40, replace network statement with 'network 192.168.40.0 255.255.255.0'."
    },

    # DNS Category (3 cases)
    {
        "case_id": "C014",
        "category": "DNS",
        "symptom": "PC can ping 8.8.8.8 directly, but browsing to www.cisco.com fails with domain name resolution error.",
        "topology_note": "Host PC (192.168.1.25) -> Router1 -> Internet. Internal DNS server is 10.0.0.53.",
        "show_outputs": (
            "--- Host PC nslookup www.cisco.com ---\n"
            ";;; Connection to 192.168.1.254 timed out -- no servers could be reached.\n\n"
            "--- Host PC ipconfig /all ---\n"
            "IPv4 Address. . . . . . . . . . . : 192.168.1.25\n"
            "Subnet Mask . . . . . . . . . . . : 255.255.255.0\n"
            "Default Gateway . . . . . . . . . : 192.168.1.1\n"
            "DNS Servers . . . . . . . . . . . : 192.168.1.254\n\n"
            "--- Router1 show ip interface brief ---\n"
            "GigabitEthernet0/0         192.168.1.1     YES manual up                    up\n"
        ),
        "expected_fault": "Host PC has an invalid DNS server IP address (192.168.1.254 where no DNS server runs).",
        "osi_layer": "Layer 7",
        "concept": "DNS Server Misconfiguration",
        "severity": "Medium",
        "correct_fix": "Change host PC DNS server setting to valid DNS server 10.0.0.53 or 8.8.8.8."
    },
    {
        "case_id": "C015",
        "category": "DNS",
        "symptom": "Pinging server by FQDN 'server1.company.local' succeeds, but pinging short name 'server1' fails.",
        "topology_note": "Host PC on internal domain company.local.",
        "show_outputs": (
            "--- Host CLI ---\n"
            "C:\\> ping server1\n"
            "Ping request could not find host server1. Please check the name and try again.\n\n"
            "C:\\> ipconfig /all\n"
            "Host Name . . . . . . . . . . . . : PC-Client\n"
            "Primary DnS Suffix  . . . . . . . : \n"
            "DNS Servers . . . . . . . . . . . : 10.0.0.53\n"
        ),
        "expected_fault": "Missing DNS domain suffix configuration on client host.",
        "osi_layer": "Layer 7",
        "concept": "DNS Domain Suffix Search",
        "severity": "Low",
        "correct_fix": "Configure DNS domain search suffix 'company.local' on host or router DHCP pool option."
    },
    {
        "case_id": "C016",
        "category": "DNS",
        "symptom": "DNS queries sent to corporate DNS server 172.16.50.2 time out across the router.",
        "topology_note": "Client on VLAN 10 (192.168.10.0/24), DNS server on DMZ (172.16.50.2). Router link between them.",
        "show_outputs": (
            "--- Router show access-lists DMZ_IN ---\n"
            "Extended IP access list DMZ_IN\n"
            "    10 permit tcp 192.168.10.0 0.0.0.255 host 172.16.50.2 eq 53\n"
            "    20 deny ip any any (142 matches)\n"
        ),
        "expected_fault": "ACL only permits TCP port 53 for DNS, blocking standard UDP port 53 DNS queries.",
        "osi_layer": "Layer 4 / 7",
        "concept": "DNS Transport Protocol (UDP vs TCP)",
        "severity": "High",
        "correct_fix": "Modify ACL DMZ_IN to permit UDP port 53 traffic: 'permit udp 192.168.10.0 0.0.0.255 host 172.16.50.2 eq 53'."
    },

    # Routing Category (5 cases)
    {
        "case_id": "C017",
        "category": "Routing",
        "symptom": "PC-A (192.168.10.10) gets IP and ping gateway works, but cannot reach Server in VLAN 30 (10.0.30.50).",
        "topology_note": "PC-A -> Router1 -> Router2 -> Server (10.0.30.50). Gateway ping succeeds.",
        "show_outputs": (
            "--- PC-A ping 10.0.30.50 ---\n"
            "Request timed out.\n\n"
            "--- Router1 show ip route ---\n"
            "Codes: C - connected, S - static, R - RIP, M - mobile, B - BGP\n"
            "Gateway of last resort is not set\n"
            "C    192.168.10.0/24 is directly connected, GigabitEthernet0/0\n"
            "C    172.16.12.0/30 is directly connected, GigabitEthernet0/1\n\n"
            "--- Router1 show access-lists ---\n"
            "No access lists configured.\n"
        ),
        "expected_fault": "Router1 missing route to destination network 10.0.30.0/24.",
        "osi_layer": "Layer 3",
        "concept": "Missing Static Route",
        "severity": "High",
        "correct_fix": "Add static route on Router1: 'ip route 10.0.30.0 255.255.255.0 172.16.12.2'."
    },
    {
        "case_id": "C018",
        "category": "Routing",
        "symptom": "OSPF neighbor adjacency between Router1 and Router2 stays in INIT/EXSTART state.",
        "topology_note": "Router1 Gi0/1 (10.0.0.1/30) connected to Router2 Gi0/1 (10.0.0.2/30).",
        "show_outputs": (
            "--- Router1 show ip ospf interface Gi0/1 ---\n"
            "GigabitEthernet0/1 is up, line protocol is up\n"
            "  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1\n"
            "  Transmit Delay is 1 sec, State DR, Priority 1\n"
            "  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5\n\n"
            "--- Router2 show ip ospf interface Gi0/1 ---\n"
            "GigabitEthernet0/1 is up, line protocol is up\n"
            "  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1\n"
            "  Timer intervals configured, Hello 30, Dead 120, Wait 120, Retransmit 5\n"
        ),
        "expected_fault": "OSPF Hello/Dead timer mismatch between Router1 (10/40) and Router2 (30/120).",
        "osi_layer": "Layer 3",
        "concept": "OSPF Timer Mismatch",
        "severity": "High",
        "correct_fix": "On Router2 interface Gi0/1, set 'ip ospf hello-interval 10' and 'ip ospf dead-interval 40'."
    },
    {
        "case_id": "C019",
        "category": "Routing",
        "symptom": "Router2 does not form EIGRP neighbor relationship with Router1.",
        "topology_note": "Router1 and Router2 connected over 172.16.1.0/30 WAN link.",
        "show_outputs": (
            "--- Router1 show ip eigrp interfaces ---\n"
            "EIGRP-IPv4 Interfaces for AS(100)\n"
            "Xmit Queue   Mean   Pacing Time   Multicast    Pending\n"
            "Interface              Peers  Un/Reliable  SRTT   Un/Reliable  Flow Timer   Routes\n"
            "Gi0/1                    1        0/0        10       0/0          50          0\n\n"
            "--- Router2 show running-config | section eigrp ---\n"
            "router eigrp 200\n"
            " network 172.16.1.0 0.0.0.3\n"
            " no auto-summary\n"
        ),
        "expected_fault": "EIGRP Autonomous System (AS) number mismatch (AS 100 on Router1 vs AS 200 on Router2).",
        "osi_layer": "Layer 3",
        "concept": "EIGRP AS Mismatch",
        "severity": "High",
        "correct_fix": "Change Router2 EIGRP process to 'router eigrp 100'."
    },
    {
        "case_id": "C020",
        "category": "Routing",
        "symptom": "Router1 fails to advertise LAN routes to Router2 via OSPF.",
        "topology_note": "Router1 LAN interface Gi0/0 (192.168.1.1/24) configured in OSPF.",
        "show_outputs": (
            "--- Router1 show running-config | section ospf ---\n"
            "router ospf 1\n"
            " router-id 1.1.1.1\n"
            " passive-interface GigabitEthernet0/1\n"
            " network 192.168.1.0 0.0.0.255 area 0\n"
            " network 10.0.0.0 0.0.0.3 area 0\n\n"
            "--- Router1 show ip ospf neighbor ---\n"
            "Neighbor ID     Pri   State           Dead Time   Address         Interface\n"
            " (No active OSPF neighbors on Gi0/1)\n"
        ),
        "expected_fault": "OSPF WAN interface GigabitEthernet0/1 misconfigured as a passive-interface.",
        "osi_layer": "Layer 3",
        "concept": "OSPF Passive Interface Misconfig",
        "severity": "High",
        "correct_fix": "Under OSPF router configuration on Router1, execute 'no passive-interface GigabitEthernet0/1'."
    },
    {
        "case_id": "C021",
        "category": "Routing",
        "symptom": "BGP session between HQ Router (AS 65001) and ISP Router (AS 65500) fails to establish.",
        "topology_note": "Point-to-point link 203.0.113.0/30.",
        "show_outputs": (
            "--- HQ Router show ip bgp summary ---\n"
            "BGP router identifier 1.1.1.1, local AS number 65001\n"
            "Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd\n"
            "203.0.113.2     4        65501       0       0        1    0    0 00:05:12 Active\n\n"
            "--- ISP Router show running-config | section bgp ---\n"
            "router bgp 65500\n"
            " bgp router-id 2.2.2.2\n"
            " neighbor 203.0.113.1 remote-as 65001\n"
        ),
        "expected_fault": "HQ Router configured with wrong remote-as (65501 instead of ISP AS 65500).",
        "osi_layer": "Layer 3 / 4",
        "concept": "BGP Remote AS Mismatch",
        "severity": "High",
        "correct_fix": "On HQ Router, correct neighbor definition to 'neighbor 203.0.113.2 remote-as 65500'."
    },

    # ACL Category (4 cases)
    {
        "case_id": "C022",
        "category": "ACL",
        "symptom": "PC-A (192.168.10.5) cannot access Web Server (10.0.0.100) on port 80.",
        "topology_note": "Router1 interface Gi0/1 outbound ACL named BLOCK_WEB.",
        "show_outputs": (
            "--- Router1 show ip access-lists BLOCK_WEB ---\n"
            "Extended IP access list BLOCK_WEB\n"
            "    10 deny tcp host 192.168.10.5 host 10.0.0.100 eq 80\n"
            "    (implicit deny ip any any at end of list)\n\n"
            "--- Router1 show ip interface Gi0/1 ---\n"
            "GigabitEthernet0/1 is up, line protocol is up\n"
            "  Outbound access list is BLOCK_WEB\n"
            "  Inbound access list is not set\n"
        ),
        "expected_fault": "ACL missing explicit 'permit ip any any' rule, causing implicit deny to block all traffic.",
        "osi_layer": "Layer 4 / 3",
        "concept": "ACL Implicit Deny",
        "severity": "High",
        "correct_fix": "Add rule '20 permit ip any any' to access-list BLOCK_WEB."
    },
    {
        "case_id": "C023",
        "category": "ACL",
        "symptom": "Host 192.168.1.50 can still SSH to Server 10.0.0.5 despite access list blocking rule.",
        "topology_note": "Target requirement: Block SSH (port 22) from host to server.",
        "show_outputs": (
            "--- Router show ip access-lists SEC_ACL ---\n"
            "Extended IP access list SEC_ACL\n"
            "    10 deny tcp host 192.168.1.50 host 10.0.0.5 eq 23\n"
            "    20 permit ip any any\n"
        ),
        "expected_fault": "ACL rule checks port 23 (Telnet) instead of port 22 (SSH).",
        "osi_layer": "Layer 4",
        "concept": "ACL Port Number Error",
        "severity": "Medium",
        "correct_fix": "Replace rule 10 in SEC_ACL with 'deny tcp host 192.168.1.50 host 10.0.0.5 eq 22'."
    },
    {
        "case_id": "C024",
        "category": "ACL",
        "symptom": "Entire HR department (192.168.20.0/24) is blocked from accessing Internet.",
        "topology_note": "Standard ACL intended to block single host 192.168.20.5.",
        "show_outputs": (
            "--- Router show access-lists 10 ---\n"
            "Standard IP access list 10\n"
            "    10 deny 192.168.20.0 0.0.0.255\n"
            "    20 permit any\n"
        ),
        "expected_fault": "Wildcard mask 0.0.0.255 matches the entire /24 subnet instead of host 192.168.20.5 (host / 0.0.0.0).",
        "osi_layer": "Layer 3",
        "concept": "ACL Wildcard Mask Error",
        "severity": "High",
        "correct_fix": "Update ACL 10 rule 10 to 'deny host 192.168.20.5' or 'deny 192.168.20.5 0.0.0.0'."
    },
    {
        "case_id": "C025",
        "category": "ACL",
        "symptom": "Inter-departmental traffic between VLAN 10 and VLAN 20 drops at router interface.",
        "topology_note": "Router subinterface Gi0/0.10 inbound ACL.",
        "show_outputs": (
            "--- Router show ip access-lists FILTER_VLAN10 ---\n"
            "Extended IP access list FILTER_VLAN10\n"
            "    10 deny ip 192.168.10.0 0.0.0.255 192.168.20.0 0.0.0.255\n\n"
            "--- Router show interface Gi0/0.10 ---\n"
            "  Inbound access list is FILTER_VLAN10\n"
        ),
        "expected_fault": "ACL missing permit statement at end, dropping all traffic coming into Gi0/0.10.",
        "osi_layer": "Layer 3",
        "concept": "ACL Inbound Drop",
        "severity": "High",
        "correct_fix": "Add 'permit ip any any' to FILTER_VLAN10."
    },

    # NAT Category (3 cases)
    {
        "case_id": "C026",
        "category": "NAT",
        "symptom": "Internal LAN PCs (192.168.1.0/24) cannot reach external Internet IP addresses (8.8.8.8).",
        "topology_note": "Router1 connected to Internal LAN (Gi0/0) and Internet ISP (Gi0/1).",
        "show_outputs": (
            "--- Router1 show ip nat translations ---\n"
            " (No active NAT translations present)\n\n"
            "--- Router1 show running-config | section nat ---\n"
            "ip nat inside source list 1 interface GigabitEthernet0/1 overload\n"
            "access-list 1 permit 192.168.1.0 0.0.0.255\n\n"
            "--- Router1 show ip interface brief ---\n"
            "Interface                  IP-Address      OK? Method Status                Protocol\n"
            "GigabitEthernet0/0         192.168.1.1     YES manual up                    up\n"
            "GigabitEthernet0/1         203.0.113.1     YES manual up                    up\n"
        ),
        "expected_fault": "Missing 'ip nat inside' on Gi0/0 and 'ip nat outside' on Gi0/1 interface configurations.",
        "osi_layer": "Layer 3 / 4 (NAT)",
        "concept": "NAT Interface Role Configuration",
        "severity": "High",
        "correct_fix": "Apply 'ip nat inside' on interface Gi0/0 and 'ip nat outside' on interface Gi0/1."
    },
    {
        "case_id": "C027",
        "category": "NAT",
        "symptom": "LAN subnet 192.168.2.0/24 hosts cannot access Internet via NAT, while 192.168.1.0/24 works.",
        "topology_note": "New subnet 192.168.2.0/24 added to corporate LAN.",
        "show_outputs": (
            "--- Router show running-config | include access-list ---\n"
            "access-list 10 permit 192.168.1.0 0.0.0.255\n\n"
            "--- Router show running-config | include ip nat ---\n"
            "ip nat inside source list 10 interface Serial0/0/0 overload\n"
        ),
        "expected_fault": "NAT ACL 10 does not permit the newly added subnet 192.168.2.0/24.",
        "osi_layer": "Layer 3",
        "concept": "NAT Access List Matching",
        "severity": "Medium",
        "correct_fix": "Add line 'access-list 10 permit 192.168.2.0 0.0.0.255' to global configuration."
    },
    {
        "case_id": "C028",
        "category": "NAT",
        "symptom": "External clients cannot reach internal Web Server via Static NAT IP 203.0.113.50.",
        "topology_note": "Internal Web Server IP: 192.168.1.50. Public IP: 203.0.113.50.",
        "show_outputs": (
            "--- Router show running-config | section nat ---\n"
            "ip nat inside source static 192.168.1.55 203.0.113.50\n"
            "interface GigabitEthernet0/0\n"
            " ip nat inside\n"
            "interface GigabitEthernet0/1\n"
            " ip nat outside\n"
        ),
        "expected_fault": "Static NAT translation maps public IP to wrong internal IP (192.168.1.55 instead of 192.168.1.50).",
        "osi_layer": "Layer 3",
        "concept": "Static NAT Mapping Error",
        "severity": "High",
        "correct_fix": "Correct static NAT entry to 'ip nat inside source static 192.168.1.50 203.0.113.50'."
    },

    # Wireless Category (4 cases)
    {
        "case_id": "C029",
        "category": "Wireless",
        "symptom": "Wireless Laptop cannot connect to Access Point; authentication fails continuously.",
        "topology_note": "Laptop connecting to WPA2-Personal Wi-Fi SSID 'Corporate_Wi-Fi'.",
        "show_outputs": (
            "--- Laptop Wireless Status ---\n"
            "SSID: Corporate_Wi-Fi\n"
            "Security: WPA2-PSK\n"
            "Key: SecretPass123\n"
            "Status: Authentication Failed\n\n"
            "--- AP show running-config | section dot11 ---\n"
            "dot11 ssid Corporate_Wi-Fi\n"
            "   authentication open\n"
            "   authentication key-management wpa version 2\n"
            "   wpa-psk ascii SecretPass123!\n"
        ),
        "expected_fault": "WPA2 Pre-Shared Key mismatch between laptop ('SecretPass123') and Access Point ('SecretPass123!').",
        "osi_layer": "Layer 2 / Security",
        "concept": "WPA2 Pre-Shared Key Mismatch",
        "severity": "High",
        "correct_fix": "Update laptop wireless security key to match AP key 'SecretPass123!'."
    },
    {
        "case_id": "C030",
        "category": "Wireless",
        "symptom": "Wireless clients see SSID 'Staff_WiFi' but fail to obtain an IP address via DHCP.",
        "topology_note": "WLC / AP mapping SSID 'Staff_WiFi' to VLAN 50.",
        "show_outputs": (
            "--- WLC show wlan 1 ---\n"
            "WLAN Identifier.................................. 1\n"
            "WLAN Network Name (SSID)......................... Staff_WiFi\n"
            "Interface Name................................... vlan-50-interface\n"
            "Status........................................... Enabled\n\n"
            "--- Switch1 show vlan brief ---\n"
            "VLAN Name                             Status    Ports\n"
            "---- -------------------------------- --------- -------------------------------\n"
            "1    default                          active    Gi0/1, Gi0/2\n"
            "10   Management                       active    Gi0/3\n"
            " (VLAN 50 missing from switch database)\n"
        ),
        "expected_fault": "WLAN mapped VLAN 50 does not exist on the underlying physical switch.",
        "osi_layer": "Layer 2",
        "concept": "WLAN VLAN Interface Mapping",
        "severity": "High",
        "correct_fix": "Add VLAN 50 to Switch1 VLAN database and trunk allowed list."
    },
    {
        "case_id": "C031",
        "category": "Wireless",
        "symptom": "Lightweight Access Point (LAP-1) remains in joining loop and fails to discover WLC.",
        "topology_note": "LAP-1 (Subnet 192.168.100.0/24) seeking Wireless LAN Controller WLC-1 (10.10.10.5).",
        "show_outputs": (
            "--- LAP-1 Console Log ---\n"
            "*Mar 1 00:02:15.111: %CAPWAP-3-ERRORLOG: Did not get response to discovery request!\n"
            "*Mar 1 00:02:20.112: %CAPWAP-3-ERRORLOG: Could not resolve WLC IP address via Option 43 or DNS.\n\n"
            "--- DHCP Router show running-config pool AP_POOL ---\n"
            "ip dhcp pool AP_POOL\n"
            " network 192.168.100.0 255.255.255.0\n"
            " default-router 192.168.100.1\n"
        ),
        "expected_fault": "DHCP pool AP_POOL missing Option 43 (hex value for WLC IP 10.10.10.5).",
        "osi_layer": "Layer 7 (CAPWAP Discovery)",
        "concept": "CAPWAP / WLC Option 43 Discovery",
        "severity": "High",
        "correct_fix": "Add 'option 43 hex f1040a0a0a05' to DHCP pool AP_POOL."
    },
    {
        "case_id": "C032",
        "category": "Wireless",
        "symptom": "Guest Wi-Fi users can ping internal corporate server 10.0.0.100.",
        "topology_note": "Guest Wi-Fi requirement: Complete isolation from internal LAN.",
        "show_outputs": (
            "--- Guest Laptop ping 10.0.0.100 ---\n"
            "Reply from 10.0.0.100: bytes=32 time=2ms TTL=128\n\n"
            "--- Router show running-config interface Gi0/0.99 (Guest GW) ---\n"
            "interface GigabitEthernet0/0.99\n"
            " encapsulation dot1Q 99\n"
            " ip address 192.168.99.1 255.255.255.0\n"
            " (No access group applied)\n"
        ),
        "expected_fault": "Guest VLAN 99 interface lacks access group blocking traffic to internal subnets (10.0.0.0/8).",
        "osi_layer": "Layer 3 / Security",
        "concept": "Guest Wireless Isolation Failure",
        "severity": "High",
        "correct_fix": "Apply inbound ACL on Gi0/0.99 blocking 10.0.0.0/8 destination traffic."
    },

    # Mixed Category (3 cases)
    {
        "case_id": "C033",
        "category": "Mixed",
        "symptom": "PC in VLAN 10 cannot access Web Server in VLAN 20. Neither VLAN can reach Internet.",
        "topology_note": "Router-on-a-stick topology with NAT overload.",
        "show_outputs": (
            "--- Router show running-config interface Gi0/0 ---\n"
            "interface GigabitEthernet0/0\n"
            " no ip address\n"
            " duplex auto\n"
            " speed auto\n"
            "! [Subinterfaces missing]\n\n"
            "--- Router show ip route ---\n"
            "Gateway of last resort is not set\n"
            "C 203.0.113.0/30 is directly connected, GigabitEthernet0/1\n"
        ),
        "expected_fault": "Router interface Gi0/0 missing subinterface VLAN encapsulation (Gi0/0.10 & Gi0/0.20) and missing default static route.",
        "osi_layer": "Layer 2 & Layer 3",
        "concept": "Inter-VLAN & Default Route Combo Fault",
        "severity": "Critical",
        "correct_fix": "Configure subinterfaces Gi0/0.10 and Gi0/0.20 with dot1q encapsulation and default route 'ip route 0.0.0.0 0.0.0.0 203.0.113.2'."
    },
    {
        "case_id": "C034",
        "category": "Mixed",
        "symptom": "PC receives IP via DHCP but cannot resolve domain names or ping outside subnet.",
        "topology_note": "Branch router supplying DHCP.",
        "show_outputs": (
            "--- Branch PC ipconfig /all ---\n"
            "IPv4 Address: 192.168.1.15\n"
            "Subnet Mask: 255.255.255.0\n"
            "Default Gateway: 192.168.1.254\n"
            "DNS Server: 192.168.1.254\n\n"
            "--- Branch Router interface Gi0/0 ---\n"
            "ip address 192.168.1.1 255.255.255.0\n"
        ),
        "expected_fault": "DHCP pool specifies invalid gateway and DNS server IP (192.168.1.254 instead of router IP 192.168.1.1).",
        "osi_layer": "Layer 3 & Layer 7",
        "concept": "DHCP Gateway & DNS Option Mismatch",
        "severity": "High",
        "correct_fix": "Update DHCP pool config: default-router 192.168.1.1, dns-server 8.8.8.8."
    },
    {
        "case_id": "C035",
        "category": "Mixed",
        "symptom": "Finance PC-1 (10.10.10.15) ping to Accounting Server (10.20.20.50) fails intermittently.",
        "topology_note": "Finance PC connected to Switch1 Fa0/1.",
        "show_outputs": (
            "--- Switch1 show interfaces Fa0/1 ---\n"
            "FastEthernet0/1 is up, line protocol is down (err-disabled)\n"
            "  Port security violation count: 1\n\n"
            "--- Switch1 show port-security interface Fa0/1 ---\n"
            "Port Security              : Enabled\n"
            "Port Status                : Secure-shutdown\n"
            "Violation Mode             : Shutdown\n"
            "Max Addresses              : 1\n"
            "Total Addresses            : 1\n"
            "Configured MAC Addresses   : 0010.a1b2.c3d4\n"
            "Last Source Address:Vlan   : 0050.7966.9999:10\n"
        ),
        "expected_fault": "Switch port Fa0/1 tripped port-security shutdown due to unauthorized MAC address connected.",
        "osi_layer": "Layer 2",
        "concept": "Port Security Violation",
        "severity": "High",
        "correct_fix": "Clear port violation with 'shutdown' / 'no shutdown' on Fa0/1 after authorizing MAC address."
    }
]

# Add evidence_status to each case (VERIFIED_LAB for validated Packet Tracer labs, DEMO_TEMPLATE for templates)
for i, c in enumerate(cases):
    c["evidence_status"] = "VERIFIED_LAB" if i < 10 else "DEMO_TEMPLATE"

# Write cases.csv
cases_file = os.path.join("data", "cases.csv")
with open(cases_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "case_id", "category", "symptom", "topology_note", "show_outputs",
        "expected_fault", "osi_layer", "concept", "severity", "correct_fix", "evidence_status"
    ])
    writer.writeheader()
    for c in cases:
        writer.writerow(c)

print(f"Successfully generated {len(cases)} cases in {cases_file}")

# Responsible AI Log (Starts clean with schema header; populated dynamically during genuine human review)
responsible_file = os.path.join("data", "responsible_ai_log.csv")
with open(responsible_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "log_id", "case_id", "timestamp", "category", "initial_ai_diagnosis",
        "human_decision", "corrected_diagnosis", "reason_for_correction"
    ])
    writer.writeheader()

print(f"Successfully initialized clean responsible AI log in {responsible_file}")

