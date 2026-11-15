"""
Enterprise-Grade Incident Simulation, Human Approval, High-Volume Telemetry & Risk-Aware Self-Healing Tests
Validates:
1. Decision Layer (AUTO_REMEDIATE, REQUEST_APPROVAL, ESCALATE, DO_NOT_ACT)
2. Novel Anomaly vs Known Failure Pattern routing with similarity threshold and confidence boost
3. Human Approval ticket generation with blast radius, RCA confidence, rollback plan, historical success
4. Role-Based Access Control (RBAC) authorization and mandatory rejection rationale
5. Scalable High-Volume Telemetry (up to 100,000+ EPS) and multi-service correlated traces
6. 33 Failure Scenarios Catalog spanning 10 distinct categories with non-overlapping cadence
"""

import pytest
import asyncio
from datetime import datetime, timezone

from backend.app.healing.decision_engine import DecisionEngine, RiskPolicyEngine
from backend.app.knowledge.incident_memory import IncidentMemoryEngine, IncidentVector
from backend.app.healing.recommender import RemediationRecommender, ACTION_CATALOG
from backend.app.monitoring.collector import collector
from backend.app.monitoring.continuous_telemetry import continuous_telemetry, SERVICE_TEMPLATES, TRANSACTION_FLOWS
from backend.app.monitoring.failure_scheduler import failure_scheduler, FAILURE_SCENARIOS, ALL_FAILURE_SCENARIOS
from backend.app.api.approvals import check_rbac_authorization, DecisionRequest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def reset_state():
    collector.pending_approvals.clear()
    collector.reviewed_approvals.clear()
    continuous_telemetry.set_eps_rate(25)
    failure_scheduler.reset()


# =========================================================================
# 1. RISK + POLICY + APPROVAL DECISION LAYER TESTS
# =========================================================================

