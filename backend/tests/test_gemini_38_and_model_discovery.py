"""
Unit & Integration Tests for Gemini 3.8 Flash, Reasoning Effort, and Dynamic Model Discovery
Verifies:
1. Gemini 3.8 Flash selection as preferred default.
2. Dynamic discovery of newer models via GET /v1beta/models with filtering of non-text models.
3. Unavailable / 404 model errors cleanly categorized as MODEL_NOT_FOUND (not timeout).
4. Invalid API credentials (401/403) categorized as AUTH_ERROR.
5. Provider timeouts and rate limits categorized properly.
6. Model configuration persistence and administrator pinning.
7. RCA and SRE Assistant consistency with reasoning effort.
8. Fallback catalog behavior when offline or unconfigured.
9. Unsupported request parameters (graceful retry without thinkingConfig on 400).
"""

import json
import pytest
from httpx import AsyncClient, ASGITransport, Response, Request
from unittest.mock import patch, AsyncMock
from backend.app.main import app
from backend.app.ai.gemini_provider import GeminiProvider
from backend.app.api.ai_config import (
    _AI_CONFIG_STORE,
    get_rca_ai_credentials,
    get_sre_ai_credentials,
)


def test_gemini_38_flash_preferred_default():
    """Requirement 1: Verify DEFAULT_MODEL is gemini-3.8-flash and normalization preserves it."""
    assert GeminiProvider.DEFAULT_MODEL == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model(None) == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("models/gemini-3.8-flash") == "gemini-3.8-flash"
    # Newer dynamic models supported without code changes
    assert GeminiProvider.normalize_model("gemini-3.8-pro") == "gemini-3.8-pro"
    assert GeminiProvider.normalize_model("gemini-4.0-ultra") == "gemini-4.0-ultra"
    # Deprecated 1.0 models upgraded to 3.8 flash
    assert GeminiProvider.normalize_model("gemini-pro") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("gemini-1.0-pro") == "gemini-3.8-flash"


def test_thinking_support_detection():
    """Requirement 4: Verify reasoning / thinking capability detection."""
    assert GeminiProvider.supports_thinking("gemini-3.8-flash") is True
    assert GeminiProvider.supports_thinking("gemini-2.5-flash") is True
    assert GeminiProvider.supports_thinking("gemini-2.0-flash-thinking-exp") is True
    assert GeminiProvider.supports_thinking("gemini-2.0-flash") is False
    assert GeminiProvider.supports_thinking("gemini-1.5-flash") is False
    assert GeminiProvider.supports_thinking("gemini-1.5-pro") is False


