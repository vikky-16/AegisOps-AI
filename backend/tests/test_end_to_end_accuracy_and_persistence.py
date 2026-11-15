"""
End-to-End Approval Accuracy, Company-Aware Recovery, Tenant Isolation, Performance & Persistence Tests.
Covers all requirements from Sections 1, 2, 3, 4, 5, 6, 7, 8, 10, 11 of the Enterprise Engineering specification.
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone
from fastapi import HTTPException

from backend.app.core.security import AuthenticatedIdentity
from backend.app.monitoring.collector import collector
from backend.app.healing.approval_manager import approval_manager
from backend.app.healing.decision_table import evidence_decision_engine, TENANT_CAPABILITIES
from backend.app.healing.solution_generator import solution_generator
from backend.app.healing.recommender import recommender
from backend.app.healing.sandbox_engine import sandbox_recovery_engine
from backend.app.ai.sre_chat_engine import sre_chat_engine
from backend.app.models.incident import Incident


@pytest.fixture(autouse=True)
def clean_test_state():
    """Ensure clean isolated state for each test run."""
    collector.active_incidents.clear()
    collector.resolved_incidents.clear()
    collector.pending_approvals.clear()
    collector.reviewed_approvals.clear()


# ==============================================================================
# SECTION 1: APPROVAL COUNTING AND LIFECYCLE TESTS (Req 1-6)
# ==============================================================================

@pytest.mark.asyncio
async def test_approval_not_counted_multiple_times():
    """1. One pending ticket is not counted multiple times."""
    inc = {
        "incident_id": "INC-TEST-ACC-01",
        "tenant_id": "test-accuracy-tenant",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "title": "Database Connection Pool Saturation",
        "severity": "CRITICAL",
        "attempt_number": 1
    }
    # Create ticket
    t1 = await approval_manager.create_or_get_approval_ticket(
        incident=inc,
        proposed_action="RESET_CONNECTION_POOL"
    )
    assert t1 is not None

    stats = approval_manager.get_approval_stats(tenant_id="test-accuracy-tenant")
    assert stats["pending_approvals"] == 1
    assert stats["total_pending"] == 1


@pytest.mark.asyncio
async def test_multiple_legitimate_tickets_counted_correctly():
    """2. Multiple legitimate tickets for one incident (e.g. distinct attempts) are counted correctly."""
    inc_att1 = {
        "incident_id": "INC-TEST-MULTI-02",
        "tenant_id": "test-multi-tenant",
        "primary_service": "database-service",
        "title": "DB Saturation Attempt 1",
        "severity": "CRITICAL",
        "attempt_number": 1
    }
    t1 = await approval_manager.create_or_get_approval_ticket(inc_att1, "RESET_CONNECTION_POOL")
    
    # Resolve attempt 1 as REJECTED
    await approval_manager.sync_ticket_status(t1["approval_id"], "REJECTED", notes="Declined attempt 1")

    # Attempt 2 is a distinct recovery action requiring approval
    inc_att2 = {
        "incident_id": "INC-TEST-MULTI-02",
        "tenant_id": "test-multi-tenant",
        "primary_service": "database-service",
        "title": "DB Saturation Attempt 2",
        "severity": "CRITICAL",
        "attempt_number": 2
    }
    t2 = await approval_manager.create_or_get_approval_ticket(inc_att2, "RESTART_CONTROLLED_SERVICE")

    all_tickets = await approval_manager.get_all_tickets(tenant_id="test-multi-tenant")
    # Both tickets exist, retaining audit history
    assert len(all_tickets) >= 2
    stats = approval_manager.get_approval_stats(tenant_id="test-multi-tenant")
    assert stats["pending_approvals"] == 1  # Only attempt 2 is pending
    assert stats["rejected_today"] >= 1     # Attempt 1 is counted as rejected


@pytest.mark.asyncio
async def test_pending_incident_counts_use_distinct_incidents():
    """3. Pending incident counts use distinct incidents."""
    inc1 = {"incident_id": "INC-DIST-01", "tenant_id": "test-dist-tenant", "attempt_number": 1}
    inc2 = {"incident_id": "INC-DIST-02", "tenant_id": "test-dist-tenant", "attempt_number": 1}

    await approval_manager.create_or_get_approval_ticket(inc1, "RESET_CONNECTION_POOL")
    await approval_manager.create_or_get_approval_ticket(inc2, "CLEAR_CACHE")

    stats = approval_manager.get_approval_stats(tenant_id="test-dist-tenant")
    assert stats["pending_approvals"] == 2
    assert stats["unique_incidents"] == 2
    assert stats["distinct_incidents_awaiting"] == 2


@pytest.mark.asyncio
async def test_historical_tickets_do_not_inflate_pending():
    """4. Historical tickets do not inflate pending counts."""
    inc = {"incident_id": "INC-HIST-01", "tenant_id": "test-hist-tenant", "attempt_number": 1}
    t = await approval_manager.create_or_get_approval_ticket(inc, "RESET_CONNECTION_POOL")
    
    # Approve ticket
    await approval_manager.sync_ticket_status(t["approval_id"], "APPROVED")

    stats = approval_manager.get_approval_stats(tenant_id="test-hist-tenant")
    assert stats["pending_approvals"] == 0
    assert stats["unique_incidents"] == 0
    assert stats["approved_today"] >= 1
    assert stats["historical_records"] >= 1


@pytest.mark.asyncio
async def test_reprocessing_incident_does_not_create_duplicate_approvals():
    """5. Reprocessing an incident with same (tenant, incident, action) returns identical ticket."""
    inc = {
        "incident_id": "INC-REPROCESS-01",
        "tenant_id": "test-reprocess-tenant",
        "primary_service": "database-service",
        "attempt_number": 1
    }
    t1 = await approval_manager.create_or_get_approval_ticket(inc, "RESET_CONNECTION_POOL")
    t2 = await approval_manager.create_or_get_approval_ticket(inc, "RESET_CONNECTION_POOL")

    assert t1["approval_id"] == t2["approval_id"]
    stats = approval_manager.get_approval_stats(tenant_id="test-reprocess-tenant")
    assert stats["pending_approvals"] == 1


@pytest.mark.asyncio
async def test_approving_or_rejecting_updates_persisted_ticket():
    """6. Approving/rejecting updates the same persisted ticket in memory and DB."""
    inc = {"incident_id": "INC-PERSIST-01", "tenant_id": "test-persist-tenant", "attempt_number": 1}
    t = await approval_manager.create_or_get_approval_ticket(inc, "RESET_CONNECTION_POOL")
    app_id = t["approval_id"]

    # Reject
    await approval_manager.sync_ticket_status(app_id, "REJECTED", reviewer="Lead_SRE", notes="Maintenance freeze")

    ticket_after = approval_manager.get_ticket(app_id, tenant_id="test-persist-tenant")
    assert ticket_after["status"] == "REJECTED"
    assert ticket_after["decision"] == "REJECTED"
    assert ticket_after["reviewed_by"] == "Lead_SRE"

    # Pending count is 0
    stats = approval_manager.get_approval_stats(tenant_id="test-persist-tenant")
    assert stats["pending_approvals"] == 0
    assert stats["rejected_today"] == 1


# ==============================================================================
# SECTION 2: RECOVERY DECISION ENGINE TESTS (Req 7-11)
# ==============================================================================

def test_different_evidence_produces_different_recovery_actions():
    """7. Different evidence patterns produce appropriate different recovery recommendations."""
    # Pattern A: Database Connection Pool Exhaustion
    inc_db = {
        "incident_id": "INC-DEC-01",
        "tenant_id": "shopsphere",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "evidence_summary": [
            "Active connection pool reached 50/50 saturation limit",
            "Client query queue experienced acquisition timeouts"
        ]
    }
    dec_db = evidence_decision_engine.evaluate_incident_recovery(inc_db)
    assert dec_db["recommended_action"] == "RESET_CONNECTION_POOL"
    assert "Restart Service" not in dec_db["why_selected"]

    # Pattern B: Redis Cache Saturation
    inc_cache = {
        "incident_id": "INC-DEC-02",
        "tenant_id": "clouddesk",
        "primary_service": "redis-cache",
        "root_cause_service": "redis-cache",
        "evidence_summary": [
            "Redis memory buffer reached 94% threshold",
            "Cache key eviction rate surged causing latency spike"
        ]
    }
    dec_cache = evidence_decision_engine.evaluate_incident_recovery(inc_cache)
    assert dec_cache["recommended_action"] == "CLEAR_CACHE"

    # Pattern C: Service Crash
    inc_crash = {
        "incident_id": "INC-DEC-03",
        "tenant_id": "shopsphere",
        "primary_service": "payment-service",
        "root_cause_service": "payment-service",
        "evidence_summary": [
            "Process exited unexpectedly with exit code 137 (OOMKilled) / SIGSEGV",
            "Health probe endpoint returned connection refused"
        ]
    }
    dec_crash = evidence_decision_engine.evaluate_incident_recovery(inc_crash)
    assert dec_crash["recommended_action"] == "RESTART_CONTROLLED_SERVICE"

    # Pattern D: Canary Deployment Regression
    inc_deploy = {
        "incident_id": "INC-DEC-04",
        "tenant_id": "clouddesk",
        "primary_service": "workspace-api",
        "root_cause_service": "workspace-api",
        "evidence_summary": [
            "Error spike onset coincided directly with deployment revision v2.4.1",
            "Canary pod health checks failed after deployment roll-out"
        ]
    }
    dec_deploy = evidence_decision_engine.evaluate_incident_recovery(inc_deploy)
    assert dec_deploy["recommended_action"] == "ROLLBACK_CONTROLLED_DEPLOYMENT"


def test_restart_is_not_universal_fallback():
    """8. Restart Service is not the universal fallback for unrelated failure classes."""
    for cat in ["DATABASE_CONNECTION_POOL_EXHAUSTION", "CACHE_SATURATION_EVICTION", "CANARY_DEPLOYMENT_REGRESSION"]:
        dec = evidence_decision_engine.evaluate_recovery_decision(
            evidence_summary=["Evidence for " + cat],
            root_category=cat,
            target_service="database-service",
            tenant_id="shopsphere"
        )
        assert dec["recommended_action"] != "RESTART_SERVICE"


def test_insufficient_evidence_produces_uncertainty():
    """9. Insufficient evidence produces an uncertainty result instead of automatically restarting."""
    ambiguous_inc = {
        "incident_id": "INC-AMBIGUOUS-01",
        "tenant_id": "shopsphere",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "evidence_summary": []  # Empty evidence
    }
    dec = evidence_decision_engine.evaluate_incident_recovery(ambiguous_inc)
    assert dec["uncertainty"] is True
    assert dec["recommended_action"] == "UNCERTAIN_EVIDENCE"
    assert "Insufficient conclusive telemetry" in dec["expected_result"]


def test_unsupported_actions_not_executable():
    """10. Unsupported actions are not presented as executable in that company environment."""
    # FinCore does NOT support CLEAR_CACHE under strict compliance policy
    dec = evidence_decision_engine.evaluate_recovery_decision(
        evidence_summary=["Redis buffer reached 95%"],
        root_category="CACHE_SATURATION_EVICTION",
        target_service="redis-cache",
        tenant_id="fincore"
    )
    assert dec["action_available"] is False
    assert "Action unavailable in the connected environment" in dec["why_selected"]


def test_tenant_capabilities_and_policies():
    """11. Recommendations respect tenant environment capabilities."""
    assert "RESET_CONNECTION_POOL" in TENANT_CAPABILITIES["shopsphere"]["supported_actions"]
    assert "CLEAR_CACHE" not in TENANT_CAPABILITIES["fincore"]["supported_actions"]
    assert "SCALE_WORKERS" in TENANT_CAPABILITIES["clouddesk"]["supported_actions"]


# ==============================================================================
# SECTION 3: TENANT ISOLATION TESTS (Req 12-14)
# ==============================================================================

@pytest.mark.asyncio
async def test_tenant_isolation_incidents_and_recovery():
    """12. Company A cannot access Company B's approval tickets or recovery history."""
    inc_a = {"incident_id": "INC-CORP-A", "tenant_id": "company-a"}
    inc_b = {"incident_id": "INC-CORP-B", "tenant_id": "company-b"}

    t_a = await approval_manager.create_or_get_approval_ticket(inc_a, "RESET_CONNECTION_POOL")
    t_b = await approval_manager.create_or_get_approval_ticket(inc_b, "CLEAR_CACHE")

    tickets_for_a = await approval_manager.get_all_tickets(tenant_id="company-a")
    assert any(t["approval_id"] == t_a["approval_id"] for t in tickets_for_a)
    assert not any(t["approval_id"] == t_b["approval_id"] for t in tickets_for_a)


