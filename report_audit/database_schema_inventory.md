# AegisOps AI — Database Schema Inventory

## 1. Database Overview

- **RDBMS Engine**: SQLite 3 (WAL mode enabled: `PRAGMA journal_mode=WAL`)
- **Database File**: `C:\Users\admin\AegisOps AI\aegisops.db`
- **Database File Size**: 9.53 MB
- **Total Managed Tables**: 48
- **ORM Layer**: SQLAlchemy 2.0 (AsyncSession with `aiosqlite`)

## 2. Table Inventory and Row Counts

| Table Name | Row Count | Column Count | Primary Key | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- |
| `anomaly_episodes` | 129 | 16 | `id` | Anomaly detection episodes, detector confidence, and metric breach history |
| `approvals` | 51 | 30 | `id` | Managed approval tickets, operator reviews, decisions, and audit archives |
| `archive_records` | 0 | 9 | `id` | Storage intelligence snapshots, tiering records, and retention compression logs |
| `archived_approvals` | 535 | 9 | `id` | Managed approval tickets, operator reviews, decisions, and audit archives |
| `audit_logs` | 0 | 7 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `azure_events` | 251 | 21 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `event_signatures` | 0 | 7 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `events` | 0 | 10 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `failure_scenarios_history` | 39 | 12 | `id` | Application data table |
| `historical_incidents` | 79 | 20 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incident_attempts` | 64 | 24 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incident_correlations` | 0 | 12 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incident_events` | 0 | 11 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incident_evidence` | 368 | 21 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incident_impacts` | 0 | 11 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incident_rca_records` | 102 | 21 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `incidents` | 100 | 59 | `id` | Stores active and historical incident records, evidence, hypotheses, and life-cycle state |
| `knowledge_base` | 36 | 22 | `id` | Curated knowledge base articles, verified symptoms, and standardized remediation runbooks |
| `log_features` | 0 | 23 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `logs` | 0 | 10 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `metrics` | 0 | 15 | `id` | Telemetry event store, normalized metrics, logs, and trace correlations |
| `notifications` | 57 | 12 | `id` | Application data table |
| `recovery_actions` | 0 | 12 | `id` | Automated and manual recovery plans, execution records, step logs, and verification state |
| `recovery_executions` | 296 | 31 | `id` | Automated and manual recovery plans, execution records, step logs, and verification state |
| `recovery_plans` | 52 | 12 | `id` | Automated and manual recovery plans, execution records, step logs, and verification state |
| `registered_services` | 0 | 13 | `id` | Application data table |
| `replica_experiments` | 104 | 32 | `id` | Digital twin instances, isolated test configurations, and experiment evaluation results |
| `replica_instances` | 11 | 16 | `id` | Digital twin instances, isolated test configurations, and experiment evaluation results |
| `revoked_tokens` | 0 | 4 | `id` | Application data table |
| `root_cause_candidates` | 129 | 10 | `id` | Application data table |
| `service_dependencies` | 0 | 12 | `id` | Application data table |
| `services` | 0 | 15 | `id` | Application data table |
| `sre_conversation_messages` | 152 | 12 | `id` | SRE conversational operations session memory, message history, and evidence references |
| `sre_conversations` | 52 | 8 | `id` | SRE conversational operations session memory, message history, and evidence references |
| `storage_snapshots` | 0 | 12 | `id` | Storage intelligence snapshots, tiering records, and retention compression logs |
| `system_settings` | 10 | 3 | `key` | Application data table |
| `team_members` | 0 | 5 | `id` | RBAC user accounts, hashed credentials, roles (VIEWER, OPERATOR, APPROVER, ADMIN) |
| `teams` | 0 | 7 | `id` | RBAC user accounts, hashed credentials, roles (VIEWER, OPERATOR, APPROVER, ADMIN) |
| `tenant_api_keys` | 78 | 10 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `tenant_architecture_nodes` | 23 | 24 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `tenant_audit_logs` | 630 | 11 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `tenant_integrations` | 71 | 18 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `tenant_policies` | 34 | 10 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `tenant_workflow_definitions` | 10 | 13 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `tenants` | 18 | 13 | `id` | Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes |
| `users` | 47 | 23 | `id` | RBAC user accounts, hashed credentials, roles (VIEWER, OPERATOR, APPROVER, ADMIN) |
| `validation_runs` | 0 | 17 | `id` | Application data table |
| `verified_recovery_patterns` | 38 | 28 | `id` | Automated and manual recovery plans, execution records, step logs, and verification state |

## 3. Comprehensive Column-Level Schema

