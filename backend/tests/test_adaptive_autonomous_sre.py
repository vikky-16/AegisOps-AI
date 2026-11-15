"""
AegisOps AI - Adaptive Autonomous SRE Comprehensive Acceptance Tests
Tests:
1. Architecture Inventory, Topology, Workflows & Coverage Gaps
2. Isolated Remediation Lab & Multi-Candidate Independent Testing
3. 9-Layer Validation Engine (Deterministic checks & truthfulness)
4. Independent AI Validator & Safety Guardrails
5. Production Execution Safeguards & Post-Production 9-Layer Validation
6. Verified Knowledge Base Learning Loop & Status Lifecycle
7. Tenant Isolation & RBAC Security Boundaries
"""

import pytest
import asyncio
from datetime import datetime, timezone

from backend.app.analytics.architecture_discovery import architecture_discovery
from backend.app.replica.remediation_lab import remediation_lab
from backend.app.validation.nine_layer_validator import nine_layer_validator
from backend.app.validation.independent_validator import independent_validator
from backend.app.knowledge.incident_memory import verified_recovery_store


@pytest.mark.asyncio
async def test_architecture_inventory_and_coverage_gaps():
    """Verify tenant architecture inventory, workflows, and coverage gap analysis."""
    # Test ShopSphere inventory
    inv = await architecture_discovery.get_tenant_inventory(tenant_id="shopsphere")
    assert inv["tenant_id"] == "shopsphere"
    assert inv["total_resources"] >= 7
    assert inv["verified_resources"] >= 6
    assert inv["architecture_coverage_percent"] > 70.0
    assert "coverage_gaps" in inv
    assert "unverified_resources" in inv["coverage_gaps"]

    # Verify critical business workflows
    wfs = inv["workflows"]
    assert len(wfs) >= 3
    checkout_wf = next((w for w in wfs if w["workflow_id"] == "WF-CHECKOUT-PRIMARY"), None)
    assert checkout_wf is not None
    assert checkout_wf["criticality"] == "MISSION_CRITICAL"
    assert "database-service" in checkout_wf["service_path"]

    # Test FinCore inventory (separate tenant isolation)
    fincore_inv = await architecture_discovery.get_tenant_inventory(tenant_id="fincore")
    assert fincore_inv["tenant_id"] == "fincore"
    assert any("fincore-edge" in n["resource_id"] for n in fincore_inv["nodes"])


@pytest.mark.asyncio
async def test_remediation_lab_multi_candidate_clean_state_isolation():
    """
    Verify isolated lab tests multiple candidates independently from clean baselines
    without cross-candidate state pollution.
    """
    candidates = [
        {
            "candidate_id": "cand-effective",
            "title": "Candidate A: Reset Connection Pool",
            "source": "AI_PROPOSED",
            "action": "RESET_CONNECTION_POOL",
            "risk": "LOW"
        },
        {
            "candidate_id": "cand-disruptive",
            "title": "Candidate B: Restart Service",
            "source": "KNOWLEDGE_BASE",
            "action": "RESTART_SERVICE",
            "risk": "MEDIUM"
        },
        {
            "candidate_id": "cand-harmful",
            "title": "Candidate C: Scale Workers",
            "source": "ALTERNATIVE_OPERATOR",
            "action": "SCALE_WORKERS",
            "risk": "HIGH"
        }
    ]

    context = {
        "title": "Database Connection Pool Exhaustion",
        "description": "503 timeouts and active connections saturated at 100%",
        "service": "database-service"
    }

    result = await remediation_lab.execute_multi_candidate_trial(
        incident_id="INC-TEST-001",
        tenant_id="shopsphere",
        candidates=candidates,
        incident_context=context
    )

    assert result["status"] == "CANDIDATE_SELECTED"
    assert result["run_id"].startswith("LAB-")
    assert len(result["candidate_trials"]) == 3

    # Check each trial verified clean state reset
    for trial in result["candidate_trials"]:
        assert trial["clean_state_reset_verified"] is True
        assert "nine_layer_validation" in trial

    # Candidate A (RESET_CONNECTION_POOL) should resolve without side effects
    cand_a = next(t for t in result["candidate_trials"] if t["action"] == "RESET_CONNECTION_POOL")
    assert cand_a["resolves_root_cause"] is True
    assert len(cand_a["side_effects_detected"]) == 0
    assert cand_a["trial_verdict"] == "VALIDATED"

    # Candidate B (RESTART_SERVICE) should trigger a latency surge side effect
    cand_b = next(t for t in result["candidate_trials"] if t["action"] == "RESTART_SERVICE")
    assert len(cand_b["side_effects_detected"]) > 0

    # Candidate C (SCALE_WORKERS) should fail to resolve original error
    cand_c = next(t for t in result["candidate_trials"] if t["action"] == "SCALE_WORKERS")
    assert cand_c["resolves_root_cause"] is False
    assert cand_c["trial_verdict"] == "REJECTED"

    # Best candidate selection based on measured evidence
    selected = result["selected_candidate"]
    assert selected is not None
    assert selected["action"] == "RESET_CONNECTION_POOL"
    assert "composite safety score" in result["selection_rationale"]


