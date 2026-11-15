# AegisOps AI - Testing & Quality Assurance

## 1. Test Suite Architecture
The automated test suite is located in `backend/tests/` and is executed via `pytest`:

```text
backend/tests/
├── test_anomaly_detection.py       # Isolation Forest & Z-Score evaluation
├── test_correlation.py             # Sliding window & cascade alert storm deduplication
├── test_rca.py                     # Dependency graph depth & multi-factor causality
├── test_healing_workflow.py        # Risk classification, recommendations, and execution
├── test_storage_intelligence.py    # Time-to-critical regression, rotation, gzip archival
├── test_knowledge_base.py          # TF-IDF vector similarity matching
└── test_e2e_scenarios.py           # Full end-to-end simulation of all 5 acceptance flows
```

---

## 2. Running Automated Tests

```bash
# Run complete test suite
pytest -v
```

All 16 unit and end-to-end integration tests execute in under 10 seconds on a standard CPU.