### Table: `anomaly_episodes` (Rows: 129)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `episode_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `feature` | `VARCHAR(64)` | YES | `NULL` | - |
| `severity` | `VARCHAR(32)` | NO | `NULL` | - |
| `first_seen` | `DATETIME` | NO | `NULL` | - |
| `last_seen` | `DATETIME` | NO | `NULL` | - |
| `duration_seconds` | `FLOAT` | NO | `NULL` | - |
| `peak_score` | `FLOAT` | NO | `NULL` | - |
| `current_score` | `FLOAT` | NO | `NULL` | - |
| `event_count` | `INTEGER` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `details_json` | `TEXT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `approvals` (Rows: 51)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `approval_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `service_name` | `VARCHAR(64)` | YES | `NULL` | - |
| `proposed_action` | `VARCHAR(128)` | YES | `NULL` | - |
| `action_parameters_json` | `TEXT` | NO | `NULL` | - |
| `risk_level` | `VARCHAR(32)` | NO | `NULL` | - |
| `risk_score` | `FLOAT` | NO | `NULL` | - |
| `reason` | `TEXT` | YES | `NULL` | - |
| `expected_outcome` | `TEXT` | NO | `NULL` | - |
| `estimated_downtime_sec` | `INTEGER` | NO | `NULL` | - |
| `rollback_plan` | `TEXT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `reviewed_by` | `VARCHAR(64)` | NO | `NULL` | - |
| `review_notes` | `TEXT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `reviewed_at` | `DATETIME` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'demo-tenant'` | - |
| `required_role` | `VARCHAR(32)` | NO | `'APPROVER'` | - |
| `decision` | `VARCHAR(32)` | NO | `NULL` | - |
| `requested_by` | `VARCHAR(64)` | NO | `'AegisOps_Policy_Engine'` | - |
| `approved_at` | `DATETIME` | NO | `NULL` | - |
| `requested_at` | `DATETIME` | NO | `NULL` | - |
| `details_json` | `TEXT` | NO | `'{}'` | - |
| `plan_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `plan_version` | `VARCHAR(16)` | NO | `'v1.0'` | - |
| `solution_source` | `VARCHAR(32)` | NO | `NULL` | - |
| `remediation_run_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `is_consumed` | `BOOLEAN` | NO | `0` | - |
| `is_simulated` | `BOOLEAN` | NO | `0` | - |

### Table: `archive_records` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `archive_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `file_name` | `VARCHAR(256)` | YES | `NULL` | - |
| `source_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `original_size_bytes` | `INTEGER` | YES | `NULL` | - |
| `compressed_size_bytes` | `INTEGER` | YES | `NULL` | - |
| `compression_ratio` | `FLOAT` | NO | `NULL` | - |
| `archive_path` | `VARCHAR(512)` | YES | `NULL` | - |
| `archived_at` | `DATETIME` | NO | `NULL` | - |

### Table: `archived_approvals` (Rows: 535)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | `NULL` | PK |
| `original_approval_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `service_name` | `VARCHAR(64)` | NO | `NULL` | - |
| `proposed_action` | `VARCHAR(128)` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `archival_reason` | `TEXT` | NO | `NULL` | - |
| `archived_at` | `DATETIME` | NO | `NULL` | - |

### Table: `audit_logs` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `user_identifier` | `VARCHAR(128)` | NO | `NULL` | - |
| `action` | `VARCHAR(128)` | YES | `NULL` | - |
| `target_resource` | `VARCHAR(128)` | YES | `NULL` | - |
| `details_json` | `TEXT` | NO | `NULL` | - |
| `ip_address` | `VARCHAR(64)` | NO | `NULL` | - |

### Table: `azure_events` (Rows: 251)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `event_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `timestamp` | `DATETIME` | YES | `NULL` | - |
| `received_at` | `DATETIME` | YES | `NULL` | - |
| `source` | `VARCHAR(64)` | YES | `NULL` | - |
| `source_type` | `VARCHAR(32)` | YES | `NULL` | - |
| `environment` | `VARCHAR(32)` | YES | `NULL` | - |
| `subscription_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `resource_group` | `VARCHAR(64)` | NO | `NULL` | - |
| `resource_id` | `VARCHAR(512)` | NO | `NULL` | - |
| `resource_type` | `VARCHAR(128)` | NO | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `severity` | `VARCHAR(16)` | YES | `NULL` | - |
| `event_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `message` | `TEXT` | YES | `NULL` | - |
| `operation` | `VARCHAR(128)` | NO | `NULL` | - |
| `category` | `VARCHAR(64)` | NO | `NULL` | - |
| `properties_json` | `TEXT` | NO | `NULL` | - |
| `raw_event_hash` | `VARCHAR(64)` | YES | `NULL` | - |
| `is_redacted` | `BOOLEAN` | NO | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | NO | `NULL` | - |

### Table: `event_signatures` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `signature` | `VARCHAR(128)` | YES | `NULL` | - |
| `original_message_sample` | `TEXT` | YES | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `frequency` | `INTEGER` | NO | `NULL` | - |
| `first_seen` | `DATETIME` | NO | `NULL` | - |
| `last_seen` | `DATETIME` | NO | `NULL` | - |

### Table: `events` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `service_name` | `VARCHAR(64)` | YES | `NULL` | - |
| `event_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `severity` | `VARCHAR(32)` | NO | `NULL` | - |
| `score` | `FLOAT` | NO | `NULL` | - |
| `summary` | `VARCHAR(256)` | YES | `NULL` | - |
| `details_json` | `TEXT` | NO | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `is_correlated` | `INTEGER` | NO | `NULL` | - |

### Table: `failure_scenarios_history` (Rows: 39)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `failure_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `scenario_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `target_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `severity` | `VARCHAR(32)` | NO | `NULL` | - |
| `duration_sec` | `INTEGER` | NO | `NULL` | - |
| `lifecycle_state` | `VARCHAR(32)` | NO | `NULL` | - |
| `associated_incident_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `execution_mode` | `VARCHAR(32)` | NO | `NULL` | - |
| `started_at` | `VARCHAR(64)` | YES | `NULL` | - |
| `resolved_at` | `VARCHAR(64)` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'demo-tenant'` | - |

