"""
AegisOps AI - Secure AI Provider & API Key Configuration
Manages provider credentials for RCA AI and SRE Chatbot.
Supports: Google Gemini (Preferred: gemini-3.8-flash), Anthropic Claude, and OpenAI.
CRITICAL SECURITY: Raw API keys are NEVER returned in API responses or serialized to the client.
Includes dynamic model discovery and reasoning effort configuration.
"""

import os
import time
import httpx
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai-config", tags=["AI Configuration"])

# Load backend/.env or root .env if present
_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_backend_env = os.path.join(_root_dir, "backend", ".env")
_root_env = os.path.join(_root_dir, ".env")
try:
    from dotenv import load_dotenv
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)
    if os.path.exists(_root_env):
        load_dotenv(_root_env)
except Exception:
    pass

from backend.app.ai.gemini_provider import GeminiProvider

_initial_rca_key = os.getenv("RCA_AI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
_initial_sre_key = os.getenv("SRE_AI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
_initial_val_key = os.getenv("VALIDATION_AI_API_KEY", "")

# In-memory runtime configuration store (secrets never returned to client)
_AI_CONFIG_STORE: Dict[str, Any] = {
    "rca_ai_provider": os.getenv("RCA_AI_PROVIDER", "gemini"),
    "rca_ai_model": GeminiProvider.normalize_model(os.getenv("RCA_AI_MODEL", GeminiProvider.DEFAULT_MODEL)),
    "rca_ai_pinned": False,
    "rca_ai_api_key": _initial_rca_key,
    "rca_ai_status": "NOT CONFIGURED" if not _initial_rca_key else "NOT TESTED",
    "sre_ai_provider": os.getenv("SRE_AI_PROVIDER", "gemini"),
    "sre_ai_model": GeminiProvider.normalize_model(os.getenv("SRE_AI_MODEL", GeminiProvider.DEFAULT_MODEL)),
    "sre_ai_pinned": False,
    "sre_ai_api_key": _initial_sre_key,
    "sre_ai_status": "NOT CONFIGURED" if not _initial_sre_key else "NOT TESTED",
    "reasoning_effort": os.getenv("AI_REASONING_EFFORT", "medium"),
    "validation_ai_provider": os.getenv("VALIDATION_AI_PROVIDER", "openai"),
    "validation_ai_model": os.getenv("VALIDATION_AI_MODEL", "gpt-4o-mini"),
    "validation_ai_api_key": _initial_val_key,
    "validation_ai_status": "NOT CONFIGURED" if not _initial_val_key else "NOT TESTED",
    "validation_ai_timeout_sec": float(os.getenv("VALIDATION_AI_TIMEOUT_SEC", "10.0")),
    "validation_ai_enabled": True,
    "use_same_key_for_both": True,
    "max_recovery_attempts": int(os.getenv("MAX_RECOVERY_ATTEMPTS", "3")),
}


class UpdateAIConfigRequest(BaseModel):
    rca_ai_provider: Optional[str] = None
    rca_ai_model: Optional[str] = None
    rca_ai_pinned: Optional[bool] = None
    rca_ai_api_key: Optional[str] = None
    sre_ai_provider: Optional[str] = None
    sre_ai_model: Optional[str] = None
    sre_ai_pinned: Optional[bool] = None
    sre_ai_api_key: Optional[str] = None
    reasoning_effort: Optional[str] = None
    validation_ai_provider: Optional[str] = None
    validation_ai_model: Optional[str] = None
    validation_ai_api_key: Optional[str] = None
    validation_ai_timeout_sec: Optional[float] = None
    validation_ai_enabled: Optional[bool] = None
    use_same_key_for_both: Optional[bool] = None
    max_recovery_attempts: Optional[int] = Field(default=None, ge=1, le=10)


def mask_key(raw_key: str) -> str:
    k = (raw_key or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return "********"
    return f"{k[:4]}****{k[-4:]}"


def get_rca_ai_credentials() -> Dict[str, Any]:
    """Backend-internal method to retrieve RCA AI credentials. NEVER call from public endpoints."""
    return {
        "provider": _AI_CONFIG_STORE.get("rca_ai_provider", "gemini"),
        "model": GeminiProvider.normalize_model(_AI_CONFIG_STORE.get("rca_ai_model", GeminiProvider.DEFAULT_MODEL)),
        "api_key": _AI_CONFIG_STORE.get("rca_ai_api_key", ""),
        "reasoning_effort": _AI_CONFIG_STORE.get("reasoning_effort", "medium"),
        "pinned": _AI_CONFIG_STORE.get("rca_ai_pinned", False),
    }


def get_sre_ai_credentials() -> Dict[str, Any]:
    """Backend-internal method to retrieve SRE AI credentials. NEVER call from public endpoints."""
    return {
        "provider": _AI_CONFIG_STORE.get("sre_ai_provider", "gemini"),
        "model": GeminiProvider.normalize_model(_AI_CONFIG_STORE.get("sre_ai_model", GeminiProvider.DEFAULT_MODEL)),
        "api_key": _AI_CONFIG_STORE.get("sre_ai_api_key", ""),
        "reasoning_effort": _AI_CONFIG_STORE.get("reasoning_effort", "medium"),
        "pinned": _AI_CONFIG_STORE.get("sre_ai_pinned", False),
    }


def get_validation_ai_credentials() -> Dict[str, Any]:
    """Backend-internal method to retrieve Independent Validation AI credentials."""
    return {
        "provider": _AI_CONFIG_STORE.get("validation_ai_provider", "openai"),
        "model": _AI_CONFIG_STORE.get("validation_ai_model", "gpt-4o-mini"),
        "api_key": _AI_CONFIG_STORE.get("validation_ai_api_key", ""),
        "timeout_sec": _AI_CONFIG_STORE.get("validation_ai_timeout_sec", 10.0),
        "enabled": _AI_CONFIG_STORE.get("validation_ai_enabled", True),
        "status": _AI_CONFIG_STORE.get("validation_ai_status", "NOT CONFIGURED")
    }


def get_max_recovery_attempts() -> int:
    return int(_AI_CONFIG_STORE.get("max_recovery_attempts", 3))


@router.get("")
@router.get("/status")
async def get_ai_config_status() -> Dict[str, Any]:
    """
    Returns public configuration status.
    CRITICAL: Never returns the raw API keys. Only returns masked values.
    Status is strictly: CONNECTED (only if tested successfully), NOT TESTED, or NOT CONFIGURED.
    """
    rca_key = _AI_CONFIG_STORE.get("rca_ai_api_key", "").strip()
    sre_key = _AI_CONFIG_STORE.get("sre_ai_api_key", "").strip()
    val_key = _AI_CONFIG_STORE.get("validation_ai_api_key", "").strip()

    rca_has_key = bool(rca_key)
    sre_has_key = bool(sre_key)
    val_has_key = bool(val_key)

    rca_status = _AI_CONFIG_STORE.get("rca_ai_status", "NOT CONFIGURED")
    if not rca_has_key:
        rca_status = "NOT CONFIGURED"
    elif rca_status == "NOT CONFIGURED":
        rca_status = "NOT TESTED"

    sre_status = _AI_CONFIG_STORE.get("sre_ai_status", "NOT CONFIGURED")
    if not sre_has_key:
        sre_status = "NOT CONFIGURED"
    elif sre_status == "NOT CONFIGURED":
        sre_status = "NOT TESTED"

    val_status = _AI_CONFIG_STORE.get("validation_ai_status", "NOT CONFIGURED")
    if not val_has_key:
        val_status = "NOT CONFIGURED"
    elif val_status == "NOT CONFIGURED":
        val_status = "NOT TESTED"

    return {
        "rca_ai": {
            "provider": _AI_CONFIG_STORE.get("rca_ai_provider", "gemini"),
            "model": GeminiProvider.normalize_model(_AI_CONFIG_STORE.get("rca_ai_model", GeminiProvider.DEFAULT_MODEL)),
            "status": rca_status,
            "is_configured": rca_has_key,
            "verified_usable": rca_status == "CONNECTED",
            "pinned": _AI_CONFIG_STORE.get("rca_ai_pinned", False),
            "masked_key": mask_key(rca_key)
        },
        "sre_ai": {
            "provider": _AI_CONFIG_STORE.get("sre_ai_provider", "gemini"),
            "model": GeminiProvider.normalize_model(_AI_CONFIG_STORE.get("sre_ai_model", GeminiProvider.DEFAULT_MODEL)),
            "status": sre_status,
            "is_configured": sre_has_key,
            "verified_usable": sre_status == "CONNECTED",
            "pinned": _AI_CONFIG_STORE.get("sre_ai_pinned", False),
            "masked_key": mask_key(sre_key)
        },
        "reasoning_effort": _AI_CONFIG_STORE.get("reasoning_effort", "medium"),
        "preferred_gemini_model": GeminiProvider.DEFAULT_MODEL,
        "recommended_fallback": GeminiProvider.RECOMMENDED_FALLBACK,
        "validation_ai": {
            "provider": _AI_CONFIG_STORE.get("validation_ai_provider", "openai"),
            "model": _AI_CONFIG_STORE.get("validation_ai_model", "gpt-4o-mini"),
            "status": val_status,
            "is_configured": val_has_key,
            "masked_key": mask_key(val_key),
            "timeout_sec": _AI_CONFIG_STORE.get("validation_ai_timeout_sec", 10.0),
            "enabled": _AI_CONFIG_STORE.get("validation_ai_enabled", True)
        },
        "use_same_key_for_both": _AI_CONFIG_STORE.get("use_same_key_for_both", True),
        "max_recovery_attempts": get_max_recovery_attempts()
    }


@router.get("/models")
@router.get("/gemini-models")
async def get_discovered_models(
    api_key: Optional[str] = Query(default=None),
    force_refresh: bool = Query(default=False)
) -> Dict[str, Any]:
    """
    Dynamic discovery endpoint: Queries official Google Generative Language API
    for available compatible text models.
    Uses saved RCA AI key if none provided in request.
    Never exposes raw API keys.
    """
    key_to_use = (api_key or "").strip() or _AI_CONFIG_STORE.get("rca_ai_api_key", "").strip()
    return await GeminiProvider.discover_models(api_key=key_to_use, force_refresh=force_refresh)


@router.post("")
@router.post("/update")
async def update_ai_config(payload: UpdateAIConfigRequest) -> Dict[str, Any]:
    """
    Updates AI provider configuration and secrets in secure memory.
    If use_same_key_for_both is True, syncing credentials across RCA and SRE Assistant.
    """
    if payload.use_same_key_for_both is not None:
        _AI_CONFIG_STORE["use_same_key_for_both"] = payload.use_same_key_for_both

    use_same = _AI_CONFIG_STORE.get("use_same_key_for_both", True)

    if payload.reasoning_effort is not None:
        effort = payload.reasoning_effort.lower()
        if effort in ["none", "low", "medium", "high"]:
            _AI_CONFIG_STORE["reasoning_effort"] = effort
            os.environ["AI_REASONING_EFFORT"] = effort

    if payload.rca_ai_provider is not None:
        _AI_CONFIG_STORE["rca_ai_provider"] = payload.rca_ai_provider
        if use_same and payload.sre_ai_provider is None:
            _AI_CONFIG_STORE["sre_ai_provider"] = payload.rca_ai_provider

    if payload.rca_ai_model is not None:
        norm_model = GeminiProvider.normalize_model(payload.rca_ai_model)
        _AI_CONFIG_STORE["rca_ai_model"] = norm_model
        if use_same and payload.sre_ai_model is None:
            _AI_CONFIG_STORE["sre_ai_model"] = norm_model

    if payload.rca_ai_pinned is not None:
        _AI_CONFIG_STORE["rca_ai_pinned"] = payload.rca_ai_pinned
        if use_same and payload.sre_ai_pinned is None:
            _AI_CONFIG_STORE["sre_ai_pinned"] = payload.rca_ai_pinned

    if payload.rca_ai_api_key is not None:
        key = payload.rca_ai_api_key.strip()
        _AI_CONFIG_STORE["rca_ai_api_key"] = key
        _AI_CONFIG_STORE["rca_ai_status"] = "NOT TESTED" if key else "NOT CONFIGURED"
        os.environ["RCA_AI_API_KEY"] = key
        if use_same and payload.sre_ai_api_key is None:
            _AI_CONFIG_STORE["sre_ai_api_key"] = key
            _AI_CONFIG_STORE["sre_ai_status"] = "NOT TESTED" if key else "NOT CONFIGURED"
            os.environ["SRE_AI_API_KEY"] = key

    if payload.sre_ai_provider is not None:
        _AI_CONFIG_STORE["sre_ai_provider"] = payload.sre_ai_provider
    if payload.sre_ai_model is not None:
        _AI_CONFIG_STORE["sre_ai_model"] = GeminiProvider.normalize_model(payload.sre_ai_model)
    if payload.sre_ai_pinned is not None:
        _AI_CONFIG_STORE["sre_ai_pinned"] = payload.sre_ai_pinned
    if payload.sre_ai_api_key is not None:
        key = payload.sre_ai_api_key.strip()
        _AI_CONFIG_STORE["sre_ai_api_key"] = key
        _AI_CONFIG_STORE["sre_ai_status"] = "NOT TESTED" if key else "NOT CONFIGURED"
        os.environ["SRE_AI_API_KEY"] = key

    if payload.validation_ai_provider is not None:
        _AI_CONFIG_STORE["validation_ai_provider"] = payload.validation_ai_provider
    if payload.validation_ai_model is not None:
        _AI_CONFIG_STORE["validation_ai_model"] = payload.validation_ai_model
    if payload.validation_ai_api_key is not None:
        key = payload.validation_ai_api_key.strip()
        _AI_CONFIG_STORE["validation_ai_api_key"] = key
        _AI_CONFIG_STORE["validation_ai_status"] = "NOT TESTED" if key else "NOT CONFIGURED"
        os.environ["VALIDATION_AI_API_KEY"] = key
    if payload.validation_ai_timeout_sec is not None:
        _AI_CONFIG_STORE["validation_ai_timeout_sec"] = payload.validation_ai_timeout_sec
    if payload.validation_ai_enabled is not None:
        _AI_CONFIG_STORE["validation_ai_enabled"] = payload.validation_ai_enabled

    if payload.max_recovery_attempts is not None:
        _AI_CONFIG_STORE["max_recovery_attempts"] = payload.max_recovery_attempts
        os.environ["MAX_RECOVERY_ATTEMPTS"] = str(payload.max_recovery_attempts)

    return {
        "status": "SUCCESS",
        "message": "AI configuration updated successfully in secure memory",
        "config": await get_ai_config_status()
    }


@router.post("/test-connection")
async def test_ai_connection(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely tests AI connection by performing a minimal live provider request.
    Never exposes raw secrets in responses or logs.
    Updates the connection status to CONNECTED only on live success.
    """
    target = payload.get("target", "rca_ai")  # "rca_ai", "sre_ai", or "validation_ai"
    if target not in ["rca_ai", "sre_ai", "validation_ai"]:
        target = "rca_ai"

    if target == "rca_ai":
        creds = get_rca_ai_credentials()
    elif target == "sre_ai":
        creds = get_sre_ai_credentials()
    else:
        creds = get_validation_ai_credentials()

    raw_payload_key = (payload.get("api_key") or "").strip()
    if raw_payload_key:
        api_key = raw_payload_key
        supplied_key = raw_payload_key
    else:
        api_key = creds.get("api_key", "").strip()
        supplied_key = ""

    if not api_key:
        _AI_CONFIG_STORE[f"{target}_status"] = "NOT CONFIGURED"
        return {
            "target": target,
            "status": "NOT CONFIGURED",
            "category": "CONFIGURATION_ERROR",
            "message": f"{target.upper()} API key is not configured. Please supply an API key.",
            "actionable_steps": "Enter your API key in the field and click 'Test Connection'."
        }

    provider = (payload.get("provider") or creds.get("provider") or "gemini").lower()
    model = payload.get("model") or creds.get("model") or GeminiProvider.DEFAULT_MODEL

    start_time = time.time()

    def record_success():
        _AI_CONFIG_STORE[f"{target}_status"] = "CONNECTED"
        if supplied_key:
            _AI_CONFIG_STORE[f"{target}_api_key"] = supplied_key
            _AI_CONFIG_STORE[f"{target}_provider"] = provider
            _AI_CONFIG_STORE[f"{target}_model"] = GeminiProvider.normalize_model(model)
            if target == "rca_ai":
                os.environ["RCA_AI_API_KEY"] = supplied_key
            elif target == "sre_ai":
                os.environ["SRE_AI_API_KEY"] = supplied_key
            else:
                os.environ["VALIDATION_AI_API_KEY"] = supplied_key
        if target in ["rca_ai", "sre_ai"] and _AI_CONFIG_STORE.get("use_same_key_for_both"):
            other_target = "sre_ai" if target == "rca_ai" else "rca_ai"
            _AI_CONFIG_STORE[f"{other_target}_status"] = "CONNECTED"
            if supplied_key:
                _AI_CONFIG_STORE[f"{other_target}_api_key"] = supplied_key
                _AI_CONFIG_STORE[f"{other_target}_provider"] = provider
                _AI_CONFIG_STORE[f"{other_target}_model"] = GeminiProvider.normalize_model(model)
                os.environ["SRE_AI_API_KEY" if target == "rca_ai" else "RCA_AI_API_KEY"] = supplied_key

    def record_failure():
        _AI_CONFIG_STORE[f"{target}_status"] = "CONNECTION FAILED"
        if target in ["rca_ai", "sre_ai"] and _AI_CONFIG_STORE.get("use_same_key_for_both"):
            other_target = "sre_ai" if target == "rca_ai" else "rca_ai"
            _AI_CONFIG_STORE[f"{other_target}_status"] = "CONNECTION FAILED"

    # 1. Google Gemini Provider
    if provider in ["gemini", "google", "google-gemini"]:
        gem_res = await GeminiProvider.test_connection(api_key=api_key, model=model)
        gem_res["target"] = target
        if gem_res["status"] == "CONNECTED":
            record_success()
        else:
            record_failure()
        return gem_res

    # 2. Other Providers (Anthropic, OpenAI)
    timeout = httpx.Timeout(connect=3.5, read=7.0, write=3.5, pool=3.5)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider in ["anthropic", "claude"]:
                claude_model = model or "claude-3-7-sonnet"
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": claude_model,
                        "max_tokens": 5,
                        "messages": [{"role": "user", "content": "ping"}]
                    }
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.status_code in [200, 201]:
                    record_success()
                    return {
                        "target": target,
                        "provider": "anthropic",
                        "model": claude_model,
                        "status": "CONNECTED",
                        "category": "SUCCESS",
                        "verified_usable": True,
                        "latency_ms": latency_ms,
                        "message": f"Successfully connected to Anthropic ({claude_model}). Latency: {latency_ms}ms"
                    }
                else:
                    record_failure()
                    return {
                        "target": target,
                        "provider": "anthropic",
                        "model": claude_model,
                        "status": "CONNECTION FAILED",
                        "verified_usable": False,
                        "latency_ms": latency_ms,
                        "category": "AUTH_ERROR" if resp.status_code in [401, 403] else "PROVIDER_ERROR",
                        "message": f"Anthropic connection failed ({resp.status_code})"
                    }

            elif provider in ["openai", "gpt"]:
                gpt_model = model or "gpt-4o"
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": gpt_model,
                        "max_tokens": 5,
                        "messages": [{"role": "user", "content": "ping"}]
                    }
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.status_code in [200, 201]:
                    record_success()
                    return {
                        "target": target,
                        "provider": "openai",
                        "model": gpt_model,
                        "status": "CONNECTED",
                        "category": "SUCCESS",
                        "verified_usable": True,
                        "latency_ms": latency_ms,
                        "message": f"Successfully connected to OpenAI ({gpt_model}). Latency: {latency_ms}ms"
                    }
                else:
                    record_failure()
                    return {
                        "target": target,
                        "provider": "openai",
                        "model": gpt_model,
                        "status": "CONNECTION FAILED",
                        "verified_usable": False,
                        "latency_ms": latency_ms,
                        "category": "AUTH_ERROR" if resp.status_code in [401, 403] else "PROVIDER_ERROR",
                        "message": f"OpenAI connection failed ({resp.status_code})"
                    }

            else:
                record_failure()
                return {
                    "target": target,
                    "provider": provider,
                    "model": model,
                    "status": "CONNECTION FAILED",
                    "verified_usable": False,
                    "category": "CONFIGURATION_ERROR",
                    "message": f"Unsupported provider '{provider}'. Supported: gemini, anthropic, openai."
                }
    except httpx.TimeoutException:
        record_failure()
        return {
            "target": target,
            "provider": provider,
            "model": model,
            "status": "CONNECTION FAILED",
            "verified_usable": False,
            "category": "TIMEOUT",
            "message": f"Connection timed out while reaching {provider} API endpoint."
        }
    except Exception as e:
        record_failure()
        clean_msg = str(e).replace(api_key, "[MASKED_KEY]")
        return {
            "target": target,
            "provider": provider,
            "model": model,
            "status": "CONNECTION FAILED",
            "verified_usable": False,
            "category": "SYSTEM_ERROR",
            "message": f"Connection error: {clean_msg}"
        }