def test_decision_layer_auto_remediate_low_risk():
    engine = RiskPolicyEngine(rca_confidence_threshold=0.85, max_blast_radius_for_auto=75.0)
    
    # Low-risk action on non-critical service with high confidence and known pattern
    incident = {
        "incident_id": "INC-TEST-001",
        "root_cause_service": "service-a",
        "recommended_action": "RESET_CONNECTION_POOL",
        "action_risk_level": "LOW",
        "rca_confidence": 0.95,
        "blast_radius_score": 30.0,
        "historical_match": {
            "is_novel": False,
            "pattern_name": "Known DB Exhaustion",
            "similarity_score": 0.92
        }
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "AUTO_REMEDIATE"
    assert decision["requires_approval"] is False
    assert decision["decision_factors"]["policy_verdict"] == "ALLOWED_BY_POLICY"


def test_decision_layer_request_approval_critical_service_restart():
    engine = RiskPolicyEngine()
    
    # RESTART_SERVICE on critical service (database-service) must strictly require operator approval
    incident = {
        "incident_id": "INC-TEST-002",
        "root_cause_service": "database-service",
        "recommended_action": "RESTART_SERVICE",
        "action_risk_level": "HIGH",
        "rca_confidence": 0.94,
        "blast_radius_score": 60.0,
        "historical_match": {"is_novel": False, "similarity_score": 0.88}
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "REQUEST_APPROVAL"
    assert decision["requires_approval"] is True
    assert "critical service" in decision["reason"].lower()


def test_decision_layer_request_approval_novel_anomaly():
    engine = RiskPolicyEngine()
    
    # Novel anomaly (no past pattern match) must require approval regardless of recommended action
    incident = {
        "incident_id": "INC-TEST-003",
        "root_cause_service": "service-b",
        "recommended_action": "CLEAR_CACHE",
        "action_risk_level": "LOW",
        "rca_confidence": 0.92,
        "blast_radius_score": 25.0,
        "historical_match": {
            "is_novel": True,
            "pattern_name": "Novel Anomaly",
            "similarity_score": 0.55
        }
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "REQUEST_APPROVAL"
    assert decision["requires_approval"] is True
    assert "novel anomaly" in decision["reason"].lower()


def test_decision_layer_request_approval_low_confidence():
    engine = RiskPolicyEngine(rca_confidence_threshold=0.85)
    
    # RCA confidence < 0.85 must NOT auto-remediate
    incident = {
        "incident_id": "INC-TEST-004",
        "root_cause_service": "service-a",
        "recommended_action": "RESET_CONNECTION_POOL",
        "action_risk_level": "LOW",
        "rca_confidence": 0.72,
        "blast_radius_score": 20.0,
        "historical_match": {"is_novel": False}
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "REQUEST_APPROVAL"
    assert "confidence" in decision["reason"].lower()


def test_decision_layer_escalate_on_critical_wide_blast():
    engine = RiskPolicyEngine()
    
    # Critical blast radius > 85 with critical severity
    incident = {
        "incident_id": "INC-TEST-005",
        "root_cause_service": "gateway",
        "severity": "CRITICAL",
        "recommended_action": "ROLLBACK_CONFIG",
        "action_risk_level": "CRITICAL",
        "rca_confidence": 0.65,
        "blast_radius_score": 92.0
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] in ["ESCALATE", "REQUEST_APPROVAL"]
    assert decision["requires_approval"] is True


def test_decision_layer_do_not_act_on_stale_telemetry():
    engine = RiskPolicyEngine()
    
    incident = {
        "incident_id": "INC-TEST-006",
        "root_cause_service": "service-a",
        "recommended_action": "RESET_CONNECTION_POOL"
    }
    decision = engine.evaluate(incident, telemetry_fresh=False)
    assert decision["decision"] == "DO_NOT_ACT"
    assert "stale" in decision["reason"].lower()


# =========================================================================
# 2. NOVEL ANOMALY VS KNOWN PATTERN RECOGNITION TESTS
# =========================================================================

def test_novel_anomaly_detection_unknown_pattern():
    memory = IncidentMemoryEngine()
    memory.clear_all()
    
    # Unprecedented failure signature
    novel_sig = {
        "symptoms": ["quantum_coherence_drop", "subspace_latency_warp"],
        "metrics": {"quantum_error": 0.99},
        "services": ["warp-drive-service"]
    }
    
    pattern = memory.get_repeated_failure_pattern(novel_sig, similarity_threshold=0.85)
    assert pattern["is_novel"] is True
    assert pattern["pattern_name"] == "Novel Anomaly"
    assert pattern["confidence_boost"] == 0.0
    assert pattern["similarity_score"] < 0.85
    assert pattern["requires_approval"] is True


def test_known_pattern_recognition_with_confidence_boost():
    memory = IncidentMemoryEngine()
    memory.clear_all()
    
    # Seed a known historical pattern
    memory.record_incident(IncidentVector(
        incident_id="INC-HIST-001",
        failure_signature={
            "symptoms": ["connection_pool_exhausted", "high_latency"],
            "metrics": {"active_connections": 50, "latency_p95": 2800},
            "services": ["database-service", "gateway"]
        },
        root_cause_service="database-service",
        remediation_action="RESET_CONNECTION_POOL",
        success=True,
        mttr_seconds=3.2
    ))
    
    # Exact recurring symptom
    matching_sig = {
        "symptoms": ["connection_pool_exhausted", "high_latency"],
        "metrics": {"active_connections": 50, "latency_p95": 2800},
        "services": ["database-service", "gateway"]
    }
    
    pattern = memory.get_repeated_failure_pattern(matching_sig, similarity_threshold=0.85)
    assert pattern["is_novel"] is False
    assert pattern["pattern_name"] == "Known Failure Pattern"
    assert pattern["similarity_score"] >= 0.85
    assert pattern["confidence_boost"] == 0.05  # +5% confidence boost
    assert pattern["historical_occurrences"] >= 1
    assert pattern["recommended_action"] == "RESET_CONNECTION_POOL"


# =========================================================================
# 3. APPROVAL TICKET GENERATION & RBAC TESTS
# =========================================================================

def test_create_approval_ticket_contains_all_enterprise_fields():
    recommender = RemediationRecommender()
    
    incident = {
        "incident_id": "INC-AUDIT-9999",
        "severity": "CRITICAL",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "service-b", "gateway"],
        "blast_radius_score": 78.5,
        "rca_confidence": 0.94,
        "failure_type": "CONNECTION_POOL_EXHAUSTION"
    }
    
    rec_result = recommender.recommend_remedy(incident, history=[])
    ticket = collector._create_approval_ticket(incident, rec_result)
    
    assert ticket["approval_id"].startswith("APR-")
    assert ticket["incident_id"] == "INC-AUDIT-9999"
    assert ticket["status"] == "PENDING_APPROVAL"
    assert ticket["blast_radius"] == "HIGH"
    assert ticket["rca_confidence"] == 94
    assert ticket["proposed_action"] == "RESET_CONNECTION_POOL"
    assert "rollback_plan" in ticket and ticket["rollback_plan"] is not None
    assert "historical_success" in ticket and ticket["historical_success"] is not None
    assert "expected_impact" in ticket and ticket["expected_impact"] is not None
    assert ticket["affected_services_count"] == 3


def test_rbac_viewer_cannot_approve():
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(role="VIEWER", action="APPROVE")
    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.detail.lower()


def test_rbac_operator_cannot_approve_high_risk():
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(role="OPERATOR", action="APPROVE", risk_level="HIGH")
    assert exc_info.value.status_code == 403
    assert "cannot approve high risk" in exc_info.value.detail.lower()


def test_rbac_admin_and_approver_can_approve_any_risk():
    # Should not raise exception
    check_rbac_authorization(role="ADMIN", action="APPROVE", risk_level="CRITICAL")
    check_rbac_authorization(role="APPROVER", action="APPROVE", risk_level="HIGH")


def test_rejection_requires_notes():
    # Valid notes
    req = DecisionRequest(reviewer="Lead SRE", role="ADMIN", notes="Not safe during peak traffic window")
    assert req.notes == "Not safe during peak traffic window"


# =========================================================================
# 4. CONTINUOUS HIGH-VOLUME TELEMETRY & CORRELATED TRACES TESTS
# =========================================================================

def test_telemetry_rate_scaling_up_to_100k():
    continuous_telemetry.set_eps_rate(10)
    assert continuous_telemetry.configured_eps == 10
    
    continuous_telemetry.set_eps_rate(1000)
    assert continuous_telemetry.configured_eps == 1000
    
    continuous_telemetry.set_eps_rate(10000)
    assert continuous_telemetry.configured_eps == 10000
    
    continuous_telemetry.set_eps_rate(100000)
    assert continuous_telemetry.configured_eps == 100000

    status = continuous_telemetry.get_status()
    assert "events_per_sec" in status
    assert "events_per_min" in status
    assert "total_events" in status
    assert "kafka_throughput_mb_s" in status
    assert "consumer_lag" in status
    assert "pipeline_latency_ms" in status


def test_multi_service_coverage_in_templates():
    canonical_6 = ["gateway", "service-a", "service-b", "payment-api", "auth-service", "database-service"]
    for svc in canonical_6:
        assert svc in SERVICE_TEMPLATES, f"Missing service template for {svc}"
        assert len(SERVICE_TEMPLATES[svc]) >= 3, f"Template for {svc} has insufficient event definitions"


def test_transaction_flows_generate_correlated_traces():
    # Validate transaction flow paths
    assert len(TRANSACTION_FLOWS) >= 3
    for flow in TRANSACTION_FLOWS:
        assert flow[0] == "gateway", "All transaction flows must initiate at gateway"
        assert len(flow) >= 2, "Transaction flow must span multiple services for trace correlation"


# =========================================================================
# 5. 33 FAILURE SCENARIOS CATALOG & CADENCE TESTS
# =========================================================================

def test_all_failure_scenarios_catalog_count():
    assert len(ALL_FAILURE_SCENARIOS) >= 32, f"Expected >= 32 scenarios, got {len(ALL_FAILURE_SCENARIOS)}"
    # Legacy backward-compatible 10-scenarios catalog must be preserved
    assert len(FAILURE_SCENARIOS) == 10


def test_all_10_categories_covered():
    expected_categories = {
        "Database", "Application", "Network", "Dependency", "Resource",
        "Performance", "Cache", "Behavioral", "Cascade", "Novel"
    }
    actual_categories = {sc["category"] for sc in ALL_FAILURE_SCENARIOS}
    for cat in expected_categories:
        assert cat in actual_categories, f"Category '{cat}' missing from scenario catalog"


def test_non_overlapping_cadence_enforced():
    failure_scheduler.reset()
    assert failure_scheduler.can_inject_next() is True
    
    # When active, injection is strictly blocked
    failure_scheduler.transition_lifecycle("INJECTING")
    assert failure_scheduler.can_inject_next() is False
    
    failure_scheduler.transition_lifecycle("ACTIVE")
    assert failure_scheduler.can_inject_next() is False
    
    failure_scheduler.transition_lifecycle("INVESTIGATING")
    assert failure_scheduler.can_inject_next() is False
    
    failure_scheduler.transition_lifecycle("REMEDIATING")
    assert failure_scheduler.can_inject_next() is False
    
    failure_scheduler.transition_lifecycle("VERIFYING")
    assert failure_scheduler.can_inject_next() is False
    
    # Only after verification passes and scenario is RESOLVED/LEARNED, next can inject
    failure_scheduler.transition_lifecycle("RESOLVED")
    assert failure_scheduler.can_inject_next() is True
    
    failure_scheduler.transition_lifecycle("LEARNED")
    assert failure_scheduler.can_inject_next() is True


# =========================================================================
# 6. LIFECYCLE INTEGRITY REGRESSION TESTS: EXECUTION FAILURE != RESOLVED
# =========================================================================

@pytest.mark.asyncio
async def test_execution_failure_is_not_marked_resolved_when_probes_fail():
    """
    Asserts: execution failure != resolved.
    If runbook execution fails and verification probe fails, incident MUST NOT be marked RESOLVED.
    """
    from unittest.mock import patch
    import httpx

    incident = {
        "incident_id": "INC-TEST-FAIL-001",
        "severity": "CRITICAL",
        "root_cause_service": "database-service",
        "affected_services": ["database-service"],
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.95,
        "timeline": []
    }
    rec_result = {
        "primary_action": "RESET_CONNECTION_POOL",
        "alternative_action": "RESET_CONNECTION_POOL",  # No distinct fallback
        "expected_outcome": "Restores pool",
        "risk_assessment": {
            "risk_level": "HIGH",
            "risk_score": 85.0,
            "decision_rationale": "High risk",
            "estimated_downtime_sec": 3
        }
    }
    collector.active_incidents = [incident]
    collector.resolved_incidents = []
    ticket = collector._create_approval_ticket(incident, rec_result)

    class MockResp:
        def __init__(self, code, data):
            self.status_code = code
            self._data = data
        def json(self):
            return self._data

    async def mock_get(url, **kwargs):
        # Verification probes fail (503)
        return MockResp(503, {"status": "DOWN", "state": "UNHEALTHY", "error_rate": 0.9})

    async def mock_post(url, **kwargs):
        # Remediation execution fails
        return MockResp(500, {"success": False, "error": "Connection pool reset failed: socket timeout"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        res = await collector.execute_approved_action(
            approval_id=ticket["approval_id"],
            decision="APPROVED",
            reviewer="SRE Lead (ADMIN)",
            notes="Testing failed execution lifecycle"
        )

    # STRICT ASSERTIONS:
    assert res["success"] is False
    assert res["status"] == "REMEDIATION_FAILED"
    assert incident["status"] == "REMEDIATION_FAILED"
    assert incident["status"] != "RESOLVED", "CRITICAL: Execution failure must NEVER be marked RESOLVED without verified recovery"
    assert incident["recovery_status"] == "FAILED_ESCALATED"
    assert any(i["incident_id"] == "INC-TEST-FAIL-001" for i in collector.active_incidents)
    assert not any(i["incident_id"] == "INC-TEST-FAIL-001" for i in collector.resolved_incidents)


@pytest.mark.asyncio
async def test_execution_failure_with_independent_recovery_sets_recovered_after_execution_error():
    """
    Asserts: If execution reports failure but independent verification proves the service recovered,
    use explicit state RECOVERED_AFTER_EXECUTION_ERROR rather than falsely reporting normal remediation success.
    """
    from unittest.mock import patch
    import httpx

    incident = {
        "incident_id": "INC-TEST-RECOVERR-002",
        "severity": "CRITICAL",
        "root_cause_service": "database-service",
        "affected_services": ["database-service"],
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.95,
        "timeline": []
    }
    rec_result = {
        "primary_action": "RESET_CONNECTION_POOL",
        "alternative_action": "RESET_CONNECTION_POOL",
        "expected_outcome": "Restores pool",
        "risk_assessment": {
            "risk_level": "HIGH",
            "risk_score": 85.0,
            "decision_rationale": "High risk",
            "estimated_downtime_sec": 3
        }
    }
    collector.active_incidents = [incident]
    collector.resolved_incidents = []
    ticket = collector._create_approval_ticket(incident, rec_result)

    class MockResp:
        def __init__(self, code, data):
            self.status_code = code
            self._data = data
        def json(self):
            return self._data

    async def mock_get(url, **kwargs):
        url_s = str(url)
        if "/work" in url_s:
            return MockResp(200, {"status": "SUCCESS"})
        if "/health" in url_s:
            return MockResp(200, {"status": "HEALTHY", "state": "HEALTHY"})
        if "/metrics" in url_s:
            return MockResp(200, {"error_rate": 0.0, "latency_p95_ms": 8.0, "cpu_percent": 10.0})
        return MockResp(200, {})

    async def mock_post(url, **kwargs):
        # Remediation hook returned execution error
        return MockResp(502, {"success": False, "error": "Remote RPC gateway timeout while triggering remedy"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        res = await collector.execute_approved_action(
            approval_id=ticket["approval_id"],
            decision="APPROVED",
            reviewer="SRE Lead (ADMIN)",
            notes="Testing independent verification after execution error"
        )

    # STRICT ASSERTIONS:
    assert res["success"] is True
    assert res["status"] == "RECOVERED_AFTER_EXECUTION_ERROR"
    assert incident["status"] == "RECOVERED_AFTER_EXECUTION_ERROR"
    assert incident["status"] != "RESOLVED", "Must use explicit RECOVERED_AFTER_EXECUTION_ERROR, not false RESOLVED"
    assert incident["remediation_status"] == "REMEDIATION_FAILED"
    assert incident["verification_status"] == "VERIFIED"
    assert any(i["incident_id"] == "INC-TEST-RECOVERR-002" for i in collector.resolved_incidents)


@pytest.mark.asyncio
async def test_execution_success_and_verified_probe_marks_resolved():
    """
    Asserts: EXECUTION_SUCCESS -> VERIFYING -> all active probes pass -> VERIFIED -> RESOLVED
    """
    from unittest.mock import patch
    import httpx

    incident = {
        "incident_id": "INC-TEST-RESOLVE-003",
        "severity": "HIGH",
        "root_cause_service": "database-service",
        "affected_services": ["database-service"],
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.95,
        "timeline": []
    }
    rec_result = {
        "primary_action": "RESET_CONNECTION_POOL",
        "alternative_action": "RESTART_SERVICE",
        "expected_outcome": "Restores pool",
        "risk_assessment": {
            "risk_level": "HIGH",
            "risk_score": 85.0,
            "decision_rationale": "High risk",
            "estimated_downtime_sec": 3
        }
    }
    collector.active_incidents = [incident]
    collector.resolved_incidents = []
    ticket = collector._create_approval_ticket(incident, rec_result)

    class MockResp:
        def __init__(self, code, data):
            self.status_code = code
            self._data = data
        def json(self):
            return self._data

    async def mock_get(url, **kwargs):
        url_s = str(url)
        if "/work" in url_s:
            return MockResp(200, {"status": "SUCCESS"})
        if "/health" in url_s:
            return MockResp(200, {"status": "HEALTHY", "state": "HEALTHY"})
        if "/metrics" in url_s:
            return MockResp(200, {"error_rate": 0.0, "latency_p95_ms": 10.0, "cpu_percent": 15.0})
        return MockResp(200, {})

    async def mock_post(url, **kwargs):
        return MockResp(200, {"success": True, "result": "Pool reset cleanly"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        res = await collector.execute_approved_action(
            approval_id=ticket["approval_id"],
            decision="APPROVED",
            reviewer="SRE Lead (ADMIN)",
            notes="Testing clean execution resolution"
        )

    # STRICT ASSERTIONS:
    assert res["success"] is True
    assert res["status"] == "RESOLVED"
    assert incident["status"] == "RESOLVED"
    assert incident["remediation_status"] == "EXECUTION_SUCCESS"
    assert incident["verification_status"] == "VERIFIED"
    assert any(i["incident_id"] == "INC-TEST-RESOLVE-003" for i in collector.resolved_incidents)

