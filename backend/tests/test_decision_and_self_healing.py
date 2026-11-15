"""
Unit and Integration Tests for DecisionEngine and SelfHealingEngine
Tests:
- Telemetry freshness policy enforcement
- Action allowlist enforcement
- Cooldown timer protection against restart storms
- Risk-based decision matrix (AUTO_REMEDIATE, REQUEST_APPROVAL, ESCALATE, DO_NOT_ACT)
- Action lock acquisition and double-remediation prevention
- Full closed-loop execution and incident memory persistence
"""

import pytest
import time
from backend.app.healing.decision_engine import DecisionEngine, ACTION_ALLOWLIST
from backend.app.healing.self_healing_engine import SelfHealingEngine
from backend.app.knowledge.incident_memory import incident_memory


def test_decision_engine_stale_telemetry():
    engine = DecisionEngine(cooldown_seconds=10)
    incident = {
        "incident_id": "INC-TEST-01",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "rca_confidence": 0.95,
        "recommended_action": "RESET_CONNECTION_POOL"
    }
    decision = engine.evaluate(incident, telemetry_fresh=False)
    assert decision["decision"] == "DO_NOT_ACT"
    assert "stale or unavailable" in decision["reason"]


def test_decision_engine_unallowlisted_action():
    engine = DecisionEngine(cooldown_seconds=10)
    incident = {
        "incident_id": "INC-TEST-02",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "rca_confidence": 0.95,
        "recommended_action": "DROP_DATABASE_TABLES"  # Forbidden/unallowlisted action
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "ESCALATE"
    assert "not in the verified allowlist" in decision["reason"]


def test_decision_engine_cooldown_protection():
    engine = DecisionEngine(cooldown_seconds=15)
    service = "database-service"
    incident = {
        "incident_id": "INC-TEST-03",
        "primary_service": service,
        "root_cause_service": service,
        "rca_confidence": 0.92,
        "recommended_action": "RESET_CONNECTION_POOL"
    }
    
    # Record action executed just now
    engine.record_action_executed(service)
    
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "DO_NOT_ACT"
    assert "remediation cooldown" in decision["reason"]


def test_decision_engine_auto_remediate_low_risk():
    engine = DecisionEngine(cooldown_seconds=10)
    incident = {
        "incident_id": "INC-TEST-04",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "rca_confidence": 0.88,
        "recommended_action": "RESET_CONNECTION_POOL"
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "AUTO_REMEDIATE"
    assert decision["risk_level"] == "LOW"
    assert decision["requires_human_approval"] is False


def test_decision_engine_request_approval_high_risk():
    engine = DecisionEngine(cooldown_seconds=10)
    incident = {
        "incident_id": "INC-TEST-05",
        "primary_service": "service-a",
        "root_cause_service": "service-a",
        "rca_confidence": 0.85,
        "recommended_action": "RESTART_CONTAINER"
    }
    decision = engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] == "REQUEST_APPROVAL"
    assert decision["risk_level"] == "HIGH"
    assert decision["requires_human_approval"] is True


@pytest.mark.asyncio
async def test_self_healing_action_locks():
    engine = SelfHealingEngine()
    svc = "test-service-lock"
    
    # First lock acquire should succeed
    locked_first = engine.acquire_lock(svc, "RESTART_SERVICE")
    assert locked_first is True
    
    # Second concurrent acquire should fail
    locked_second = engine.acquire_lock(svc, "RESTART_SERVICE")
    assert locked_second is False
    
    # Release and re-acquire should succeed
    engine.release_lock(svc)
    locked_third = engine.acquire_lock(svc, "RESTART_SERVICE")
    assert locked_third is True
    engine.release_lock(svc)


@pytest.mark.asyncio
async def test_self_healing_full_recovery_loop():
    engine = SelfHealingEngine()
    incident = {
        "incident_id": "INC-TEST-LOOP-99",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause": "connection_pool_exhaustion",
        "affected_services": ["database-service", "service-b", "gateway"],
        "severity": "HIGH",
        "status": "OPEN",
        "timeline": []
    }
    
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
        res = await engine.execute_recovery_loop(
            incident=incident,
            action="RESET_CONNECTION_POOL",
            caller="TestRunner",
            fresh_telemetry_wait_sec=0.1
        )
    
    assert res["success"] is True
    assert incident["status"] == "RESOLVED"
    assert incident["verification_status"] == "VERIFIED"
    assert len(incident["timeline"]) >= 3
    
    # Check that incident was indexed in incident memory
    similar = incident_memory.find_similar_incidents(
        service="database-service",
        category="CONNECTION_POOL_EXHAUSTION"
    )
    assert len(similar) > 0
    assert similar[0]["action_taken"] == "RESET_CONNECTION_POOL"

    proven = incident_memory.get_proven_remedies(
        service="database-service",
        category="CONNECTION_POOL_EXHAUSTION"
    )
    assert len(proven) > 0
    assert proven[0]["action"] == "RESET_CONNECTION_POOL"
    assert proven[0]["success_rate_pct"] == 100.0
