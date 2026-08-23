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
│   └── responsible_ai_log.csv   # Dynamic log recording genuine human reviews (Accept/Edit/Reject)
├── checker/
│   ├── rule_checker.py          # Deterministic Python network check engine
│   └── test_rule_checker.py     # Unit test suite
├── ai/                          # AI Engine (Milestone 4)
├── prompts/                     # Structured AI prompt templates & worked examples (Milestone 4)
├── dashboard/                   # Streamlit web interface (Milestone 6)
├── packet_tracer/               # Base Packet Tracer topologies & guides (Milestone 5)
├── scripts/
│   └── generate_dataset.py      # Dataset generation script
├── requirements.txt             # Project Python dependencies
└── README.md                    # Project documentation
```

---

## 🚀 Quickstart & Verification

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Deterministic Rule Checker Tests
```bash
python -m unittest discover -s checker
```

---

## 🛣️ Milestone Roadmap

- [x] **Milestone 1**: Project Skeleton & Architecture Setup
- [x] **Milestone 2**: Dataset & Evidence Management (`data/cases.csv` + `evidence_status`)
- [x] **Milestone 3**: Deterministic Rule Checker Engine & Unit Tests (`checker/`)
- [ ] **Milestone 4**: AI Diagnosis Engine & Structured Prompts (`ai/`, `prompts/`)
- [ ] **Milestone 5**: Human Review & Responsible AI Logger (`data/responsible_ai_log.csv`)
- [ ] **Milestone 6**: Fix & Verification Workflow + Streamlit Dashboard (`dashboard/app.py`)
- [ ] **Milestone 7**: End-to-End Verification & Verification Walkthrough
