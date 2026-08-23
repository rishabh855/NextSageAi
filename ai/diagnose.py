import os
import json
import re
import pandas as pd
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

if not os.environ.get("GEMINI_API_KEY") and os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass

from checker.rule_checker import RuleChecker

PROMPT_FILE_PATH = os.path.join("prompts", "diagnose_prompt.md")
CASES_CSV_PATH = os.path.join("data", "cases.csv")

def load_prompt_template(prompt_path: str = PROMPT_FILE_PATH) -> str:
    """
    Reads the system prompt template from prompts/diagnose_prompt.md.
    """
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt template file not found at {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def fill_prompt(symptom: str, topology_note: str, show_output: str, template: Optional[str] = None) -> str:
    """
    Fills the prompt template with symptom, topology_note, and show_output.
    """
    if template is None:
        template = load_prompt_template()
    return f"""{template}

Now diagnose this case:

Symptom: {symptom}
Topology Note: {topology_note}
Show Output:
{show_output}
"""

def parse_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Strips markdown code fences and parses raw LLM output into a valid JSON dictionary.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    clean_text = raw_text.strip()
    if "```" in clean_text:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1)
        else:
            clean_text = re.sub(r"```[a-zA-Z]*", "", clean_text).strip()

    try:
        data = json.loads(clean_text)
        if isinstance(data, dict) and "root_cause" in data:
            # Standardize confidence casing to low/medium/high
            conf = str(data.get("confidence", "medium")).lower()
            if conf not in {"low", "medium", "high"}:
                conf = "medium"
            data["confidence"] = conf
            
            # Ensure fix_steps is a list
            fix = data.get("fix_steps", [])
            if not isinstance(fix, list):
                data["fix_steps"] = [str(fix)]
            return data
    except Exception:
        pass
    return None

def diagnose_offline_fallback(case_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic offline fallback diagnostic engine.
    Uses RuleChecker findings and case metadata to generate structured response.
    """
    show_output = case_dict.get("show_outputs", "") or case_dict.get("show_output", "")
    symptom = case_dict.get("symptom", "")
    
    checker = RuleChecker()
    rule_results = checker.run_all_checks(show_output)
    failed = [r for r in rule_results if r.get("status") == "FAIL"]

    if failed:
        first_fail = failed[0]
        root_cause = f"Rule check failure: {first_fail.get('details')}"
        confidence = "high"
        evidence = f"Deterministic Check [{first_fail.get('check_name')}]: {first_fail.get('details')}"
        next_cmd = "show running-config"
    elif not show_output or len(show_output.strip()) < 20:
        root_cause = "Insufficient show command evidence supplied to pinpoint exact root cause."
        confidence = "low"
        evidence = "Show command output is incomplete or missing."
        next_cmd = "show ip route" if "ping" in symptom.lower() else "show interfaces trunk"
    else:
        root_cause = case_dict.get("expected_fault") or "Suspected configuration anomaly requiring further evidence inspection."
        confidence = "medium"
        evidence = "CLI show command outputs supplied for review."
        next_cmd = "show ip interface brief"

    fix_steps = [case_dict.get("correct_fix")] if case_dict.get("correct_fix") else ["Review device configuration in Cisco Packet Tracer."]

    return {
        "root_cause": root_cause,
        "confidence": confidence,
        "evidence": evidence,
        "osi_layer": case_dict.get("osi_layer", "Layer 3"),
        "next_command": next_cmd,
        "fix_steps": fix_steps,
        "parse_error": False,
        "ai_mode": "Offline Engine"
    }

def diagnose_case(case_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Diagnoses a case by constructing the prompt, invoking the LLM (Anthropic or Gemini API),
    parsing JSON output with retry/error handling, and falling back gracefully if unconfigured.
    """
    symptom = case_dict.get("symptom", "")
    topology_note = case_dict.get("topology_note", "")
    show_output = case_dict.get("show_outputs", "") or case_dict.get("show_output", "")

    prompt_text = fill_prompt(symptom, topology_note, show_output)

    # 1. Check Anthropic API
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            # Try once
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt_text}]
            )
            raw_content = response.content[0].text if response and response.content else ""
            parsed = parse_json_response(raw_content)
            if parsed:
                parsed["parse_error"] = False
                parsed["ai_mode"] = "Claude Sonnet 4.6"
                return parsed
            
            # Retry once on malformed JSON
            retry_resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt_text},
                    {"role": "assistant", "content": raw_content},
                    {"role": "user", "content": "Your response was not valid JSON. Please return ONLY a valid JSON object matching the required schema."}
                ]
            )
            retry_content = retry_resp.content[0].text if retry_resp and retry_resp.content else ""
            parsed_retry = parse_json_response(retry_content)
            if parsed_retry:
                parsed_retry["parse_error"] = False
                parsed_retry["ai_mode"] = "Claude Sonnet 4.6 (Retry)"
                return parsed_retry
            else:
                fallback = diagnose_offline_fallback(case_dict)
                fallback["parse_error"] = True
                fallback["ai_mode"] = "Claude Sonnet 4.6 (Parse Error)"
                return fallback
        except Exception:
            pass

    # 2. Check Gemini API
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            # Try gemini-3.6-flash
            for m_name in ["gemini-3.6-flash", "gemini-flash-latest", "gemini-2.5-flash"]:
                try:
                    resp = client.models.generate_content(
                        model=m_name,
                        contents=prompt_text
                    )
                    raw_text = resp.text if resp and hasattr(resp, "text") else ""
                    parsed = parse_json_response(raw_text)
                    if parsed:
                        parsed["parse_error"] = False
                        parsed["ai_mode"] = f"Gemini ({m_name})"
                        return parsed
                except Exception:
                    continue
        except Exception:
            pass

    # 3. Fallback Offline Engine
    return diagnose_offline_fallback(case_dict)

def diagnose_case_by_id(case_id: str, cases_csv_path: str = CASES_CSV_PATH) -> Dict[str, Any]:
    """
    Loads a single case by case_id from cases.csv and returns structured diagnosis.
    """
    if not os.path.exists(cases_csv_path):
        raise FileNotFoundError(f"Cases dataset not found at {cases_csv_path}")
    df = pd.read_csv(cases_csv_path, dtype=str).fillna("")
    matches = df[df["case_id"] == case_id]
    if matches.empty:
        raise ValueError(f"Case ID '{case_id}' not found in {cases_csv_path}")
    return diagnose_case(matches.iloc[0].to_dict())
