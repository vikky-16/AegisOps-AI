"""
Tests for Complete Automated Incident Response Platform Lifecycle & Authorization:
Failure Detection -> Incident Creation -> RCA -> RBAC Approval -> Remediation -> Verification -> Resolution
"""

import pytest
from datetime import datetime, timezone
from backend.app.incidents.incident_manager import IncidentManager
from backend.app.rca.engine import rca_engine
from backend.app.monitoring.collector import collector
from backend.app.monitoring.failure_scheduler import failure_scheduler, FAILURE_SCENARIOS
from backend.app.api.approvals import check_rbac_authorization, reject_ticket, DecisionRequest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def clean_collector_state():
    collector.active_incidents.clear()
    collector.resolved_incidents.clear()
    collector.pending_approvals.clear()
    collector.reviewed_approvals.clear()
    collector.audit_logs.clear()


def test_failure_scheduler_scenarios_and_config():
    """Verify all 10 controlled failure scenarios are available with valid configurations."""
    assert len(FAILURE_SCENARIOS) == 10
    scenario_ids = [s["id"] for s in FAILURE_SCENARIOS]
    assert "DATABASE_CONNECTION_FAILURE" in scenario_ids
    assert "PAYMENT_API_FAILURE" in scenario_ids
    assert "HTTP_500_SPIKE" in scenario_ids
    assert "HTTP_502_503_SPIKE" in scenario_ids
    assert "REQUEST_TIMEOUT" in scenario_ids
    assert "HIGH_LATENCY" in scenario_ids
    assert "SERVICE_UNAVAILABLE" in scenario_ids
    assert "DEPENDENCY_FAILURE" in scenario_ids
    assert "RESOURCE_EXHAUSTION" in scenario_ids
    assert "CONTAINER_PROCESS_CRASH" in scenario_ids

    # Test configuration updates
    failure_scheduler.set_config(enabled=True, interval_seconds=30, scenario_id="DATABASE_CONNECTION_FAILURE")
    status = failure_scheduler.get_status()
    assert status["interval_seconds"] == 30
    assert status["selected_scenario_id"] == "DATABASE_CONNECTION_FAILURE"
    assert status["is_enabled"] is True


def test_incident_creation_and_timeline():
    """Verify incident creation includes full lifecycle schema, event IDs, and timeline."""
    events = [
        {"event_id": "EVT-AZ-001", "service_name": "database-service", "event_type": "CONNECTION_POOL_EXHAUSTION", "timestamp": "2026-08-22T18:00:01Z"},
        {"event_id": "EVT-AZ-002", "service_name": "service-b", "event_type": "HTTP_504_TIMEOUT", "timestamp": "2026-08-22T18:00:03Z"}
    ]
    metrics = {
        "database-service": {"error_rate": 0.88, "request_count": 140, "latency_p95_ms": 3200.0, "active_connections": 50},
        "service-b": {"error_rate": 0.45, "request_count": 90, "latency_p95_ms": 1500.0}
    }

    inc = IncidentManager.create_incident_from_anomaly(
        service_name="database-service",
        anomaly_score=0.92,
        evidence=["Database connection pool saturated"],
        events=events,
        metrics_snapshot=metrics
    )

    assert inc["incident_id"].startswith("INC-")
    assert inc["severity"] == "CRITICAL"
    assert inc["root_cause_service"] == "database-service"
    assert inc["root_cause_confidence"] >= 0.80
    assert "EVT-AZ-001" in inc["event_ids"]
    assert len(inc["timeline"]) >= 3
    assert any(t["type"] == "ANOMALY_DETECTED" for t in inc["timeline"])
    assert any(t["type"] == "ROOT_CAUSE_IDENTIFIED" for t in inc["timeline"])


