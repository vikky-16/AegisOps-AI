# AegisOps AI — Architectural Diagrams & Visual Specifications

This document contains report-ready Mermaid architectural diagrams illustrating the core subsystems of AegisOps AI.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Client Tier (React 18 + Vite)"]
        UI["SRE Operations Dashboard"]
        RCA_UI["Dual-Solution RCA & Blast Radius"]
        Lab_UI["Replica Lab (Digital Twin)"]
        App_UI["Approval Center (Governance)"]
        Rec_UI["Recovery Orchestrator"]
        Set_UI["AI Config & Model Discovery"]
    end

    subgraph APILayer["FastAPI Asynchronous Gateway (:8000)"]
        Auth["JWT Auth & RBAC Guard"]
        Router_Inc["Incident & RCA Routers"]
        Router_App["Approval Center Routers"]
        Router_Rec["Recovery & Sandbox Routers"]
        Router_Lab["Replica Lab Routers"]
        Router_AI["Gemini 3.8 & Model Discovery"]
        Ingest["Telemetry Ingestion Gateway"]
    end

    subgraph PerceptionLayer["Perception & Anomaly Engine"]
        Normalizer["Universal Normalizer (OTel / JSON)"]
        EventBus["AegisEventBus (Kafka / In-Memory)"]
        Detectors["Multi-Detector Engine (Z-Score, EWMA, IsoForest)"]
        Correlator["Event Correlator & Graph Engine"]
    end

    subgraph CognitiveLayer["Cognitive & Reasoning Engine"]
        RCA15["15-Question RCA Fact Builder"]
        DualEngine["Dual-Solution Synthesis Engine"]
        Gemini38["Google Gemini 3.8 Flash (thinkingBudget: 8192)"]
        KB["Curated Runbook Knowledge Base"]
    end

    subgraph ExecutionLayer["Digital Twin & Safe Remediation Tier"]
        ReplicaLab["Digital Twin Replica Lab (17-Step Lifecycle)"]
        ApprovalMgr["Approval Governance & Risk Evaluator"]
        ExecEngine["Controlled Execution Engine (Allowlisted Actions)"]
        Validator["8-Point Empirical Validator"]
        RefineLoop["Bounded Refinement Engine (Ceiling: 3)"]
    end

    subgraph StorageLayer["Data & Persistence Tier"]
        SQLite[("SQLite 3 (WAL Mode - aegisops.db, 48 Tables)")]
        AuditLog[("Immutable Audit Trail (tenant_audit_logs)")]
        Memory[("Verified Recovery Patterns & History")]
    end

    ClientLayer <-->|HTTP REST / SSE Stream| APILayer
    APILayer --> PerceptionLayer
    PerceptionLayer --> CognitiveLayer
    CognitiveLayer --> ExecutionLayer
    ExecutionLayer --> StorageLayer
    CognitiveLayer <--> Gemini38
    CognitiveLayer <--> KB
    ExecutionLayer -->|Empirical Delta| StorageLayer
```

---

## 2. Detailed Incident-Processing Data Flow

```mermaid
flowchart LR
    A["Raw Telemetry Stream (Metrics, Logs, Spans)"] --> B["Universal Normalizer"]
    B --> C["UnifiedTelemetryEvent Contract"]
    C --> D["Multi-Detector Statistical Evaluation"]
    D -->|Z-Score > 3.0 or EWMA Breach| E{"Consecutive Breach Guard (3 Cycles)?"}
    E -- No --> F["Discard (Transient Noise)"]
    E -- Yes --> G["Event Correlator (Temporal 300s & Graph)"]
    G --> H["Incident State Machine (State: OPEN)"]
    H --> I["15-Question Evidence Package Extraction"]
    I --> J["Dual-Solution Synthesis"]
    J --> K["Solution A (Gemini 3.8 Flash LLM)"]
    J --> L["Solution B (Knowledge Base Runbook)"]
    K --> M["Consensus Evaluator (Aligned vs Conflict)"]
    L --> M
    M --> N["Submit to Digital Twin Replica Lab"]
```

---

## 3. Recovery and Validation Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Operator as SRE Operator / Commander
    participant Lab as Replica Lab (Digital Twin)
    participant Twin as Isolated Replica Sandbox
    participant Appr as Approval Center
    participant Exec as Controlled Execution Engine
    participant Target as Target Microservice
    participant Val as 8-Point Empirical Validator
    participant DB as SQLite Storage (aegisops.db)

    Operator->>Lab: 1. Trigger Replica Experiment for Incident
    Lab->>Twin: 2. Allocate Twin & Inject Scenario Fault
    Twin-->>Lab: 3. Return Pre-Intervention Baseline Metrics
    Lab->>Twin: 4. Apply Candidate Remediation in Sandbox
    Lab->>Twin: 5. Replay Stress Workload (2,500 reqs, concurrency 50)
    Twin-->>Lab: 6. Measure Post-Intervention Delta & Regressions
    Lab->>DB: 7. Save Experiment Record (Verdict: PASS / INCONCLUSIVE)
    Lab-->>Operator: 8. Present Multi-Candidate Comparison Matrix

    alt Risk Exceeds Tenant Risk Ceiling
        Lab->>Appr: 9a. Create Approval Ticket (State: PENDING)
        Operator->>Appr: 10a. Review Justification & Sign Off (Approve)
        Appr->>Exec: 11a. Authorize Allowlisted Action Dispatch
    else Pre-Approved Low Risk Action
        Lab->>Exec: 9b. Direct Dispatch Permitted
    end

    Exec->>Target: 12. Invoke Allowlisted Action (e.g., RESET_CONNECTION_POOL)
    Target-->>Exec: 13. Acknowledge Execution
    Exec->>Val: 14. Trigger Post-Recovery Validation
    Val->>Target: 15. Check Reachability, Error Rate, Latency Envelope
    Val->>Target: 16. Verify Telemetry Freshness & No Secondary Side-Effects

    alt All 8 Empirical Criteria Pass
        Val->>DB: 17a. Mark Incident RESOLVED & Commit Verified Pattern
        Val-->>Operator: 18a. Notify Incident Successfully Mitigated
    else Any Validation Criterion Fails
        Val->>DB: 17b. Record Failed Attempt (Attempt Count: k / 3)
        alt Attempt < Max Ceiling
            Val->>Lab: 18b. Trigger Next Bounded Refinement Candidate
        else Attempt == Max Ceiling
            Val->>DB: 19. Mark State: UNRESOLVED
            Val-->>Operator: 20. Escalate to SRE Incident Commander
        end
    end
```

