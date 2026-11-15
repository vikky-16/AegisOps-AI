# AegisOps AI — Interactive Demo & Verification Guide

This guide details how to run, demonstrate, and verify all operational scenarios, OpenTelemetry ingestion, Kafka streaming, and autonomous closed-loop self-healing in AegisOps AI.

---

## 🚀 Quick Launch

### 1. Launch All Microservices, Backend & Frontend
```bash
# Start backend, microservices, and React dashboard
python scripts/start_all.py
```

### 2. Access Dashboards & Endpoints
- **React SRE Dashboard**: [http://127.0.0.1:5173](http://127.0.0.1:5173) (or `5174`)
- **FastAPI Central Backend**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI / Swagger**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Platform Health Probe**: [http://127.0.0.1:8000/api/platform/health](http://127.0.0.1:8000/api/platform/health)
- **Kafka / EventBus Health**: [http://127.0.0.1:8000/api/platform/kafka/health](http://127.0.0.1:8000/api/platform/kafka/health)
- **OpenTelemetry Ingestion Health**: [http://127.0.0.1:8000/api/otel/health](http://127.0.0.1:8000/api/otel/health)

---

## 🎮 Interactive Demo Scenarios

### Scenario 1: Behavioral Anomaly & Autonomous Closed-Loop Self-Healing
1. Open the **Demo Center** or **Live Telemetry** page in the UI.
2. Trigger **Scenario 1: Behavioral Latency Shift & Pool Saturation**.
3. Observe the full 23-step autonomous pipeline:
   - Behavioral anomaly is detected (p95 latency shifts > 1500ms with zero initial error logs).
   - Multi-detector engine flags statistical and rate-of-change deviations.
   - Event correlator aggregates downstream cascade alerts into a single deduplicated incident (`INC-...`, Fingerprint: `FP-DATABASE_SERVICE-...`).
   - Ranked Root Cause Analysis identifies `database-service` as root cause (#1 rank, 94% confidence).
   - Blast Radius calculates downstream impact on `service-b` and `gateway`.
   - Decision Engine verifies telemetry freshness and allowlisted runbook (`RESET_CONNECTION_POOL`).
   - Action lock is acquired, recovery action is executed, and engine enters `VERIFYING` state.
   - Engine collects **fresh telemetry** samples and runs multi-point verification probe.
   - Verification succeeds -> Incident status transitions to **RESOLVED**.
   - Incident is indexed into **Incident Memory** for historical learning.

### Scenario 2: High-Risk Action & Human-in-the-Loop Operator Approval
1. In the **Demo Center**, trigger **Scenario 2: Container Failure (High Risk)**.
2. System evaluates decision policy: action `RESTART_CONTAINER` is categorized as `HIGH` risk.
3. Decision engine creates an approval ticket and transitions incident to `AWAITING_APPROVAL`.
4. Open the **Incidents** or **Approvals** page in the UI.
5. Click **Approve Remediation** with an operator note.
6. System acquires lock, applies the restart, waits for fresh telemetry, verifies health, and marks incident **RESOLVED**.

### Scenario 3: Alert Storm & Multi-Service Deduplication
1. In the **Demo Center**, trigger **Scenario 3: Alert Storm Injection**.
2. System fires 500+ cascade errors across Gateway, Service A, Service B, and Database.
3. Observe that Event Correlator aggregates all 500+ events into **1 unified incident**, eliminating alert noise.

### Scenario 4: Storage Pressure & Predictive Archival
1. Trigger **Scenario 4: Storage Capacity Saturation**.
2. Linear trend extrapolator detects storage growth (+1.8 GB/h) forecasting capacity exhaustion in 10h.
3. Recommends automated log rotation and gzip compression.
4. Executes optimization: rotates active logs, creates `.tar.gz` archives in `/data/archive/`, and reclaims disk space.

### Scenario 5: Incident Memory, Proven Remedies & AI Operations Copilot
1. Open the **Knowledge Base** page to inspect past resolved incidents, observed MTTR, and remedy success rates.
2. Open the **AI SRE Assistant** page.
3. Ask grounded operational questions:
   - *"What caused the latest database incident?"*
   - *"What is the health status of the Kafka event streaming bus?"*
   - *"What is the historically proven remedy for connection pool exhaustion?"*
4. Verify grounded response backed by real telemetry tool executions with zero hallucination.

---

## 🧪 Automated Test & Benchmark Verification

### Run Complete Pytest Suite (93 Tests, 100% Pass Rate)
```bash
# Run all unit, integration, multi-detector, Kafka, and 23-step closed-loop tests
.\venv\Scripts\python.exe -m pytest backend/tests -v
```

### Run High-Throughput Load Benchmark (100, 500, 1000 EPS)
```bash
# Run multi-stage load benchmark
.\venv\Scripts\python.exe scripts/load_benchmark.py
```
