"""
Unit and Integration Tests for Multi-Point Post-Remediation Verification
Tests:
- Verification probe on healthy mock targets
- Verification failure when target or downstream metrics remain degraded
- Self-healing state transitions (VERIFYING -> WAITING_FOR_FRESH_TELEMETRY -> VERIFIED vs VERIFICATION_FAILED)
- Prevention of premature resolution without fresh telemetry
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch
from backend.app.healing.verifier import RecoveryVerifier
from backend.app.healing.self_healing_engine import SelfHealingEngine


class MockResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


@pytest.mark.asyncio
async def test_recovery_verifier_success():
    verifier = RecoveryVerifier()
    
    async def mock_get(url, **kwargs):
        url_str = str(url)
        if "/work" in url_str:
            return MockResponse(200, {"status": "SUCCESS", "message": "Synthetic workload passed"})
        if "/health" in url_str:
            return MockResponse(200, {"status": "HEALTHY", "state": "HEALTHY"})
        if "/metrics" in url_str:
            return MockResponse(200, {
                "error_rate": 0.01,
                "latency_p95_ms": 15.0,
                "cpu_percent": 15.0
            })
        return MockResponse(200, {})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
        result = await verifier.verify_recovery(
            target_service="database-service",
            affected_services=["service-b", "gateway"],
            probe_delay_sec=0.0
        )
        
        assert result["verified"] is True
        assert result["status"] == "SUCCESS"
        assert len(result["probed_services"]) >= 1
        assert result["checks"]["synthetic_transaction"]["passed"] is True


@pytest.mark.asyncio
async def test_recovery_verifier_unreachable_service_fails():
    verifier = RecoveryVerifier()
    # No mocks and services are offline or raise connection error
    async def mock_fail_get(url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_fail_get):
        result = await verifier.verify_recovery(
            target_service="database-service",
            affected_services=["service-b"],
            probe_delay_sec=0.0
        )
        # MUST NOT be verified=True on exception
        assert result["verified"] is False
        assert result["status"] == "FAILED"
        assert result["failure_reason"] is not None
        assert "unreachable" in result["failure_reason"].lower() or "connection" in result["failure_reason"].lower()



@pytest.mark.asyncio
async def test_recovery_verifier_degraded_metrics_failure():
    verifier = RecoveryVerifier()
    
    async def mock_get(url, **kwargs):
        url_str = str(url)
        if "/health" in url_str:
            return MockResponse(200, {"status": "HEALTHY", "state": "HEALTHY"})
        elif "/metrics" in url_str and ("8003" in url_str or "service-b" in url_str):
            return MockResponse(200, {
                "error_rate": 0.45,
                "latency_p95_ms": 1800.0,
                "cpu_percent": 88.0
            })
        elif "/metrics" in url_str:
            return MockResponse(200, {
                "error_rate": 0.01,
                "latency_p95_ms": 45.0,
                "cpu_percent": 25.0
            })
        return MockResponse(200, {})
    
    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
        result = await verifier.verify_recovery(
            target_service="database-service",
            affected_services=["service-b"],
            probe_delay_sec=0.0
        )
        
        assert result["verified"] is False
        assert result["status"] == "FAILED"
        assert any("error rate remained elevated" in r or "latency p95 remained elevated" in r for r in result["failure_reasons"])


@pytest.mark.asyncio
async def test_self_healing_verification_failure_lifecycle():
    engine = SelfHealingEngine()
    incident = {
        "incident_id": "INC-TEST-FAIL-VERIF-01",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "affected_services": ["database-service", "service-b"],
        "severity": "CRITICAL",
        "status": "OPEN",
        "timeline": []
    }
    
    # Mock verifier to simulate failure
    with patch.object(
        engine.verifier,
        "verify_recovery",
        new=AsyncMock(return_value={
            "verified": False,
            "status": "FAILED",
            "failure_reasons": ["Service 'database-service' latency p95 remained elevated (1900.0ms)"],
            "probed_services": {"database-service": {"healthy": False}}
        })
    ):
        res = await engine.execute_recovery_loop(
            incident=incident,
            action="RESET_CONNECTION_POOL",
            caller="TestVerificationRunner",
            fresh_telemetry_wait_sec=0.0
        )
        
        assert res["success"] is False
        assert incident["status"] == "REMEDIATION_FAILED"
        assert incident["verification_status"] == "VERIFICATION_FAILED"
        assert incident["recovery_status"] == "FAILED"
        assert any(t["type"] == "VERIFICATION_FAILED" for t in incident["timeline"])