### Table: `historical_incidents` (Rows: 79)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `failure_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `failure_category` | `VARCHAR(64)` | YES | `NULL` | - |
| `primary_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `affected_services_json` | `TEXT` | NO | `NULL` | - |
| `telemetry_signature_json` | `TEXT` | NO | `NULL` | - |
| `root_cause` | `VARCHAR(256)` | YES | `NULL` | - |
| `rca_confidence` | `FLOAT` | NO | `NULL` | - |
| `remediation_action` | `VARCHAR(128)` | YES | `NULL` | - |
| `remediation_result` | `TEXT` | NO | `NULL` | - |
| `verification_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `verification_details_json` | `TEXT` | NO | `NULL` | - |
| `time_to_detect_sec` | `FLOAT` | NO | `NULL` | - |
| `time_to_recover_sec` | `FLOAT` | NO | `NULL` | - |
| `retry_count` | `INTEGER` | NO | `NULL` | - |
| `success` | `BOOLEAN` | NO | `NULL` | - |
| `created_at` | `VARCHAR(64)` | YES | `NULL` | - |
| `resolved_at` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'demo-tenant'` | - |

### Table: `incident_attempts` (Rows: 64)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `attempt_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `iteration` | `INTEGER` | NO | `NULL` | - |
| `solution_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `action` | `VARCHAR(128)` | YES | `NULL` | - |
| `target_component` | `VARCHAR(128)` | NO | `NULL` | - |
| `timestamp` | `FLOAT` | NO | `NULL` | - |
| `pre_execution_metrics_json` | `TEXT` | NO | `NULL` | - |
| `post_execution_metrics_json` | `TEXT` | NO | `NULL` | - |
| `execution_logs_json` | `TEXT` | NO | `NULL` | - |
| `execution_result_json` | `TEXT` | NO | `NULL` | - |
| `validation_result_json` | `TEXT` | NO | `NULL` | - |
| `original_error_resolved` | `BOOLEAN` | NO | `NULL` | - |
| `side_effect_detected` | `BOOLEAN` | NO | `NULL` | - |
| `solution_validated` | `BOOLEAN` | NO | `NULL` | - |
| `unresolved_conditions_json` | `TEXT` | NO | `NULL` | - |
| `side_effects_json` | `TEXT` | NO | `NULL` | - |
| `improved_conditions_json` | `TEXT` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
| `reasoning` | `TEXT` | NO | `NULL` | - |
| `next_action` | `VARCHAR(64)` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `incident_correlations` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `correlation_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `temporal_score` | `FLOAT` | NO | `NULL` | - |
| `dependency_score` | `FLOAT` | NO | `NULL` | - |
| `trace_score` | `FLOAT` | NO | `NULL` | - |
| `signature_score` | `FLOAT` | NO | `NULL` | - |
| `resource_score` | `FLOAT` | NO | `NULL` | - |
| `causal_score` | `FLOAT` | NO | `NULL` | - |
| `overall_score` | `FLOAT` | NO | `NULL` | - |
| `explanation_json` | `TEXT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `incident_events` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `event_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `severity` | `VARCHAR(32)` | NO | `NULL` | - |
| `message` | `TEXT` | YES | `NULL` | - |
| `trace_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `latency_ms` | `FLOAT` | NO | `NULL` | - |
| `details_json` | `TEXT` | NO | `NULL` | - |

### Table: `incident_evidence` (Rows: 368)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `timestamp` | `FLOAT` | NO | `NULL` | - |
| `source` | `VARCHAR(64)` | YES | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `component` | `VARCHAR(64)` | YES | `NULL` | - |
| `signal_type` | `VARCHAR(32)` | YES | `NULL` | - |
| `metric_or_log_value` | `VARCHAR(256)` | YES | `NULL` | - |
| `baseline` | `VARCHAR(64)` | NO | `NULL` | - |
| `deviation` | `VARCHAR(64)` | NO | `NULL` | - |
| `correlation_info_json` | `TEXT` | NO | `NULL` | - |
| `execution_iteration` | `INTEGER` | NO | `NULL` | - |
| `before_after_state` | `VARCHAR(16)` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `evidence_type` | `VARCHAR(32)` | NO | `'metric'` | - |
| `metric_name` | `VARCHAR(64)` | NO | `NULL` | - |
| `before_val` | `FLOAT` | NO | `NULL` | - |
| `after_val` | `FLOAT` | NO | `NULL` | - |
| `threshold_val` | `FLOAT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `'PASS'` | - |

