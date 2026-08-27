import pandas as pd

cases_df = pd.read_csv('data/cases.csv')
resp_df = pd.read_csv('data/ai_responses.csv')
merged = pd.merge(cases_df, resp_df, on='case_id')

for idx, r in merged.iterrows():
    cid = r['case_id']
    mode = r.get('ai_mode', '')
    exp = r.get('expected_fault', '')
    ai_cause = r.get('ai_root_cause', '')
    fix = r.get('correct_fix', '')
    ai_steps = r.get('ai_fix_steps', '')
    
    print(f"[{cid}] Mode: {mode}")
    print(f"  EXPECTED: {exp}")
    print(f"  AI CAUSE: {ai_cause}")
    print(f"  FIX CMD : {fix}")
    print(f"  AI STEPS: {ai_steps}")
    print("-" * 80)
