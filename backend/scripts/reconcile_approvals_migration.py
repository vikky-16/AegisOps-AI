"""
Safe, auditable database reconciliation migration for AegisOps AI.
Preserves existing companies, legitimate incidents, and audit trails.
Safely archives orphaned/test duplicates to `archived_approvals`.
Ensures FinCore, ShopSphere, and CloudDesk have realistic incidents, dual solutions, and legitimate approval requests.
"""

import sqlite3
import json
import os
import shutil
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROOT_DB = os.path.join(WORKSPACE_ROOT, "aegisops.db")
BACKEND_DB = os.path.join(WORKSPACE_ROOT, "backend", "aegisops.db")

def run_migration_on_db(db_path: str):
    print(f"--- Running migration on {db_path} ---")
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist, skipping.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Add missing columns safely if not present
    def add_col_if_missing(table, col, col_def):
        cur.execute(f"PRAGMA table_info({table});")
        cols = {r[1] for r in cur.fetchall()}
        if col not in cols:
            print(f"Adding column {col} to {table}...")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def};")

    add_col_if_missing("incidents", "tenant_id", "VARCHAR(64) DEFAULT 'demo-tenant'")
    add_col_if_missing("incidents", "telemetry_source_mode", "VARCHAR(32) DEFAULT 'LIVE_CUSTOMER'")
    add_col_if_missing("incidents", "dual_solutions_json", "TEXT DEFAULT '{}'")
    add_col_if_missing("incidents", "selected_solution_source", "VARCHAR(32)")
    add_col_if_missing("incidents", "rca_id", "VARCHAR(64)")
    add_col_if_missing("incidents", "plan_id", "VARCHAR(64)")
    add_col_if_missing("incidents", "plan_version", "VARCHAR(16) DEFAULT 'v1.0'")
    add_col_if_missing("incidents", "remediation_run_id", "VARCHAR(64)")
    add_col_if_missing("incidents", "verification_outcome", "VARCHAR(64)")

    add_col_if_missing("approvals", "tenant_id", "VARCHAR(64) DEFAULT 'demo-tenant'")
    add_col_if_missing("approvals", "required_role", "VARCHAR(32) DEFAULT 'APPROVER'")
    add_col_if_missing("approvals", "decision", "VARCHAR(32)")
    add_col_if_missing("approvals", "requested_by", "VARCHAR(64) DEFAULT 'AegisOps_Policy_Engine'")
    add_col_if_missing("approvals", "approved_at", "DATETIME")
    add_col_if_missing("approvals", "requested_at", "DATETIME")
    add_col_if_missing("approvals", "details_json", "TEXT DEFAULT '{}'")
    add_col_if_missing("approvals", "plan_id", "VARCHAR(64)")
    add_col_if_missing("approvals", "plan_version", "VARCHAR(16) DEFAULT 'v1.0'")
    add_col_if_missing("approvals", "solution_source", "VARCHAR(32)")
    add_col_if_missing("approvals", "remediation_run_id", "VARCHAR(64)")
    add_col_if_missing("approvals", "is_consumed", "BOOLEAN DEFAULT 0")

    add_col_if_missing("recovery_executions", "tenant_id", "VARCHAR(64)")
    add_col_if_missing("recovery_executions", "plan_id", "VARCHAR(64)")
    add_col_if_missing("recovery_executions", "plan_version", "VARCHAR(16) DEFAULT 'v1.0'")
    add_col_if_missing("recovery_executions", "solution_source", "VARCHAR(32)")
    add_col_if_missing("recovery_executions", "is_simulated", "BOOLEAN DEFAULT 0")

    add_col_if_missing("recovery_plans", "plan_version", "VARCHAR(16) DEFAULT 'v1.0'")
    add_col_if_missing("recovery_plans", "solution_source", "VARCHAR(32)")

    # 2. Create archived_approvals table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS archived_approvals (
        id INTEGER PRIMARY KEY,
        original_approval_id VARCHAR(64),
        incident_id VARCHAR(64),
        tenant_id VARCHAR(64),
        service_name VARCHAR(64),
        proposed_action VARCHAR(128),
        status VARCHAR(32),
        archival_reason TEXT,
        archived_at DATETIME
    );
    """)

    # 3. Archive invalid test approvals (APP-6-xxxx, orphaned approvals whose incidents don't exist)
    cur.execute("SELECT approval_id, incident_id, tenant_id, service_name, proposed_action, status FROM approvals;")
    all_approvals = cur.fetchall()

    cur.execute("SELECT incident_id FROM incidents;")
    valid_inc_ids = {r[0] for r in cur.fetchall()}

    now_iso = datetime.now(timezone.utc).isoformat()
    archived_count = 0
    preserved_count = 0

    for app in all_approvals:
        app_id, inc_id, t_id, svc, act, st = app
        is_invalid = False
        reason = ""

        if app_id.startswith("APP-6-"):
            is_invalid = True
            reason = "Legacy automated diagnostic test record"
        elif app_id.startswith("APP-VAL-") and (inc_id not in valid_inc_ids):
            is_invalid = True
            reason = f"Orphaned approval from old test run: incident {inc_id} does not exist"
        elif inc_id not in valid_inc_ids and not inc_id.startswith("INC-HIST-") and not inc_id.startswith("INC-FINCORE-") and not inc_id.startswith("INC-SHOPSPHERE-") and not inc_id.startswith("INC-CLOUDDESK-"):
            is_invalid = True
            reason = f"Orphaned approval: referenced incident {inc_id} does not exist"
        elif t_id in ["test-accuracy-tenant", "test-dist-tenant", "test-persist-tenant", "test-reprocess-tenant", "company-a", "company-b"]:
            is_invalid = True
            reason = f"Ephemeral test runner tenant: {t_id}"

        if is_invalid:
            cur.execute("""
            INSERT INTO archived_approvals (original_approval_id, incident_id, tenant_id, service_name, proposed_action, status, archival_reason, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (app_id, inc_id, t_id, svc, act, st, reason, now_iso))
            cur.execute("DELETE FROM approvals WHERE approval_id = ?;", (app_id,))
            archived_count += 1
        else:
            preserved_count += 1

    print(f"Archived {archived_count} invalid/orphaned approval records. Preserved {preserved_count} valid records.")

    # 4. Ensure realistic canonical incidents exist for FinCore, ShopSphere, and CloudDesk
    # FinCore incident:
    cur.execute("SELECT incident_id FROM incidents WHERE incident_id = 'INC-FINCORE-001';")
    if not cur.fetchone():
        print("Seeding canonical FinCore incident INC-FINCORE-001...")
        cur.execute("""
        INSERT OR REPLACE INTO incidents (
            incident_id, title, description, severity, status, primary_service, root_cause_service,
            root_cause_category, root_cause_summary, root_cause_confidence, rca_confidence,
            recommended_action, action_risk_level, approval_status, remediation_status,
            verification_status, recovery_status, lifecycle_state, tenant_id, telemetry_source_mode,
            affected_services_json, rca_evidence_json, error_rate, created_at, updated_at,
            selected_solution_source, plan_id, plan_version
        ) VALUES (
            'INC-FINCORE-001',
            'ACID Transaction Ledger Connection Pool Saturation on database-service',
            'Ledger settlement connections reached 20/20 max capacity. Payment API experienced HTTP 504 timeouts.',
            'HIGH',
            'AWAITING_APPROVAL',
            'database-service',
            'database-service',
            'DATABASE_CONNECTION_POOL_EXHAUSTION',
            'Long-running transaction locks held during peak settlement window exhausted connection pool handles.',
            0.95,
            0.95,
            'RESET_CONNECTION_POOL',
            'HIGH',
            'PENDING',
            'PENDING',
            'WAITING_FOR_TELEMETRY',
            'AWAITING_APPROVAL',
            'AWAITING_APPROVAL',
            'fincore',
            'LIVE_CUSTOMER',
            '["database-service", "payment-api", "service-b"]',
            '["Active connections reached 20/20 limit on ledger DB port 8004", "Transaction acquire wait time jumped from 12ms to 4850ms", "Downstream payment settlement API returning HTTP 504 Gateway Timeout"]',
            0.185,
            ?,
            ?,
            'AI_PROPOSED',
            'PLAN-FINCORE-001',
            'v1.0'
        );
        """, (now_iso, now_iso))

    # FinCore approval ticket
    cur.execute("SELECT approval_id FROM approvals WHERE approval_id = 'APP-FINCORE-001';")
    if not cur.fetchone():
        cur.execute("""
        INSERT OR REPLACE INTO approvals (
            approval_id, incident_id, tenant_id, service_name, proposed_action,
            risk_level, risk_score, required_role, reason, expected_outcome,
            estimated_downtime_sec, rollback_plan, status, requested_by,
            created_at, requested_at, plan_id, plan_version, solution_source,
            details_json
        ) VALUES (
            'APP-FINCORE-001',
            'INC-FINCORE-001',
            'fincore',
            'database-service',
            'RESET_CONNECTION_POOL',
            'HIGH',
            85.0,
            'APPROVER',
            'Action RESET_CONNECTION_POOL on ACID Ledger Database carries HIGH production risk under FinCore regulatory policy.',
            'Flushes leaked TCP socket descriptors on port 8004 and reallocates 20 healthy pool handles without database restart.',
            15,
            'RECONNECT_DATABASE',
            'PENDING',
            'fincore.devsec',
            ?,
            ?,
            'PLAN-FINCORE-001',
            'v1.0',
            'AI_PROPOSED',
            ?
        );
        """, (now_iso, now_iso, json.dumps({
            "title": "ACID Transaction Ledger Connection Pool Saturation on database-service",
            "why_selected": "Telemetry confirms connection pool handles reached 100% capacity on port 8004.",
            "why_approval_required": "Regulatory compliance policy mandates independent authorization for database connection resets.",
            "expected_impact": "Drains orphaned idle client sockets past 15s, restoring query latency below 50ms.",
            "solution_source": "AI_PROPOSED",
            "plan_version": "v1.0"
        })))

    # ShopSphere incident:
    cur.execute("SELECT incident_id FROM incidents WHERE incident_id = 'INC-SHOPSPHERE-001';")
    if not cur.fetchone():
        print("Seeding canonical ShopSphere incident INC-SHOPSPHERE-001...")
        cur.execute("""
        INSERT OR REPLACE INTO incidents (
            incident_id, title, description, severity, status, primary_service, root_cause_service,
            root_cause_category, root_cause_summary, root_cause_confidence, rca_confidence,
            recommended_action, action_risk_level, approval_status, remediation_status,
            verification_status, recovery_status, lifecycle_state, tenant_id, telemetry_source_mode,
            affected_services_json, rca_evidence_json, error_rate, created_at, updated_at,
            selected_solution_source, plan_id, plan_version
        ) VALUES (
            'INC-SHOPSPHERE-001',
            'Redis Catalog Cache Buffer Deserialization Corruption on service-b',
            'Cache miss rate spiked to 92%, causing database read penetration and memory saturation.',
            'HIGH',
            'AWAITING_APPROVAL',
            'service-b',
            'service-b',
            'CACHE_FAILURE',
            'Stale serialization keys in Redis buffer leading to unmarshaling errors and memory pressure.',
            0.94,
            0.94,
            'CLEAR_CACHE',
            'MEDIUM',
            'PENDING',
            'PENDING',
            'WAITING_FOR_TELEMETRY',
            'AWAITING_APPROVAL',
            'AWAITING_APPROVAL',
            'shopsphere',
            'LIVE_CUSTOMER',
            '["service-b", "database-service", "gateway"]',
            '["Redis memory utilization crossed 88% threshold", "Cache hit ratio dropped from 94% baseline to 8%", "Downstream order catalog latency increased to 1250ms"]',
            0.142,
            ?,
            ?,
            'KNOWLEDGE_BASE',
            'PLAN-SHOPSPHERE-001',
            'v1.0'
        );
        """, (now_iso, now_iso))

    # ShopSphere approval ticket
    cur.execute("SELECT approval_id FROM approvals WHERE approval_id = 'APP-SHOPSPHERE-001';")
    if not cur.fetchone():
        cur.execute("""
        INSERT OR REPLACE INTO approvals (
            approval_id, incident_id, tenant_id, service_name, proposed_action,
            risk_level, risk_score, required_role, reason, expected_outcome,
            estimated_downtime_sec, rollback_plan, status, requested_by,
            created_at, requested_at, plan_id, plan_version, solution_source,
            details_json
        ) VALUES (
            'APP-SHOPSPHERE-001',
            'INC-SHOPSPHERE-001',
            'shopsphere',
            'service-b',
            'CLEAR_CACHE',
            'MEDIUM',
            50.0,
            'APPROVER',
            'Action CLEAR_CACHE requires approver confirmation to prevent uncoordinated cache stampedes.',
            'Flushes invalidation buffer, purges corrupted cache keys, and reclaims memory heap space.',
            10,
            'RESTART_CONTROLLED_SERVICE',
            'PENDING',
            'shopsphere.devsec',
            ?,
            ?,
            'PLAN-SHOPSPHERE-001',
            'v1.0',
            'KNOWLEDGE_BASE',
            ?
        );
        """, (now_iso, now_iso, json.dumps({
            "title": "Redis Catalog Cache Buffer Deserialization Corruption on service-b",
            "why_selected": "Grounded in verified knowledge base article KB-2026-027 (v1.3, 93.8% success rate).",
            "why_approval_required": "Enterprise policy requires authorization for cache purges affecting customer checkout.",
            "expected_impact": "Purges corrupted keyspace and rewarms priority product catalog keys.",
            "solution_source": "KNOWLEDGE_BASE",
            "kb_reference": "KB-2026-027 v1.3",
            "plan_version": "v1.0"
        })))

    # CloudDesk incident:
    cur.execute("SELECT incident_id FROM incidents WHERE incident_id = 'INC-CLOUDDESK-001';")
    if not cur.fetchone():
        print("Seeding canonical CloudDesk incident INC-CLOUDDESK-001...")
        cur.execute("""
        INSERT OR REPLACE INTO incidents (
            incident_id, title, description, severity, status, primary_service, root_cause_service,
            root_cause_category, root_cause_summary, root_cause_confidence, rca_confidence,
            recommended_action, action_risk_level, approval_status, remediation_status,
            verification_status, recovery_status, lifecycle_state, tenant_id, telemetry_source_mode,
            affected_services_json, rca_evidence_json, error_rate, created_at, updated_at,
            selected_solution_source, plan_id, plan_version
        ) VALUES (
            'INC-CLOUDDESK-001',
            'Workspace Compute Worker Thread Starvation and CPU Saturation on service-a',
            'Worker thread pool reached 100% concurrency saturation. Workspace provisioning latency jumped to 1840ms.',
            'HIGH',
            'AWAITING_APPROVAL',
            'service-a',
            'service-a',
            'CPU_WORKER_STARVATION',
            'Worker concurrency pool saturation during concurrent workspace provisioning requests.',
            0.92,
            0.92,
            'SCALE_WORKERS',
            'MEDIUM',
            'PENDING',
            'PENDING',
            'WAITING_FOR_TELEMETRY',
            'AWAITING_APPROVAL',
            'AWAITING_APPROVAL',
            'clouddesk',
            'LIVE_CUSTOMER',
            '["service-a", "gateway"]',
            '["CPU utilization on compute worker pool surged past 88%", "OS thread queue depth reached 45 pending items", "Workspace creation p95 latency jumped to 1840ms"]',
            0.128,
            ?,
            ?,
            'AI_PROPOSED',
            'PLAN-CLOUDDESK-001',
            'v1.0'
        );
        """, (now_iso, now_iso))

    # CloudDesk approval ticket
    cur.execute("SELECT approval_id FROM approvals WHERE approval_id = 'APP-CLOUDDESK-001';")
    if not cur.fetchone():
        cur.execute("""
        INSERT OR REPLACE INTO approvals (
            approval_id, incident_id, tenant_id, service_name, proposed_action,
            risk_level, risk_score, required_role, reason, expected_outcome,
            estimated_downtime_sec, rollback_plan, status, requested_by,
            created_at, requested_at, plan_id, plan_version, solution_source,
            details_json
        ) VALUES (
            'APP-CLOUDDESK-001',
            'INC-CLOUDDESK-001',
            'clouddesk',
            'service-a',
            'SCALE_WORKERS',
            'MEDIUM',
            50.0,
            'APPROVER',
            'Action SCALE_WORKERS expands compute concurrency from 2 to 6 workers under CloudDesk capacity governance.',
            'Expands worker thread pool from 2 to 6 threads, draining queue backpressure.',
            15,
            'SCALE_WORKERS',
            'PENDING',
            'clouddesk.devsec',
            ?,
            ?,
            'PLAN-CLOUDDESK-001',
            'v1.0',
            'AI_PROPOSED',
            ?
        );
        """, (now_iso, now_iso, json.dumps({
            "title": "Workspace Compute Worker Thread Starvation and CPU Saturation on service-a",
            "why_selected": "Expands concurrency pool from 2 to 6 threads to absorb burst provisioning traffic.",
            "why_approval_required": "Capacity allocation policy requires approver authorization for compute expansion.",
            "expected_impact": "Drains queue backlog and returns workspace provisioning latency below 200ms.",
            "solution_source": "AI_PROPOSED",
            "plan_version": "v1.0"
        })))

    # Also seed recovery plans for the 3 canonical incidents if missing
    plans_data = [
        ("PLAN-FINCORE-001", "INC-FINCORE-001", "fincore", "RESET_CONNECTION_POOL", "AI_PROPOSED", "v1.0", "AWAITING_APPROVAL", "APP-FINCORE-001"),
        ("PLAN-SHOPSPHERE-001", "INC-SHOPSPHERE-001", "shopsphere", "CLEAR_CACHE", "KNOWLEDGE_BASE", "v1.0", "AWAITING_APPROVAL", "APP-SHOPSPHERE-001"),
        ("PLAN-CLOUDDESK-001", "INC-CLOUDDESK-001", "clouddesk", "SCALE_WORKERS", "AI_PROPOSED", "v1.0", "AWAITING_APPROVAL", "APP-CLOUDDESK-001"),
    ]
    for p_id, i_id, t_id, act, src, ver, st, app_id in plans_data:
        cur.execute("SELECT plan_id FROM recovery_plans WHERE plan_id = ?;", (p_id,))
        if not cur.fetchone():
            cur.execute("""
            INSERT INTO recovery_plans (plan_id, incident_id, tenant_id, recommended_action, solution_source, plan_version, status, candidate_solutions_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (p_id, i_id, t_id, act, src, ver, st, json.dumps({
                "selected_source": src,
                "solution_source": src,
                "recommended_action": act,
                "plan_version": ver,
                "approval_id": app_id,
                "remediation_steps": [
                    {"step_number": 1, "action": f"Safety preflight check on {t_id}", "status": "COMPLETED"},
                    {"step_number": 2, "action": f"Execute authorized {act}", "status": "PENDING_APPROVAL"},
                    {"step_number": 3, "action": "Post-remediation telemetry verification", "status": "QUEUED"}
                ]
            }), now_iso))

    conn.commit()

    # Query final counts
    cur.execute("SELECT tenant_id, status, count(*) FROM incidents GROUP BY tenant_id, status;")
    print("Final incidents:", cur.fetchall())
    cur.execute("SELECT tenant_id, status, count(*) FROM approvals GROUP BY tenant_id, status;")
    print("Final approvals:", cur.fetchall())

    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    print(f"Workspace Root: {WORKSPACE_ROOT}")
    run_migration_on_db(ROOT_DB)
    # Mirror root db to backend db so both files are byte-for-byte identical
    if os.path.exists(ROOT_DB):
        shutil.copy2(ROOT_DB, BACKEND_DB)
        print(f"Mirrored {ROOT_DB} to {BACKEND_DB}.")
