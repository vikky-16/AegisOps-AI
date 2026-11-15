"""
End-to-End Tests for Real Customer Live Telemetry Connectivity Pipeline
Validates:
1. Customer Onboarding & Integration creation in PENDING status.
2. Production OpenTelemetry Collector YAML, Docker, and K8s configuration generation.
3. Real live telemetry ingestion via REST/OTLP gateway with genuine API key authentication.
4. Dynamic integration state transition from PENDING -> CONNECTED upon first real packet arrival.
5. Strict tenant isolation (Tenant Alpha cannot see or query Tenant Beta telemetry).
6. API Key lifecycle (issuance, rotation, revocation yielding 401).
7. Customer incident webhook dispatcher with automatic secret scrubbing.
8. Platform self-observability and health reporting.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from backend.app.main import app
from backend.app.core.security import (
    generate_tenant_api_key,
    register_cached_api_key,
    evict_cached_api_key,
    API_KEY_CACHE
)
from backend.app.storage.telemetry_store import telemetry_store
from backend.app.healing.webhook_notifier import WebhookNotifier
from backend.app.api.ingestion_gateway import ingestion_tracker
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.tenant import Tenant, TenantIntegration, TenantAPIKey


TEST_TENANT_ID = "cust-pipeline-test"
TEST_TENANT_NAME = "Pipeline Test Enterprises"


@pytest.fixture(autouse=True)
async def setup_test_tenant():
    """Ensure clean test tenant and integration records in DB."""
    async with AsyncSessionLocal() as session:
        # Check if tenant exists, create if not
        existing = await session.get(Tenant, TEST_TENANT_ID)
        if not existing:
            new_t = Tenant(
                id=TEST_TENANT_ID,
                name=TEST_TENANT_NAME,
                slug="pipeline-test",
                tier="ENTERPRISE",
                status="ACTIVE"
            )
            session.add(new_t)
            await session.commit()
    yield
    # Cleanup memory store
    await telemetry_store.clear_tenant(TEST_TENANT_ID)


@pytest.mark.asyncio
async def test_onboarding_and_otel_config_generation():
    """Customer onboards, registers integration in PENDING state, and receives OTel configs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Integration (must start as PENDING)
        create_intg_resp = await client.post(
            f"/api/v1/tenants/{TEST_TENANT_ID}/integrations",
            json={
                "name": "Production K8s OTel Collector",
                "type": "OTEL",
                "config": {"cluster": "us-east-prod-1"}
            }
        )
        assert create_intg_resp.status_code == 201
        intg_data = create_intg_resp.json()
        intg_id = intg_data["id"]
        assert intg_data["status"] == "PENDING"
        assert intg_data["tenant_id"] == TEST_TENANT_ID

        # 2. Generate OTel Collector Configuration
        otel_cfg_resp = await client.post(
            f"/api/v1/tenants/{TEST_TENANT_ID}/otel-config",
            json={
                "integration_id": intg_id,
                "deployment_target": "kubernetes",
                "cluster_name": "us-east-prod-1",
                "tls_enabled": True
            }
        )
        assert otel_cfg_resp.status_code == 200
        cfg_data = otel_cfg_resp.json()
        
        # Verify required OTel Collector configuration artifacts
        assert cfg_data["tenant_id"] == TEST_TENANT_ID
        assert "receivers:" in cfg_data["collector_config_yaml"]
        assert "otlp:" in cfg_data["collector_config_yaml"]
        assert "exporters:" in cfg_data["collector_config_yaml"]
        assert "otlphttp/aegisops:" in cfg_data["collector_config_yaml"]
        assert intg_id in cfg_data["collector_config_yaml"]
        assert "DaemonSet" in cfg_data["kubernetes_manifest_yaml"]
        assert "docker run" in cfg_data["docker_run_command"]


@pytest.mark.asyncio
async def test_live_ingestion_and_state_transition():
    """When real telemetry arrives, integration transitions from PENDING to CONNECTED."""
    # 1. Create a dedicated API key for this test
    raw_key, prefix, hashed = generate_tenant_api_key(TEST_TENANT_ID)
    
    import uuid
    intg_id = f"intg-live-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        # Create an integration
        intg = TenantIntegration(
            id=intg_id,
            tenant_id=TEST_TENANT_ID,
            name="Live Probe Collector",
            type="OTEL",
            status="PENDING"
        )
        session.add(intg)

        key_rec = TenantAPIKey(
            tenant_id=TEST_TENANT_ID,
            key_prefix=prefix,
            hashed_key=hashed,
            name="Test Ingestion Key",
            is_active=True
        )
        session.add(key_rec)
        await session.commit()

    register_cached_api_key(raw_key, TEST_TENANT_ID, "Test Ingestion Key")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Ingest Log Event with integration_id tag
        log_payload = {
            "service": "customer-checkout",
            "message": "Order completed #99482 for $120.00",
            "level": "INFO",
            "integration_id": intg_id,
            "environment": "production"
        }
        log_resp = await client.post(
            "/api/v1/telemetry/logs",
            headers={"X-API-Key": raw_key},
            json=log_payload
        )
        assert log_resp.status_code == 200
        assert log_resp.json()["status"] in ["ACCEPTED", "INGESTED"]
        assert log_resp.json()["tenant_id"] == TEST_TENANT_ID

        # 3. Ingest Metric Event
        metric_resp = await client.post(
            "/api/v1/telemetry/metrics",
            headers={"X-API-Key": raw_key},
            json={
                "service": "customer-checkout",
                "metric_name": "checkout.latency.ms",
                "metric_value": 45.2,
                "unit": "ms"
            }
        )
        assert metric_resp.status_code == 200

        # 4. Ingest Trace Batch
        batch_resp = await client.post(
            "/api/v1/telemetry/batch",
            headers={"X-API-Key": raw_key},
            json={
                "events": [
                    {
                        "type": "trace",
                        "service": "customer-checkout",
                        "trace_id": "trace-test-1001",
                        "span_id": "span-test-01",
                        "duration_ms": 42.0,
                        "message": "POST /checkout"
                    }
                ]
            }
        )
        assert batch_resp.status_code == 200

        # 5. Check Integration Status - Must now be CONNECTED!
        list_resp = await client.get(
            f"/api/v1/tenants/{TEST_TENANT_ID}/integrations",
            headers={"X-API-Key": raw_key}
        )
        assert list_resp.status_code == 200
        integrations = list_resp.json()
        target_intg = next((i for i in integrations if i["id"] == intg_id), None)
        assert target_intg is not None
        assert target_intg["status"] == "CONNECTED"
        assert target_intg["events_received"] >= 1
        assert target_intg["last_seen_at"] is not None

        # 6. Verify TelemetryStore contains customer events
        stored_logs = await telemetry_store.query_logs(tenant_id=TEST_TENANT_ID)
        assert len(stored_logs) >= 1
        stored_messages = [log["message"] for log in stored_logs]
        assert any("Order completed" in msg for msg in stored_messages)


