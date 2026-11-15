"""
Tests for Verified Self-Healing Engine, Persistence, and False-Positive Elimination
"""

import pytest
import httpx
from unittest.mock import patch, AsyncMock
from backend.app.healing.verifier import RecoveryVerifier
from backend.app.healing.persistence import (
    save_recovery_execution,
    get_recovery_executions,
    sync_history_from_db
)
from backend.app.api.recovery import trigger_manual_recovery, ManualRecoveryRequest, get_recovery_history
from backend.app.monitoring.collector import collector
from backend.app.core.database import init_db


class MockResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
async def ensure_db_ready():
    await init_db()


@pytest.mark.asyncio
async def test_persistence_save_and_retrieve():
    entry = {
        "execution_id": "REC-TEST-PERSIST-001",
        "incident_id": "INC-TEST-001",
        "service_name": "database-service",
        "action": "RESET_CONNECTION_POOL",
        "status": "SUCCESS",
        "success": True,
        "duration_ms": 150.0,
        "verification_status": "VERIFIED",
        "verification_result": {"verified": True, "checks": {"health": {"database-service": {"healthy": True}}}},
        "result": "Connection pool reset",
        "error": None,
        "execution_mode": "CONTROLLED_DEMO"
    }

    saved = await save_recovery_execution(entry)
    assert saved["execution_id"] == "REC-TEST-PERSIST-001"
    assert saved["verification_status"] == "VERIFIED"
    assert saved["success"] is True

    records = await get_recovery_executions(limit=100)
    matched = next((r for r in records if r["execution_id"] == "REC-TEST-PERSIST-001"), None)
    assert matched is not None
    assert matched["service_name"] == "database-service"
    assert matched["action"] == "RESET_CONNECTION_POOL"


@pytest.mark.asyncio
async def test_persistence_survives_restart_simulation():
    # Insert a record
    entry = {
        "execution_id": "REC-TEST-SURVIVE-002",
        "incident_id": "INC-TEST-002",
        "service_name": "service-b",
        "action": "SCALE_WORKERS",
        "status": "SUCCESS",
        "success": True,
        "duration_ms": 220.0,
        "verification_status": "VERIFIED",
        "result": "Scaled workers",
        "execution_mode": "CONTROLLED_DEMO"
    }
    await save_recovery_execution(entry)

    # Wipe in-memory collector cache (simulating process death)
    collector.recovery_history.clear()
    assert len(collector.recovery_history) == 0

    # Sync from DB (simulating backend startup)
    await sync_history_from_db()
    assert len(collector.recovery_history) > 0
    assert any(r["execution_id"] == "REC-TEST-SURVIVE-002" for r in collector.recovery_history)


@pytest.mark.asyncio
async def test_active_verification_failure_is_not_masked():
    verifier = RecoveryVerifier()

    # Simulate failing health probe
    async def mock_unhealthy_get(url, **kwargs):
        url_str = str(url)
        if "/health" in url_str:
            return MockResponse(503, {"status": "DOWN", "state": "CRASHED"})
        elif "/metrics" in url_str:
            return MockResponse(200, {"error_rate": 0.85, "latency_p95_ms": 1200.0})
        elif "/work" in url_str or "/query" in url_str:
            return MockResponse(503, {"error": "Service unavailable"})
        return MockResponse(200, {})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_unhealthy_get):
        result = await verifier.verify_recovery(
            target_service="database-service",
            affected_services=["service-b"],
            probe_delay_sec=0.0
        )

        # Verification must be FALSE and reasons must be reported
        assert result["verified"] is False
        assert result["status"] == "FAILED"
        assert result["checks"]["health"]["database-service"]["healthy"] is False
        assert result["checks"]["synthetic_transaction"]["passed"] is False
        assert len(result["failure_reasons"]) > 0


@pytest.mark.asyncio
async def test_manual_recovery_endpoint_complete_flow():
    async def mock_get(url, **kwargs):
        url_str = str(url)
        if "/health" in url_str:
            return MockResponse(200, {"status": "HEALTHY", "state": "HEALTHY"})
        if "/metrics" in url_str:
            return MockResponse(200, {"error_rate": 0.0, "latency_p95_ms": 8.0, "cpu_percent": 12.0})
        if "/work" in url_str:
            return MockResponse(200, {"status": "SUCCESS"})
        return MockResponse(200, {})

    async def mock_post(url, **kwargs):
        return MockResponse(200, {"success": True, "result": "Connection pool reset"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):

        req = ManualRecoveryRequest(service_name="database-service", action="RESET_CONNECTION_POOL")
        res = await trigger_manual_recovery(req)

        assert res["success"] is True
        assert res["verification"]["verified"] is True
        assert res["record"]["execution_mode"] == "CONTROLLED_DEMO"
        assert res["record"]["status"] == "SUCCESS"
        assert res["record"]["verification_status"] == "VERIFIED"

        # Verify history endpoint returns the persisted execution
        history = await get_recovery_history()
        assert len(history) > 0
        assert history[0]["action"] == "RESET_CONNECTION_POOL"