@pytest.mark.asyncio
async def test_dynamic_model_discovery_filtering():
    """Requirement 2: Test live model discovery parsing and filtering of non-text models."""
    mock_api_models = {
        "models": [
            {
                "name": "models/text-embedding-004",
                "displayName": "Text Embedding 004",
                "supportedGenerationMethods": ["embedContent"]
            },
            {
                "name": "models/imagen-3.0-generate-002",
                "displayName": "Imagen 3.0",
                "supportedGenerationMethods": ["generateImages"]
            },
            {
                "name": "models/aqa",
                "displayName": "Attributed Question Answering",
                "supportedGenerationMethods": ["generateAnswer"]
            },
            {
                "name": "models/gemini-1.0-pro",
                "displayName": "Gemini 1.0 Pro (Deprecated)",
                "supportedGenerationMethods": ["generateContent"]
            },
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 8192,
                "supportedGenerationMethods": ["generateContent", "countTokens"]
            },
            {
                "name": "models/gemini-3.8-flash",
                "displayName": "Gemini 3.8 Flash",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 8192,
                "supportedGenerationMethods": ["generateContent", "countTokens"]
            },
            {
                "name": "models/gemini-3.9-ultra-preview",
                "displayName": "Gemini 3.9 Ultra Preview",
                "inputTokenLimit": 2097152,
                "outputTokenLimit": 8192,
                "supportedGenerationMethods": ["generateContent"]
            }
        ]
    }

    mock_resp = Response(
        status_code=200,
        content=json.dumps(mock_api_models).encode("utf-8"),
        request=Request("GET", "https://generativelanguage.googleapis.com/v1beta/models")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await GeminiProvider.discover_models(api_key="AIzaSyMockKeyForTest", force_refresh=True)

        assert res["status"] == "SUCCESS"
        assert res["is_live"] is True
        assert res["source"] == "live_discovery"
        assert res["preferred_model"] == "gemini-3.8-flash"
        assert res["is_preferred_available"] is True

        model_ids = [m["id"] for m in res["models"]]
        # Embeddings, imagen, aqa, and deprecated 1.0 must be excluded
        assert "text-embedding-004" not in model_ids
        assert "imagen-3.0-generate-002" not in model_ids
        assert "aqa" not in model_ids
        assert "gemini-1.0-pro" not in model_ids

        # Compatible text models must be discovered dynamically
        assert "gemini-3.8-flash" in model_ids
        assert "gemini-2.5-flash" in model_ids
        assert "gemini-3.9-ultra-preview" in model_ids

        # gemini-3.8-flash must be sorted first as preferred
        assert model_ids[0] == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_model_discovery_fallback_when_38_unavailable():
    """Requirement 2: When gemini-3.8-flash is not available to a specific key, pick best fallback."""
    mock_api_models = {
        "models": [
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "supportedGenerationMethods": ["generateContent"]
            },
            {
                "name": "models/gemini-2.0-flash",
                "displayName": "Gemini 2.0 Flash",
                "supportedGenerationMethods": ["generateContent"]
            }
        ]
    }

    mock_resp = Response(
        status_code=200,
        content=json.dumps(mock_api_models).encode("utf-8"),
        request=Request("GET", "https://generativelanguage.googleapis.com/v1beta/models")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await GeminiProvider.discover_models(api_key="AIzaSyMockKeyLimited", force_refresh=True)
        assert res["status"] == "SUCCESS"
        assert res["is_preferred_available"] is False
        assert res["recommended_fallback"] == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_connection_test_success_with_low_reasoning():
    """Requirement 5: Test connection probe returns latency, verified_usable, and reasoning flags."""
    mock_resp = Response(
        status_code=200,
        content=json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "pong"}]}
            }]
        }).encode("utf-8"),
        request=Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await GeminiProvider.test_connection(api_key="AIzaSyValidKeyTest", model="gemini-3.8-flash")
        assert res["status"] == "CONNECTED"
        assert res["category"] == "SUCCESS"
        assert res["verified_usable"] is True
        assert res["model"] == "gemini-3.8-flash"
        assert res["reasoning_supported"] is True
        assert res["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_connection_test_model_not_found_404_not_timeout():
    """Requirement 5: HTTP 404 must be categorized as MODEL_NOT_FOUND, never as TIMEOUT."""
    mock_resp = Response(
        status_code=404,
        content=json.dumps({"error": {"message": "models/gemini-custom-unsupported is not found"}}).encode("utf-8"),
        request=Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-custom-unsupported:generateContent")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await GeminiProvider.test_connection(api_key="AIzaSyValidKeyTest", model="gemini-custom-unsupported")
        assert res["status"] == "CONNECTION FAILED"
        assert res["category"] == "MODEL_NOT_FOUND"
        assert res["verified_usable"] is False
        assert "suggested_fallback" in res
        assert "404" in res["message"]
        # Must NOT be classified as timeout
        assert res["category"] != "TIMEOUT"


@pytest.mark.asyncio
async def test_connection_test_auth_error():
    """Requirement 5: HTTP 401/403 must be categorized as AUTH_ERROR with actionable steps."""
    mock_resp = Response(
        status_code=403,
        content=json.dumps({"error": {"message": "API key not valid. Please pass a valid API key."}}).encode("utf-8"),
        request=Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await GeminiProvider.test_connection(api_key="AIzaSyInvalidKeyTest", model="gemini-3.8-flash")
        assert res["status"] == "CONNECTION FAILED"
        assert res["category"] == "AUTH_ERROR"
        assert res["verified_usable"] is False
        assert "AI Studio" in res["actionable_steps"]


@pytest.mark.asyncio
async def test_connection_test_rate_limit_429():
    """Requirement 5: HTTP 429 categorized as RATE_LIMIT."""
    mock_resp = Response(
        status_code=429,
        content=json.dumps({"error": {"message": "Quota exceeded"}}).encode("utf-8"),
        request=Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await GeminiProvider.test_connection(api_key="AIzaSyQuotaKey", model="gemini-3.8-flash")
        assert res["status"] == "CONNECTION FAILED"
        assert res["category"] == "RATE_LIMIT"
        assert res["verified_usable"] is False


@pytest.mark.asyncio
async def test_reasoning_effort_retry_on_unsupported_thinking():
    """Requirement 4 & 6: If model returns 400 rejecting thinkingConfig, automatically retry without it."""
    resp_400 = Response(
        status_code=400,
        content=json.dumps({"error": {"message": "Invalid argument: thinkingConfig is not supported"}}).encode("utf-8"),
        request=Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-legacy:generateContent")
    )
    resp_200 = Response(
        status_code=200,
        content=json.dumps({"candidates": [{"content": {"parts": [{"text": "Root cause identified"}]}}]}).encode("utf-8"),
        request=Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-legacy:generateContent")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[resp_400, resp_200]):
        res = await GeminiProvider.generate_response(
            prompt="Analyze incident",
            api_key="AIzaSyValidKey",
            model="gemini-2.5-flash",
            reasoning_effort="high"
        )
        assert res["status"] == "SUCCESS"
        assert "Root cause identified" in res["text"]


@pytest.mark.asyncio
async def test_model_pinning_and_config_persistence():
    """Requirement 2 & 3: Administrator can pin models and configure reasoning effort."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "rca_ai_provider": "gemini",
            "rca_ai_model": "gemini-3.8-flash",
            "rca_ai_pinned": True,
            "rca_ai_api_key": "AIzaSyTestPersistenceKey777",
            "reasoning_effort": "high",
            "use_same_key_for_both": True
        }
        res = await client.post("/api/ai-config/update", json=payload)
        assert res.status_code == 200

        status_res = await client.get("/api/ai-config/status")
        assert status_res.status_code == 200
        data = status_res.json()

        assert data["rca_ai"]["model"] == "gemini-3.8-flash"
        assert data["rca_ai"]["pinned"] is True
        assert data["sre_ai"]["model"] == "gemini-3.8-flash"
        assert data["sre_ai"]["pinned"] is True
        assert data["reasoning_effort"] == "high"
        assert data["preferred_gemini_model"] == "gemini-3.8-flash"

        # Check credentials function
        creds = get_rca_ai_credentials()
        assert creds["model"] == "gemini-3.8-flash"
        assert creds["pinned"] is True
        assert creds["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_models_discovery_endpoint():
    """Requirement 2: GET /api/ai-config/models returns discovered models list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/ai-config/models")
        assert res.status_code == 200
        data = res.json()
        assert "models" in data
        assert data["preferred_model"] == "gemini-3.8-flash"
        assert len(data["models"]) >= 1

