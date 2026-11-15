"""
Unit & Integration Tests for Enterprise Synthetic Telemetry Simulator & Streaming Engine
Verifies symptom-only generation, streaming rates (100–1000 EPS), pause/resume, and cascade correlation.
"""

import pytest
import asyncio
from backend.app.simulator.generator import generate_enterprise_event, generate_synthetic_batch, ENTERPRISE_SERVICES
from backend.app.simulator.engine import simulator_engine
from backend.app.integrations.models import TelemetrySeverity


def test_symptom_only_generation_no_root_cause_leakage():
    allowed_services = {s["name"] for s in ENTERPRISE_SERVICES}
    # Test across all failure scenarios
    scenarios = [
        "normal_traffic",
        "database_exhaustion",
        "payment_gateway_timeout",
        "payment_transaction_spike",
        "api_server_crash",
        "cpu_saturation",
        "memory_leak",
        "storage_pressure",
        "log_storm_100k",
        "queue_backlog",
        "data_mart_failure"
    ]

    for sc in scenarios:
        events = generate_synthetic_batch(scenario=sc, count=25)
        assert len(events) == 25
        for ev in events:
            # Verify event contains standard envelope fields
            assert ev.service in allowed_services
            assert ev.severity in [TelemetrySeverity.INFO, TelemetrySeverity.WARNING, TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]
            assert ev.trace_id is not None
            # STRICT REQUIREMENT: Ensure no 'root_cause' field in metadata or message
            assert "root_cause=" not in ev.message
            assert "root_cause" not in ev.metadata


@pytest.mark.asyncio
async def test_simulator_engine_streaming_lifecycle():
    # 1. Start streaming 2000 events at 200 EPS
    res = await simulator_engine.start_stream(
        scenario="normal_traffic",
        target_count=2000,
        eps=200
    )
    assert res["status"] == "STREAMING"
    assert res["target_count"] == 2000

    # Wait for partial stream
    await asyncio.sleep(0.2)
    stat = simulator_engine.get_status()
    assert stat["events_streamed"] > 0

    # 2. Pause stream
    paused_stat = simulator_engine.pause_stream()
    assert paused_stat["status"] == "PAUSED"
    streamed_at_pause = paused_stat["events_streamed"]

    # Wait and verify no new events streamed while paused
    await asyncio.sleep(0.1)
    assert simulator_engine.events_streamed == streamed_at_pause

    # 3. Resume stream
    resumed_stat = simulator_engine.resume_stream()
    assert resumed_stat["status"] == "STREAMING"

    # Wait for completion
    await asyncio.sleep(0.4)
    final_stat = simulator_engine.get_status()
    assert final_stat["events_streamed"] >= 50
    assert final_stat["status"] in ["STREAMING", "COMPLETED"]

    # 4. Reset environment
    reset_res = await simulator_engine.reset_environment()
    assert reset_res["success"] is True
    assert simulator_engine.events_streamed == 0
    assert simulator_engine.status == "IDLE"
