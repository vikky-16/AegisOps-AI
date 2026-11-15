"""
Unit Tests for Continuous Telemetry Generator & Ingestion Latency Calculation
"""

import pytest
import asyncio
from datetime import datetime, timezone

from backend.app.monitoring.continuous_telemetry import continuous_telemetry
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetrySeverity


@pytest.mark.asyncio
async def test_continuous_telemetry_status_and_pacing():
    status = continuous_telemetry.get_status()
    assert "is_running" in status
    assert "configured_eps" in status
    assert "avg_ingestion_latency_ms" in status
    assert "recent_diagnostics_count" in status

    # Test rate adjustment
    continuous_telemetry.set_eps_rate(100)
    assert continuous_telemetry.configured_eps == 100

    continuous_telemetry.set_eps_rate(25)
    assert continuous_telemetry.configured_eps == 25


@pytest.mark.asyncio
async def test_continuous_telemetry_failure_override():
    # Inject temporary failure on database-service
    continuous_telemetry.set_service_failure(
        service="database-service",
        failure_type="DATABASE_CONNECTION_FAILURE",
        severity="CRITICAL",
        duration_sec=5.0
    )

    status = continuous_telemetry.get_status()
    assert "database-service" in status["active_failure_overrides"]

    # Clear failure overrides
    continuous_telemetry.clear_all_failures()
    status_cleared = continuous_telemetry.get_status()
    assert len(status_cleared["active_failure_overrides"]) == 0


@pytest.mark.asyncio
async def test_ingestion_latency_diagnostics_structure():
    diags = continuous_telemetry.get_recent_diagnostics(10)
    assert isinstance(diags, list)
    if len(diags) > 0:
        first = diags[0]
        assert "event_id" in first
        assert "source_type" in first
        assert "timestamp" in first
        assert "received_at" in first
        assert "ingestion_latency_ms" in first
        assert first["ingestion_latency_ms"] >= 0.0
        assert "service" in first
        assert "severity" in first
        assert "message" in first
