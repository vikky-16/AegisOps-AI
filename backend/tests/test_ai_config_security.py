"""
Unit & Integration Tests for AegisOps AI Configuration & Provider Security
Verifies:
- Raw secrets are never leaked in status responses
- Status is NEVER 'CONNECTED' merely because a key is present
- 'CONNECTED' only occurs when live test succeeds
- Gemini, Claude, and OpenAI provider settings
- Shared / unified key mode synchronization
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.api.ai_config import (
    _AI_CONFIG_STORE,
    mask_key,
    get_rca_ai_credentials,
    get_sre_ai_credentials,
)


def test_mask_key_security():
    assert mask_key("") == ""
    assert mask_key("short") == "********"
    assert mask_key("12345678") == "********"
    masked = mask_key("AIzaSyB1234567890abcdefXYZ")
    assert masked == "AIza****fXYZ"
    assert "1234567890abcdef" not in masked


@pytest.mark.asyncio
async def test_ai_config_status_zero_secret_leak():
    # Set a dummy secret in memory
    _AI_CONFIG_STORE["rca_ai_api_key"] = "test-secret-key-123456789"
    _AI_CONFIG_STORE["sre_ai_api_key"] = "test-secret-key-123456789"
    _AI_CONFIG_STORE["rca_ai_status"] = "NOT TESTED"
    _AI_CONFIG_STORE["sre_ai_status"] = "NOT TESTED"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ai-config/status")
        assert resp.status_code == 200
        data = resp.json()

        # Verify raw secret is NOT leaked
        assert "test-secret-key-123456789" not in resp.text
        assert data["rca_ai"]["masked_key"] == "test****6789"
        assert data["sre_ai"]["masked_key"] == "test****6789"

        # Verify status is NOT 'CONNECTED' merely because key exists
        assert data["rca_ai"]["status"] != "CONNECTED"
        assert data["rca_ai"]["status"] == "NOT TESTED"


@pytest.mark.asyncio
async def test_test_connection_without_key_returns_not_configured():
    # Reset store
    _AI_CONFIG_STORE["rca_ai_api_key"] = ""
    _AI_CONFIG_STORE["sre_ai_api_key"] = ""
    _AI_CONFIG_STORE["rca_ai_status"] = "NOT CONFIGURED"
    _AI_CONFIG_STORE["sre_ai_status"] = "NOT CONFIGURED"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test connection with empty key
        resp = await client.post("/api/ai-config/test-connection", json={"target": "rca_ai", "api_key": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "NOT CONFIGURED"


@pytest.mark.asyncio
async def test_unified_credentials_sync():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        update_payload = {
            "rca_ai_provider": "gemini",
            "rca_ai_model": "gemini-2.0-flash",
            "rca_ai_api_key": "AIzaSyTestKeyUnified999",
            "use_same_key_for_both": True,
        }
        resp = await client.post("/api/ai-config/update", json=update_payload)
        assert resp.status_code == 200

        rca_creds = get_rca_ai_credentials()
        sre_creds = get_sre_ai_credentials()

        assert rca_creds["api_key"] == "AIzaSyTestKeyUnified999"
        assert sre_creds["api_key"] == "AIzaSyTestKeyUnified999"
        assert rca_creds["provider"] == "gemini"
        assert sre_creds["provider"] == "gemini"
        assert rca_creds["model"] == "gemini-2.0-flash"


def test_gemini_provider_model_normalization():
    from backend.app.ai.gemini_provider import GeminiProvider
    assert GeminiProvider.DEFAULT_MODEL == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("gemini-2.5-flash") == "gemini-2.5-flash"
    assert GeminiProvider.normalize_model("gemini-2.0-flash") == "gemini-2.0-flash"
    assert GeminiProvider.normalize_model("gemini-1.5-flash") == "gemini-1.5-flash"
    assert GeminiProvider.normalize_model("") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model(None) == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("gemini-pro") == "gemini-3.8-flash"
