# AegisOps AI — Enterprise Architecture Specification

## 1. Executive Summary

AegisOps AI is an enterprise-grade Observability and Autonomous Incident Response SaaS platform designed to detect, correlate, isolate, remediate, and verify distributed system failures with zero human intervention for low-risk events and strict policy-governed authorization gates for high-risk interventions.

AegisOps AI operates as a multi-tenant distributed system handling OpenTelemetry (logs, metrics, traces, events), Apache Kafka message queues, real-time dynamic graph dependency mapping, and continuous verification loops.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             TELEMETRY INGESTION TIER                             │
│  Kubernetes Pods / VMs / Lambda  ──►  OTel Collector DaemonSet  ──►  Kafka Broker│
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          REAL-TIME PIPELINE & STREAMING                          │
│  Kafka Topic: aegisops-telemetry  ──►  Log Processor  ──►  Normalized Event Bus  │
│                                   ──►  Metric Buffers ──►  Anomaly Detectors     │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         AI REASONING & ROOT CAUSE ENGINE                         │
│  Dynamic Dependency Topology Map  ──►  Temporal Correlation Window (60s)        │
│  Blast Radius Impact Analyzer    ──►  Causal Terminus Graph Traversal            │
│  Case-Based Reasoning (CBR Memory) ──► Explainable RCA Formulation               │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS ORCHESTRATION & GATING                         │
│  Remediation Policy Engine       ──►  RBAC Authorization Gate (CEO Locked)       │
│  Risk Scoring (LOW/MED/HIGH/CRIT) ──► Orchestrated Self-Healing Action           │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       ACTIVE VERIFICATION & INCIDENT MEMORY                      │
│  Live Telemetry Health Probe     ──►  Verification Verifier (Post-Fix Telemetry) │
│  Vector Embeddings Stored        ──►  Continuous SLO & Error Budget Recalibration│
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ingestion Subsystem

### 2.1 OpenTelemetry Standard Ingestion
- **Protocols Supported:** OTLP/gRPC (`:4317`), OTLP/HTTP (`:4318`), REST Ingestion (`/v1/telemetry/ingest`).
- **Data Planes:**
  - **Logs:** Structured JSON with normalized severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`), trace/span bindings, and arbitrary attributes.
  - **Metrics:** Golden signals (Latency P50/P90/P99, Error Rate, Request Rate, Saturation, CPU/Memory/Pool usage).
  - **Traces:** Distributed W3C `traceparent` headers correlating parent and child spans across service boundaries.
  - **Events:** Cloud deployment events, container restarts, policy changes, and circuit-breaker triggers.

### 2.2 Kafka Broker Integration
- High-throughput buffering via Apache Kafka `aegisops-telemetry` topic.
- Consumer lag monitoring ensuring zero buffer overflow during high-volume spikes.
- Fallback in-memory circular buffer (depth: 50,000 events) for local demo and air-gapped test environments.

---

## 3. Autonomous Correlation & Root Cause Analysis

### 3.1 Dynamic Topology Mapping
- Live directed acyclic graph (DAG) automatically updated from distributed trace spans and HTTP ingress paths.
- Nodes represent microservices (`auth-service`, `payment-gateway`, `order-processor`, `inventory-manager`, `customer-api`, `database-cluster`).
- Edges represent live invocation flows with real-time latency and error propagation weights.

### 3.2 Explainable RCA Algorithm
AegisOps isolates the root cause using a three-stage mathematical pipeline:
1. **Temporal Precedence:** Identifies the earliest onset timestamp among all correlated anomalies within a 60-second window.
2. **Topological Propagation:** Traverses the dependency graph from client-facing ingress towards downstream dependencies until the terminus origin node is identified.
3. **Multi-Variate Signature Matching:** Correlates log error messages and metric deviations against known failure modes to calculate a mathematical confidence score (0.0 to 1.0).

---

## 4. Policy Engine, Guardrails & RBAC

### 4.1 Risk Classification
| Action Category | Example Actions | Max Auto-Risk | Gating Requirement |
|---|---|---|---|
| **Low Risk** | `RESET_CONNECTION_POOL`, `CLEAR_CACHE`, `ROTATE_CONNECTIONS` | LOW | Autonomous under policy |
| **Medium Risk** | `SCALE_REPLICAS`, `DRAIN_QUEUE`, `THROTTLE_CALLERS` | MEDIUM | SRE Lead or Incident Commander approval |
| **High Risk** | `RESTART_SERVICE`, `ROLLBACK_DEPLOYMENT`, `FAILOVER_DB` | HIGH / CRITICAL | Dual SRE Lead sign-off |

### 4.2 Role-Based Guardrails
- **CEO Persona:** Executive Read & Governance only. Strictly prohibited from approving technical remediation actions to prevent non-technical operational disruption.
- **SRE Lead & Incident Commander:** Full authority to approve, gate, or override automated remediation proposals.
- **Security Engineer:** Authority over audit logs, compliance certificates, and tenant boundary verification.

---

## 5. Active Post-Remediation Verifier

Remediations are never marked resolved until physically verified:
1. Following runbook execution, the **Verifier** waits for fresh incoming telemetry (5 to 15 seconds).
2. Computes the rolling error rate and P99 latency on the target service.
3. If golden metrics normalize below alert thresholds, the incident status transitions to `RESOLVED` and the incident lifecycle completes.
4. If golden metrics remain degraded, the verifier triggers an immediate fallback/rollback plan and escalates to the Incident Commander.

---

## 6. Multi-Tenancy & Data Isolation

- **Partitioning:** Cryptographic tenant token validation on every ingress request.
- **Database Architecture:** Row-level `tenant_id` foreign keys indexed across SQLite and PostgreSQL databases.
- **Memory Scoping:** In-memory anomaly buffers, CBR incident memory, and topology graphs are partition-isolated by `tenant_id`. Cross-tenant data leakage is mathematically prevented.