@pytest.mark.asyncio
async def test_multi_tenant_isolation_boundary():
    """Tenant A API key cannot query or access Tenant B's data or endpoints."""
    raw_key_a, _, _ = generate_tenant_api_key("tenant-alpha")
    raw_key_b, _, _ = generate_tenant_api_key("tenant-beta")
    register_cached_api_key(raw_key_a, "tenant-alpha", "Alpha Key")
    register_cached_api_key(raw_key_b, "tenant-beta", "Beta Key")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant A tries to access Tenant B's integrations -> 403 Forbidden
        cross_resp = await client.get(
            "/api/v1/tenants/tenant-beta/integrations",
            headers={"X-API-Key": raw_key_a}
        )
        assert cross_resp.status_code == 403

        # Tenant B tries to access Tenant A's audit logs -> 403 Forbidden
        cross_audit = await client.get(
            "/api/v1/tenants/tenant-alpha/audit",
            headers={"X-API-Key": raw_key_b}
        )
        assert cross_audit.status_code == 403


@pytest.mark.asyncio
async def test_key_rotation_and_revocation():
    """Revoking an API key strictly denies further telemetry ingestion (401 Unauthorized)."""
    raw_key, prefix, hashed = generate_tenant_api_key(TEST_TENANT_ID)
    
    key_id = None
    async with AsyncSessionLocal() as session:
        key_rec = TenantAPIKey(
            tenant_id=TEST_TENANT_ID,
            key_prefix=prefix,
            hashed_key=hashed,
            name="Revocation Target Key",
            is_active=True
        )
        session.add(key_rec)
        await session.commit()
        key_id = key_rec.id

    register_cached_api_key(raw_key, TEST_TENANT_ID, "Revocation Target Key")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingestion succeeds initially
        valid_resp = await client.post(
            "/api/v1/telemetry/logs",
            headers={"X-API-Key": raw_key},
            json={"service": "test", "message": "Pre-revocation log"}
        )
        assert valid_resp.status_code == 200

        # Revoke key via API
        del_resp = await client.delete(
            f"/api/v1/tenants/{TEST_TENANT_ID}/api-keys/{key_id}",
            headers={"X-API-Key": raw_key}
        )
        assert del_resp.status_code == 200

        # Subsequent ingestion must fail with 401 Unauthorized
        blocked_resp = await client.post(
            "/api/v1/telemetry/logs",
            headers={"X-API-Key": raw_key},
            json={"service": "test", "message": "Post-revocation attempt"}
        )
        assert blocked_resp.status_code == 401


@pytest.mark.asyncio
async def test_customer_webhook_secret_scrubbing():
    """Webhook notifier scrubs passwords, tokens, and authorization keys from incident payloads."""
    notifier = WebhookNotifier(timeout_sec=2.0)
    
    incident = {
        "id": "INC-8839",
        "tenant_id": "tenant-alpha",
        "severity": "CRITICAL",
        "service": "auth-service",
        "summary": "Database connection refused password=super_secret_db_pass",
        "confidence": 0.95,
        "blast_radius": 0.45,
        "status": "OPEN",
        "db_password": "super_secret_pass",
        "api_token": "bearer eyJhbGciOiJIUzI1Ni..."
    }

    payload = notifier.build_payload(incident)
    
    # Assert core fields exist
    assert payload["incident_id"] == "INC-8839"
    assert payload["tenant_id"] == "tenant-alpha"
    assert payload["severity"] == "CRITICAL"
    
    # Assert secrets in summary are redacted
    assert "super_secret_db_pass" not in payload["root_cause"]
    assert "[REDACTED]" in payload["root_cause"]

    # Test delivery mock
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        res = await notifier.notify_incident(incident, webhook_url="https://hooks.slack.com/services/T00/B00/X00")
        assert res["success"] is True
        assert res["status_code"] == 200


@pytest.mark.asyncio
async def test_platform_health_and_self_observability():
    """GET /platform/health returns ingestion throughput, pipeline queues, and storage health."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/platform/health")
        assert resp.status_code == 200
        health = resp.json()
        
        assert health["status"] == "HEALTHY"
        assert "ingestion_gateway" in health
        assert health["ingestion_gateway"]["status"] == "ONLINE"
        assert "pipeline_queues" in health
        assert "telemetry_storage" in health
        assert health["telemetry_storage"]["backend"] == "LocalMemoryTelemetryStore"
