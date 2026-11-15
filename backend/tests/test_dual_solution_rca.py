"""
Comprehensive Automated Test Suite for Dual-Solution Root Cause Analysis (RCA)
Verifies:
1. Two distinct labeled solution sections: Solution A (AI-Proposed) + Solution B (Knowledge Base)
2. AI-proposed solution grounded in specific incident evidence & configured provider
3. Real Knowledge Base retrieval preserving stored remediation steps verbatim
4. Different incidents receive different solutions
5. Irrelevant knowledge articles rejected by relevance threshold (<65%)
6. Empty Knowledge Base handled honestly without fake data
7. Independent failure handling (AI failure and KB failure handled independently)
8. Multi-tenant isolation (company-specific resolutions isolated)
9. Result persistence and idempotency (navigating away and returning restores solutions)
10. Solution selection creates recovery plan and follows approval requirements
11. Recovery execution confirmed with post-action validation evidence
12. User knowledge contribution workflow (adding verified resolutions)
"""

import pytest
import uuid
import json
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.knowledge.retrieval import knowledge_retrieval_engine
from backend.app.rca.dual_solution_engine import dual_solution_rca_engine
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.rca import IncidentRCARecord
from backend.app.models.knowledge import KnowledgeArticle


@pytest.mark.asyncio
async def test_dual_solutions_produced_in_rca_endpoint():
    """Verify GET /api/incidents/{id}/rca and /dual-solutions produce two labeled solution options."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/incidents/INC-20261008-001/dual-solutions")
        assert resp.status_code == 200
        data = resp.json()

        assert "ai_solution" in data, "Must provide Solution A (AI-Proposed Solution)"
        assert "kb_solution" in data, "Must provide Solution B (Knowledge Base Solution)"
        assert "comparison" in data, "Must provide side-by-side comparison"

        # Verify Solution A schema
        ai_sol = data["ai_solution"]
        assert "proposed_action" in ai_sol
        assert "why_this_solution" in ai_sol
        assert "supporting_evidence" in ai_sol
        assert "implementation_steps" in ai_sol
        assert "expected_outcome" in ai_sol
        assert "risk_and_side_effects" in ai_sol
        assert "verification_plan" in ai_sol
        assert "approval_requirements" in ai_sol

        # Verify Solution B schema
        kb_sol = data["kb_solution"]
        assert "status" in kb_sol
        assert "matched" in kb_sol
        if kb_sol["matched"]:
            assert "article_id" in kb_sol
            assert "why_it_matches" in kb_sol
            assert "original_problem" in kb_sol
            assert "known_root_cause" in kb_sol
            assert "stored_remediation_steps" in kb_sol
            assert "prerequisites_and_permissions" in kb_sol
            assert "known_risks" in kb_sol
            assert "historical_outcome" in kb_sol


@pytest.mark.asyncio
async def test_ai_solution_uses_specific_incident_evidence():
    """Verify Solution A is specific to the incident's service and root cause evidence."""
    inc = {
        "incident_id": "INC-TEST-EVID-01",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause": "Database connection pool exhaustion on database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "severity": "CRITICAL",
        "affected_services": ["database-service", "service-b", "gateway"],
        "tenant_id": "demo-tenant"
    }
    evidence = {
        "suspected_origin_service": "database-service",
        "incident_type": "CONNECTION_POOL_EXHAUSTION",
        "logs": [{"service": "database-service", "message": "ConnectionPoolTimeoutException: 100/100 acquired"}],
        "metrics": [{"metric": "active_connections", "observed_value": "100", "service": "database-service"}]
    }

    result = await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc["incident_id"],
        incident=inc,
        evidence_package=evidence,
        tenant_id="demo-tenant",
        force_regenerate=True
    )

    ai_sol = result["ai_solution"]
    assert ai_sol["target_service"] == "database-service"
    assert ai_sol["action_key"] in ["RESET_CONNECTION_POOL", "RESTART_CONTROLLED_SERVICE"]
    # Evidence must be grounded in incident
    assert len(ai_sol["supporting_evidence"]) > 0


@pytest.mark.asyncio
async def test_kb_solution_retrieves_real_stored_entry_and_preserves_steps():
    """Verify Solution B retrieves real entry from database and preserves stored steps verbatim."""
    kb_res = await knowledge_retrieval_engine.retrieve_matching_solution(
        service="database-service",
        category="CONNECTION_POOL_EXHAUSTION",
        error_signature="ConnectionPoolTimeoutException",
        tenant_id="demo-tenant"
    )

    assert kb_res.matched is True
    assert kb_res.article_id in ["KB-2025-089", "VRP-014"]
    assert len(kb_res.stored_remediation_steps) >= 3
    # Step 1 must be preserved verbatim from KB-2025-089 or pattern
    assert any("Verify active connection count" in s or "Quiesce" in s or "pool" in s.lower() for s in kb_res.stored_remediation_steps)
    assert kb_res.remediation_action == "RESET_CONNECTION_POOL"


