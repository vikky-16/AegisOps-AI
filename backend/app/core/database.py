"""
AegisOps AI Database Engine & Session Management
"""

import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

from sqlalchemy.pool import NullPool
from sqlalchemy import event

# For SQLite async, configure connection args with timeout for high concurrency
connect_args = {"check_same_thread": False, "timeout": 30.0} if "sqlite" in settings.DATABASE_URL else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    poolclass=NullPool if "sqlite" in settings.DATABASE_URL else None,
    future=True
)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            # aiosqlite wraps sqlite3 connection in _conn
            conn = getattr(dbapi_connection, "_conn", dbapi_connection)
            cursor = conn.cursor() if hasattr(conn, "cursor") else dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=60000;")
            cursor.close()
        except Exception:
            pass

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initializes the database tables and configures SQLite WAL mode."""
    import backend.app.models  # noqa: F401 - ensure all models register with Base.metadata
    async with engine.begin() as conn:
        # Enable WAL mode and busy timeout for SQLite to support concurrent reads & writes
        if "sqlite" in settings.DATABASE_URL:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))
            await conn.execute(text("PRAGMA busy_timeout=30000;"))
        await conn.run_sync(Base.metadata.create_all)

        # Migrate recovery_executions columns if table was created in an older schema
        if "sqlite" in settings.DATABASE_URL:
            try:
                res = await conn.execute(text("PRAGMA table_info(recovery_executions);"))
                existing_cols = {row[1] for row in res.fetchall()}
                col_defs = [
                    ("runbook_id", "VARCHAR(64)"),
                    ("executor", "VARCHAR(64) DEFAULT 'AegisOps_Remediation_Engine'"),
                    ("success", "BOOLEAN DEFAULT 1"),
                    ("verification_status", "VARCHAR(32) DEFAULT 'VERIFIED'"),
                    ("steps_json", "TEXT DEFAULT '[]'"),
                    ("result_json", "TEXT DEFAULT '{}'"),
                    ("rollback_status", "VARCHAR(32) DEFAULT 'NONE'"),
                    ("started_at", "DATETIME"),
                    ("completed_at", "DATETIME")
                ]
                for col_name, col_type in col_defs:
                    if col_name not in existing_cols:
                        await conn.execute(text(f"ALTER TABLE recovery_executions ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

            # Migrate users columns (tenant_id, is_platform_admin)
            try:
                res = await conn.execute(text("PRAGMA table_info(users);"))
                user_cols = {row[1] for row in res.fetchall()}
                if "tenant_id" not in user_cols:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN tenant_id VARCHAR(64);"))
                if "is_platform_admin" not in user_cols:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN DEFAULT 0;"))
            except Exception:
                pass

            # Migrate incidents columns (tenant_id, telemetry_source_mode)
            try:
                res = await conn.execute(text("PRAGMA table_info(incidents);"))
                inc_cols = {row[1] for row in res.fetchall()}
                if "tenant_id" not in inc_cols:
                    await conn.execute(text("ALTER TABLE incidents ADD COLUMN tenant_id VARCHAR(64) DEFAULT 'demo-tenant';"))
                if "telemetry_source_mode" not in inc_cols:
                    await conn.execute(text("ALTER TABLE incidents ADD COLUMN telemetry_source_mode VARCHAR(32) DEFAULT 'LIVE_DEMO_ENVIRONMENT';"))
                if "dual_solutions_json" not in inc_cols:
                    await conn.execute(text("ALTER TABLE incidents ADD COLUMN dual_solutions_json TEXT DEFAULT '{}';"))
                if "selected_solution_source" not in inc_cols:
                    await conn.execute(text("ALTER TABLE incidents ADD COLUMN selected_solution_source VARCHAR(32);"))
                if "rca_id" not in inc_cols:
                    await conn.execute(text("ALTER TABLE incidents ADD COLUMN rca_id VARCHAR(64);"))
                if "is_synthetic" not in inc_cols:
                    await conn.execute(text("ALTER TABLE incidents ADD COLUMN is_synthetic BOOLEAN DEFAULT 1;"))
            except Exception:
                pass

            # Migrate historical_incidents columns (tenant_id)
            try:
                res = await conn.execute(text("PRAGMA table_info(historical_incidents);"))
                hist_cols = {row[1] for row in res.fetchall()}
                if "tenant_id" not in hist_cols:
                    await conn.execute(text("ALTER TABLE historical_incidents ADD COLUMN tenant_id VARCHAR(64) DEFAULT 'demo-tenant';"))
            except Exception:
                pass

            # Migrate failure_scenarios_history columns (tenant_id)
            try:
                res = await conn.execute(text("PRAGMA table_info(failure_scenarios_history);"))
                fail_cols = {row[1] for row in res.fetchall()}
                if "tenant_id" not in fail_cols:
                    await conn.execute(text("ALTER TABLE failure_scenarios_history ADD COLUMN tenant_id VARCHAR(64) DEFAULT 'demo-tenant';"))
            except Exception:
                pass

            # Migrate approvals columns (tenant_id, plan_id, plan_version, solution_source, etc.)
            try:
                res = await conn.execute(text("PRAGMA table_info(approvals);"))
                app_cols = {row[1] for row in res.fetchall()}
                app_defs = [
                    ("tenant_id", "VARCHAR(64) DEFAULT 'demo-tenant'"),
                    ("required_role", "VARCHAR(32) DEFAULT 'APPROVER'"),
                    ("decision", "VARCHAR(32)"),
                    ("requested_by", "VARCHAR(64) DEFAULT 'AegisOps_Policy_Engine'"),
                    ("approved_at", "DATETIME"),
                    ("requested_at", "DATETIME"),
                    ("details_json", "TEXT DEFAULT '{}'"),
                    ("plan_id", "VARCHAR(64)"),
                    ("plan_version", "VARCHAR(16) DEFAULT 'v1.0'"),
                    ("solution_source", "VARCHAR(32)"),
                    ("remediation_run_id", "VARCHAR(64)"),
                    ("is_consumed", "BOOLEAN DEFAULT 0")
                ]
                for col_name, col_type in app_defs:
                    if col_name not in app_cols:
                        await conn.execute(text(f"ALTER TABLE approvals ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

            # Migrate recovery_plans columns
            try:
                res = await conn.execute(text("PRAGMA table_info(recovery_plans);"))
                plan_cols = {row[1] for row in res.fetchall()}
                plan_defs = [
                    ("plan_version", "VARCHAR(16) DEFAULT 'v1.0'"),
                    ("solution_source", "VARCHAR(32)")
                ]
                for col_name, col_type in plan_defs:
                    if col_name not in plan_cols:
                        await conn.execute(text(f"ALTER TABLE recovery_plans ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

            # Create performance indexes for high-throughput queries
            try:
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_incidents_tenant_status ON incidents(tenant_id, status);",
                    "CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);",
                    "CREATE INDEX IF NOT EXISTS idx_approvals_tenant_status ON approvals(tenant_id, status);",
                    "CREATE INDEX IF NOT EXISTS idx_approvals_incident_id ON approvals(incident_id);",
                    "CREATE INDEX IF NOT EXISTS idx_recovery_executions_incident_id ON recovery_executions(incident_id);",
                    "CREATE INDEX IF NOT EXISTS idx_recovery_executions_status ON recovery_executions(status);",
                    "CREATE INDEX IF NOT EXISTS idx_conversations_tenant_updated ON conversations(tenant_id, updated_at DESC);",
                    "CREATE INDEX IF NOT EXISTS idx_conversation_messages_cid ON conversation_messages(conversation_id, timestamp ASC);",
                    "CREATE INDEX IF NOT EXISTS idx_evidence_incident_id ON evidence_items(incident_id);"
                ]
                for idx_sql in indexes:
                    await conn.execute(text(idx_sql))
            except Exception:
                pass

            # Migrate tenants columns (plan, industry, region, logo_url, environments_json)
            try:
                res = await conn.execute(text("PRAGMA table_info(tenants);"))
                t_cols = {row[1] for row in res.fetchall()}
                t_defs = [
                    ("plan", "VARCHAR(32) DEFAULT 'Enterprise'"),
                    ("industry", "VARCHAR(64) DEFAULT 'Financial Services'"),
                    ("region", "VARCHAR(64) DEFAULT 'India'"),
                    ("logo_url", "VARCHAR(256)"),
                    ("environments_json", "TEXT DEFAULT '[\"PRODUCTION\", \"STAGING\", \"DEVELOPMENT\", \"CONTROLLED_CUSTOMER_TEST\", \"DEMO\", \"LOAD_TEST\"]'")
                ]
                for col_name, col_type in t_defs:
                    if col_name not in t_cols:
                        await conn.execute(text(f"ALTER TABLE tenants ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

            # Migrate users columns (tenant_id, is_platform_admin, organization_id, mfa_enabled, etc.)
            try:
                res = await conn.execute(text("PRAGMA table_info(users);"))
                user_cols = {row[1] for row in res.fetchall()}
                u_defs = [
                    ("tenant_id", "VARCHAR(64)"),
                    ("is_platform_admin", "BOOLEAN DEFAULT 0"),
                    ("organization_id", "VARCHAR(64)"),
                    ("mfa_enabled", "BOOLEAN DEFAULT 0"),
                    ("mfa_secret", "VARCHAR(64)"),
                    ("phone", "VARCHAR(32)"),
                    ("last_login_at", "DATETIME")
                ]
                for col_name, col_type in u_defs:
                    if col_name not in user_cols:
                        await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

            # Migrate tenant_audit_logs columns (user_role, result)
            try:
                res = await conn.execute(text("PRAGMA table_info(tenant_audit_logs);"))
                audit_cols = {row[1] for row in res.fetchall()}
                if "user_role" not in audit_cols:
                    await conn.execute(text("ALTER TABLE tenant_audit_logs ADD COLUMN user_role VARCHAR(32) DEFAULT 'OPERATOR';"))
                if "result" not in audit_cols:
                    await conn.execute(text("ALTER TABLE tenant_audit_logs ADD COLUMN result VARCHAR(32) DEFAULT 'SUCCESS';"))
            except Exception:
                pass

            # Migrate knowledge_base columns
            try:
                res = await conn.execute(text("PRAGMA table_info(knowledge_base);"))
                kb_cols = {row[1] for row in res.fetchall()}
                kb_defs = [
                    ("tenant_id", "VARCHAR(64) DEFAULT 'demo-tenant'"),
                    ("remediation_steps_json", "TEXT DEFAULT '[]'"),
                    ("prerequisites_json", "TEXT DEFAULT '[]'"),
                    ("risks_and_rollback_json", "TEXT DEFAULT '[]'"),
                    ("verified_outcome_details", "TEXT"),
                    ("version", "VARCHAR(32) DEFAULT 'v1.0'"),
                    ("updated_at", "DATETIME")
                ]
                for col_name, col_type in kb_defs:
                    if col_name not in kb_cols:
                        await conn.execute(text(f"ALTER TABLE knowledge_base ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

            # Safe Auditable Reconciliation of Approvals & Incident Integrity
            try:
                # 1. Create archived_approvals table if it does not exist
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS archived_approvals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_id INTEGER,
                        approval_id VARCHAR(64),
                        incident_id VARCHAR(64),
                        tenant_id VARCHAR(64),
                        service_name VARCHAR(64),
                        proposed_action VARCHAR(128),
                        action_parameters_json TEXT,
                        risk_level VARCHAR(32),
                        risk_score FLOAT,
                        reason TEXT,
                        expected_outcome TEXT,
                        status VARCHAR(32),
                        reviewed_by VARCHAR(64),
                        review_notes TEXT,
                        created_at DATETIME,
                        archived_at DATETIME,
                        archive_reason VARCHAR(256)
                    );
                """))

                # 2. Archive orphaned approvals referencing deleted/missing incidents
                res = await conn.execute(text("""
                    SELECT a.id, a.approval_id, a.incident_id, a.tenant_id, a.service_name,
                           a.proposed_action, a.status
                    FROM approvals a
                    LEFT JOIN incidents i ON a.incident_id = i.incident_id
                    WHERE i.incident_id IS NULL;
                """))
                orphans = res.fetchall()
                for o in orphans:
                    await conn.execute(text("""
                        INSERT INTO archived_approvals (
                            original_approval_id, incident_id, tenant_id, service_name,
                            proposed_action, status, archival_reason, archived_at
                        ) VALUES (
                            :app_id, :inc_id, :tenant_id, :svc,
                            :action, :status, :archival_reason, CURRENT_TIMESTAMP
                        );
                    """), {
                        "app_id": o[1], "inc_id": o[2], "tenant_id": o[3], "svc": o[4],
                        "action": o[5], "status": o[6],
                        "archival_reason": f"Safely archived: incident {o[2]} was deleted or does not exist."
                    })
                    await conn.execute(text("DELETE FROM approvals WHERE id = :id;"), {"id": o[0]})

                # 3. For resolved incidents, mark lingering PENDING approvals as CONSUMED
                await conn.execute(text("""
                    UPDATE approvals
                    SET status = 'CONSUMED',
                        decision = 'CONSUMED',
                        review_notes = 'Automatically consumed: incident was successfully resolved and verified.'
                    WHERE status = 'PENDING'
                      AND incident_id IN (
                          SELECT incident_id FROM incidents WHERE status IN ('RESOLVED', 'VALIDATED')
                      );
                """))

                # 4. Deduplicate multiple PENDING approvals for the same (tenant_id, incident_id, proposed_action)
                # Mark older pending approvals as SUPERSEDED, preserving the newest one as PENDING
                res = await conn.execute(text("""
                    SELECT tenant_id, incident_id, proposed_action, count(*)
                    FROM approvals
                    WHERE status = 'PENDING'
                    GROUP BY tenant_id, incident_id, proposed_action
                    HAVING count(*) > 1;
                """))
                dup_groups = res.fetchall()
                for dg in dup_groups:
                    t_id, i_id, act = dg[0], dg[1], dg[2]
                    res_all = await conn.execute(text("""
                        SELECT id FROM approvals
                        WHERE tenant_id = :t_id AND incident_id = :i_id AND proposed_action = :act AND status = 'PENDING'
                        ORDER BY id DESC;
                    """), {"t_id": t_id, "i_id": i_id, "act": act})
                    ids = [r[0] for r in res_all.fetchall()]
                    if len(ids) > 1:
                        older_ids = ids[1:]
                        for old_id in older_ids:
                            await conn.execute(text("""
                                UPDATE approvals
                                SET status = 'SUPERSEDED',
                                    decision = 'SUPERSEDED',
                                    review_notes = 'Superseded by newer approval for same remediation action'
                                WHERE id = :id;
                            """), {"id": old_id})

            except Exception as exc:
                pass

            # Safe migration for replica tables
            try:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS replica_instances (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        replica_id VARCHAR(64) UNIQUE NOT NULL,
                        tenant_id VARCHAR(64) NOT NULL DEFAULT 'demo-tenant',
                        name VARCHAR(128) NOT NULL,
                        environment_type VARCHAR(32) NOT NULL DEFAULT 'SYNTHETIC',
                        fidelity_level FLOAT NOT NULL DEFAULT 0.98,
                        status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
                        target_service VARCHAR(64) NOT NULL DEFAULT 'database-service',
                        target_component VARCHAR(64) DEFAULT 'connection_pool',
                        active_scenario_id VARCHAR(64),
                        isolation_boundaries_json TEXT DEFAULT '{}',
                        limitations_json TEXT DEFAULT '[]',
                        data_source_json TEXT DEFAULT '{}',
                        current_metrics_json TEXT DEFAULT '{}',
                        created_at DATETIME,
                        updated_at DATETIME
                    );
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS replica_experiments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id VARCHAR(64) UNIQUE NOT NULL,
                        incident_id VARCHAR(64) NOT NULL,
                        tenant_id VARCHAR(64) NOT NULL DEFAULT 'demo-tenant',
                        replica_id VARCHAR(64) NOT NULL,
                        environment_type VARCHAR(32) NOT NULL DEFAULT 'SYNTHETIC',
                        fidelity_level FLOAT NOT NULL DEFAULT 0.98,
                        scenario_id VARCHAR(64) NOT NULL,
                        scenario_name VARCHAR(128) NOT NULL,
                        target_service VARCHAR(64) NOT NULL DEFAULT 'database-service',
                        stage VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
                        status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
                        evaluation_verdict VARCHAR(32) NOT NULL DEFAULT 'PASS',
                        confidence_score FLOAT NOT NULL DEFAULT 0.94,
                        initial_conditions_json TEXT DEFAULT '{}',
                        baseline_metrics_json TEXT DEFAULT '{}',
                        candidate_remediations_json TEXT DEFAULT '[]',
                        selected_candidate_id VARCHAR(64),
                        applied_changes_json TEXT DEFAULT '{}',
                        test_workload_json TEXT DEFAULT '{}',
                        before_after_metrics_json TEXT DEFAULT '{}',
                        regression_checks_json TEXT DEFAULT '[]',
                        resource_usage_json TEXT DEFAULT '{}',
                        logs_json TEXT DEFAULT '[]',
                        evidence_references_json TEXT DEFAULT '[]',
                        ai_provider_model_json TEXT DEFAULT '{}',
                        approval_history_json TEXT DEFAULT '[]',
                        target_deployment_json TEXT DEFAULT '{}',
                        limitations_notes TEXT DEFAULT '',
                        duration_ms INTEGER DEFAULT 0,
                        created_at DATETIME,
                        completed_at DATETIME
                    );
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_replica_tenant ON replica_instances(tenant_id);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_experiment_tenant ON replica_experiments(tenant_id, incident_id);"))
            except Exception:
                pass

    # Seed initial tenants, policies, API keys, enterprise users, and replica twins
    await seed_initial_tenants()
    await seed_initial_knowledge_base()
    await seed_initial_replicas()



