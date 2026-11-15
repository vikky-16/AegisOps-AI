# AegisOps AI - API Reference

Base API Path: `http://127.0.0.1:8000/api`

---

## 1. Microservices Observatory
- `GET /api/services` - Returns live health, latency p95, error rates, and CPU/RAM for all 4 microservices.
- `GET /api/services/{service_name}` - Detailed telemetry metadata and history for a specific service.

## 2. Telemetry & Metrics
- `GET /api/metrics` - Aggregated system health score and real-time metric snapshots.
- `GET /api/metrics/{service_name}/history` - Historical time-series points.
- `WS /ws/telemetry` - Live WebSocket feed streaming 1-second telemetry ticks.

## 3. Log Intelligence
- `GET /api/logs` - Query structured JSON logs filtered by service or level.
- `GET /api/logs/summary` - Aggregated log distribution by service and level.

## 4. Incidents & Root Cause Analysis (RCA)
- `GET /api/incidents` - List all open, investigating, and resolved incidents.
- `GET /api/incidents/{incident_id}` - Detailed incident lifecycle, timeline, and business impact.
- `GET /api/incidents/{incident_id}/rca` - Dependency graph causality analysis, evidence facts, and confidence score.

## 5. Human Approvals
- `GET /api/approvals` - List pending human-in-the-loop authorization tickets.
- `POST /api/approvals/{approval_id}/approve` - Authorize and trigger recovery action.
- `POST /api/approvals/{approval_id}/reject` - Reject ticket and log reason to audit.

## 6. Self-Healing & Recovery
- `GET /api/recovery` - History of remediation executions and verification probe results.
- `POST /api/recovery/manual` - Trigger an on-demand recovery action on a target service.

## 7. Storage Intelligence
- `GET /api/storage` - Disk capacity analytics, growth rates, and time-to-critical estimates.
- `POST /api/storage/optimize` - Executes automated log rotation, gzip compression, and table compaction.

## 8. Knowledge Base & CBR
- `GET /api/knowledge` - Retrieve all historical incident post-mortems.
- `GET /api/knowledge/search?q={query}` - TF-IDF vector similarity search over past incidents.

## 9. Operations AI Copilot
- `POST /api/assistant/query` - Evaluates natural-language SRE queries and returns grounded answers.

## 10. Sandboxed Failure Simulations
- `POST /api/simulations/service-failure` - Injects crash into Payment Service B.
- `POST /api/simulations/high-cpu` - Injects high CPU saturation.
- `POST /api/simulations/storage-pressure` - Simulates tablespace growth.
- `POST /api/simulations/log-storm` - Fires 500+ cascade errors across microservices.
- `POST /api/simulations/failed-recovery` - Injects connection exhaustion to test recovery failure escalation.
- `POST /api/simulations/reset-all` - Restores all systems to clean baseline.

## 11. Platform Self-Monitoring
- `GET /api/platform/health` - Health status of backend, database, monitoring worker, and ML models.