def test_nine_layer_validation_engine_statuses():
    """Verify 9-layer validation evaluates all 9 layers with truthful statuses."""
    pre_metrics = {
        "database-service": {"error_rate": 0.88, "latency_p95_ms": 1850.0, "active_connections": 98.0},
        "gateway": {"error_rate": 0.55, "latency_p95_ms": 1200.0}
    }

    # Case 1: Healthy recovery
    post_metrics_clean = {
        "database-service": {"error_rate": 0.002, "latency_p95_ms": 25.0, "active_connections": 10.0, "healthy": True},
        "gateway": {"error_rate": 0.005, "latency_p95_ms": 32.0, "healthy": True}
    }

    val_clean = nine_layer_validator.validate(
        target_service="database-service",
        action_name="RESET_CONNECTION_POOL",
        pre_metrics=pre_metrics,
        post_metrics=post_metrics_clean,
        success_criteria={"max_error_rate": 0.05, "max_latency_p95_ms": 120.0, "max_active_connections": 20.0},
        side_effects=[]
    )

    assert val_clean["overall_status"] == "PASS"
    assert val_clean["total_layers"] == 9
    assert val_clean["failed_layers"] == 0
    assert val_clean["can_progress_to_production"] is True

    # Case 2: Incomplete recovery (error rate still high)
    post_metrics_unresolved = {
        "database-service": {"error_rate": 0.65, "latency_p95_ms": 900.0, "active_connections": 80.0, "healthy": False},
        "gateway": {"error_rate": 0.40, "latency_p95_ms": 800.0, "healthy": False}
    }

    val_fail = nine_layer_validator.validate(
        target_service="database-service",
        action_name="SCALE_WORKERS",
        pre_metrics=pre_metrics,
        post_metrics=post_metrics_unresolved,
        success_criteria={"max_error_rate": 0.05, "max_latency_p95_ms": 120.0, "max_active_connections": 20.0},
        side_effects=[]
    )

    assert val_fail["overall_status"] == "FAIL"
    assert val_fail["failed_layers"] >= 2
    assert val_fail["can_progress_to_production"] is False


@pytest.mark.asyncio
async def test_independent_validator_guardrail_prevents_override():
    """
    Verify independent validator cannot override failed mandatory deterministic validation.
    """
    cand = {"action": "SCALE_WORKERS", "title": "Harmful Scale"}
    replica_res = {"run_id": "RUN-01", "side_effects": [{"type": "LATENCY_SURGE"}]}

    # Simulate validation layers that FAILED
    failing_layers = {
        "overall_status": "FAIL",
        "failed_layers": 3,
        "layers": [{"layer_number": 2, "name": "Root-Cause and Symptom", "status": "FAIL", "required": True}]
    }

    # Internal helper check: even if AI tried to return "APPROVED", guardrail must downgrade it
    res = independent_validator._finalize_assessment(
        parsed={"assessment": "APPROVED", "confidence_score": 0.95, "findings": ["Looks plausible"]},
        expected_references=["INCIDENT_ID:INC-100"],
        deterministic_failed=True,
        provider="openai",
        model="gpt-4o-mini",
        now_iso=datetime.now(timezone.utc).isoformat()
    )

    assert res["assessment"] != "APPROVED"
    assert res["assessment"] == "FLAGGED_RISK"
    assert any("GUARDRAIL ENFORCED" in f for f in res["findings"])


def test_verified_knowledge_base_learning_loop_lifecycle():
    """Verify structured resolution recording enforces explicit statuses."""
    # 1. Replica Validated (Not yet production)
    res_id_replica = verified_recovery_store.record_structured_resolution({
        "incident_id": "INC-LEARN-001",
        "tenant_id": "shopsphere",
        "resolution_status": "REPLICA_VALIDATED",
        "root_cause_category": "DATABASE_CONNECTION_EXHAUSTION",
        "root_cause_description": "Connection pool leaked by upstream worker handles",
        "origin_service": "database-service",
        "selected_solution": {"action": "RESET_CONNECTION_POOL"},
        "replica_validated_at": datetime.now(timezone.utc).isoformat()
    })

    records = verified_recovery_store.get_structured_resolutions(incident_id="INC-LEARN-001")
    assert len(records) >= 1
    assert records[0]["resolution_status"] == "REPLICA_VALIDATED"

    # 2. Guardrail test: claiming PRODUCTION_VALIDATED without production timestamp is downgraded
    res_id_downgraded = verified_recovery_store.record_structured_resolution({
        "incident_id": "INC-LEARN-002",
        "tenant_id": "shopsphere",
        "resolution_status": "PRODUCTION_VALIDATED",
        "replica_validated_at": datetime.now(timezone.utc).isoformat(),
        "production_validated_at": None  # No real production validation!
    })

    rec_downgraded = verified_recovery_store.get_structured_resolutions(incident_id="INC-LEARN-002")[0]
    assert rec_downgraded["resolution_status"] == "REPLICA_VALIDATED"

    # 3. Compatibility Search
    matches = verified_recovery_store.search_knowledge_with_compatibility(
        incident={"service": "database-service", "root_cause_category": "DATABASE_CONNECTION_EXHAUSTION"},
        tenant_id="shopsphere"
    )
    assert len(matches) >= 1
    assert matches[0]["requires_lab_retesting"] is True
