import sys, os, csv
sys.path.insert(0, os.getcwd())

from checker.fact_extractor import FactExtractor

cases_path = os.path.join("data", "cases.csv")
with open(cases_path, "r", encoding="utf-8") as f:
    cases = {c["case_id"]: c["show_outputs"] for c in csv.DictReader(f)}

print("=== C003 Raw Sections ===")
sections = FactExtractor._parse_device_sections(cases["C003"])
for dev, cmd, content in sections:
    print(f"Dev: {dev} | Cmd: {cmd}")
    print("Content snippet:", repr(content[:100]))

print("\n=== C001 Raw Sections ===")
sections1 = FactExtractor._parse_device_sections(cases["C001"])
for dev, cmd, content in sections1:
    print(f"Dev: {dev} | Cmd: {cmd}")
    print("Content snippet:", repr(content[:100]))
