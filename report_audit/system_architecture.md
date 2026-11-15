# AegisOps AI — System Architecture Specification

**System Classification**: Autonomous SRE & Closed-Loop Validated Recovery Platform  
**Architecture Style**: Asynchronous Micro-Kernel with Multi-Tenant Service Mesh Adapters  
**Authoritative Path**: `C:\Users\admin\AegisOps AI`  

---

## 1. Architectural Overview & Design Philosophy

AegisOps AI is architected as an **evidence-guided, closed-loop autonomous reliability engineering platform**. Unlike passive observability platforms that merely raise alerts, or naive auto-remediation scripts that blindly execute against production, AegisOps AI operates on the principle of **empirical pre-validation**:
> *Every proposed remediation intervention must be hypothesized, isolated in a digital twin replica, validated against regression criteria, authorized through policy governance, and empirically verified post-deployment before being committed to persistent operational memory.*

The architecture bridges three decoupled subsystems:
1. **Perception Layer (Continuous Telemetry & Ingestion)**: Normalizes heterogenous signals across OpenTelemetry, Kafka, and REST gateways.
2. **Cognitive Layer (Multi-Detector Anomaly & Dual-Solution RCA)**: Evaluates statistical baselines, forms incident correlations, evaluates 15-question evidence contracts, and synthesizes AI vs KB dual solutions.
3. **Execution & Validation Layer (Replica Twin, Approval Center & Remediation)**: Manages 17-stage scientific replica trials, enforces RBAC human-in-the-loop approvals, executes allowlisted actions, and verifies target recovery across 8 empirical criteria.

---

## 2. Component Architecture Breakdown

### 2.1 Frontend Architecture (`frontend/src/`)
- **Technology Stack**: React 18, TypeScript 5.x, Vite 8.2 (Rolldown compiler), Tailwind CSS, Lucide React icons.
- **Application Structure**:
  - `layouts/AppLayout.tsx`: SRE dark-theme navigation shell with dynamic status badges, tenant switcher, and system health tickers.
  - `pages/`: 27 specialized functional views including `DashboardPage`, `RcaPage`, `ApprovalsPage`, `RecoveryPage`, `TestingSimulationLabPage`, `SettingsPage`, `AssistantPage`, and `LiveTelemetryPage`.
  - `context/`: `TenantContext` (multi-tenant state, active tenant slug, JWT credentials) and `WorkspaceContext`.
  - `hooks/`: `useWebSocket.ts` (real-time telemetry bus subscription with automatic reconnection and polling fallback).
  - `services/api.ts`: Centralized HTTP API client communicating with the backend over JSON REST and SSE.

### 2.2 Backend Architecture (`backend/app/`)
- **Technology Stack**: Python 3.13.7, FastAPI (ASGI), Uvicorn server, SQLAlchemy 2.0 (AsyncSession), Pydantic v2.
- **Core Engine Packages (24 packages)**:
  - `api/`: 40 REST router modules exposing 367 endpoints across authentication, incidents, approvals, recovery, replica lab, and telemetry.
  - `core/`: Application bootstrapping (`config.py`), async database pool (`database.py`), RBAC security (`security.py`), and PII scrubbing (`pii_masker.py`).
  - `models/`: 22 SQLAlchemy ORM models defining 48 database tables.
  - `integrations/`: `normalizer.py` (converts raw payloads into `UnifiedTelemetryEvent`), connectors for Kafka, OTel, and databases.
  - `ai/detectors/`: 11 detector modules (ZScore, EWMA, IQR, Isolation Forest, Consecutive Breach, Multi-Detector Engine).
  - `rca/`: 15-question structured evidence builder (`evidence_package.py`), dual-solution engine (`dual_solution_engine.py`), and prompt synthesis.
  - `replica/`: Digital Twin engine (`remediation_lab.py`) with adapter abstraction (`adapters.py`) supporting Synthetic, Container, and Staging modes.
  - `healing/`: Closed-loop orchestrator (`closed_loop_engine.py`), decision table (`decision_table.py`), approval governance (`approval_manager.py`), action executor (`actions.py`), and 8-point validation (`sandbox_engine.py`).
  - `ai/`: Gemini 3.8 Flash provider (`gemini_provider.py`), conversational assistant (`sre_chat_engine.py`), and dynamic model discovery.
  - `storage/`: Telemetry ring-buffer store (`telemetry_store.py`), rotation, and compression intelligence.

---

## 3. Data Flow & Communication Protocols

### 3.1 Ingestion & Normalization Flow
1. Microservices emit metrics, logs, or traces via:
   - OTLP HTTP/gRPC to Customer OTel Collector (`services/customer_otel_collector.py`)
   - HTTP POST to Ingestion Gateway (`/api/v1/telemetry/metrics`, `/logs`, `/traces`)
   - Apache Kafka topic streams (`telemetry.metrics`, `telemetry.logs`)
2. `UniversalNormalizer` transforms the payload into a strictly validated `UnifiedTelemetryEvent`:
   - Extracts `service_name`, `tenant_id`, `metric_name`, `metric_value`, `level`, `trace_id`.
   - Injects normalized UTC timestamp and environment metadata.
3. Event is dispatched to `AegisEventBus` (in-memory async queue or live Kafka broker).

### 3.2 Detection, Correlation & Incident Lifecycle
1. `MultiDetectorEngine` computes rolling baselines:
   - Statistical checks: Z-Score (> 3.0σ), EWMA (α = 0.3), IQR Outliers (> 1.5×IQR).
   - Machine Learning: Scikit-learn Isolation Forest (contamination = 0.05).
   - Flapping guard: Consecutive breach detector requiring 3 consecutive breached cycles.
