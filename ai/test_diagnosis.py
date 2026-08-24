import os
import unittest
from ai.diagnosis import AIDiagnosisEngine

class TestAIDiagnosisEngine(unittest.TestCase):
    def setUp(self):
        self.sample_case = {
            "case_id": "C001",
            "category": "VLAN",
            "symptom": "PC-A in VLAN 10 cannot ping PC-B in VLAN 10 connected to Switch 2.",
            "topology_note": "PC-A -> Switch1 -> Switch2 -> PC-B",
            "show_outputs": "Switch1 active VLANs: 1,10,20\nSwitch2 allowed VLANs: 1,20,30",
            "expected_fault": "VLAN 10 is pruned/disallowed on Switch2 trunk interface Gi0/1.",
            "osi_layer": "Layer 2",
            "concept": "VLAN Trunking / Pruning",
            "severity": "High",
            "correct_fix": "On Switch2 interface Gi0/1, execute 'switchport trunk allowed vlan add 10'.",
            "evidence_status": "VERIFIED_LAB"
        }
        self.sample_rule_results = [
            {
                "check_name": "VLAN Trunking Check",
                "status": "FAIL",
                "details": "VLAN pruning mismatch: VLAN 10 active on Switch1 trunk but not allowed/active on Switch2."
            }
        ]

    def test_schema_validation_valid(self):
        engine = AIDiagnosisEngine()
        valid_data = {
            "root_cause": "VLAN 10 pruned on trunk",
            "confidence": "High",
            "evidence": ["Switch2 show interfaces trunk missing VLAN 10"],
            "next_command": "show interfaces trunk",
            "fix_steps": ["switchport trunk allowed vlan add 10"],
            "osi_layer": "Layer 2",
            "concept": "VLAN Trunking / Pruning"
        }
        self.assertTrue(engine.validate_schema(valid_data))

    def test_schema_validation_invalid_confidence(self):
        engine = AIDiagnosisEngine()
        invalid_data = {
            "root_cause": "VLAN 10 pruned",
            "confidence": "Very High",  # Invalid confidence value
            "evidence": ["Missing VLAN 10"],
            "next_command": "show interfaces trunk",
            "fix_steps": ["fix"],
            "osi_layer": "Layer 2",
            "concept": "VLAN"
        }
        self.assertFalse(engine.validate_schema(invalid_data))

    def test_schema_validation_missing_key(self):
        engine = AIDiagnosisEngine()
        missing_key_data = {
            "root_cause": "VLAN 10 pruned",
            "confidence": "High",
            # Missing "evidence" key
            "next_command": "show interfaces trunk",
            "fix_steps": ["fix"],
            "osi_layer": "Layer 2",
            "concept": "VLAN"
        }
        self.assertFalse(engine.validate_schema(missing_key_data))

    def test_parse_llm_response_with_markdown_fences(self):
        engine = AIDiagnosisEngine()
        raw_text = """```json
        {
          "root_cause": "Missing static route to 10.0.30.0/24",
          "confidence": "High",
          "evidence": ["show ip route missing 10.0.30.0/24"],
          "next_command": "show ip route",
          "fix_steps": ["ip route 10.0.30.0 255.255.255.0 172.16.12.2"],
          "osi_layer": "Layer 3",
          "concept": "Missing Static Route"
        }
        ```"""
        parsed = engine.parse_llm_response(raw_text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["confidence"], "High")

    def test_parse_llm_response_malformed_json(self):
        engine = AIDiagnosisEngine()
        raw_text = "This is not a JSON object { root_cause: broken }"
        parsed = engine.parse_llm_response(raw_text)
        self.assertIsNone(parsed)

    def test_missing_api_key_triggers_offline_fallback(self):
        # Ensure API key is None
        engine = AIDiagnosisEngine(api_key=None)
        res = engine.diagnose(self.sample_case, self.sample_rule_results)
        self.assertEqual(res["ai_mode"], "Offline Demo")
        self.assertIn(res["confidence"], ["High", "Medium", "Low"])
        self.assertTrue(engine.validate_schema(res))

    def test_offline_fallback_deterministic_output(self):
        engine = AIDiagnosisEngine(api_key=None)
        res = engine.diagnose_offline(self.sample_case, self.sample_rule_results)
        self.assertEqual(res["ai_mode"], "Offline Demo")
        self.assertEqual(res["confidence"], "High")
        self.assertIn("Rule check failure", res["root_cause"])

    def test_insufficient_evidence_handling(self):
        engine = AIDiagnosisEngine(api_key=None)
        empty_case = {
            "case_id": "C999",
            "category": "Routing",
            "symptom": "Ping fails",
            "topology_note": "Host -> Router",
            "show_outputs": "",  # Missing evidence
            "expected_fault": "Unknown",
            "osi_layer": "Layer 3",
            "concept": "Routing",
            "correct_fix": "Investigate router"
        }
        res = engine.diagnose_offline(empty_case, [])
        self.assertEqual(res["confidence"], "Low")
        self.assertIn("Insufficient", res["root_cause"])
        self.assertEqual(res["next_command"], "show ip route")

    def test_evidence_grounding_no_invented_claims(self):
        engine = AIDiagnosisEngine(api_key=None)
        res = engine.diagnose(self.sample_case, self.sample_rule_results)
        # Verify AI engine never claims to have applied a fix or run a live command
        self.assertNotIn("applied fix", res["root_cause"].lower())
        self.assertNotIn("modified packet tracer", res["root_cause"].lower())
        self.assertTrue(res["ai_mode"].startswith("Gemini") or res["ai_mode"] == "Offline Demo")

if __name__ == "__main__":
    unittest.main()
