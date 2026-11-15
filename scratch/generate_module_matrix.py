import csv
import os

output_path = os.path.join("report_audit", "module_implementation_matrix.csv")

modules = [
    # Perception & Anomaly Detection
    {
        "component": "Universal Normalizer",
        "file_path": "backend/app/integrations/normalizer.py",
        "purpose": "Normalize heterogeneous incoming JSON and OTLP payloads into UnifiedTelemetryEvent contracts",
        "inputs": "Raw dictionary payloads (REST, Kafka, OTel)",
        "processing": "Schema mapping, field type casting, UTC timestamp normalization, service name validation",
        "outputs": "UnifiedTelemetryEvent (Pydantic model)",
        "dependencies": "pydantic, backend.app.schemas.telemetry_contract",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_real_telemetry_pipeline.py"
    },
    {
        "component": "Multi-Detector Anomaly Engine",
        "file_path": "backend/app/ai/detectors/multi_detector_engine.py",
        "purpose": "Orchestrates multi-algorithm metric anomaly evaluation",
        "inputs": "Metric name, current value, rolling history, baseline mean/std",
        "processing": "Executes Z-Score, EWMA, IQR, and Isolation Forest detectors in parallel; aggregates scores",
        "outputs": "Anomaly evaluation dictionary with is_anomaly, score, and detector breakdown",
        "dependencies": "zscore_detector, ewma_detector, iqr_detector, isolation_forest_detector",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_multi_detectors.py"
    },
    {
        "component": "Event & Incident Correlator",
        "file_path": "backend/app/services/event_correlator.py",
        "purpose": "Clusters correlated telemetry anomalies into unified incidents within temporal windows",
        "inputs": "Anomalous UnifiedTelemetryEvent instances",
        "processing": "Temporal proximity matching (300s), service dependency traversal, deduplication",
        "outputs": "Incident record or appended evidence entry",
        "dependencies": "SQLAlchemy, backend.app.models.incident, dependency_graph",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_event_correlation_advanced.py"
    },

    # Cognitive & RCA
    {
        "component": "15-Question RCA Fact Builder",
        "file_path": "backend/app/rca/evidence_package.py",
        "purpose": "Evaluates the 15-question root cause evidence package",
        "inputs": "Incident record and associated telemetry timeline",
        "processing": "Chronological trace ordering, first error extraction, propagation path inference, blast radius scoring",
        "outputs": "15-question fact dictionary (q1 through q15)",
        "dependencies": "backend.app.models.incident, backend.app.models.rca",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_automated_incident_response.py"
    },
    {
        "component": "Dual-Solution Synthesis Engine",
        "file_path": "backend/app/rca/dual_solution_engine.py",
        "purpose": "Synthesizes Solution A (Gemini LLM) and Solution B (Curated KB) and evaluates consensus vs conflict",
        "inputs": "Incident ID, tenant credentials, 15-question evidence package",
        "processing": "Asynchronous invocation of GeminiProvider, SQL query of KnowledgeArticle, comparison algorithm",
        "outputs": "Dual solution payload with consensus_status and action candidates",
        "dependencies": "GeminiProvider, KnowledgeArticle, SQLAlchemy",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_e2e_three_incidents.py"
    },
    {
        "component": "Google Gemini 3.8 Flash Provider",
        "file_path": "backend/app/ai/gemini_provider.py",
        "purpose": "Official Google Generative Language API adapter with dynamic discovery and reasoning effort",
        "inputs": "Prompt text, API key, model identifier, reasoning_effort ('low', 'medium', 'high')",
        "processing": "Constructs generateContent JSON with thinkingConfig, handles bounded timeouts, scrubs secrets",
        "outputs": "Structured generation response or diagnostic connection probe result",
        "dependencies": "httpx, json, uuid",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_gemini_38_and_model_discovery.py"
    },

    # Digital Twin & Replica Lab
    {
        "component": "Remediation Lab (Digital Twin Engine)",
        "file_path": "backend/app/replica/remediation_lab.py",
        "purpose": "Executes the 17-step scientific experiment lifecycle in isolated digital twin",
        "inputs": "Incident ID, scenario ID, candidate remediations list",
        "processing": "Allocates twin adapter, injects fault, captures baseline, applies fix, replays stress workload, ranks candidates",
        "outputs": "ReplicaExperiment record with before/after metrics, regression checks, and evaluation verdict",
        "dependencies": "adapters.py, ReplicaExperiment, SQLAlchemy",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_replica_lab_and_system_repair.py"
    },
    {
        "component": "Replica Adapters",
        "file_path": "backend/app/replica/adapters.py",
        "purpose": "Abstract adapter interface supporting Synthetic, Container, and Staging execution modes",
        "inputs": "Replica configuration parameters, scenario injection command",
        "processing": "Fidelity calculation (98% synthetic), fault generation, container isolation",
        "outputs": "Metric snapshots, container lifecycle status",
        "dependencies": "asyncio, json, random",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_replica_lab_and_system_repair.py"
    },

    # Governance & Execution
    {
        "component": "Approval Governance Manager",
        "file_path": "backend/app/healing/approval_manager.py",
        "purpose": "Enforces tenant risk policies, separation of duties, and approval ticket lifecycle",
        "inputs": "Incident ID, proposed action, evaluated risk score, tenant risk ceiling",
        "processing": "Determines auto-approval vs human gating; tracks approval state transitions",
        "outputs": "ApprovalTicket record or immediate execution clearance",
        "dependencies": "ApprovalTicket, TenantPolicy, SQLAlchemy",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_approval_center_restoration.py"
    },
    {
        "component": "Controlled Execution Engine",
        "file_path": "backend/app/healing/controlled_execution_engine.py",
        "purpose": "Executes allowlisted operational actions against target services",
        "inputs": "Approved action key (e.g. RESET_CONNECTION_POOL), target service, parameters",
        "processing": "Validates action against allowlist; invokes service mitigation handler; logs audit record",
        "outputs": "Execution result status, duration_ms, and target acknowledgment",
        "dependencies": "RecoveryExecution, actions.py, SQLAlchemy",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_controlled_execution_verified_recovery.py"
    },
    {
        "component": "8-Point Empirical Validator",
        "file_path": "backend/app/healing/sandbox_engine.py",
        "purpose": "Validates target service health across 8 empirical criteria post-remediation",
        "inputs": "Incident ID, target service, baseline telemetry envelope",
        "processing": "Checks reachability, error rate, latency envelope, freshness, downstream health, side effects",
        "outputs": "Validation report with all_passed boolean and criteria breakdown",
        "dependencies": "httpx, telemetry_store, collector",
        "status": "VERIFIED_ACTIVE",
        "evidence": "benchmark_and_verify.py / test_closed_loop_recovery_validation.py"
    },
    {
        "component": "Bounded Refinement & Escalation Engine",
        "file_path": "backend/app/healing/closed_loop_engine.py",
        "purpose": "Orchestrates iterative recovery refinement up to configured ceiling (default: 3)",
        "inputs": "Validation outcome, current attempt counter, remaining candidate solutions",
        "processing": "Applies backoff cooldown; triggers next ranked candidate or escalates to SRE lead on max attempts",
        "outputs": "Refinement iteration update or ESCALATED_TO_HUMAN alert",
        "dependencies": "IncidentAttempt, IncidentModel, SQLAlchemy",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_closed_loop_recovery_validation.py"
    },

    # Storage & Persistence
    {
        "component": "Database Core & Connection Pool",
        "file_path": "backend/app/core/database.py",
        "purpose": "Manages SQLite WAL connection pool, async sessions, and table migrations",
        "inputs": "DATABASE_URL environment string ('sqlite+aiosqlite:///aegisops.db')",
        "processing": "Creates async engine with WAL mode PRAGMA, manages session scope",
        "outputs": "AsyncSessionLocal generator",
        "dependencies": "sqlalchemy.ext.asyncio, aiosqlite",
        "status": "VERIFIED_ACTIVE",
        "evidence": "All test suites"
    },
    {
        "component": "Telemetry Store & Ring Buffer",
        "file_path": "backend/app/storage/telemetry_store.py",
        "purpose": "In-memory circular ring buffer for sub-second telemetry queries and trace waterfalls",
        "inputs": "UnifiedTelemetryEvent streams",
        "processing": "FIFO ring-buffer eviction, multi-tenant index lookup, trace span indexing",
        "outputs": "Filtered telemetry slices, trace waterfall trees",
        "dependencies": "collections.deque, threading.Lock",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_telemetry_store.py"
    },

    # Security & RBAC
    {
        "component": "RBAC Security & JWT Token Manager",
        "file_path": "backend/app/core/security.py",
        "purpose": "Issues and verifies JWT bearer tokens, hashes passwords (bcrypt), and enforces roles",
        "inputs": "Username, password, role, tenant_id, JWT token string",
        "processing": "HMAC-SHA256 token generation and validation, password salt hashing",
        "outputs": "Access token string or decoded claims dictionary",
        "dependencies": "python-jose, passlib[bcrypt]",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_enterprise_auth_rbac.py"
    },
    {
        "component": "PII & Secret Masker",
        "file_path": "backend/app/core/pii_masker.py",
        "purpose": "Scrubs API keys, passwords, credit card numbers, and emails from logs and payloads",
        "inputs": "Raw strings, log messages, dictionaries",
        "processing": "Regex substitution of secret patterns (e.g. AIza****XYZ, [MASKED_KEY])",
        "outputs": "Sanitized string / payload",
        "dependencies": "re",
        "status": "VERIFIED_ACTIVE",
        "evidence": "backend/tests/test_ai_config_security.py"
    }
]

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "component", "file_path", "purpose", "inputs", "processing",
        "outputs", "dependencies", "status", "evidence"
    ])
    writer.writeheader()
    writer.writerows(modules)

print(f"Wrote {len(modules)} module implementations to {output_path}")