2. Anomalous events pass to `EventCorrelator`:
   - Groups events matching temporal window (300s) and service dependency relationships.
   - Evaluates whether an existing incident is open; if so, deduplicates and appends evidence.
   - If novel, instantiates an `Incident` record with state `OPEN` and severity `HIGH` or `CRITICAL`.

### 3.3 Dual-Solution RCA Synthesis
1. The 15-Question RCA Engine inspects telemetry facts:
   - What failed, where failed, start time, earliest error, propagation path, affected services, blast radius.
2. `DualSolutionEngine` generates two independent remediation candidates:
   - **Solution A (AI Model)**: Dispatched to Google Gemini (`gemini-3.8-flash` with `thinkingBudget: 8192`) requesting structured JSON remediation steps.
   - **Solution B (Knowledge Base)**: Queries curated runbooks in `KnowledgeArticle` matching incident category and tenant slug.
3. The engine computes a **Consensus Alignment Score**:
   - If AI action aligns with KB action: flags `CONSENSUS_ALIGNED` with high confidence.
   - If AI diverges from KB: flags `CONFLICT_DETECTED` with risk warning.

### 3.4 Digital Twin Replica Lab (17-Step Lifecycle)
Prior to live execution, the candidate remediation is submitted to `RemediationLab`:
1. Select incident & allocate isolated replica (`SyntheticReplicaAdapter`).
2. Inject fault scenario (e.g., connection pool exhaustion, latency surge).
3. Capture baseline metrics (P95 latency, error rate, active connections).
4. Apply candidate remediation inside isolated sandbox twin.
5. Replay synthetic stress workload (2,500 requests, concurrency 50).
6. Measure post-intervention metrics delta.
7. Run regression checks across upstream/downstream services (`auth-service`, `gateway`, `service-b`).
8. Rank candidates by composite score (effectiveness, safety, cost, confidence).
9. Output structured verdict (`PASS`, `INCONCLUSIVE`, `FAIL`) and transition to `AWAITING_APPROVAL`.

### 3.5 Approval Governance & Controlled Execution
1. If candidate risk level exceeds tenant risk ceiling (e.g., `MEDIUM` or `HIGH` actions when ceiling is `LOW`), the system generates an `ApprovalTicket`.
2. Authorized human operator (Role: `APPROVER` or `ADMIN`) reviews ticket in Approval Center and clicks **Approve**.
3. `ControlledExecutionEngine` invokes the allowlisted action handler:
   - Allowed actions: `RESET_CONNECTION_POOL`, `RESTART_CONTROLLED_SERVICE`, `SCALE_WORKERS`, `CLEAR_CACHE_KEYS`, `DIVERT_TRAFFIC`, `ROLLBACK_DEPLOYMENT`.
   - Dispatches safe mitigation command to target microservice.

### 3.6 Independent 8-Point Empirical Validation
Immediately following remediation execution, `SandboxRecoveryEngine` runs empirical verification:
1. `service_reachability`: Target `/health` endpoint responds HTTP 200 within timeout.
2. `error_rate_threshold`: Error rate drops below 1.0% (post-intervention).
3. `latency_p95_threshold`: P95 latency returns within acceptable baseline envelope.
4. `telemetry_freshness`: Telemetry events timestamped within the last 60 seconds.
5. `downstream_health`: No secondary cascading failures induced on dependent services.
6. `no_side_effects`: Memory and CPU remain below 85% utilization ceiling.
7. `synthetic_probe_success`: Replayed probe transactions succeed with 100% pass rate.
8. `state_consistency`: Database connection handles and pool queues within normal limits.

If all 8 criteria pass: incident transitions to `RESOLVED` and verified pattern is saved to `verified_recovery_patterns`.  
If validation fails: `ClosedLoopEngine` triggers bounded refinement (Attempt 2 of 3) or escalates to `ESCALATED_TO_HUMAN`.

---

## 4. Multi-Tenant Boundaries & Isolation
AegisOps AI enforces strict multi-tenancy across database, API, and microservice tiers:
- **Tenant Context**: Every request carries an `X-Tenant-ID` header validated against authenticated user scopes.
- **Tenant Data Separation**: Tables (`incidents`, `approvals`, `recovery_executions`, `replica_experiments`, `tenant_policies`) contain foreign keys to `tenant_id`. SQL queries strictly filter by `where(tenant_id == active_tenant)`.
- **Tenant Microservice Ecosystem**:
  - `ShopSphere`: E-commerce tenant with cart, orders, inventory, and payment microservices.
  - `FinCore`: Banking tenant with core ledger, account management, and payment gateway.
  - `CloudDesk`: Collaborative workspace tenant with document store, token verification, and real-time sync.

---

## 5. Security Architecture
- **Zero Secret Exposure**: Raw API keys (e.g. Gemini, OpenAI, Slack webhooks) are masked in responses (`AIza****XYZ`) and stored strictly in backend memory or server `.env`.
- **Role-Based Access Control (RBAC)**:
  - `VIEWER`: Read-only access to dashboards and incident timelines.
  - `OPERATOR`: Permitted to trigger diagnostic scans and execute pre-approved low-risk runbooks.
  - `APPROVER`: Authorized to review and approve medium/high-risk approval tickets.
  - `ADMIN`: Full platform administrative control including model pinning, tenant onboarding, and credential updates.
- **Immutable Audit Logging**: Every approval, deferral, rejection, and remediation execution is recorded in `tenant_audit_logs` with actor ID, timestamp, and target resource.

