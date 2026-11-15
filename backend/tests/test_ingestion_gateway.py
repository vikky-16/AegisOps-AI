"""
Tests for Multi-Tenant Ingestion Gateway, PII Redaction, and Throughput Metrics
Validates:
- Scenario B: Streaming ingestion via Kafka & Ingestion Gateway with real tenant API keys.
- PII & Secret Redaction: Passwords, tokens, bearer headers, and private keys are scrubbed.
- Ingestion Throughput Tracking: Real measured KPIs (EPS, bytes/sec) without hardcoded values.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.pii_masker import pii_masker
from backend.app.api.ingestion_gateway import ingestion_tracker


VALID_DEMO_KEY = "agt_live_demo_11112222333344445555"
VALID_ACME_KEY = "agt_live_acme_aaaa1111bbbb2222cccc"
INVALID_KEY = "agt_live_invalid_key_9999999999999999"


@pytest.mark.asyncio
async def test_ingestion_gateway_auth_success():
    """Valid API keys authenticate successfully and ingest single and batch events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest Log
        resp = await client.post(
            "/api/v1/telemetry/logs",
            headers={"X-API-Key": VALID_ACME_KEY},
            json={
                "service": "order-service",
                "message": "Order #45091 processed successfully",
                "level": "INFO"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["ACCEPTED", "INGESTED"]
        assert data["tenant_id"] == "tenant-alpha"
        assert data["ingested_count"] >= 1

        # 2. Ingest Metric
        resp = await client.post(
            "/api/v1/telemetry/metrics",
            headers={"X-API-Key": VALID_ACME_KEY},
            json={
                "service": "order-service",
                "metric_name": "http.server.requests",
                "metric_value": 450.0,
                "unit": "req/sec"
            }
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ["ACCEPTED", "INGESTED"]

        # 3. Ingest Batch
        resp = await client.post(
            "/api/v1/telemetry/batch",
            headers={"X-API-Key": VALID_DEMO_KEY},
            json={
                "events": [
                    {"type": "METRIC", "service": "gateway", "metric_name": "cpu_utilization", "metric_value": 45.2},
                    {"type": "LOG", "service": "gateway", "message": "Health check ok", "level": "INFO"}
                ]
            }
        )
        assert resp.status_code == 200
        batch_data = resp.json()
        assert batch_data["ingested_count"] == 2
        assert batch_data["tenant_id"] == "demo-tenant"


@pytest.mark.asyncio
async def test_ingestion_gateway_auth_failure():
    """Missing or invalid API keys are rejected with 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing header
        resp = await client.post(
            "/api/v1/telemetry/logs",
            json={"service": "unauth-service", "message": "test"}
        )
        assert resp.status_code == 401

        # Invalid key
        resp = await client.post(
            "/api/v1/telemetry/logs",
            headers={"X-API-Key": INVALID_KEY},
            json={"service": "unauth-service", "message": "test"}
        )
        assert resp.status_code == 401


def test_pii_masking_engine():
    """Verifies that secrets, bearer tokens, passwords, and private keys are scrubbed."""
    raw_text = "User auth failed for user=admin password=SecretPassword123 with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeak"
    redacted = pii_masker.mask_text(raw_text)
    
    assert "SecretPassword123" not in redacted
    assert "[REDACTED_SECRET]" in redacted or "[REDACTED_BEARER_TOKEN]" in redacted or "[REDACTED" in redacted
    assert "password=" in redacted

    # Test dictionary redaction
    payload = {
        "service": "auth-service",
        "api_key": "sk_live_99887766554433221100",
        "nested": {
            "db_password": "super_secure_db_pass",
            "message": "Connection to postgres://admin:super_secure_db_pass@db.internal:5432 failed"
        }
    }
    cleaned = pii_masker.mask_dict(payload)
    assert cleaned["api_key"] == "[REDACTED_API_KEY]"
    assert cleaned["nested"]["db_password"] == "[REDACTED_SECRET]"
    assert "super_secure_db_pass" not in cleaned["nested"]["message"]


def test_throughput_kpi_tracker():
    """Verifies that ingestion tracker computes actual EPS, bytes/sec, and active tenants."""
    ingestion_tracker.record_ingested("tenant-alpha", event_count=20, byte_size=4096)
    ingestion_tracker.record_ingested("tenant-beta", event_count=10, byte_size=2048)

    stats = ingestion_tracker.get_stats()
    assert stats["total_events_ingested"] >= 30
    assert stats["total_bytes_ingested"] >= 6144
    assert stats["active_tenants"] >= 2
    assert "tenant_rates" in stats
    assert "tenant-alpha" in stats["tenant_rates"]
    assert "tenant-beta" in stats["tenant_rates"]
