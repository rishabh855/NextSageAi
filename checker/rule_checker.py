import re
from typing import List, Optional, Dict, Any
from checker.fact_extractor import FactExtractor, FactContext
from checker.rule_contracts import (
    RuleStatus, RuleResult, BaseRule,
    InterfaceStatusRule, DHCPRelayRule, DHCPOptionAndPoolRule,
    NativeVlanMismatchRule, VlanDatabaseRule, DuplicateIPRule,
    SubnetMaskRule, GatewayMismatchRule, MissingRouteRule,
    RoutingProtocolFaultRule, ACLFaultRule, NATAndServicesRule
)

class RuleChecker:
    """
    Fact-based, prioritized Rule Engine for Cisco network configurations and host evidence.
    Executes evidence normalization, applicability/suppression checks, and minimum evidence thresholds.
    """

    def __init__(self):
        self.rules: List[BaseRule] = [
            InterfaceStatusRule(),
            DHCPRelayRule(),
            DHCPOptionAndPoolRule(),
            NativeVlanMismatchRule(),
            VlanDatabaseRule(),
            DuplicateIPRule(),
            SubnetMaskRule(),
            GatewayMismatchRule(),
            MissingRouteRule(),
            RoutingProtocolFaultRule(),
            ACLFaultRule(),
            NATAndServicesRule()
        ]

    def evaluate_all_rules(self, evidence: str) -> Dict[str, Any]:
        facts = FactExtractor.extract(evidence)

        failed_results: List[RuleResult] = []
        pending_results: List[RuleResult] = []
        suppressed_results: List[RuleResult] = []
        passed_results: List[RuleResult] = []

        for rule in self.rules:
            result = rule.evaluate(facts)
            if result.status == RuleStatus.FAIL:
                failed_results.append(result)
            elif result.status == RuleStatus.NEED_MORE_EVIDENCE:
                pending_results.append(result)
            elif result.status == RuleStatus.SUPPRESSED:
                suppressed_results.append(result)
            elif result.status == RuleStatus.PASS:
                passed_results.append(result)

        # Sort failed results by priority (ascending: 1 = highest)
        failed_results.sort(key=lambda r: r.priority)

        primary_failure = failed_results[0] if failed_results else None
        secondary_findings = failed_results[1:] if len(failed_results) > 1 else []

        return {
            "primary_failure": primary_failure,
            "secondary_findings": secondary_findings,
            "pending_evidence_rules": pending_results,
            "suppressed_rules": suppressed_results,
            "passed_rules": passed_results,
            "facts": facts
        }

    def run_all_checks(self, evidence: str) -> List[Dict[str, Any]]:
        """
        Backward-compatible interface for test suite & session manager.
        """
        facts = FactExtractor.extract(evidence)
        output = []

        for rule in self.rules:
            res = rule.evaluate(facts)
            status_str = "FAIL" if res.status == RuleStatus.FAIL else "PASS"
            output.append({
                "check_name": res.check_name,
                "status": status_str,
                "details": res.details
            })

        return output

    # Direct legacy method delegators for granular unit tests
    def check_duplicate_ip(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = DuplicateIPRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_subnet_mask(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = SubnetMaskRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_gateway_mismatch(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = GatewayMismatchRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_interface_down(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = InterfaceStatusRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_missing_vlan(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = VlanDatabaseRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_native_vlan_mismatch(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = NativeVlanMismatchRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_missing_route(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = MissingRouteRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_routing_protocol_fault(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = RoutingProtocolFaultRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_dhcp_fault(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = DHCPRelayRule().evaluate(facts)
        if res.status == RuleStatus.FAIL:
            return {"check_name": res.check_name, "status": "FAIL", "details": res.details}
        res2 = DHCPOptionAndPoolRule().evaluate(facts)
        return {"check_name": res2.check_name, "status": "FAIL" if res2.status == RuleStatus.FAIL else "PASS", "details": res2.details}

    def check_acl_fault(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = ACLFaultRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}

    def check_nat_and_services_fault(self, evidence: str) -> dict:
        facts = FactExtractor.extract(evidence)
        res = NATAndServicesRule().evaluate(facts)
        return {"check_name": res.check_name, "status": "FAIL" if res.status == RuleStatus.FAIL else "PASS", "details": res.details}