def test_explainable_rca_evidence():
    """Verify explainable RCA outputs concrete event IDs and causal explanations."""
    events = [
        {"event_id": "EVT-AZ-101", "service_name": "database-service", "event_type": "CONNECTION_POOL_TIMEOUT", "timestamp": "2026-08-22T18:10:00Z"},
        {"event_id": "EVT-AZ-102", "service_name": "service-b", "event_type": "CASCADE_ERROR", "timestamp": "2026-08-22T18:10:02Z"}
    ]
    metrics = {
        "database-service": {"error_rate": 0.75, "latency_p95_ms": 2500.0, "active_connections": 45}
    }

    rca = rca_engine.analyze_incident(
        affected_services=["database-service", "service-b"],
        events=events,
        current_metrics=metrics
    )

    assert rca["root_cause_service"] == "database-service"
    assert rca["confidence"] >= 0.85
    assert len(rca["evidence"]) > 0
    assert any("EVT-AZ-101" in ev for ev in rca["evidence"])


def test_rbac_authorization_rules():
    """Verify Role-Based Access Control on approvals."""
    # 1. VIEWER is strictly read-only (forbidden for all actions)
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(role="VIEWER", action="APPROVE", risk_level="HIGH")
    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(role="VIEWER", action="REJECT", risk_level="LOW")
    assert exc_info.value.status_code == 403

    # 2. OPERATOR cannot approve HIGH or CRITICAL risk
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(role="OPERATOR", action="APPROVE", risk_level="HIGH")
    assert exc_info.value.status_code == 403
    assert "OPERATOR" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(role="OPERATOR", action="APPROVE", risk_level="CRITICAL")
    assert exc_info.value.status_code == 403

    # 3. APPROVER and ADMIN have full permission
    check_rbac_authorization(role="APPROVER", action="APPROVE", risk_level="HIGH")
    check_rbac_authorization(role="ADMIN", action="APPROVE", risk_level="CRITICAL")


def test_request_incident_approval_flow():
    """Verify transitions to AWAITING_APPROVAL and creates approval ticket."""
    inc_data = {
        "incident_id": "INC-TEST-0042",
        "title": "Payment Service Failure",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "service-b"],
        "status": "INVESTIGATING",
        "action_risk_level": "HIGH",
        "timeline": []
    }
    collector.active_incidents = [inc_data]

    res = collector.request_incident_approval("INC-TEST-0042", requester="SRE Lead Investigator")
    assert res["success"] is True
    assert res["approval_id"].startswith("APR-") or res["approval_id"].startswith("APP-")
    assert inc_data["status"] == "AWAITING_APPROVAL"
    assert inc_data["approval_status"] == "AWAITING_APPROVAL"
    assert any(t["type"] == "APPROVAL_REQUESTED" for t in inc_data["timeline"])
    assert any(a["approval_id"] == res["approval_id"] for a in collector.pending_approvals)


@pytest.mark.asyncio
async def test_rejection_requires_reason_and_persists():
    """Verify rejection requires a reason and updates ticket + incident to REJECTED."""
    inc_data = {
        "incident_id": "INC-TEST-0043",
        "primary_service": "gateway",
        "root_cause_service": "gateway",
        "affected_services": ["gateway"],
        "status": "AWAITING_APPROVAL",
        "action_risk_level": "HIGH",
        "timeline": []
    }
    rec_result = {
        "primary_action": "restart_service",
        "alternative_action": "rollback_config",
        "expected_outcome": "Restores ingress gateway",
        "risk_assessment": {
            "risk_level": "HIGH",
            "risk_score": 80.0,
            "decision_rationale": "High traffic gateway restart",
            "estimated_downtime_sec": 3
        }
    }
    collector.active_incidents = [inc_data]
    ticket = collector._create_approval_ticket(inc_data, rec_result)
    approval_id = ticket["approval_id"]

    # 1. Empty reason raises 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        await reject_ticket(approval_id=approval_id, payload=DecisionRequest(reviewer="Admin", role="ADMIN", notes=""))
    assert exc_info.value.status_code == 400
    assert "Rejection reason is required" in exc_info.value.detail

    # 2. Valid reason executes rejection
    res = await reject_ticket(
        approval_id=approval_id,
        payload=DecisionRequest(reviewer="Lead SRE", role="ADMIN", notes="Peak business hours; reschedule to maintenance window")
    )
    assert res["status"] == "REJECTED"
    assert inc_data["status"] == "REJECTED"
    assert inc_data["approval_status"] == "REJECTED"
    assert any(a["approval_id"] == approval_id for a in collector.reviewed_approvals)