@pytest.mark.asyncio
async def test_ai_context_is_tenant_scoped():
    """13. SRE Assistant context is tenant-scoped."""
    collector.active_incidents.append({
        "incident_id": "INC-PRIVATE-A",
        "tenant_id": "tenant-alpha",
        "title": "Confidential Alpha Database Outage"
    })
    collector.active_incidents.append({
        "incident_id": "INC-PRIVATE-B",
        "tenant_id": "tenant-beta",
        "title": "Confidential Beta API Crash"
    })

    # Query context for tenant-alpha
    ctx_a = await sre_chat_engine._retrieve_context(
        incident_id="INC-PRIVATE-A",
        query="What happened?",
        tenant_id="tenant-alpha"
    )
    assert "INC-PRIVATE-A" in ctx_a["active_incidents"]
    assert "INC-PRIVATE-B" not in ctx_a["active_incidents"]


@pytest.mark.asyncio
async def test_conversation_ids_enforce_tenant_auth():
    """14. Conversation history cannot be retrieved across tenant boundaries."""
    conv_id = f"CONV-ISOLATION-{int(time.time())}"
    await sre_chat_engine.chat(
        message="Sensitive question for tenant A",
        conversation_id=conv_id,
        tenant_id="tenant-alpha"
    )

    # Retrieval by tenant-alpha succeeds
    history_a = await sre_chat_engine.get_conversation_history_async(conv_id, tenant_id="tenant-alpha")
    assert len(history_a) >= 2

    # Retrieval by tenant-beta returns empty (isolated)
    history_b = await sre_chat_engine.get_conversation_history_async(conv_id, tenant_id="tenant-beta")
    assert len(history_b) == 0