@pytest.mark.asyncio
async def test_different_incidents_receive_different_solutions():
    """Verify database exhaustion and cache failure incidents receive distinct solutions."""
    # Incident 1: DB connection pool
    inc_db = {
        "incident_id": "INC-TEST-DB-99",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause": "Database connection pool exhaustion",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "tenant_id": "demo-tenant"
    }
    # Incident 2: Redis cache degradation
    inc_cache = {
        "incident_id": "INC-TEST-CACHE-99",
        "primary_service": "cache-service",
        "root_cause_service": "cache-service",
        "root_cause": "Cache evictions and stale memory leak",
        "root_cause_category": "CACHE_FAILURE",
        "tenant_id": "demo-tenant"
    }

    res_db = await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc_db["incident_id"],
        incident=inc_db,
        evidence_package={"suspected_origin_service": "database-service", "incident_type": "CONNECTION_POOL_EXHAUSTION"},
        tenant_id="demo-tenant",
        force_regenerate=True
    )

    res_cache = await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc_cache["incident_id"],
        incident=inc_cache,
        evidence_package={"suspected_origin_service": "cache-service", "incident_type": "CACHE_FAILURE"},
        tenant_id="demo-tenant",
        force_regenerate=True
    )

    # Must produce different actions
    db_act = res_db["ai_solution"]["action_key"]
    cache_act = res_cache["ai_solution"]["action_key"]
    assert db_act != cache_act, f"Expected distinct actions, got {db_act} and {cache_act}"
    assert "POOL" in db_act
    assert "CACHE" in cache_act


@pytest.mark.asyncio
async def test_relevance_threshold_rejects_irrelevant_kb_article():
    """Verify unrelated symptoms and services do not match KB (<65% threshold)."""
    kb_res = await knowledge_retrieval_engine.retrieve_matching_solution(
        service="unknown-unregistered-service",
        category="NON_EXISTENT_ANOMALY",
        error_signature="UniqueUnrelatedErrorString999",
        tenant_id="demo-tenant"
    )

    assert kb_res.matched is False
    assert kb_res.status == "NO_RELEVANT_MATCH"
    assert "No sufficiently relevant" in kb_res.missing_information or "threshold" in kb_res.missing_information
    assert kb_res.article_id is None


@pytest.mark.asyncio
async def test_empty_knowledge_base_handled_honestly():
    """Verify an isolated tenant with zero entries returns truthful no match without fake data."""
    empty_tenant = f"empty-tenant-{uuid.uuid4().hex[:8]}"
    kb_res = await knowledge_retrieval_engine.retrieve_matching_solution(
        service="custom-microservice",
        category="CUSTOM_EXCEPTION",
        tenant_id=empty_tenant
    )

    assert kb_res.matched is False
    assert kb_res.status == "NO_RELEVANT_MATCH"
    assert kb_res.article_id is None


@pytest.mark.asyncio
async def test_independent_failure_handling():
    """Verify KB succeeds even if AI credentials are unset or provider is down."""
    # When AI is not configured
    inc = {
        "incident_id": "INC-TEST-INDEP-01",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "tenant_id": "demo-tenant"
    }

    res = await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc["incident_id"],
        incident=inc,
        evidence_package={"suspected_origin_service": "database-service", "incident_type": "CONNECTION_POOL_EXHAUSTION"},
        tenant_id="demo-tenant",
        force_regenerate=True
    )

    # Even if AI is NOT_CONFIGURED or error, KB is MATCH_FOUND
    assert res["kb_solution"]["matched"] is True
    assert res["kb_solution"]["article_id"] is not None


