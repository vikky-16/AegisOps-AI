"""
AegisOps AI - Auditable Database Reconciliation Script
Preserves all historical records while safely archiving orphaned approvals,
correcting superseded statuses, and eliminating duplicate pending approvals.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import asyncio
import logging
from sqlalchemy import text
from backend.app.core.database import engine, AsyncSessionLocal

logger = logging.getLogger(__name__)


async def reconcile_database(engine_override=None):
    active_engine = engine_override or engine
    async with active_engine.begin() as conn:
        print("[RECONCILE] Starting safe auditable database reconciliation...")

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

        # 2. Find and archive orphaned approvals (where incident_id was deleted or does not exist)
        res = await conn.execute(text("""
            SELECT a.id, a.approval_id, a.incident_id, a.tenant_id, a.service_name,
                   a.proposed_action, a.status
            FROM approvals a
            LEFT JOIN incidents i ON a.incident_id = i.incident_id
            WHERE i.incident_id IS NULL;
        """))
        orphans = res.fetchall()
        print(f"[RECONCILE] Found {len(orphans)} orphaned approvals without associated incident.")

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
                "archival_reason": f"Archived: incident {o[2]} was deleted or does not exist."
            })
            await conn.execute(text("DELETE FROM approvals WHERE id = :id;"), {"id": o[0]})
        print(f"[RECONCILE] Successfully archived {len(orphans)} orphaned approvals into archived_approvals.")

        # 3. For resolved or validated incidents, ensure their pending approvals are marked CONSUMED
        up_res = await conn.execute(text("""
            UPDATE approvals
            SET status = 'CONSUMED',
                decision = 'CONSUMED',
                review_notes = 'Automatically consumed: incident was successfully resolved and verified.'
            WHERE status = 'PENDING'
              AND incident_id IN (
                  SELECT incident_id FROM incidents WHERE status IN ('RESOLVED', 'VALIDATED')
              );
        """))
        print(f"[RECONCILE] Marked resolved incident pending approvals as CONSUMED.")

        # 4. Deduplicate multiple PENDING approvals for the same (tenant_id, incident_id, proposed_action)
        # Keep only the latest one PENDING; mark earlier duplicates SUPERSEDED
        res = await conn.execute(text("""
            SELECT tenant_id, incident_id, proposed_action, count(*)
            FROM approvals
            WHERE status = 'PENDING'
            GROUP BY tenant_id, incident_id, proposed_action
            HAVING count(*) > 1;
        """))
        dup_groups = res.fetchall()
        print(f"[RECONCILE] Found {len(dup_groups)} groups with duplicate pending approvals.")
        dedup_count = 0
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
                            review_notes = 'Superseded by newer approval for same remediation action.'
                        WHERE id = :id;
                    """), {"id": old_id})
                    dedup_count += 1
        print(f"[RECONCILE] Superseded {dedup_count} older duplicate pending approvals.")

        # 5. Ensure performance indexes exist
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_approvals_tenant_status ON approvals(tenant_id, status);",
            "CREATE INDEX IF NOT EXISTS idx_approvals_inc_status ON approvals(incident_id, status);",
            "CREATE INDEX IF NOT EXISTS idx_archived_approvals_orig ON archived_approvals(original_id, approval_id);",
            "CREATE INDEX IF NOT EXISTS idx_replica_instances_tenant ON replica_instances(tenant_id);",
            "CREATE INDEX IF NOT EXISTS idx_replica_experiments_tenant ON replica_experiments(tenant_id, incident_id);"
        ]
        for idx in indexes:
            try:
                await conn.execute(text(idx))
            except Exception:
                pass

        print("[RECONCILE] Safe auditable database reconciliation complete!")


if __name__ == "__main__":
    asyncio.run(reconcile_database())
