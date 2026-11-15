# AegisOps AI — 15-Step Autonomous Incident Lifecycle & Explainable RCA

## 1. The 15-Step Failure Lifecycle Pipeline

Every incident processed by AegisOps AI progresses through a deterministic, auditable 15-step failure lifecycle. This guarantees that remediations are safe, explainable, authorized, and actively verified before closure.

```
 [1. Telemetry Ingest]
        │ (OTel Logs, Golden Metrics, Distributed Traces, Events)
        ▼
 [2. Anomaly Detect]
        │ (Dynamic Baselines, Z-Score Drift, Rapid Spike Thresholds)
        ▼
 [3. Alert Trigger]
        │ (Multi-Window SLO Burn Rate & Error Spike Evaluators)
        ▼
 [4. Incident Created]
        │ (UUID Assigned, Tenant Context Attached, P0-P3 Severity Tagged)
        ▼
 [5. Context Correlate]
        │ (60-Second Sliding Correlation Window Across Multi-Services)
        ▼
 [6. Blast Radius Map]
        │ (Dynamic Topology Traversal: Direct vs Downstream Impact)
        ▼
 [7. Root Cause Isolation]
        │ (Temporal Onset Precedence + Causal Terminus Graph Node)
        ▼
 [8. Knowledge Graph Query]
        │ (Case-Based Reasoning [CBR] Historical Vector Match Search)
        ▼
 [9. Remediation Proposal]
        │ (Target Runbook Selected, e.g. RESET_CONNECTION_POOL)
        ▼
 [10. Safety Guardrail Check]
        │ (Blast Radius Upper Bounds, Service Cooldown Limits Verified)
        ▼
 [11. RBAC Approval Request]
        │ (CEO Role Blocked; SRE Lead / Incident Commander Gated)
        ▼
 [12. Orchestrated Remediation]
        │ (Kubernetes API / Cloud Provider / Service Webhook Executed)
        ▼
 [13. Active Health Verification]
        │ (Verifier Evaluates Post-Remediation Fresh Telemetry Stream)
        ▼
 [14. Incident Memory Stored]
        │ (Vector Embeddings & Resolution Pattern Persisted to CBR DB)
        ▼
 [15. Incident Closed]
        │ (SLO Recalibrated, Post-Mortem Generated, Audit Trail Signed)
```

---

## 2. Explainable Root Cause Analysis (Explainable RCA)

AegisOps AI rejects opaque "black box" machine learning models. For every detected incident, AegisOps generates a transparent card titled:

### "WHY AEGISOPS THINKS THIS IS THE ROOT CAUSE"

This card provides three pillars of mathematical and topological evidence:

1. **Temporal Precedence:** Proves that the anomalous metric deviation or error log signature first occurred in the root cause service, exactly *N* milliseconds prior to downstream consumer degradation.
2. **Topological Dependency Propagation:** Shows the exact distributed trace span trajectory along the active directed dependency graph (`database-service` → `service-b` → `service-a` → `gateway`). The failure cascades downstream from the isolated terminus origin node.
3. **Multi-Variate Statistical Confidence:** Formulates a quantitative confidence percentage (e.g. 94%) based on metric correlation, log fingerprint frequency, and historical pattern matching.

---

## 3. Autonomous vs Human-in-the-Loop Gating

- **Autonomous Execution (Low-Risk):** For known failure patterns with confidence >= 85% and action risk rated `LOW` (e.g. `RESET_CONNECTION_POOL`, `CLEAR_CACHE`), the policy engine approves execution automatically without human lag.
- **Human Authorization (High-Risk):** For high-risk interventions (`RESTART_SERVICE`, `ROLLBACK_DEPLOYMENT`), the incident halts at Step 11 (`RBAC Approval Request`).
- **Executive Lockout:** If a user holding the `CEO` role attempts to approve technical execution, the action is rejected with `HTTP 403 Forbidden`. Only certified `SRE_LEAD`, `INCIDENT_COMMANDER`, or `SUPER_ADMIN` personnel can authorize technical changes.