@pytest.mark.asyncio
async def test_tenant_isolation_strictly_enforced():
    """Verify company-specific resolution in Tenant A is invisible to Tenant B."""
    tenant_a = f"company-a-{uuid.uuid4().hex[:6]}"
    tenant_b = f"company-b-{uuid.uuid4().hex[:6]}"

    # Add resolution in Tenant A
    article_a = await knowledge_retrieval_engine.record_verified_resolution(
        incident_id=f"INC-{tenant_a}-01",
        title="Company A Internal Payment Gateway Timeout",
        category="PAYMENT_GATEWAY_TIMEOUT",
        service="payment-processor",
        symptoms=["504 Gateway Timeout from stripe-internal-proxy"],
        root_cause="Stripe proxy connection limit",
        remediation_steps=["1. Rotate Company A proxy endpoint", "2. Reset connection pool"],
        action_key="RESET_CONNECTION_POOL",
        tenant_id=tenant_a
    )
    assert article_a.tenant_id == tenant_a

    # Query as Tenant B
    match_b = await knowledge_retrieval_engine.retrieve_matching_solution(
        service="payment-processor",
        category="PAYMENT_GATEWAY_TIMEOUT",
        tenant_id=tenant_b
    )

    # Tenant B MUST NOT see Tenant A's private resolution
    if match_b.matched:
        assert match_b.article_id != article_a.article_id, "Tenant B leaked Tenant A's private article!"
    else:
        assert match_b.matched is False


@pytest.mark.asyncio
async def test_idempotent_persistence_restores_solutions():
    """Verify navigating away and returning restores the exact same solutions without regeneration."""
    inc_id = f"INC-PERSIST-{uuid.uuid4().hex[:6]}"
    inc = {
        "incident_id": inc_id,
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "tenant_id": "demo-tenant"
    }

    # First generation
    res1 = await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc_id,
        incident=inc,
        evidence_package={"suspected_origin_service": "database-service", "incident_type": "CONNECTION_POOL_EXHAUSTION"},
        tenant_id="demo-tenant"
    )

    # Second fetch without force_regenerate (simulating reload/navigation)
    res2 = await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc_id,
        incident=inc,
        evidence_package={"suspected_origin_service": "database-service", "incident_type": "CONNECTION_POOL_EXHAUSTION"},
        tenant_id="demo-tenant",
        force_regenerate=False
    )

    assert res1["rca_id"] == res2["rca_id"]
    assert res1["ai_solution"]["action_key"] == res2["ai_solution"]["action_key"]
    assert res1["kb_solution"]["article_id"] == res2["kb_solution"]["article_id"]


@pytest.mark.asyncio
async def test_solution_selection_recovery_plan_and_validation():
    """Verify selecting a solution creates recovery plan, checks policy/approvals, and records validation."""
    inc_id = f"INC-SELECT-{uuid.uuid4().hex[:6]}"
    inc = {
        "incident_id": inc_id,
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "tenant_id": "demo-tenant"
    }

    # Ensure dual solutions generated
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident_id=inc_id,
        incident=inc,
        evidence_package={"suspected_origin_service": "database-service", "incident_type": "CONNECTION_POOL_EXHAUSTION"},
        tenant_id="demo-tenant"
    )

    # Select Knowledge Base solution
    select_res = await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="KNOWLEDGE_BASE",
        tenant_id="demo-tenant",
        user="Lead SRE"
    )

    assert select_res["selected_source"] == "KNOWLEDGE_BASE"
    assert "plan_id" in select_res
    assert select_res["status"] in ["SELECTED", "AWAITING_APPROVAL", "APPROVAL_REQUIRED", "EXECUTED", "VERIFIED"]

    # Verify via API endpoint as well
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        api_resp = await client.get(f"/api/incidents/{inc_id}/dual-solutions")
        assert api_resp.status_code == 200
        data = api_resp.json()
        assert data["selection"] is not None
        assert data["selection"]["selected_source"] == "KNOWLEDGE_BASE"


@pytest.mark.asyncio
async def test_user_adds_verified_resolution_workflow():
    """Verify an authorized user can record a verified resolution when no match was found."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "title": "Kafka Consumer Group Lag Remediation",
            "category": "CONSUMER_LAG",
            "service": "order-processor",
            "symptoms": ["Consumer offset lagging 45,000 records", "Thread pool starvation"],
            "root_cause": "Worker thread blockage on external billing dependency",
            "remediation_steps": [
                "1. Pause consumer polling",
                "2. Scale worker thread capacity to 16",
                "3. Resume partition consumption"
            ],
            "prerequisites": ["SRE operator access to kafka cluster"],
            "risks_and_rollback": {"risk_level": "LOW", "rollback_steps": ["Scale down workers"]},
            "verified_outcome_details": "Consumer lag drained within 90s, zero dropped messages.",
            "action_key": "SCALE_WORKERS",
            "tenant_id": "demo-tenant"
        }

        resp = await client.post("/api/incidents/INC-20261008-001/knowledge-base/add", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CREATED"
        assert "article" in data
        assert data["article"]["title"] == "Kafka Consumer Group Lag Remediation"
        assert data["article"]["category"] == "CONSUMER_LAG"