### Table: `incident_impacts` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `criticality` | `VARCHAR(32)` | NO | `NULL` | - |
| `direct_impact_json` | `TEXT` | NO | `NULL` | - |
| `downstream_impact_json` | `TEXT` | NO | `NULL` | - |
| `affected_services_count` | `INTEGER` | NO | `NULL` | - |
| `affected_requests_count` | `INTEGER` | NO | `NULL` | - |
| `customer_facing` | `BOOLEAN` | NO | `NULL` | - |
| `impact_level` | `VARCHAR(32)` | NO | `NULL` | - |
| `blast_radius_score` | `FLOAT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `incident_rca_records` (Rows: 102)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `rca_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `root_cause_service` | `VARCHAR(64)` | NO | `NULL` | - |
| `root_cause_category` | `VARCHAR(64)` | NO | `NULL` | - |
| `root_cause_summary` | `TEXT` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
| `ai_solution_json` | `TEXT` | NO | `NULL` | - |
| `kb_solution_json` | `TEXT` | NO | `NULL` | - |
| `comparison_json` | `TEXT` | NO | `NULL` | - |
| `selected_solution_source` | `VARCHAR(32)` | NO | `NULL` | - |
| `selected_solution_json` | `TEXT` | NO | `NULL` | - |
| `selection_history_json` | `TEXT` | NO | `NULL` | - |
| `recovery_plan_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `recovery_execution_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `approval_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `approval_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `validation_result_json` | `TEXT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `incidents` (Rows: 100)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `title` | `VARCHAR(256)` | YES | `NULL` | - |
| `description` | `TEXT` | NO | `NULL` | - |
| `severity` | `VARCHAR(32)` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `primary_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `affected_services_json` | `TEXT` | NO | `NULL` | - |
| `correlated_event_count` | `INTEGER` | NO | `NULL` | - |
| `anomaly_score` | `FLOAT` | NO | `NULL` | - |
| `root_cause_service` | `VARCHAR(64)` | NO | `NULL` | - |
| `root_cause_category` | `VARCHAR(128)` | NO | `NULL` | - |
| `root_cause_summary` | `TEXT` | NO | `NULL` | - |
| `rca_confidence` | `FLOAT` | NO | `NULL` | - |
| `rca_evidence_json` | `TEXT` | NO | `NULL` | - |
| `business_impact_score` | `FLOAT` | NO | `NULL` | - |
| `estimated_users_affected` | `INTEGER` | NO | `NULL` | - |
| `sla_breach_risk` | `VARCHAR(32)` | NO | `NULL` | - |
| `recommended_action` | `VARCHAR(128)` | NO | `NULL` | - |
| `alternative_action` | `VARCHAR(128)` | NO | `NULL` | - |
| `action_risk_level` | `VARCHAR(32)` | NO | `NULL` | - |
| `recovery_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `timeline_json` | `TEXT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |
| `resolved_at` | `DATETIME` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'demo-tenant'` | - |
| `telemetry_source_mode` | `VARCHAR(32)` | NO | `'LIVE_DEMO_ENVIRONMENT'` | - |
| `lifecycle_state` | `VARCHAR(32)` | NO | `'DETECTED'` | - |
| `state_transitions_json` | `TEXT` | NO | `'[]'` | - |
| `hypotheses_json` | `TEXT` | NO | `'{}'` | - |
| `candidate_solutions_json` | `TEXT` | NO | `'[]'` | - |
| `selected_solution_json` | `TEXT` | NO | `'{}'` | - |
| `iteration_count` | `INTEGER` | NO | `0` | - |
| `max_iterations` | `INTEGER` | NO | `3` | - |
| `scenario_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `execution_history_json` | `TEXT` | NO | `'[]'` | - |
| `validation_report_json` | `TEXT` | NO | `'{}'` | - |
| `side_effects_detected_json` | `TEXT` | NO | `'[]'` | - |
| `unresolved_explanation` | `TEXT` | NO | `NULL` | - |
| `affected_resources_json` | `TEXT` | NO | `'[]'` | - |
| `affected_dependencies_json` | `TEXT` | NO | `'[]'` | - |
| `baseline_error_rate` | `FLOAT` | NO | `0.01` | - |
| `correlation_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `event_ids_json` | `TEXT` | NO | `NULL` | - |
| `error_rate` | `FLOAT` | NO | `NULL` | - |
| `root_cause` | `VARCHAR(256)` | NO | `NULL` | - |
| `root_cause_confidence` | `FLOAT` | NO | `NULL` | - |
| `approval_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `remediation_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `verification_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `dual_solutions_json` | `TEXT` | NO | `'{}'` | - |
| `selected_solution_source` | `VARCHAR(32)` | NO | `NULL` | - |
| `rca_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `plan_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `plan_version` | `VARCHAR(16)` | NO | `'v1.0'` | - |
| `remediation_run_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `verification_outcome` | `VARCHAR(64)` | NO | `NULL` | - |
| `is_synthetic` | `BOOLEAN` | NO | `1` | - |

### Table: `knowledge_base` (Rows: 36)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `incident_code` | `VARCHAR(64)` | YES | `NULL` | - |
| `title` | `VARCHAR(256)` | YES | `NULL` | - |
| `primary_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `symptoms_summary` | `TEXT` | YES | `NULL` | - |
| `root_cause` | `TEXT` | YES | `NULL` | - |
| `recommended_remedy` | `VARCHAR(128)` | YES | `NULL` | - |
| `recovery_action_taken` | `VARCHAR(128)` | YES | `NULL` | - |
| `recovery_duration_sec` | `FLOAT` | NO | `NULL` | - |
| `outcome` | `VARCHAR(32)` | NO | `NULL` | - |
| `historical_success_rate` | `FLOAT` | NO | `NULL` | - |
| `tags_json` | `TEXT` | NO | `NULL` | - |
| `vector_features_json` | `TEXT` | NO | `NULL` | - |
| `times_referenced` | `INTEGER` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'demo-tenant'` | - |
| `remediation_steps_json` | `TEXT` | NO | `'[]'` | - |
| `prerequisites_json` | `TEXT` | NO | `'[]'` | - |
| `risks_and_rollback_json` | `TEXT` | NO | `'[]'` | - |
| `verified_outcome_details` | `TEXT` | NO | `NULL` | - |
| `version` | `VARCHAR(32)` | NO | `'v1.0'` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `log_features` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `company` | `VARCHAR(64)` | YES | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `endpoint` | `VARCHAR(128)` | NO | `NULL` | - |
| `window_sec` | `FLOAT` | NO | `NULL` | - |
| `request_count` | `INTEGER` | NO | `NULL` | - |
| `error_count` | `INTEGER` | NO | `NULL` | - |
| `warning_count` | `INTEGER` | NO | `NULL` | - |
| `error_rate` | `FLOAT` | NO | `NULL` | - |
| `warning_rate` | `FLOAT` | NO | `NULL` | - |
| `five_xx_rate` | `FLOAT` | NO | `NULL` | - |
| `four_xx_rate` | `FLOAT` | NO | `NULL` | - |
| `timeout_count` | `INTEGER` | NO | `NULL` | - |
| `exception_count` | `INTEGER` | NO | `NULL` | - |
| `unique_error_patterns` | `INTEGER` | NO | `NULL` | - |
| `average_latency` | `FLOAT` | NO | `NULL` | - |
| `p95_latency` | `FLOAT` | NO | `NULL` | - |
| `p99_latency` | `FLOAT` | NO | `NULL` | - |
| `error_rate_change` | `FLOAT` | NO | `NULL` | - |
| `latency_change` | `FLOAT` | NO | `NULL` | - |
| `traffic_change` | `FLOAT` | NO | `NULL` | - |
| `timestamp` | `DATETIME` | NO | `NULL` | - |

### Table: `logs` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `service_name` | `VARCHAR(64)` | YES | `NULL` | - |
| `level` | `VARCHAR(16)` | YES | `NULL` | - |
| `event_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `message` | `TEXT` | YES | `NULL` | - |
| `trace_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `fingerprint` | `VARCHAR(64)` | YES | `NULL` | - |
| `occurrence_count` | `INTEGER` | NO | `NULL` | - |
| `metadata_json` | `TEXT` | NO | `NULL` | - |

### Table: `metrics` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `service_name` | `VARCHAR(64)` | YES | `NULL` | - |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `cpu_percent` | `FLOAT` | NO | `NULL` | - |
| `memory_mb` | `FLOAT` | NO | `NULL` | - |
| `request_count` | `INTEGER` | NO | `NULL` | - |
| `error_count` | `INTEGER` | NO | `NULL` | - |
| `error_rate` | `FLOAT` | NO | `NULL` | - |
| `latency_p50_ms` | `FLOAT` | NO | `NULL` | - |
| `latency_p95_ms` | `FLOAT` | NO | `NULL` | - |
| `latency_p99_ms` | `FLOAT` | NO | `NULL` | - |
| `active_connections` | `INTEGER` | NO | `NULL` | - |
| `anomaly_score` | `FLOAT` | NO | `NULL` | - |
| `is_anomaly` | `INTEGER` | NO | `NULL` | - |

### Table: `notifications` (Rows: 57)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `user_id` | `INTEGER` | NO | `NULL` | - |
| `role_target` | `VARCHAR(32)` | YES | `NULL` | - |
| `title` | `VARCHAR(256)` | YES | `NULL` | - |
| `message` | `TEXT` | YES | `NULL` | - |
| `severity` | `VARCHAR(32)` | YES | `NULL` | - |
| `event_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `deep_link` | `VARCHAR(256)` | NO | `NULL` | - |
| `is_read` | `BOOLEAN` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `recovery_actions` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `action_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `action_type` | `VARCHAR(128)` | YES | `NULL` | - |
| `target` | `VARCHAR(64)` | YES | `NULL` | - |
| `reason` | `TEXT` | NO | `NULL` | - |
| `risk` | `VARCHAR(32)` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `result` | `TEXT` | NO | `NULL` | - |
| `started_at` | `DATETIME` | NO | `NULL` | - |
| `finished_at` | `DATETIME` | NO | `NULL` | - |

### Table: `recovery_executions` (Rows: 296)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `execution_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `approval_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `service_name` | `VARCHAR(64)` | YES | `NULL` | - |
| `action` | `VARCHAR(128)` | YES | `NULL` | - |
| `risk_level` | `VARCHAR(32)` | NO | `NULL` | - |
| `execution_mode` | `VARCHAR(32)` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `duration_ms` | `FLOAT` | NO | `NULL` | - |
| `pre_health_score` | `FLOAT` | NO | `NULL` | - |
| `post_health_score` | `FLOAT` | NO | `NULL` | - |
| `verification_metrics_json` | `TEXT` | NO | `NULL` | - |
| `error_message` | `TEXT` | NO | `NULL` | - |
| `executed_at` | `DATETIME` | NO | `NULL` | - |
| `verified_at` | `DATETIME` | NO | `NULL` | - |
| `runbook_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `executor` | `VARCHAR(64)` | NO | `'AegisOps_Remediation_Engine'` | - |
| `success` | `BOOLEAN` | NO | `1` | - |
| `verification_status` | `VARCHAR(32)` | NO | `'VERIFIED'` | - |
| `steps_json` | `TEXT` | NO | `'[]'` | - |
| `result_json` | `TEXT` | NO | `'{}'` | - |
| `rollback_status` | `VARCHAR(32)` | NO | `'NONE'` | - |
| `started_at` | `DATETIME` | NO | `NULL` | - |
| `completed_at` | `DATETIME` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'demo-tenant'` | - |
| `plan_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `plan_version` | `VARCHAR(16)` | NO | `'v1.0'` | - |
| `solution_source` | `VARCHAR(32)` | NO | `NULL` | - |
| `is_simulated` | `BOOLEAN` | NO | `0` | - |
| `remediation_run_id` | `VARCHAR(64)` | NO | `NULL` | - |

