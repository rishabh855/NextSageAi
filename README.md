# NetSage AI — AI-Assisted Cisco Network Troubleshooting

NetSage AI is an AI-assisted network troubleshooting application for Cisco Packet Tracer / lab networks. It accepts symptoms, topology notes, and Cisco `show` command outputs, runs deterministic Python rule checks, requests structured AI diagnoses, and enforces mandatory human review before logging fixes and tracking AI agreement rates.

---

## 🏛️ System Architecture

```text
                  ┌───────────────────┐
                  │       USER        │
                  │  Network Engineer │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │   Troubleshooting │
                  │       Case        │
                  └─────────┬─────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
     ┌─────────────────┐        ┌─────────────────┐
     │ Python Rule     │        │ Network Evidence│
     │ Checker         │        │ / Show Output   │
     └────────┬────────┘        └────────┬────────┘
              │                          │
              └────────────┬─────────────┘
                           ▼
                  ┌───────────────────┐
                  │     AI Engine     │
                  │    Diagnosis      │
                  └─────────┬─────────┘
                            ▼
                  ┌───────────────────┐
                  │  Human Reviewer   │
                  └─────┬────┬────┬───┘
                        │    │    │
                     Accept Edit Reject
                        │    │    │
                        └────┼────┘
                             ▼
                    ┌────────────────┐
                    │ Fix & Verify   │
                    └───────┬────────┘
                            ▼
                    ┌────────────────┐
                    │    Dashboard   │
                    └────────────────┘
```

---

## 📁 Repository Structure

```text
NetSage-AI/
├── data/
│   ├── cases.csv                # 35 troubleshooting cases across 9 categories
│   ├── ai_responses.csv         # Batch AI diagnostic outputs for 35 cases
│   ├── responsible_ai_log.csv   # Dynamic log recording genuine human reviews (Accept/Edit/Reject)
│   └── verification_log.csv    # Manual Packet Tracer fix & verification log
├── checker/
│   ├── rule_checker.py          # Deterministic Python network check engine
│   ├── human_review.py          # CLI / module for human review logging
│   └── test_rule_checker.py     # Unit test suite
├── ai/
│   ├── diagnose.py              # LLM diagnosis engine (Claude Sonnet 4.6 / Gemini / Offline engine)
│   ├── diagnosis.py             # Diagnosis Engine implementation
│   └── run_all_cases.py         # Batch execution script across 35 cases
├── prompts/
│   ├── diagnose_prompt.md       # Structured system prompt with JSON schema
│   └── examples.md              # Worked reference examples (VLAN/ACL, Guest Wi-Fi, Missing Route)
├── dashboard/
│   ├── app.py                   # Streamlit web application (Case Explorer, Guided Assistant, Analytics)
│   ├── session_manager.py       # Interactive session & inventory manager
│   ├── analytics.py             # Dashboard KPI & metrics aggregator
│   └── review_manager.py        # Human review manager
├── packet_tracer/
│   └── cases/                   # Physical Packet Tracer topology labs (C001, C002)
├── scripts/
│   ├── run_batch_diagnosis.py   # Batch execution runner
│   └── verify_pipeline.py       # End-to-end pipeline verification test script
├── requirements.txt             # Project Python dependencies
└── README.md                    # Project documentation
```

---

## 🚀 Quickstart & Verification

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run All Unit Tests
```bash
python -m unittest discover -s . -v
```

### 3. Run End-to-End Pipeline Verification
```bash
python -m scripts.verify_pipeline
```

### 4. Launch Streamlit Dashboard
```bash
python -m streamlit run dashboard/app.py
```

---

## 🛣️ Milestone Roadmap

- [x] **Milestone 1**: Project Skeleton & Architecture Setup
- [x] **Milestone 2**: Dataset & Evidence Management (`data/cases.csv` + `evidence_status`)
- [x] **Milestone 3**: Deterministic Rule Checker Engine & Unit Tests (`checker/`)
- [x] **Milestone 4**: AI Diagnosis Engine & Structured Prompts (`ai/`, `prompts/`, `ai/run_all_cases.py`)
- [x] **Milestone 5**: Human Review & Responsible AI Logger (`checker/human_review.py`, `data/responsible_ai_log.csv`)
- [x] **Milestone 6**: Fix & Verification Workflow + Streamlit Dashboard (`dashboard/app.py`, `data/ai_responses.csv`)
- [x] **Milestone 7**: End-to-End Pipeline Verification (`scripts/verify_pipeline.py`)