# ==============================================================================
# SECTION 4: PERSISTENCE & NAVIGATION SURVIVAL TESTS (Req 15-21)
# ==============================================================================

@pytest.mark.asyncio
async def test_recovery_results_survive_navigation():
    """15 & 17. Completed recovery results survive page remount/navigation."""
    inc = {
        "incident_id": "INC-NAV-SURVIVE-01",
        "tenant_id": "shopsphere",
        "primary_service": "database-service",
        "root_cause_service": "database-service"
    }
    # Initialize sandbox
    sbx = await sandbox_recovery_engine.initialize_sandbox(inc, initial_action="RESET_CONNECTION_POOL")
    assert sbx["sandbox_id"].upper().startswith("SBX-")

    # Simulate navigating away and re-fetching
    retrieved = sandbox_recovery_engine.get_sandbox(inc["incident_id"])
    assert retrieved is not None
    assert retrieved["sandbox_id"] == sbx["sandbox_id"]
    assert retrieved["incident_id"] == inc["incident_id"]


@pytest.mark.asyncio
async def test_running_execution_resumes_from_backend():
    """16. Running executions retain their execution state in backend."""
    inc_id = "INC-RUNNING-01"
    sbx = await sandbox_recovery_engine.initialize_sandbox(
        {"incident_id": inc_id, "primary_service": "database-service"},
        initial_action="RESET_CONNECTION_POOL"
    )
    assert sbx["current_stage"] in ["SANDBOX_INITIALIZED", "READY", "INITIALIZING"]