### Table: `recovery_plans` (Rows: 52)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `plan_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `recommended_action` | `VARCHAR(128)` | YES | `NULL` | - |
| `candidate_solutions_json` | `TEXT` | NO | `NULL` | - |
| `recovery_score` | `FLOAT` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `plan_version` | `VARCHAR(16)` | NO | `'v1.0'` | - |
| `solution_source` | `VARCHAR(32)` | NO | `NULL` | - |

### Table: `registered_services` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `service_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `name` | `VARCHAR(64)` | YES | `NULL` | - |
| `display_name` | `VARCHAR(128)` | YES | `NULL` | - |
| `service_type` | `VARCHAR(64)` | NO | `NULL` | - |
| `environment` | `VARCHAR(32)` | NO | `NULL` | - |
| `resource_id` | `VARCHAR(256)` | NO | `NULL` | - |
| `resource_group` | `VARCHAR(128)` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `owner` | `VARCHAR(128)` | NO | `NULL` | - |
| `criticality` | `VARCHAR(32)` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `replica_experiments` (Rows: 104)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `experiment_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `replica_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `environment_type` | `VARCHAR(32)` | YES | `NULL` | - |
| `fidelity_level` | `FLOAT` | YES | `NULL` | - |
| `scenario_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `scenario_name` | `VARCHAR(128)` | YES | `NULL` | - |
| `target_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `stage` | `VARCHAR(32)` | YES | `NULL` | - |
| `status` | `VARCHAR(32)` | YES | `NULL` | - |
| `evaluation_verdict` | `VARCHAR(32)` | YES | `NULL` | - |
| `confidence_score` | `FLOAT` | YES | `NULL` | - |
| `initial_conditions_json` | `TEXT` | NO | `NULL` | - |
| `baseline_metrics_json` | `TEXT` | NO | `NULL` | - |
| `candidate_remediations_json` | `TEXT` | NO | `NULL` | - |
| `selected_candidate_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `applied_changes_json` | `TEXT` | NO | `NULL` | - |
| `test_workload_json` | `TEXT` | NO | `NULL` | - |
| `before_after_metrics_json` | `TEXT` | NO | `NULL` | - |
| `regression_checks_json` | `TEXT` | NO | `NULL` | - |
| `resource_usage_json` | `TEXT` | NO | `NULL` | - |
| `logs_json` | `TEXT` | NO | `NULL` | - |
| `evidence_references_json` | `TEXT` | NO | `NULL` | - |
| `ai_provider_model_json` | `TEXT` | NO | `NULL` | - |
| `approval_history_json` | `TEXT` | NO | `NULL` | - |
| `target_deployment_json` | `TEXT` | NO | `NULL` | - |
| `limitations_notes` | `TEXT` | NO | `NULL` | - |
| `duration_ms` | `INTEGER` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `completed_at` | `DATETIME` | NO | `NULL` | - |

### Table: `replica_instances` (Rows: 11)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `replica_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `environment_type` | `VARCHAR(32)` | YES | `NULL` | - |
| `fidelity_level` | `FLOAT` | YES | `NULL` | - |
| `status` | `VARCHAR(32)` | YES | `NULL` | - |
| `target_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `target_component` | `VARCHAR(64)` | NO | `NULL` | - |
| `active_scenario_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `isolation_boundaries_json` | `TEXT` | NO | `NULL` | - |
| `limitations_json` | `TEXT` | NO | `NULL` | - |
| `data_source_json` | `TEXT` | NO | `NULL` | - |
| `current_metrics_json` | `TEXT` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `revoked_tokens` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `jti` | `VARCHAR(128)` | YES | `NULL` | - |
| `revoked_at` | `DATETIME` | YES | `NULL` | - |
| `expires_at` | `DATETIME` | YES | `NULL` | - |

