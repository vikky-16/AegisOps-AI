"""
Unit tests for the real-time logging engine, circular buffer, and streaming endpoints.
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.logger import realtime_logger, StructuredLogEntry


@pytest.mark.asyncio
async def test_structured_log_emission_and_buffer():
    # Clear buffer for test
    realtime_logger.buffer.clear()

    # Emit logs
    entry_info = realtime_logger.info("Test info message", user_id="u123")
    entry_warn = realtime_logger.warn("Test warning message", threshold=90)
    entry_err = realtime_logger.error("Test error message", error_code="ERR_500")

    assert len(realtime_logger.buffer) == 3
    assert entry_info.level == "info"
    assert entry_warn.level == "warn"
    assert entry_err.level == "error"

    history = realtime_logger.get_history()
    assert len(history) == 3
    assert history[0]["message"] == "Test info message"
    assert history[0]["meta"]["user_id"] == "u123"
    assert history[1]["level"] == "warn"
    assert history[2]["level"] == "error"


@pytest.mark.asyncio
async def test_circular_buffer_capacity_300():
    realtime_logger.buffer.clear()

    # Emit 350 logs
    for i in range(350):
        realtime_logger.info(f"Log sequence {i}", seq=i)

    # Buffer must hold exactly 300 logs (oldest 50 evicted)
    assert len(realtime_logger.buffer) == 300
    history = realtime_logger.get_history()
    assert len(history) == 300
    assert history[0]["meta"]["seq"] == 50
    assert history[-1]["meta"]["seq"] == 349


@pytest.mark.asyncio
async def test_api_history_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/logs/history")
        assert res.status_code == 200
        data = res.json()
        assert "count" in data
        assert "capacity" in data
        assert data["capacity"] == 300
        assert "logs" in data


@pytest.mark.asyncio
async def test_test_event_emission_and_unhandled_capture():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test info emission
        res = await client.post("/api/logs/test-event?level=info&message=HelloFromTest")
        assert res.status_code == 200
        assert res.json()["emitted_log"]["message"] == "HelloFromTest"
        assert res.json()["emitted_log"]["level"] == "info"

        # Test error emission with stack trace
        res_err = await client.post("/api/logs/test-event?level=error&message=FailureTest")
        assert res_err.status_code == 200
        assert res_err.json()["emitted_log"]["level"] == "error"
        assert "stack_trace" in res_err.json()["emitted_log"]["meta"]


@pytest.mark.asyncio
async def test_standalone_admin_logs_html_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/admin/logs")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "AegisOps Real-Time Live Logs" in res.text
