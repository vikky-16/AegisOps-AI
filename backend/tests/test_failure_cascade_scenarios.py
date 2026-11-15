"""
End-to-End Tests for Controlled Failure Cascade Scenarios & Full Healing Loop
"""

import pytest
import asyncio
from backend.app.core.database import init_db
from backend.app.monitoring.collector import collector
from backend.app.monitoring.continuous_telemetry import continuous_telemetry
from backend.app.monitoring.failure_scheduler import failure_scheduler, FAILURE_SCENARIOS
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetrySeverity, TelemetryType


@pytest.fixture(autouse=True)
async def setup():
    await init_db()
    collector.operating_mode = "CONTROLLED_DEMO"
    collector.active_incidents.clear()
    collector.pending_approvals.clear()


@pytest.mark.asyncio
async def test_all_10_failure_scenarios_catalog():
    scenarios = failure_scheduler.legacy_scenarios
    assert len(scenarios) == 10
    
    scenario_ids = [s["id"] for s in scenarios]
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


@pytest.mark.asyncio
async def test_database_connection_failure_cascade_and_rca():
    # 1. Trigger database connection failure cascade
    res = await failure_scheduler.trigger_manual_scenario("DATABASE_CONNECTION_FAILURE")
    assert res["success"] is True
    assert res["primary_service"] == "database-service"
    assert "payment-api" in res["downstream"]
    assert "gateway" in res["downstream"]

    # 2. Simulate cascade events passing into collector
    # Earliest failure on database-service
    evt_db = NormalizedTelemetryEvent(
        source="test-services",
        service="database-service",
        type=TelemetryType.LOG,
        severity=TelemetrySeverity.CRITICAL,
        event_type="DATABASE_CONNECTION_FAILURE",
        message="Connection pool exhausted (50/50). Timeout waiting for connection after 3000ms",
        timestamp="2026-08-22T00:00:00Z",
        trace_id="trc-casc-01",
        metadata={"error_code": 40613}
    )
    collector.handle_continuous_telemetry_event(evt_db)

    # Downstream failure on payment-api
    evt_pay = NormalizedTelemetryEvent(
        source="test-services",
        service="payment-api",
        type=TelemetryType.LOG,
        severity=TelemetrySeverity.ERROR,
        event_type="PAYMENT_DECLINED_ERROR",
        message="Payment processing failed: Database connection timeout during transaction commit",
        timestamp="2026-08-22T00:00:02Z",
        trace_id="trc-casc-01",
        metadata={"error_code": "ERR_DB_LOCK"}
    )
    collector.handle_continuous_telemetry_event(evt_pay)

    # Downstream failure on gateway (502 Bad Gateway)
    evt_gw = NormalizedTelemetryEvent(
        source="test-services",
        service="gateway",
        type=TelemetryType.LOG,
        severity=TelemetrySeverity.ERROR,
        event_type="GATEWAY_502_BAD_GATEWAY",
        message="HTTP 502 Bad Gateway: Upstream connection refused to target service",
        timestamp="2026-08-22T00:00:04Z",
        trace_id="trc-casc-01",
        metadata={"http_status": 502}
    )
    collector.handle_continuous_telemetry_event(evt_gw)

    # 3. Verify that correlated incident was created
    assert len(collector.active_incidents) > 0
    inc = collector.active_incidents[-1]

    # 4. Verify Explainable RCA Evidence identifies database-service as the earliest cause
    assert inc["root_cause_service"] == "database-service"
    assert inc["correlated_event_count"] >= 1
    assert "RESET_CONNECTION_POOL" in inc["recommended_action"] or "DATABASE" in inc["recommended_action"] or "RESTART" in inc["recommended_action"]


@pytest.mark.asyncio
async def test_failure_scheduler_configuration():
    # Test setting scheduler config
    failure_scheduler.set_config(enabled=False, interval_seconds=45)
    status = failure_scheduler.get_status()
    assert status["is_enabled"] is False
    assert status["interval_seconds"] == 45

    # Re-enable
    failure_scheduler.set_config(enabled=True, interval_seconds=60)
    status_active = failure_scheduler.get_status()
    assert status_active["is_enabled"] is True
    assert status_active["interval_seconds"] == 60