@pytest.mark.asyncio
async def test_prevent_double_approval_and_approval_of_resolved():
    """Verify already-approved ticket and already-resolved incident cannot be approved again."""
    inc_data = {
        "incident_id": "INC-TEST-0044",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "affected_services": ["database-service"],
        "status": "AWAITING_APPROVAL",
        "action_risk_level": "HIGH",
        "timeline": []
    }
    rec_result = {
        "primary_action": "reset_connection_pool",
        "alternative_action": "restart_service",
        "expected_outcome": "Resets connection pool",
        "risk_assessment": {
            "risk_level": "HIGH",
            "risk_score": 75.0,
            "decision_rationale": "Connection pool reset",
            "estimated_downtime_sec": 2
        }
    }
    collector.active_incidents = [inc_data]
    ticket = collector._create_approval_ticket(inc_data, rec_result)
    approval_id = ticket["approval_id"]

    # 1. First approval succeeds
    from unittest.mock import patch
    import httpx

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
        return MockResp(200, {"success": True, "result": "Remediation executed"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        res1 = await collector.execute_approved_action(
            approval_id=approval_id,
            decision="APPROVED",
            reviewer="SRE Lead (ADMIN)",
            notes="First approval"
        )
        assert res1["success"] is True

    # 2. Attempting second approval fails
    res2 = await collector.execute_approved_action(
        approval_id=approval_id,
        decision="APPROVED",
        reviewer="SRE Lead (ADMIN)",
        notes="Second approval attempt"
    )
    assert res2["success"] is False
    assert "already been approved" in res2["error"]

    # 3. Attempting approval on resolved incident fails
    collector.resolved_incidents = [inc_data]
    collector.active_incidents = []
    ticket_dummy = {"approval_id": "APR-DUMMY", "incident_id": "INC-TEST-0044", "service_name": "database-service", "proposed_action": "reset_connection_pool"}
    collector.pending_approvals = [ticket_dummy]
    res3 = await collector.execute_approved_action(approval_id="APR-DUMMY", decision="APPROVED")
    assert res3["success"] is False
    assert "already resolved" in res3["error"]


@pytest.mark.asyncio
async def test_end_to_end_approval_and_resolution_flow():
    """Verify full lifecycle: Ticket Created -> Approved -> Runbook Executing -> Verification -> Resolved with Audit."""
    inc_data = {
        "incident_id": "INC-TEST-0099",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "service-b"],
        "status": "AWAITING_APPROVAL",
        "action_risk_level": "HIGH",
        "timeline": []
    }
    rec_result = {
        "primary_action": "reset_connection_pool",
        "alternative_action": "restart_service",
        "expected_outcome": "Restores connection pool",
        "risk_assessment": {
            "risk_level": "HIGH",
            "risk_score": 85.0,
            "decision_rationale": "High-risk connection pool flush",
            "estimated_downtime_sec": 3
        }
    }

    # 1. Create approval ticket
    collector.active_incidents = [inc_data]
    ticket = collector._create_approval_ticket(inc_data, rec_result)
    approval_id = ticket["approval_id"]

    # 2. Execute approved action
    from unittest.mock import patch
    import httpx

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
        return MockResp(200, {"success": True, "result": "Remediation executed"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        exec_res = await collector.execute_approved_action(
            approval_id=approval_id,
            decision="APPROVED",
            reviewer="SRE Lead (ADMIN)",
            notes="Automated lifecycle verification test"
        )

    assert exec_res["success"] is True
    # Incident resolved and moved to resolved_incidents
    assert any(i["incident_id"] == "INC-TEST-0099" for i in collector.resolved_incidents)
    resolved_inc = next(i for i in collector.resolved_incidents if i["incident_id"] == "INC-TEST-0099")
    assert resolved_inc["status"] == "RESOLVED"
    assert resolved_inc["recovery_status"] == "SUCCESS"
    assert any(t["type"] == "APPROVAL_GRANTED" for t in resolved_inc["timeline"])
    assert any(t["type"] == "RESOLVED" for t in resolved_inc["timeline"])

    # Audit log check
    assert any(a["target_resource"] == approval_id and "APPROVAL_APPROVED" in a["action"] for a in collector.audit_logs)
