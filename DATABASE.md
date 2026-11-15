# AegisOps AI - Database Architecture

## 1. Overview
AegisOps AI utilizes **SQLite with SQLAlchemy 2.0 Async ORM** (`sqlite+aiosqlite`), configured with **Write-Ahead Logging (WAL) mode** (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`) for concurrent read/write throughput without blocking. The database abstraction layer is designed for seamless zero-code-change migration to **PostgreSQL**.

---

## 2. Entity Relational Schema

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      users      │       │    services     │       │     metrics     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ username        │       │ name (Unique)   │       │ service_name    │
│ email           │       │ display_name    │       │ timestamp       │
│ hashed_password │       │ role            │       │ cpu_percent     │
│ role            │       │ port, url       │       │ memory_mb       │
│ created_at      │       │ dependencies    │       │ error_rate      │
└─────────────────┘       │ criticality     │       │ latency_p95_ms  │
                          │ status          │       │ anomaly_score   │
                          └─────────────────┘       └─────────────────┘
                                   │
                                   ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    incidents    │◄──────┤    approvals    │       │    recovery     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ incident_id (UQ)│       │ approval_id (UQ)│       │ execution_id    │
│ title, status   │       │ incident_id     │       │ incident_id     │
│ severity        │       │ service_name    │       │ service_name    │
│ primary_service │       │ proposed_action │       │ action          │
│ root_cause_svc  │       │ risk_level      │       │ status          │
│ rca_confidence  │       │ risk_score      │       │ duration_ms     │
│ rca_evidence    │       │ reason, status  │       │ verification_res│
│ business_impact │       │ reviewed_by     │       │ executed_at     │
│ timeline_json   │       └─────────────────┘       └─────────────────┘
└─────────────────┘
         │
         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ knowledge_base  │       │  storage_snaps  │       │   audit_logs    │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ incident_code   │       │ timestamp       │       │ timestamp       │
│ title           │       │ total_gb        │       │ user_identifier │
│ symptoms_summary│       │ used_gb         │       │ action          │
│ root_cause      │       │ growth_rate     │       │ target_resource │
│ recovery_action │       │ predicted_hours │       │ details_json    │
│ success_rate    │       │ top_consumers   │       │ ip_address      │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

---

## 3. ML Intelligence & Simulation Lab Persistence

```text
┌─────────────────────────┐       ┌─────────────────────────┐
│        ml_models        │       │     ml_evaluations      │
├─────────────────────────┤       ├─────────────────────────┤
│ id (PK)                 │       │ id (PK)                 │
│ model_id (Unique)       │       │ evaluation_id           │
│ name, algorithm         │       │ model_id (FK)           │
│ version                 │       │ observations_count      │
│ status (ACTIVE|CANDIDATE│       │ precision, recall, f1   │
│ training_samples        │       │ false_positive_rate     │
│ evaluated_at            │       │ promotion_verdict       │
└─────────────────────────┘       └─────────────────────────┘
             │
             ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│   simulation_test_runs  │       │  simulation_test_events │
├─────────────────────────┤       ├─────────────────────────┤
│ id (PK)                 │◄──────┤ id (PK)                 │
│ test_id (Unique)        │       │ test_id (FK)            │
│ scenario_id, name       │       │ timestamp               │
│ target_service          │       │ event_type              │
│ severity                │       │ message                 │
│ status (PASSED|FAILED)  │       │ payload_json            │
│ attempts                │       └─────────────────────────┘
│ before_after_metrics    │
│ rca_result              │
│ verification_result     │
└─────────────────────────┘
```
