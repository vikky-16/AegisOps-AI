# AegisOps AI — System Architecture & Topology

## Executive Overview
AegisOps AI is a real-time, multi-tenant autonomous observability and intelligent incident-response platform. It transforms raw telemetry streams into high-confidence root cause diagnoses, calculates operational blast radius, and executes policy-governed self-healing actions verified by multi-point active probes.

---

## 1. High-Level Architectural Flow
```
[External Clusters / Microservices / OTel Collectors]
                      │
                      ▼
         [Telemetry Ingestion Gateway]
         (/api/v1/telemetry/{logs,metrics,traces,batch})
                      │
     ┌────────────────┴────────────────┐
     ▼                                 ▼
[PII & Secret Redaction Engine]   [Tenant Authentication & API Key Cache]
     │                                 │
     └────────────────┬────────────────┘
                      ▼
            [Apache Kafka Cluster]
        Topics: aegisops.telemetry.*
                      │
                      ▼
           [EventBus Streaming Hub]
                      │
     ┌────────────────┼────────────────┐
     ▼                ▼                ▼
[Multi-Detector   [Dynamic Graph    [Real-Time Ingestion
 ML Engine]        Topology Engine]  KPI Tracker]
     │                │                │
     └────────────────┼────────────────┘
                      ▼
           [Event Cascade Correlator]
                      │
                      ▼
            [Incident Lifecycle Manager]
                      │
                      ▼
            [Risk-Aware Decision Engine]
           (Autonomous vs Human Approval)
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
[Autonomous Runbook Executor]   [Human Approval Center]
        │                           │
        └─────────────┬─────────────┘
                      ▼
       [Active Multi-Point Verification Probe]
                      │
                      ▼
          [Incident Memory Store (CBR)]
```

---

## 2. Core Architectural Components

### A. Ingestion Gateway (`backend/app/api/ingestion_gateway.py`)
- High-throughput asynchronous ingress accepting HTTP OTLP and batch payloads.
- Validates cryptographic `X-API-Key` headers against a microsecond in-memory hash cache.
- Tracks real measured Events Per Second (EPS), bytes/sec, and active streaming tenants without synthetic placeholders.

### B. Secret & PII Scrubbing Engine (`backend/app/core/pii_masker.py`)
- High-performance regex pipeline inspecting all raw text, logs, and trace attributes.
- Automatically redacts authorization bearer tokens, JWTs, database connection URI passwords, cloud secrets, and private keys.

### C. Message Broker & Event Streaming (`backend/app/kafka/`)
- Apache Kafka topic hierarchy partitioned by tenant ID:
  - `aegisops.telemetry.logs`, `aegisops.telemetry.metrics`, `aegisops.telemetry.traces`
  - `aegisops.anomalies`, `aegisops.correlations`, `aegisops.incidents`
  - `aegisops.remediation.requests`, `aegisops.remediation.results`, `aegisops.audit`
- Fallback in-memory EventBus with DLQ routing for local deployments.

### D. Machine Learning Anomaly Detection (`backend/app/ai/`)
- Dynamic rolling statistical baselines (Welford's algorithm).
- Multi-detector ensemble: Isolation Forest, Z-score variance, and Interquartile Range (IQR) detectors.
- Produces normalized anomaly scores (0.00 – 1.00) with detailed causal evidence.

### E. Root Cause Analysis & Dependency Graph (`backend/app/rca/`)
- Live service dependency topology dynamically updated from telemetry traces.
- Computes betweenness centrality and PageRank to isolate primary failure origins from downstream cascading symptoms.
- Mathematical blast radius calculation evaluating topological criticality and downstream service degradation.

### F. Self-Healing & Active Verification (`backend/app/healing/`)
- Policy-controlled autonomous execution of allowlisted declarative runbooks.
- Strict gating: critical service restarts and high-risk runbooks require explicit SRE human authorization.
- Active multi-point verification probe validates service health, error rates, and synthetic transactions before marking incidents resolved.