### Table: `root_cause_candidates` (Rows: 129)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `service` | `VARCHAR(64)` | YES | `NULL` | - |
| `rank` | `INTEGER` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
| `score` | `FLOAT` | NO | `NULL` | - |
| `causal_onset_time` | `VARCHAR(64)` | NO | `NULL` | - |
| `rationale` | `TEXT` | NO | `NULL` | - |
| `is_primary` | `BOOLEAN` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `'shopsphere'` | - |

### Table: `service_dependencies` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `dependency_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `source_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `target_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `relationship_type` | `VARCHAR(64)` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
| `observation_count` | `INTEGER` | NO | `NULL` | - |
| `correlated_failures_count` | `INTEGER` | NO | `NULL` | - |
| `evidence_json` | `TEXT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `first_seen` | `DATETIME` | NO | `NULL` | - |
| `last_seen` | `DATETIME` | NO | `NULL` | - |

### Table: `services` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `name` | `VARCHAR(64)` | YES | `NULL` | - |
| `display_name` | `VARCHAR(128)` | YES | `NULL` | - |
| `role` | `VARCHAR(128)` | YES | `NULL` | - |
| `port` | `INTEGER` | YES | `NULL` | - |
| `url` | `VARCHAR(256)` | YES | `NULL` | - |
| `health_endpoint` | `VARCHAR(128)` | NO | `NULL` | - |
| `metrics_endpoint` | `VARCHAR(128)` | NO | `NULL` | - |
| `dependencies_json` | `TEXT` | NO | `NULL` | - |
| `criticality` | `VARCHAR(32)` | NO | `NULL` | - |
| `sla_target_pct` | `FLOAT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `is_monitored` | `BOOLEAN` | NO | `NULL` | - |
| `last_seen` | `DATETIME` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `sre_conversation_messages` (Rows: 152)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `message_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `conversation_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `role` | `VARCHAR(16)` | YES | `NULL` | - |
| `content` | `TEXT` | YES | `NULL` | - |
| `sources_json` | `TEXT` | NO | `NULL` | - |
| `evidence_json` | `TEXT` | NO | `NULL` | - |
| `suggested_json` | `TEXT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `error_message` | `TEXT` | NO | `NULL` | - |
| `timestamp` | `DATETIME` | NO | `NULL` | - |

### Table: `sre_conversations` (Rows: 52)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `conversation_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `title` | `VARCHAR(256)` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `storage_snapshots` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `total_gb` | `FLOAT` | NO | `NULL` | - |
| `used_gb` | `FLOAT` | NO | `NULL` | - |
| `free_gb` | `FLOAT` | NO | `NULL` | - |
| `used_percentage` | `FLOAT` | NO | `NULL` | - |
| `growth_rate_gb_per_hour` | `FLOAT` | NO | `NULL` | - |
| `predicted_critical_hours` | `FLOAT` | NO | `NULL` | - |
| `log_files_count` | `INTEGER` | NO | `NULL` | - |
| `total_log_size_mb` | `FLOAT` | NO | `NULL` | - |
| `archive_size_mb` | `FLOAT` | NO | `NULL` | - |
| `top_consumers_json` | `TEXT` | NO | `NULL` | - |

