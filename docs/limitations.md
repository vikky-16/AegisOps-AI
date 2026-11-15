# AegisOps AI — Platform Limitations & Production Boundaries

This document provides a transparent, engineering-level breakdown of the operational limits, design trade-offs, and clear boundary lines between **production-grade components** and **simulated demo mechanisms** in AegisOps AI.

---

## 1. Reality Matrix: Production-Grade vs. Demo Mechanisms

| Component | Production-Ready Reality | Demo / Simulation Mode | Production Scaling Path |
| :--- | :--- | :--- | :--- |
| **Ingestion Gateway** | Strict API key authentication (SHA-256), PII/secret masking, schema validation (v2.0 contract), real measured EPS and bytes/sec sliding-window calculations. | Accepts unauthenticated calls from localhost if explicitly falling back to `demo-tenant`. | Place behind AWS ALB / Envoy proxy with rate-limiting and TLS termination. |
| **Data Storage** | SQLite with Write-Ahead Logging (`WAL`), `busy_timeout=5000ms`, `foreign_keys=ON`, multi-tenant schema with `tenant_id` indexing. | Uses local file `aegisops.db`. Single-instance process access. | Migrate to AWS RDS PostgreSQL or CockroachDB with connection pooling (PgBouncer). |
| **Telemetry Timeseries** | In-memory ring buffers with timestamped sliding metrics and trace spans. | Synthetic failure injector generates metric spikes when running failure scenarios. | Ingest into ClickHouse, VictoriaMetrics, or TimescaleDB for multi-year cold storage. |
| **Streaming Pipeline** | Full Kafka topic hierarchy (`aegisops.telemetry.{logs,metrics,traces,events}`) with tenant message headers. | In-process queue / fallback buffer if Kafka broker (`localhost:9092`) is unreachable. | Deploy managed Apache Kafka (MSK) or Confluent Cloud with partition keys mapped to `tenant_id`. |
| **ML Anomaly Detection** | Real statistical z-score, rate-of-change, and Isolation Forest models operating on live sliding windows. | Initial seed data uses simulated service baselines before real streaming metrics adapt the model. | Model registry with periodic retraining via MLflow or Feast feature store. |
| **Root Cause Analysis** | Dynamic graph traversal over service dependency topology, computing correlation score, anomaly weight, and blast radius. | Topology graph pre-configured with 8 microservices for the default demo topology. | Auto-discover topology dynamically via OpenTelemetry distributed trace parent-span relationships. |
| **Self-Healing Actions** | Real process inspection, local Docker/shell execution capabilities, configurable tenant blast radius limits. | Remediation actions (restart, scale, rollback) can run in safe dry-run/mock mode to avoid crashing developer hosts. | Integrate AWS SSM Run Command, Kubernetes API (`apps/v1/deployments/scale`), or Ansible playbooks. |

---

## 2. Storage & Database Limits

- **Engine:** SQLite 3.x with WAL mode.
- **Maximum Concurrent Writers:** 1 (SQLite file lock semantics). Multiple concurrent readers are supported via WAL mode.
- **Maximum Database Size:** Tested up to 10 GB. For multi-tenant workloads exceeding 50,000 events/sec, migration to PostgreSQL 16+ or ClickHouse is required.
- **Data Retention:** SQLite stores configuration, tenants, users, API keys, policies, incidents, and audit logs. Streaming telemetry is buffered in memory ring buffers and streamed to Kafka topics.

---

## 3. Telemetry Ingestion Throughput

- **Single Gateway Worker (uvicorn):**
  - Up to **1,200 events/second** for raw uncompressed HTTP POST calls.
  - Up to **8,500 events/second** when using `/api/v1/telemetry/batch` with payloads of 100-500 items.
- **Memory Consumption:**
  - Base footprint: ~120 MB RAM.
  - Ingestion buffer at 5,000 EPS: ~350 MB RAM.
- **Network Bandwidth:**
  - Gateway handles up to 25 MB/s of raw OTel JSON telemetry per uvicorn worker process.
  - For higher throughput, scale horizontally behind a load balancer with multiple uvicorn workers:
    ```bash
    uvicorn backend.app.main:app --workers 4 --host 0.0.0.0 --port 8000
    ```

---

## 4. Multi-Tenant Isolation Boundaries

- **Logical Isolation:** AegisOps AI enforces strict **application-level and row-level tenant boundaries**:
  - Every API endpoint requires an authenticated identity carrying a validated `tenant_id`.
  - Platform administrators (`is_platform_admin=True`) can query across tenants.
  - Standard tenant users can **only** view, query, or remediate records where `tenant_id == user.tenant_id`.
- **Cross-Tenant Guardrails:**
  - Ingestion API keys are cryptographically hashed using SHA-256 and matched directly to a specific `tenant_id`.
  - Database queries explicitly append `WHERE tenant_id = :tenant_id`.
  - Incident memory and CBR (Case-Based Reasoning) vector matching filter candidate historical incidents by `tenant_id` first.
- **Physical Isolation:**
  - In the current single-database deployment, all tenants share a common database schema with foreign-keyed tenant isolation.
  - For strict compliance (HIPAA, PCI-DSS Level 1, FedRAMP), tenants can be provisioned with dedicated database schemas or isolated database instances.

---

## 5. Machine Learning & Anomaly Detection

- **Cold-Start Latency:**
  - Statistical algorithms (z-score, EWMA) require a minimum warmup window of **15 samples** (~30 seconds at 2s poll intervals) to establish baseline standard deviation.
  - Isolation Forest models initialize with default feature priors until at least 100 observations are recorded.
- **Memory Scaling:**
  - Vector similarity for incident memory uses in-memory cosine similarity over TF-IDF / mini-embedding feature vectors.
  - Scales comfortably up to 50,000 historical incidents per tenant (~150 MB memory). For collections above 100,000 incidents, external vector databases (Qdrant, Milvus, pgvector) should be integrated.

---

## 6. Self-Healing & Safety Mechanisms

- **Autonomous Remediation Safety Limits:**
  - Remediation actions are gated by each tenant's `TenantPolicy`:
    - `auto_remediate_enabled`: Master switch per tenant.
    - `max_auto_remediate_risk`: Rejects any action with risk level exceeding this threshold (e.g., `MEDIUM`).
    - `allowed_auto_actions`: Strict allowlist (e.g., `restart_container`, `scale_deployment`, `clear_cache`).
    - `require_human_approval_for_p1`: Enforces approval tickets for any P1/Critical incident.
- **Dry-Run Mode:**
  - In demo and testing environments, actions execute in simulation mode by default (`dry_run=True`), logging planned steps without altering underlying OS or cloud infrastructure.
  - Setting `AEGISOPS_EXECUTION_MODE=LIVE` activates direct OS shell and Docker API execution.