async def seed_initial_tenants():
    """Seeds baseline tenants, default policies, API keys, and demo users."""
    from backend.app.models.tenant import Tenant, TenantPolicy, TenantAPIKey, TenantIntegration
    from backend.app.models.user import User
    from backend.app.core.security import get_password_hash, hash_api_key, register_cached_api_key
    from sqlalchemy import select

    # Predefined baseline keys
    SEED_KEYS = {
        "demo-tenant": "agt_live_demo_11112222333344445555",
        "tenant-alpha": "agt_live_acme_aaaa1111bbbb2222cccc",
        "tenant-beta": "agt_live_cyber_xxxx9999yyyy8888zzzz",
        "shopsphere": "agt_live_shopsphere_11112222333344445555",
        "fincore": "agt_live_fincore_aaaa1111bbbb2222cccc",
        "clouddesk": "agt_live_clouddesk_xxxx9999yyyy8888zzzz"
    }

    # Register all seed keys in memory cache immediately for zero-delay validation
    for t_id, raw_key in SEED_KEYS.items():
        register_cached_api_key(raw_key, t_id, f"{t_id} Primary Key")

    try:
        async with AsyncSessionLocal() as session:
            # 1. Seed Tenants
            tenants_data = [
                {"id": "demo-tenant", "name": "AegisOps Controlled Demo", "slug": "demo-tenant", "tier": "ENTERPRISE"},
                {"id": "tenant-alpha", "name": "Acme Corporation", "slug": "acme-corp", "tier": "ENTERPRISE"},
                {"id": "tenant-beta", "name": "Cyberdyne Systems", "slug": "cyberdyne", "tier": "ENTERPRISE"},
                {"id": "shopsphere", "name": "ShopSphere", "slug": "shopsphere", "tier": "ENTERPRISE"},
                {"id": "fincore", "name": "FinCore", "slug": "fincore", "tier": "ENTERPRISE"},
                {"id": "clouddesk", "name": "CloudDesk", "slug": "clouddesk", "tier": "ENTERPRISE"}
            ]
            for td in tenants_data:
                existing = await session.get(Tenant, td["id"])
                if not existing:
                    t = Tenant(
                        id=td["id"],
                        name=td["name"],
                        slug=td["slug"],
                        tier=td["tier"],
                        status="ACTIVE",
                        retention_days=30
                    )
                    session.add(t)

            # 2. Seed Tenant Policies
            for td in tenants_data:
                stmt = select(TenantPolicy).where(TenantPolicy.tenant_id == td["id"])
                res = await session.execute(stmt)
                if not res.scalars().first():
                    policy = TenantPolicy(
                        tenant_id=td["id"],
                        auto_remediation_enabled=True,
                        allowed_actions_json='["RESET_CONNECTION_POOL", "CLEAR_CACHE", "DRAIN_QUEUE", "ROTATE_CONNECTIONS"]',
                        max_auto_risk_level="LOW",
                        min_rca_confidence=0.85,
                        max_blast_radius=60.0,
                        cooldown_seconds=300
                    )
                    session.add(policy)

            # 3. Seed Tenant API Keys
            for t_id, raw_key in SEED_KEYS.items():
                hashed = hash_api_key(raw_key)
                stmt = select(TenantAPIKey).where(TenantAPIKey.hashed_key == hashed)
                res = await session.execute(stmt)
                if not res.scalars().first():
                    k = TenantAPIKey(
                        tenant_id=t_id,
                        key_prefix=raw_key[:16],
                        hashed_key=hashed,
                        name=f"{t_id} Ingestion Key",
                        scopes="telemetry:write,telemetry:read",
                        is_active=True
                    )
                    session.add(k)

            # 4. Seed Enterprise Users
            users_data = [
                {"username": "admin", "email": "admin@aegisops.ai", "full_name": "AegisOps Platform Admin", "role": "PLATFORM_ADMIN", "tenant_id": "demo-tenant", "is_platform_admin": True, "pwd": "admin123"},
                {"username": "sre_acme", "email": "sre@acme.com", "full_name": "Acme Lead SRE", "role": "TENANT_ADMIN", "tenant_id": "tenant-alpha", "is_platform_admin": False, "pwd": "acme123"},
                {"username": "engineer_acme", "email": "eng@acme.com", "full_name": "Acme SRE Engineer", "role": "SRE_ENGINEER", "tenant_id": "tenant-alpha", "is_platform_admin": False, "pwd": "acme123"},
                {"username": "sre_cyber", "email": "sre@cyberdyne.com", "full_name": "Cyberdyne Lead SRE", "role": "TENANT_ADMIN", "tenant_id": "tenant-beta", "is_platform_admin": False, "pwd": "cyber123"},
                {"username": "operator", "email": "operator@aegisops.ai", "full_name": "Operations Center Engineer", "role": "OPERATOR", "tenant_id": "demo-tenant", "is_platform_admin": False, "pwd": "operator123"},
                {"username": "viewer", "email": "viewer@aegisops.ai", "full_name": "Read-Only Stakeholder", "role": "VIEWER", "tenant_id": "demo-tenant", "is_platform_admin": False, "pwd": "viewer123"},
                # ShopSphere
                {"username": "admin_shopsphere", "email": "admin@shopsphere.io", "full_name": "ShopSphere Company Admin", "role": "ORG_ADMIN", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                {"username": "ceo_shopsphere", "email": "ceo@shopsphere.io", "full_name": "Rachel Zane (CEO - ShopSphere)", "role": "CEO", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                {"username": "sre_shopsphere", "email": "sre@shopsphere.io", "full_name": "Devin Murphy (Lead SRE - ShopSphere)", "role": "SRE_LEAD", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                {"username": "devops_shopsphere", "email": "devops@shopsphere.io", "full_name": "Liam Connor (DevOps - ShopSphere)", "role": "DEVOPS_ENGINEER", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                {"username": "dev_shopsphere", "email": "dev@shopsphere.io", "full_name": "Amina Patel (Developer - ShopSphere)", "role": "DEVELOPER", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                {"username": "sec_shopsphere", "email": "sec@shopsphere.io", "full_name": "Klaus Richter (Security - ShopSphere)", "role": "SECURITY_ENGINEER", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                {"username": "viewer_shopsphere", "email": "viewer@shopsphere.io", "full_name": "ShopSphere Auditor (Viewer)", "role": "VIEWER", "tenant_id": "shopsphere", "is_platform_admin": False, "pwd": "shopsphere123"},
                # FinCore
                {"username": "admin_fincore", "email": "admin@fincore.financial", "full_name": "FinCore Company Admin", "role": "ORG_ADMIN", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                {"username": "ceo_fincore", "email": "ceo@fincore.financial", "full_name": "Sterling Archer (CEO - FinCore)", "role": "CEO", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                {"username": "sre_fincore", "email": "sre@fincore.financial", "full_name": "Maya Lin (Lead SRE - FinCore)", "role": "SRE_LEAD", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                {"username": "devops_fincore", "email": "devops@fincore.financial", "full_name": "Vikram Seth (DevOps - FinCore)", "role": "DEVOPS_ENGINEER", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                {"username": "dev_fincore", "email": "dev@fincore.financial", "full_name": "Chen Wei (Developer - FinCore)", "role": "DEVELOPER", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                {"username": "sec_fincore", "email": "sec@fincore.financial", "full_name": "Grace Hopper (Security - FinCore)", "role": "SECURITY_ENGINEER", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                {"username": "viewer_fincore", "email": "viewer@fincore.financial", "full_name": "FinCore Regulatory Auditor (Viewer)", "role": "VIEWER", "tenant_id": "fincore", "is_platform_admin": False, "pwd": "fincore123"},
                # CloudDesk
                {"username": "admin_clouddesk", "email": "admin@clouddesk.app", "full_name": "CloudDesk Company Admin", "role": "ORG_ADMIN", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"},
                {"username": "ceo_clouddesk", "email": "ceo@clouddesk.app", "full_name": "Siddharth Roy (CEO - CloudDesk)", "role": "CEO", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"},
                {"username": "sre_clouddesk", "email": "sre@clouddesk.app", "full_name": "Claire Redfield (Lead SRE - CloudDesk)", "role": "SRE_LEAD", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"},
                {"username": "devops_clouddesk", "email": "devops@clouddesk.app", "full_name": "Jordan Bell (DevOps - CloudDesk)", "role": "DEVOPS_ENGINEER", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"},
                {"username": "dev_clouddesk", "email": "dev@clouddesk.app", "full_name": "Lucas Silva (Developer - CloudDesk)", "role": "DEVELOPER", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"},
                {"username": "sec_clouddesk", "email": "sec@clouddesk.app", "full_name": "Nadia Osman (Security - CloudDesk)", "role": "SECURITY_ENGINEER", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"},
                {"username": "viewer_clouddesk", "email": "viewer@clouddesk.app", "full_name": "CloudDesk Stakeholder (Viewer)", "role": "VIEWER", "tenant_id": "clouddesk", "is_platform_admin": False, "pwd": "clouddesk123"}
            ]
            for ud in users_data:
                stmt = select(User).where(User.username == ud["username"])
                res = await session.execute(stmt)
                existing_user = res.scalars().first()
                if not existing_user:
                    u = User(
                        username=ud["username"],
                        email=ud["email"],
                        full_name=ud["full_name"],
                        hashed_password=get_password_hash(ud["pwd"]),
                        role=ud["role"],
                        tenant_id=ud["tenant_id"],
                        is_platform_admin=ud["is_platform_admin"],
                        is_active=True
                    )
                    session.add(u)
                else:
                    # Update fields if missing
                    existing_user.tenant_id = ud["tenant_id"]
                    existing_user.is_platform_admin = ud["is_platform_admin"]
                    existing_user.role = ud["role"]

            await session.commit()
    except Exception:
        # Fallback gracefully if database locked
        pass


async def seed_initial_knowledge_base():
    """Seeds baseline real verified knowledge base articles if table is empty."""
    import json
    from backend.app.models.knowledge import KnowledgeArticle
    from sqlalchemy import select, func

    SEED_ARTICLES = [
        {
            "incident_code": "KB-2025-089",
            "tenant_id": "demo-tenant",
            "title": "Database Connection Pool Exhaustion under Concurrency Surge",
            "primary_service": "database-service",
            "symptoms_summary": "Active connections reached 20/20 max capacity. Upstream Service B experienced HTTP 504 gateway timeouts and transaction lock wait aborts.",
            "root_cause": "Long-running transaction locks held during peak traffic exhausted database connection pool slots.",
            "recommended_remedy": "RESET_CONNECTION_POOL",
            "recovery_action_taken": "RESET_CONNECTION_POOL",
            "recovery_duration_sec": 2.1,
            "outcome": "RESOLVED",
            "historical_success_rate": 94.5,
            "tags_json": json.dumps(["database", "connection_pool", "timeout", "service-b"]),
            "remediation_steps_json": json.dumps([
                "1. Quiesce incoming checkout transactions at the ingress gateway by activating circuit breaker.",
                "2. Execute socket drain on database connection pool listener (port 8004).",
                "3. Terminate orphaned idle client handles holding locks past 15 seconds.",
                "4. Re-allocate 20 fresh pooled TCP sockets with keep-alive verification.",
                "5. Reset circuit breaker and verify downstream transaction latency drops below 50ms."
            ]),
            "prerequisites_json": json.dumps([
                "Database server daemon is alive and responding on port 8004",
                "Operator holds SRE_LEAD or OPERATOR role with recovery:execute scope",
                "Zero uncommitted DDL migrations in progress"
            ]),
            "risks_and_rollback_json": json.dumps([
                "Known risks: In-flight queries in aborted connections will trigger immediate retry from Service B.",
                "Rollback procedure: Re-invoke RECONNECT_DATABASE with persistent socket pool configuration."
            ]),
            "verified_outcome_details": "Empirically verified in sandbox SBX-088. 8/8 validation criteria passed. MTTR: 2.1s, 0 collateral regressions.",
            "version": "v1.4",
            "times_referenced": 18
        },
        {
            "incident_code": "KB-2025-112",
            "tenant_id": "demo-tenant",
            "title": "Payment Service Worker Thread Starvation and CPU Saturation",
            "primary_service": "service-b",
            "symptoms_summary": "CPU utilization surged past 88%. Request queue latency p95 jumped to 1420ms. Ingress Gateway returned 502 errors.",
            "root_cause": "Worker concurrency saturation during cryptographic payment signature verification.",
            "recommended_remedy": "SCALE_WORKERS",
            "recovery_action_taken": "SCALE_WORKERS",
            "recovery_duration_sec": 3.4,
            "outcome": "RESOLVED",
            "historical_success_rate": 91.2,
            "tags_json": json.dumps(["service-b", "cpu", "workers", "latency"]),
            "remediation_steps_json": json.dumps([
                "1. Inspect current thread pool capacity on Service B (baseline: 2 workers).",
                "2. Issue worker scale directive expanding concurrency pool from 2 to 6 threads.",
                "3. Verify OS scheduler thread queue depth decreases below 5 pending items.",
                "4. Monitor p95 latency across a 15-second window to confirm recovery under 150ms."
            ]),
            "prerequisites_json": json.dumps([
                "Host available memory > 512MB",
                "Worker runtime supports dynamic pool adjustment"
            ]),
            "risks_and_rollback_json": json.dumps([
                "Known risks: Increased database connection demand from expanded worker pool.",
                "Rollback procedure: Scale workers down to 2 threads if CPU throttling occurs."
            ]),
            "verified_outcome_details": "Empirically verified in post-mortem INC-HIST-2025-112. Error rate dropped from 38% to 0.0%. MTTR: 3.4s.",
            "version": "v1.2",
            "times_referenced": 12
        },
        {
            "incident_code": "KB-2026-004",
            "tenant_id": "demo-tenant",
            "title": "Service Process Crash from Segmentation Fault / Unhandled Signal",
            "primary_service": "service-a",
            "symptoms_summary": "Service A became abruptly unreachable (HTTP 503 / Connection Refused). Gateway unable to forward order traffic.",
            "root_cause": "Process termination due to out-of-bounds pointer or memory corruption in legacy serialization worker.",
            "recommended_remedy": "RESTART_CONTROLLED_SERVICE",
            "recovery_action_taken": "RESTART_CONTROLLED_SERVICE",
            "recovery_duration_sec": 4.2,
            "outcome": "RESOLVED",
            "historical_success_rate": 98.0,
            "tags_json": json.dumps(["service-a", "crash", "restart", "503"]),
            "remediation_steps_json": json.dumps([
                "1. Confirm process termination status code and dump stack trace to audit log.",
                "2. Route standby ingress traffic away from crashed instance to prevent connection drops.",
                "3. Execute graceful process restart of service container runtime.",
                "4. Run synthetic health probe GET /health to confirm HTTP 200 readiness.",
                "5. Restore ingress traffic and observe error rate across 30 seconds."
            ]),
            "prerequisites_json": json.dumps([
                "Container runtime daemon is healthy",
                "Configuration volume is mounted and valid"
            ]),
            "risks_and_rollback_json": json.dumps([
                "Known risks: 2-3 second service interruption during process cold start.",
                "Rollback procedure: Revert to previous stable container image if crash loop persists."
            ]),
            "verified_outcome_details": "Verified in sandbox test cycle. Service regained readiness in 4.2s with zero lingering memory corruptions.",
            "version": "v2.1",
            "times_referenced": 24
        },
        {
            "incident_code": "KB-2026-019",
            "tenant_id": "demo-tenant",
            "title": "Rapid Log Explosion Causing Tablespace Disk Pressure",
            "primary_service": "database-service",
            "symptoms_summary": "Storage volume crossed 85% warning threshold. Log generation velocity exceeded 1.8 GB/hour.",
            "root_cause": "Repeated unindexed query error loop generated 40,000 duplicate warning logs per minute.",
            "recommended_remedy": "ROTATE_AND_COMPRESS_LOGS",
            "recovery_action_taken": "ROTATE_AND_COMPRESS_LOGS",
            "recovery_duration_sec": 4.8,
            "outcome": "RESOLVED",
            "historical_success_rate": 96.0,
            "tags_json": json.dumps(["storage", "logs", "disk", "archive"]),
            "remediation_steps_json": json.dumps([
                "1. Quiesce non-essential log streams to prevent write buffer locks.",
                "2. Execute atomic log rotation on active logging descriptors.",
                "3. Trigger asynchronous gzip compression on rotated archival log segments.",
                "4. Verify tablespace disk free space increases above 30% safety margin."
            ]),
            "prerequisites_json": json.dumps([
                "Disk write permissions on log archival directory",
                "Gzip utility available on runtime host"
            ]),
            "risks_and_rollback_json": json.dumps([
                "Known risks: Brief CPU spike during gzip compression.",
                "Rollback procedure: Move uncompressed logs to backup cold volume."
            ]),
            "verified_outcome_details": "Storage recovered 12.4GB in 4.8 seconds, eliminating tablespace warning.",
            "version": "v1.1",
            "times_referenced": 15
        },
        {
            "incident_code": "KB-2026-027",
            "tenant_id": "demo-tenant",
            "title": "Redis Cache Buffer Deserialization Corruption",
            "primary_service": "service-b",
            "symptoms_summary": "Cache miss rate spiked to 92%, causing database read penetration and elevated memory allocation on Service B.",
            "root_cause": "Stale serialization keys in Redis buffer leading to unmarshaling errors and memory pressure.",
            "recommended_remedy": "CLEAR_CACHE",
            "recovery_action_taken": "CLEAR_CACHE",
            "recovery_duration_sec": 1.4,
            "outcome": "RESOLVED",
            "historical_success_rate": 93.8,
            "tags_json": json.dumps(["cache", "redis", "service-b", "memory"]),
            "remediation_steps_json": json.dumps([
                "1. Flush invalidation buffer and purge corrupted Redis cache keyspace.",
                "2. Force garbage collection on Service B to release leaked unmarshaling buffers.",
                "3. Warm cache gradually with high-frequency product catalog keys.",
                "4. Verify cache hit ratio recovers above 90% and Service B memory drops below 250MB."
            ]),
            "prerequisites_json": json.dumps([
                "Downstream database is healthy and able to serve read requests during cache warming.",
                "Cache client supports FLUSHDB / key eviction."
            ]),
            "risks_and_rollback_json": json.dumps([
                "Known risks: Temporary database read latency increase during initial cache warming window.",
                "Rollback procedure: Re-populate priority keys from read replica."
            ]),
            "verified_outcome_details": "Empirically verified in VRP-CACHE-002 with 8/8 test criteria passed and zero side effects.",
            "version": "v1.3",
            "times_referenced": 19
        }
    ]

    try:
        async with AsyncSessionLocal() as session:
            count_res = await session.execute(select(func.count(KnowledgeArticle.id)))
            existing_count = count_res.scalar() or 0
            if existing_count == 0:
                for art in SEED_ARTICLES:
                    rec = KnowledgeArticle(
                        incident_code=art["incident_code"],
                        tenant_id=art.get("tenant_id", "demo-tenant"),
                        title=art["title"],
                        primary_service=art["primary_service"],
                        symptoms_summary=art["symptoms_summary"],
                        root_cause=art["root_cause"],
                        recommended_remedy=art["recommended_remedy"],
                        recovery_action_taken=art["recovery_action_taken"],
                        recovery_duration_sec=art["recovery_duration_sec"],
                        outcome=art["outcome"],
                        historical_success_rate=art["historical_success_rate"],
                        tags_json=art["tags_json"],
                        remediation_steps_json=art["remediation_steps_json"],
                        prerequisites_json=art["prerequisites_json"],
                        risks_and_rollback_json=art["risks_and_rollback_json"],
                        verified_outcome_details=art.get("verified_outcome_details"),
                        version=art.get("version", "v1.0"),
                        times_referenced=art["times_referenced"]
                    )
                    session.add(rec)
                await session.commit()
    except Exception:
        pass


async def seed_initial_replicas():
    """Seeds baseline isolated digital twin replicas for FinCore, ShopSphere, and CloudDesk."""
    import json
    from backend.app.models.replica import ReplicaInstance
    from sqlalchemy import select, func

    SEED_REPLICAS = [
        {
            "replica_id": "REP-FINCORE-PAYMENT-01",
            "tenant_id": "fincore",
            "name": "FinCore Payment Authorization Twin",
            "environment_type": "SYNTHETIC",
            "fidelity_level": 0.99,
            "status": "HEALTHY",
            "target_service": "payment-api",
            "target_component": "transaction_authorizer",
            "isolation_boundaries": {
                "network": "AIRGAPPED_SANDBOX",
                "credentials": "SCOPED_TEST_ONLY",
                "target_database": "isolated_fincore_replica_db",
                "production_leak_prevention": "ACTIVE"
            },
            "limitations": [
                "Synthetic downstream bank ledger emulator with 30ms latency fixture",
                "PCI-DSS compliant test credentials only; zero real payment networks connected"
            ],
            "data_source": {
                "telemetry_source": "SYNTHETIC_DETERMINISTIC_FIXTURE",
                "recordings_count": 14200,
                "recorded_incident_signatures": ["DB_POOL_EXHAUSTION", "LATENCY_SPIKE", "FRAUD_TIMEOUT"]
            },
            "current_metrics": {
                "cpu_percent": 14.5,
                "memory_mb": 210,
                "latency_p50_ms": 18,
                "latency_p95_ms": 38,
                "error_rate": 0.0,
                "active_connections": 12
            }
        },
        {
            "replica_id": "REP-SHOPSPHERE-CHECKOUT-01",
            "tenant_id": "shopsphere",
            "name": "ShopSphere Checkout & Inventory Twin",
            "environment_type": "SYNTHETIC",
            "fidelity_level": 0.985,
            "status": "HEALTHY",
            "target_service": "order-service",
            "target_component": "checkout_pipeline",
            "isolation_boundaries": {
                "network": "AIRGAPPED_SANDBOX",
                "credentials": "SCOPED_TEST_ONLY",
                "target_database": "isolated_shopsphere_replica_db",
                "production_leak_prevention": "ACTIVE"
            },
            "limitations": [
                "Simulated payment gateway responding with deterministic 200/500 code fixtures",
                "Catalog cache preloaded with 5,000 synthetic retail SKUs"
            ],
            "data_source": {
                "telemetry_source": "SYNTHETIC_DETERMINISTIC_FIXTURE",
                "recordings_count": 28500,
                "recorded_incident_signatures": ["CHECKOUT_FAILURE", "INVENTORY_LAG", "CATALOG_TIMEOUT"]
            },
            "current_metrics": {
                "cpu_percent": 19.2,
                "memory_mb": 340,
                "latency_p50_ms": 22,
                "latency_p95_ms": 45,
                "error_rate": 0.0,
                "active_connections": 18
            }
        },
        {
            "replica_id": "REP-CLOUDDESK-WORKER-01",
            "tenant_id": "clouddesk",
            "name": "CloudDesk Auth & Job Worker Twin",
            "environment_type": "SYNTHETIC",
            "fidelity_level": 0.98,
            "status": "HEALTHY",
            "target_service": "compute-worker",
            "target_component": "job_queue_consumer",
            "isolation_boundaries": {
                "network": "AIRGAPPED_SANDBOX",
                "credentials": "SCOPED_TEST_ONLY",
                "target_database": "isolated_clouddesk_replica_db",
                "production_leak_prevention": "ACTIVE"
            },
            "limitations": [
                "Ephemeral Redis queue emulator with configurable backlog injection",
                "Synthetic multi-tenant workspace workspaces for isolation testing"
            ],
            "data_source": {
                "telemetry_source": "SYNTHETIC_DETERMINISTIC_FIXTURE",
                "recordings_count": 9800,
                "recorded_incident_signatures": ["AUTH_FAILURE", "QUEUE_BACKLOG", "WORKSPACE_DEGRADATION"]
            },
            "current_metrics": {
                "cpu_percent": 16.0,
                "memory_mb": 185,
                "latency_p50_ms": 15,
                "latency_p95_ms": 32,
                "error_rate": 0.0,
                "active_connections": 8
            }
        },
        {
            "replica_id": "REP-DEMO-CONTAINER-01",
            "tenant_id": "demo-tenant",
            "name": "Controlled Local Container Replica",
            "environment_type": "CONTAINER",
            "fidelity_level": 0.95,
            "status": "HEALTHY",
            "target_service": "database-service",
            "target_component": "connection_pool_manager",
            "isolation_boundaries": {
                "network": "BRIDGE_ISOLATED",
                "credentials": "CONTAINER_INTERNAL_ONLY",
                "target_database": "sqlite_container_sandbox",
                "production_leak_prevention": "ACTIVE"
            },
            "limitations": [
                "Container runs in isolated loopback namespace; cannot route to external host ports",
                "Synthetic stress tool injects controlled socket locks"
            ],
            "data_source": {
                "telemetry_source": "LOCAL_CONTAINER_FIXTURE",
                "recordings_count": 5200,
                "recorded_incident_signatures": ["CONNECTION_POOL_EXHAUSTION", "WORKER_SATURATION"]
            },
            "current_metrics": {
                "cpu_percent": 12.0,
                "memory_mb": 160,
                "latency_p50_ms": 12,
                "latency_p95_ms": 28,
                "error_rate": 0.0,
                "active_connections": 6
            }
        }
    ]

    try:
        async with AsyncSessionLocal() as session:
            count_res = await session.execute(select(func.count(ReplicaInstance.id)))
            existing_count = count_res.scalar() or 0
            if existing_count == 0:
                for rep in SEED_REPLICAS:
                    inst = ReplicaInstance(
                        replica_id=rep["replica_id"],
                        tenant_id=rep["tenant_id"],
                        name=rep["name"],
                        environment_type=rep["environment_type"],
                        fidelity_level=rep["fidelity_level"],
                        status=rep["status"],
                        target_service=rep["target_service"],
                        target_component=rep["target_component"],
                        isolation_boundaries_json=json.dumps(rep["isolation_boundaries"]),
                        limitations_json=json.dumps(rep["limitations"]),
                        data_source_json=json.dumps(rep["data_source"]),
                        current_metrics_json=json.dumps(rep["current_metrics"])
                    )
                    session.add(inst)
                await session.commit()
    except Exception:
        pass