### Table: `system_settings` (Rows: 10)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `key` | `VARCHAR(128)` | YES | `NULL` | PK |
| `value` | `TEXT` | YES | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `team_members` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `team_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `user_id` | `INTEGER` | YES | `NULL` | - |
| `role_in_team` | `VARCHAR(32)` | YES | `NULL` | - |
| `joined_at` | `DATETIME` | NO | `NULL` | - |

### Table: `teams` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `description` | `VARCHAR(256)` | NO | `NULL` | - |
| `lead_user` | `VARCHAR(128)` | NO | `NULL` | - |
| `assigned_services_json` | `TEXT` | YES | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `tenant_api_keys` (Rows: 78)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `key_prefix` | `VARCHAR(16)` | YES | `NULL` | - |
| `hashed_key` | `VARCHAR(128)` | YES | `NULL` | - |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `scopes` | `VARCHAR(256)` | YES | `NULL` | - |
| `is_active` | `BOOLEAN` | YES | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `expires_at` | `DATETIME` | NO | `NULL` | - |
| `last_used_at` | `DATETIME` | NO | `NULL` | - |

### Table: `tenant_architecture_nodes` (Rows: 23)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `resource_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `display_name` | `VARCHAR(128)` | YES | `NULL` | - |
| `resource_type` | `VARCHAR(64)` | NO | `NULL` | - |
| `environment` | `VARCHAR(32)` | NO | `NULL` | - |
| `runtime_platform` | `VARCHAR(64)` | NO | `NULL` | - |
| `owner_team` | `VARCHAR(128)` | NO | `NULL` | - |
| `on_call_schedule` | `VARCHAR(128)` | NO | `NULL` | - |
| `maintenance_window` | `VARCHAR(128)` | NO | `NULL` | - |
| `data_classification` | `VARCHAR(32)` | NO | `NULL` | - |
| `recovery_capabilities_json` | `TEXT` | NO | `NULL` | - |
| `rollback_supported` | `BOOLEAN` | NO | `NULL` | - |
| `change_freeze_active` | `BOOLEAN` | NO | `NULL` | - |
| `discovery_source` | `VARCHAR(64)` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
| `freshness_status` | `VARCHAR(32)` | NO | `NULL` | - |
| `is_verified` | `BOOLEAN` | NO | `NULL` | - |
| `metadata_json` | `TEXT` | NO | `NULL` | - |
| `first_seen` | `DATETIME` | NO | `NULL` | - |
| `last_seen` | `DATETIME` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `tenant_audit_logs` (Rows: 630)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `user_identifier` | `VARCHAR(128)` | YES | `NULL` | - |
| `action` | `VARCHAR(64)` | YES | `NULL` | - |
| `resource_type` | `VARCHAR(64)` | NO | `NULL` | - |
| `resource_id` | `VARCHAR(128)` | NO | `NULL` | - |
| `details_json` | `TEXT` | NO | `NULL` | - |
| `ip_address` | `VARCHAR(64)` | NO | `NULL` | - |
| `timestamp` | `DATETIME` | NO | `NULL` | - |
| `user_role` | `VARCHAR(32)` | NO | `'OPERATOR'` | - |
| `result` | `VARCHAR(32)` | NO | `'SUCCESS'` | - |

### Table: `tenant_integrations` (Rows: 71)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `type` | `VARCHAR(32)` | YES | `NULL` | - |
| `status` | `VARCHAR(32)` | YES | `NULL` | - |
| `config_json` | `TEXT` | NO | `NULL` | - |
| `last_telemetry_at` | `DATETIME` | NO | `NULL` | - |
| `events_per_sec` | `FLOAT` | NO | `NULL` | - |
| `bytes_per_sec` | `FLOAT` | NO | `NULL` | - |
| `dropped_events` | `INTEGER` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `last_seen_at` | `DATETIME` | NO | `NULL` | - |
| `last_log_at` | `DATETIME` | NO | `NULL` | - |
| `last_metric_at` | `DATETIME` | NO | `NULL` | - |
| `last_trace_at` | `DATETIME` | NO | `NULL` | - |
| `last_event_at` | `DATETIME` | NO | `NULL` | - |
| `events_received` | `INTEGER` | NO | `0` | - |
| `bytes_received` | `INTEGER` | NO | `0` | - |

### Table: `tenant_policies` (Rows: 34)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `auto_remediation_enabled` | `BOOLEAN` | YES | `NULL` | - |
| `allowed_actions_json` | `TEXT` | YES | `NULL` | - |
| `max_auto_risk_level` | `VARCHAR(32)` | YES | `NULL` | - |
| `min_rca_confidence` | `FLOAT` | YES | `NULL` | - |
| `max_blast_radius` | `FLOAT` | YES | `NULL` | - |
| `cooldown_seconds` | `INTEGER` | YES | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `tenant_workflow_definitions` (Rows: 10)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `workflow_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `criticality` | `VARCHAR(32)` | NO | `NULL` | - |
| `entrypoint_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `service_path_json` | `TEXT` | NO | `NULL` | - |
| `slo_target_latency_ms` | `FLOAT` | NO | `NULL` | - |
| `slo_target_availability_pct` | `FLOAT` | NO | `NULL` | - |
| `discovery_source` | `VARCHAR(64)` | NO | `NULL` | - |
| `is_verified` | `BOOLEAN` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `updated_at` | `DATETIME` | NO | `NULL` | - |

