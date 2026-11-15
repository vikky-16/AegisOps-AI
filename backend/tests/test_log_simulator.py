"""
Unit tests for the Continuous Log Traffic & Failure Simulator.
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.dev_tools.log_simulator import ContinuousLogSimulator, log_simulator
from backend.app.logger import realtime_logger


@pytest.mark.asyncio
async def test_log_simulator_lifecycle_and_emission():
    sim = ContinuousLogSimulator(log_rate_per_sec=20.0, failure_rate_per_min=0.0, max_logs=15)
    realtime_logger.buffer.clear()

    # Start simulator
    started = await sim.start()
    assert started is True
    assert sim.is_running is True

    # Wait for completion of 15 logs
    await asyncio.sleep(1.2)

    # Stop simulator
    sim.stop()
    assert sim.is_running is False
    assert sim._total_emitted >= 10
    assert len(realtime_logger.buffer) >= 10

    # Ensure logs have structured metadata
    last_log = list(realtime_logger.buffer)[-1]
    assert last_log.level in ("info", "warn", "error")
    assert "service" in last_log.meta


@pytest.mark.asyncio
async def test_failure_injection_and_paired_self_healing_resolution():
    sim = ContinuousLogSimulator(log_rate_per_sec=10.0, failure_rate_per_min=60.0)
    realtime_logger.buffer.clear()

    # Force a failure with paired self-healing resolution
    sim._emit_failure_with_resolution()
    assert sim._total_errors == 1

    # Check error log in buffer
    logs_snapshot = list(realtime_logger.buffer)
    error_log = [l for l in logs_snapshot if l.level == "error"][0]
    assert error_log.level == "error"
    assert "trace_id" in error_log.meta
    err_trace_id = error_log.meta["trace_id"]
    assert "stack_trace" in error_log.meta

    # Wait for delayed self-healing resolution (up to 5s)
    sim.is_running = True
    await asyncio.sleep(4.8)
    sim.stop()

    # Verify matching resolution log was emitted with the exact same trace_id
    updated_logs = list(realtime_logger.buffer)
    resolution_logs = [l for l in updated_logs if l.meta.get("trace_id") == err_trace_id and l.meta.get("healed_trace") is True]
    assert len(resolution_logs) == 1
    assert "Resolved:" in resolution_logs[0].message
    assert resolution_logs[0].level in ("info", "warn")


@pytest.mark.asyncio
async def test_simulator_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Start via API
        start_res = await client.post("/dev/logs/simulate/start?rate=15.0&failures=10.0&max_logs=25")
        assert start_res.status_code == 200
        data = start_res.json()
        assert data["success"] is True
        assert data["status"]["is_running"] is True

        # 2. Check status
        st_res = await client.get("/dev/logs/simulate/status")
        assert st_res.status_code == 200
        st_data = st_res.json()
        assert st_data["log_rate_per_sec"] == 15.0

        # 3. Update config
        cfg_res = await client.post("/dev/logs/simulate/config", json={"log_rate_per_sec": 12.0, "failure_rate_per_min": 6.0})
        assert cfg_res.status_code == 200
        assert cfg_res.json()["status"]["log_rate_per_sec"] == 12.0

        # Let it emit for a brief moment
        await asyncio.sleep(0.5)

        # 4. Stop via API
        stop_res = await client.post("/dev/logs/simulate/stop")
        assert stop_res.status_code == 200
        assert stop_res.json()["status"]["is_running"] is False