---

## 4. Multi-Tenant Microservice & Deployment Topology

```mermaid
flowchart TD
    subgraph HostEnvironment["Host Virtual / Bare-Metal Environment (Windows 11 / Linux)"]
        subgraph CorePlatform["AegisOps AI Core Services"]
            FastAPI["FastAPI ASGI Backend (:8000)"]
            ReactUI["React 18 Frontend Dev/Vite (:5173 / :80)"]
            DB_Instance[("SQLite aegisops.db (WAL Mode)")]
        end

        subgraph CoreDemoServices["Core Demo Microservices Mesh (:8001 - :8005)"]
            GW["gateway (:8001)"]
            SvA["service-a (:8002)"]
            SvB["service-b (:8003)"]
            AuthSvc["auth-service (:8004)"]
            DBSvc["database-service (:8005)"]
        end

        subgraph TenantShopSphere["ShopSphere Tenant Fleet (E-Commerce)"]
            Shop_Store["Storefront API (:8010)"]
            Shop_Cart["Cart Service (:8011)"]
            Shop_Order["Order Processor (:8012)"]
            Shop_Pay["Payment Gateway (:8013)"]
            Shop_Streamer["ShopSphere Telemetry Streamer"]
        end

        subgraph TenantFinCore["FinCore Tenant Fleet (Banking & Ledger)"]
            Fin_Core["Core Banking API (:8020)"]
            Fin_Ledger["Transaction Ledger (:8021)"]
            Fin_Acct["Account Service (:8022)"]
            Fin_Fraud["Fraud Detection Pipeline (:8023)"]
        end

        subgraph TenantCloudDesk["CloudDesk Tenant Fleet (Collaborative SaaS)"]
            Cloud_Auth["Token Verification (:8030)"]
            Cloud_Doc["Document Store (:8031)"]
            Cloud_Sync["Real-Time Sync Engine (:8032)"]
        end
    end

    GW --> SvA & SvB
    SvA --> DBSvc
    SvB --> AuthSvc

    Shop_Store --> Shop_Cart --> Shop_Order --> Shop_Pay
    Fin_Core --> Fin_Acct --> Fin_Ledger --> Fin_Fraud
    Cloud_Doc --> Cloud_Sync --> Cloud_Auth

    Shop_Streamer & CoreDemoServices & TenantFinCore & TenantCloudDesk -->|OTLP / REST Ingest| FastAPI
    FastAPI <--> DB_Instance
```

---

## 5. Entity Relationship Diagram (Database Schema)

```mermaid
erDiagram
    TENANTS ||--o{ INCIDENTS : owns
    TENANTS ||--o{ APPROVALS : governs
    TENANTS ||--o{ RECOVERY_PLANS : configures
    TENANTS ||--o{ REPLICA_INSTANCES : hosts
    TENANTS ||--o{ REPLICA_EXPERIMENTS : executes
    TENANTS ||--o{ TENANT_POLICIES : enforces
    TENANTS ||--o{ TENANT_API_KEYS : issues

    INCIDENTS ||--o{ INCIDENT_EVIDENCE : contains
    INCIDENTS ||--o{ INCIDENT_RCA_RECORDS : produces
    INCIDENTS ||--o{ APPROVALS : requires
    INCIDENTS ||--o{ RECOVERY_PLANS : plans
    INCIDENTS ||--o{ RECOVERY_EXECUTIONS : attempts
    INCIDENTS ||--o{ REPLICA_EXPERIMENTS : tests_in
    INCIDENTS ||--o{ INCIDENT_ATTEMPTS : records

    RECOVERY_PLANS ||--o{ RECOVERY_EXECUTIONS : executes
    APPROVALS ||--o{ RECOVERY_EXECUTIONS : authorizes

    INCIDENTS {
        string incident_id PK
        string tenant_id FK
        string title
        string severity
        string status
        string primary_service
        string root_cause_category
        string root_cause_confidence
        string lifecycle_state
        boolean is_synthetic
        datetime created_at
        datetime resolved_at
    }

    APPROVALS {
        string approval_id PK
        string incident_id FK
        string tenant_id FK
        string service_name
        string proposed_action
        string risk_level
        string status
        string required_role
        string reviewed_by
        datetime created_at
        datetime approved_at
    }

    REPLICA_EXPERIMENTS {
        string experiment_id PK
        string incident_id FK
        string replica_id FK
        string tenant_id FK
        string environment_type
        string fidelity_level
        string evaluation_verdict
        float confidence_score
        string selected_candidate_id
        int duration_ms
        datetime created_at
    }

    RECOVERY_EXECUTIONS {
        string execution_id PK
        string incident_id FK
        string approval_id FK
        string service_name
        string action
        string status
        string verification_status
        datetime created_at
    }

    TENANT_POLICIES {
        string tenant_id PK
        boolean auto_remediation_enabled
        string allowed_actions_json
        string max_auto_risk_level
        float min_rca_confidence
    }
```