### Table: `tenants` (Rows: 18)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | YES | `NULL` | PK |
| `name` | `VARCHAR(128)` | YES | `NULL` | - |
| `slug` | `VARCHAR(64)` | YES | `NULL` | - |
| `tier` | `VARCHAR(32)` | YES | `NULL` | - |
| `status` | `VARCHAR(32)` | YES | `NULL` | - |
| `retention_days` | `INTEGER` | YES | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `settings_json` | `TEXT` | NO | `NULL` | - |
| `plan` | `VARCHAR(32)` | NO | `'Enterprise'` | - |
| `industry` | `VARCHAR(64)` | NO | `'Financial Services'` | - |
| `region` | `VARCHAR(64)` | NO | `'India'` | - |
| `logo_url` | `VARCHAR(256)` | NO | `NULL` | - |
| `environments_json` | `TEXT` | NO | `'["PRODUCTION", "STAGING", "DEVELOPMENT", "CONTROLLED_CUSTOMER_TEST", "DEMO", "LOAD_TEST"]'` | - |

### Table: `users` (Rows: 47)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `username` | `VARCHAR(64)` | YES | `NULL` | - |
| `email` | `VARCHAR(128)` | YES | `NULL` | - |
| `hashed_password` | `VARCHAR(256)` | YES | `NULL` | - |
| `full_name` | `VARCHAR(128)` | NO | `NULL` | - |
| `role` | `VARCHAR(32)` | YES | `NULL` | - |
| `is_active` | `BOOLEAN` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `is_platform_admin` | `BOOLEAN` | NO | `0` | - |
| `organization_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `mfa_enabled` | `BOOLEAN` | NO | `0` | - |
| `mfa_secret` | `VARCHAR(64)` | NO | `NULL` | - |
| `phone` | `VARCHAR(32)` | NO | `NULL` | - |
| `last_login_at` | `DATETIME` | NO | `NULL` | - |
| `must_change_password` | `BOOLEAN` | NO | `0` | - |
| `failed_login_attempts` | `INTEGER` | NO | `0` | - |
| `locked_until` | `DATETIME` | NO | `NULL` | - |
| `password_reset_token` | `VARCHAR(128)` | NO | `NULL` | - |
| `password_reset_expires_at` | `DATETIME` | NO | `NULL` | - |
| `invitation_token` | `VARCHAR(128)` | NO | `NULL` | - |
| `invitation_expires_at` | `DATETIME` | NO | `NULL` | - |
| `session_revoked_at` | `DATETIME` | NO | `NULL` | - |

### Table: `validation_runs` (Rows: 0)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `validation_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `action_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `iteration` | `INTEGER` | NO | `NULL` | - |
| `pre_metrics_json` | `TEXT` | NO | `NULL` | - |
| `post_metrics_json` | `TEXT` | NO | `NULL` | - |
| `comparison_table_json` | `TEXT` | NO | `NULL` | - |
| `error_reduction` | `FLOAT` | NO | `NULL` | - |
| `latency_reduction` | `FLOAT` | NO | `NULL` | - |
| `availability_improvement` | `FLOAT` | NO | `NULL` | - |
| `original_error_resolved` | `BOOLEAN` | NO | `NULL` | - |
| `side_effect_detected` | `BOOLEAN` | NO | `NULL` | - |
| `side_effects_json` | `TEXT` | NO | `NULL` | - |
| `status` | `VARCHAR(32)` | NO | `NULL` | - |
| `created_at` | `DATETIME` | NO | `NULL` | - |

### Table: `verified_recovery_patterns` (Rows: 38)

| Column Name | Type | Not Null | Default Value | Primary Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | YES | `NULL` | PK |
| `pattern_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `tenant_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `incident_type` | `VARCHAR(64)` | YES | `NULL` | - |
| `failure_signature_json` | `TEXT` | NO | `NULL` | - |
| `root_cause_category` | `VARCHAR(64)` | YES | `NULL` | - |
| `root_cause_description` | `TEXT` | YES | `NULL` | - |
| `origin_service` | `VARCHAR(64)` | YES | `NULL` | - |
| `affected_services_json` | `TEXT` | NO | `NULL` | - |
| `relevant_metrics_json` | `TEXT` | NO | `NULL` | - |
| `relevant_log_signatures_json` | `TEXT` | NO | `NULL` | - |
| `relevant_trace_signatures_json` | `TEXT` | NO | `NULL` | - |
| `dependency_context_json` | `TEXT` | NO | `NULL` | - |
| `recovery_action` | `VARCHAR(128)` | YES | `NULL` | - |
| `recovery_reason` | `TEXT` | YES | `NULL` | - |
| `attempts_required` | `INTEGER` | NO | `NULL` | - |
| `pre_fix_metrics_json` | `TEXT` | NO | `NULL` | - |
| `post_fix_metrics_json` | `TEXT` | NO | `NULL` | - |
| `validation_results_json` | `TEXT` | NO | `NULL` | - |
| `side_effect_results_json` | `TEXT` | NO | `NULL` | - |
| `recovery_duration_sec` | `FLOAT` | NO | `NULL` | - |
| `verified_at` | `VARCHAR(64)` | YES | `NULL` | - |
| `verification_score` | `FLOAT` | NO | `NULL` | - |
| `environment_type` | `VARCHAR(32)` | NO | `NULL` | - |
| `sandbox_id` | `VARCHAR(64)` | YES | `NULL` | - |
| `source_execution_id` | `VARCHAR(64)` | NO | `NULL` | - |
| `confidence` | `FLOAT` | NO | `NULL` | - |