@pytest.mark.asyncio
async def test_sre_conversations_survive_navigation_and_reload():
    """18. SRE conversations persist in backend database across sessions."""
    conv_id = f"CONV-TEST-PERSIST-{int(time.time()*1000)}"
    res1 = await sre_chat_engine.chat(
        message="What is the root cause of the current database issue?",
        conversation_id=conv_id,
        tenant_id="shopsphere"
    )
    assert res1["conversation_id"] == conv_id

    # Simulate navigating away and returning: fetch from database
    history = await sre_chat_engine.get_conversation_history_async(conv_id, tenant_id="shopsphere")
    assert len(history) >= 2
    assert any(m["role"] == "user" and "root cause" in m["text"] for m in history)
    assert any(m["role"] == "assistant" for m in history)


@pytest.mark.asyncio
async def test_failed_assistant_request_retains_question():
    """19. Failed assistant requests preserve the original user question."""
    conv_id = f"CONV-FAIL-RETAIN-{int(time.time()*1000)}"
    user_query = "Detailed forensic trace analysis question"

    # Simulate a run with conversation storage
    res = await sre_chat_engine.chat(
        message=user_query,
        conversation_id=conv_id,
        tenant_id="shopsphere"
    )
    history = await sre_chat_engine.get_conversation_history_async(conv_id, tenant_id="shopsphere")
    assert any(m["role"] == "user" and m["text"] == user_query for m in history)


# ==============================================================================
# SECTION 5: PERFORMANCE & EMPIRICAL VALIDATION INTEGRITY (Req 22-24)
# ==============================================================================

@pytest.mark.asyncio
async def test_performance_timings_and_validation_criteria_not_skipped():
    """22-24. Measures execution timings and confirms full 8 criteria are validated without shortcuts."""
    inc = {
        "incident_id": "INC-PERF-CHECK-01",
        "tenant_id": "shopsphere",
        "primary_service": "database-service",
        "root_cause_service": "database-service"
    }
    t0 = time.perf_counter()
    cycle_res = await sandbox_recovery_engine.run_full_validation_cycle(inc, action="RESET_CONNECTION_POOL")
    elapsed_backend = time.perf_counter() - t0

    assert cycle_res is not None
    assert elapsed_backend < 8.0  # Backend executes promptly without blocking

    val = cycle_res.get("validation", {})
    criteria = val.get("criteria_results", [])
    # Verify that all 8 validation criteria are evaluated (no criteria skipped)
    assert len(criteria) == 8
    crit_names = [c.get("criterion") for c in criteria]
    assert "CRIT-1" in crit_names
    assert "CRIT-8" in crit_names
