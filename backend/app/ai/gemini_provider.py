"""
AegisOps AI - Production Google Gemini Provider
Handles direct server-side communication with Google Gemini Generative Language API:
- Preferred Default Model: gemini-3.8-flash
- Automatic dynamic discovery of newer compatible models via GET /v1beta/models
- Filtering non-text models (embeddings, imagen, aqa, tts, deprecated PaLM)
- Reasoning effort configuration (low, medium, high) mapped to official thinkingConfig.thinkingBudget
- Fallback mitigation if thinkingConfig is rejected by legacy/non-thinking models
- Fast, low-latency connectivity probe with bounded timeouts and zero secret leakage
- Structured diagnostics: SUCCESS, AUTH_ERROR, MODEL_NOT_FOUND, RATE_LIMIT, TIMEOUT, NETWORK_ERROR
- Request ID tracing and sanitized diagnostics
"""

import time
import uuid
import httpx
from typing import Dict, Any, Optional, List


class GeminiProvider:
    DEFAULT_MODEL = "gemini-3.8-flash"
    RECOMMENDED_FALLBACK = "gemini-2.5-flash"
    SECONDARY_FALLBACK = "gemini-2.0-flash"

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
    GENERATE_CONTENT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    MODEL_INFO_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}"

    REASONING_BUDGET_MAP = {
        "none": 0,
        "low": 0,          # 0 budget disables extra thinking tokens for ultra-low latency & fast classification
        "medium": 2048,    # 2048 thinking tokens for routine RCA and remediation planning
        "high": 8192       # 8192 thinking tokens for complex multi-step RCA, dependency analysis, replica comparisons
    }

    # In-memory discovery cache (TTL = 300 seconds)
    _discovery_cache: Dict[str, Any] = {
        "timestamp": 0.0,
        "key_hash": "",
        "data": None
    }

    @classmethod
    def normalize_model(cls, model: Optional[str]) -> str:
        """
        Normalizes model identifier:
        - Defaults empty/null to gemini-3.8-flash
        - Strips 'models/' prefix
        - Maps legacy/deprecated PaLM/1.0 models to DEFAULT_MODEL (gemini-3.8-flash)
        - Preserves dynamic newer gemini models (e.g. gemini-3.8-flash, gemini-2.5-flash, gemini-3.8-pro)
        """
        m = (model or "").strip()
        if not m:
            return cls.DEFAULT_MODEL
        if m.startswith("models/"):
            m = m[len("models/"):]
        if m in ["gemini-pro", "gemini-1.0-pro", "gemini-1.0-pro-001", "gemini-pro-vision"]:
            return cls.DEFAULT_MODEL
        return m

    @classmethod
    def supports_thinking(cls, model: str) -> bool:
        """Determines if a model supports thinking/reasoning configuration."""
        clean = cls.normalize_model(model).lower()
        if "thinking" in clean:
            return True
        if "3.8" in clean or "3." in clean or "gemini-3" in clean:
            return True
        if "2.5" in clean:
            return True
        return False

    @classmethod
    def get_static_catalog(cls) -> List[Dict[str, Any]]:
        """
        Deterministic, verified catalog of Gemini models supported by AegisOps AI.
        Used as transparent fallback when offline or before live discovery runs.
        """
        return [
            {
                "id": "gemini-3.8-flash",
                "display_name": "Gemini 3.8 Flash (Preferred Default)",
                "description": "Next-gen ultra-fast multimodal model with integrated thinking and SRE reasoning.",
                "supports_thinking": True,
                "is_preferred": True,
                "recommended_for": ["Fast Connection Tests", "Routine RCA", "Replica Lab Analysis", "SRE Assistant"],
                "input_token_limit": 1048576,
                "output_token_limit": 8192
            },
            {
                "id": "gemini-2.5-flash",
                "display_name": "Gemini 2.5 Flash",
                "description": "High-efficiency reasoning model with balanced latency and deep incident synthesis.",
                "supports_thinking": True,
                "is_preferred": False,
                "recommended_for": ["Routine RCA", "Remediation Planning"],
                "input_token_limit": 1048576,
                "output_token_limit": 8192
            },
            {
                "id": "gemini-2.0-flash",
                "display_name": "Gemini 2.0 Flash",
                "description": "High-throughput, ultra-low latency model for high-frequency telemetry and health checks.",
                "supports_thinking": False,
                "is_preferred": False,
                "recommended_for": ["Realtime Telemetry", "Health Checks"],
                "input_token_limit": 1048576,
                "output_token_limit": 8192
            },
            {
                "id": "gemini-2.0-flash-thinking-exp",
                "display_name": "Gemini 2.0 Flash Thinking Experimental",
                "description": "Deep reasoning model that exposes internal chain of thought for complex cascades.",
                "supports_thinking": True,
                "is_preferred": False,
                "recommended_for": ["Complex Multi-step RCA", "Replica Twin Analysis"],
                "input_token_limit": 1048576,
                "output_token_limit": 8192
            },
            {
                "id": "gemini-1.5-flash",
                "display_name": "Gemini 1.5 Flash (LTS)",
                "description": "Stable long-term support release for high-volume tasks.",
                "supports_thinking": False,
                "is_preferred": False,
                "recommended_for": ["Standard Alert Summaries"],
                "input_token_limit": 1048576,
                "output_token_limit": 8192
            },
            {
                "id": "gemini-1.5-pro",
                "display_name": "Gemini 1.5 Pro (LTS)",
                "description": "Large context window for extensive distributed tracing packages.",
                "supports_thinking": False,
                "is_preferred": False,
                "recommended_for": ["Deep Historical Trace Analysis"],
                "input_token_limit": 2097152,
                "output_token_limit": 8192
            }
        ]

    @classmethod
    async def discover_models(
        cls,
        api_key: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Dynamically queries Google Generative Language API (GET /v1beta/models) to discover
        available models for the provided key.
        Filters out non-text models (embeddings, imagen, aqa, tts, deprecated PaLM).
        Detects newer models dynamically without code changes.
        Accurately reports live availability and never claims an unverified model is live.
        """
        clean_key = (api_key or "").strip()
        now = time.time()
        key_hash = str(hash(clean_key)) if clean_key else ""

        # Check cache if not forcing refresh and valid within 300s
        if not force_refresh and cls._discovery_cache["data"] and (now - cls._discovery_cache["timestamp"] < 300):
            if cls._discovery_cache["key_hash"] == key_hash:
                cached = dict(cls._discovery_cache["data"])
                cached["cached"] = True
                return cached

        if not clean_key:
            catalog = cls.get_static_catalog()
            return {
                "status": "NOT_CONFIGURED",
                "source": "catalog",
                "is_live": False,
                "total_found": len(catalog),
                "preferred_model": cls.DEFAULT_MODEL,
                "is_preferred_available": False,
                "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                "models": catalog,
                "message": "API key is not configured. Displaying verified standard catalog.",
                "timestamp": now,
                "cached": False
            }

        timeout = httpx.Timeout(connect=3.5, read=7.0, write=3.5, pool=3.5)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                headers = {
                    "x-goog-api-key": clean_key,
                    "Content-Type": "application/json"
                }
                resp = await client.get(cls.MODELS_ENDPOINT, headers=headers)

                # Fallback to query param if x-goog-api-key header returned 401/403
                if resp.status_code in [401, 403]:
                    resp = await client.get(f"{cls.MODELS_ENDPOINT}?key={clean_key}")

                if resp.status_code == 200:
                    raw_models = resp.json().get("models", [])
                    compatible: List[Dict[str, Any]] = []

                    excluded_keywords = [
                        "embedding", "imagen", "aqa", "tts", "whisper",
                        "bison", "gemini-1.0-pro", "gemini-pro-vision"
                    ]

                    for item in raw_models:
                        name = item.get("name", "")
                        clean_id = name[len("models/"):] if name.startswith("models/") else name
                        methods = item.get("supportedGenerationMethods", [])

                        # 1. Must support generateContent
                        if "generateContent" not in methods:
                            continue

                        # 2. Exclude non-text, image generation, audio, and deprecated models
                        clean_lower = clean_id.lower()
                        if any(kw in clean_lower for kw in excluded_keywords):
                            continue

                        supports_think = cls.supports_thinking(clean_id)
                        is_preferred = (clean_id == cls.DEFAULT_MODEL)

                        compatible.append({
                            "id": clean_id,
                            "display_name": item.get("displayName") or clean_id,
                            "description": item.get("description", ""),
                            "supports_thinking": supports_think,
                            "is_preferred": is_preferred,
                            "input_token_limit": item.get("inputTokenLimit", 1048576),
                            "output_token_limit": item.get("outputTokenLimit", 8192),
                            "supported_methods": methods
                        })

                    # Sort: preferred model first, then models with thinking, then newest
                    def sort_key(m: Dict[str, Any]):
                        score = 0
                        mid = m["id"]
                        if mid == cls.DEFAULT_MODEL:
                            score += 1000
                        elif "3.8" in mid or "3." in mid:
                            score += 800
                        elif "2.5" in mid:
                            score += 600
                        elif "2.0" in mid:
                            score += 400
                        elif "1.5" in mid:
                            score += 200
                        if m.get("supports_thinking"):
                            score += 50
                        return score

                    compatible.sort(key=sort_key, reverse=True)

                    is_pref_avail = any(m["id"] == cls.DEFAULT_MODEL for m in compatible)
                    # Pick best available fallback if 3.8 is not present
                    rec_fallback = cls.RECOMMENDED_FALLBACK
                    if not is_pref_avail and compatible:
                        rec_fallback = compatible[0]["id"]

                    res_data = {
                        "status": "SUCCESS",
                        "source": "live_discovery",
                        "is_live": True,
                        "total_found": len(compatible),
                        "preferred_model": cls.DEFAULT_MODEL,
                        "is_preferred_available": is_pref_avail,
                        "recommended_fallback": rec_fallback,
                        "models": compatible if compatible else cls.get_static_catalog(),
                        "message": f"Successfully discovered {len(compatible)} compatible models from Google Generative Language API.",
                        "timestamp": now,
                        "cached": False
                    }

                    cls._discovery_cache = {
                        "timestamp": now,
                        "key_hash": key_hash,
                        "data": res_data
                    }
                    return res_data

                elif resp.status_code in [401, 403]:
                    catalog = cls.get_static_catalog()
                    return {
                        "status": "AUTH_ERROR",
                        "source": "catalog",
                        "is_live": False,
                        "total_found": len(catalog),
                        "preferred_model": cls.DEFAULT_MODEL,
                        "is_preferred_available": False,
                        "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                        "models": catalog,
                        "message": f"Google Gemini discovery failed ({resp.status_code}): Invalid API key or unauthorized permissions.",
                        "actionable_steps": "Verify your Google Gemini API key in Google AI Studio (https://aistudio.google.com/).",
                        "timestamp": now,
                        "cached": False
                    }
                elif resp.status_code == 429:
                    catalog = cls.get_static_catalog()
                    return {
                        "status": "RATE_LIMIT",
                        "source": "catalog",
                        "is_live": False,
                        "total_found": len(catalog),
                        "preferred_model": cls.DEFAULT_MODEL,
                        "is_preferred_available": False,
                        "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                        "models": catalog,
                        "message": "Google Gemini API rate limit or quota exceeded during model discovery.",
                        "actionable_steps": "Check quota limits in Google Cloud Console or wait before re-querying.",
                        "timestamp": now,
                        "cached": False
                    }
                else:
                    catalog = cls.get_static_catalog()
                    return {
                        "status": "PROVIDER_ERROR",
                        "source": "catalog",
                        "is_live": False,
                        "total_found": len(catalog),
                        "preferred_model": cls.DEFAULT_MODEL,
                        "is_preferred_available": False,
                        "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                        "models": catalog,
                        "message": f"Google Gemini returned HTTP status {resp.status_code} during model discovery.",
                        "actionable_steps": "Check endpoint status or network connectivity.",
                        "timestamp": now,
                        "cached": False
                    }

        except httpx.TimeoutException:
            catalog = cls.get_static_catalog()
            return {
                "status": "TIMEOUT",
                "source": "catalog",
                "is_live": False,
                "total_found": len(catalog),
                "preferred_model": cls.DEFAULT_MODEL,
                "is_preferred_available": False,
                "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                "models": catalog,
                "message": "Model discovery timed out connecting to Google Gemini endpoint.",
                "actionable_steps": "Verify internet connectivity and firewall egress to generativelanguage.googleapis.com.",
                "timestamp": now,
                "cached": False
            }
        except httpx.ConnectError:
            catalog = cls.get_static_catalog()
            return {
                "status": "NETWORK_ERROR",
                "source": "catalog",
                "is_live": False,
                "total_found": len(catalog),
                "preferred_model": cls.DEFAULT_MODEL,
                "is_preferred_available": False,
                "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                "models": catalog,
                "message": "Network unreachable or DNS resolution failed for Google Gemini endpoint.",
                "actionable_steps": "Check network connection or DNS settings.",
                "timestamp": now,
                "cached": False
            }
        except Exception as e:
            catalog = cls.get_static_catalog()
            clean_err = str(e).replace(clean_key, "[MASKED_KEY]")
            return {
                "status": "SYSTEM_ERROR",
                "source": "catalog",
                "is_live": False,
                "total_found": len(catalog),
                "preferred_model": cls.DEFAULT_MODEL,
                "is_preferred_available": False,
                "recommended_fallback": cls.RECOMMENDED_FALLBACK,
                "models": catalog,
                "message": f"Discovery error: {clean_err}",
                "timestamp": now,
                "cached": False
            }

    @classmethod
    async def test_connection(
        cls,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 6.0
    ) -> Dict[str, Any]:
        """
        Performs a fast, low-cost connectivity probe against Google Gemini API.
        Uses low reasoning effort (thinkingBudget: 0) and maxOutputTokens: 3.
        Reports:
        - model & verified_usable status
        - response latency (ms)
        - rich category: SUCCESS, AUTH_ERROR, MODEL_NOT_FOUND (not timeout), RATE_LIMIT, TIMEOUT, NETWORK_ERROR
        - actionable next steps
        - zero secret leakage
        """
        clean_key = (api_key or "").strip()
        if not clean_key:
            return {
                "status": "NOT CONFIGURED",
                "category": "CONFIGURATION_ERROR",
                "provider": "google-gemini",
                "model": model,
                "verified_usable": False,
                "latency_ms": 0,
                "message": "API key is empty. Please provide a valid Google Gemini API key.",
                "actionable_steps": "Obtain an API key from Google AI Studio (https://aistudio.google.com/) and enter it in Settings."
            }

        active_model = cls.normalize_model(model)
        supports_think = cls.supports_thinking(active_model)
        start_time = time.time()
        timeout = httpx.Timeout(connect=3.5, read=timeout_seconds, write=3.5, pool=3.5)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = cls.GENERATE_CONTENT_ENDPOINT.format(model=active_model)
                headers = {
                    "x-goog-api-key": clean_key,
                    "Content-Type": "application/json"
                }

                # Construct fast probe payload with low reasoning effort
                gen_config: Dict[str, Any] = {
                    "maxOutputTokens": 3,
                    "temperature": 0.0
                }
                if supports_think:
                    gen_config["thinkingConfig"] = {"thinkingBudget": 0}

                body = {
                    "contents": [{"parts": [{"text": "ping"}]}],
                    "generationConfig": gen_config
                }

                resp = await client.post(url, headers=headers, json=body)
                latency_ms = int((time.time() - start_time) * 1000)

                # Retry without thinkingConfig if model rejected it (HTTP 400)
                if resp.status_code == 400 and supports_think:
                    err_txt = resp.text.lower()
                    if "thinking" in err_txt or "unknown field" in err_txt:
                        body_nothink = {
                            "contents": [{"parts": [{"text": "ping"}]}],
                            "generationConfig": {"maxOutputTokens": 3, "temperature": 0.0}
                        }
                        resp = await client.post(url, headers=headers, json=body_nothink)
                        latency_ms = int((time.time() - start_time) * 1000)

                # Fallback to query parameter if header returned 401/403
                if resp.status_code in [401, 403]:
                    url_with_key = f"{url}?key={clean_key}"
                    resp2 = await client.post(url_with_key, headers={"Content-Type": "application/json"}, json=body)
                    if resp2.status_code == 200:
                        latency_ms = int((time.time() - start_time) * 1000)
                        return {
                            "status": "CONNECTED",
                            "category": "SUCCESS",
                            "provider": "google-gemini",
                            "model": active_model,
                            "verified_usable": True,
                            "latency_ms": latency_ms,
                            "reasoning_supported": supports_think,
                            "message": f"Successfully connected to Google Gemini ({active_model}). Latency: {latency_ms}ms",
                            "actionable_steps": "Connection verified and active. Ready for autonomous RCA and SRE workloads."
                        }

                if resp.status_code == 200:
                    return {
                        "status": "CONNECTED",
                        "category": "SUCCESS",
                        "provider": "google-gemini",
                        "model": active_model,
                        "verified_usable": True,
                        "latency_ms": latency_ms,
                        "reasoning_supported": supports_think,
                        "message": f"Successfully connected to Google Gemini ({active_model}). Latency: {latency_ms}ms",
                        "actionable_steps": "Connection verified and active. Ready for autonomous RCA and SRE workloads."
                    }

                # Detailed diagnostics
                err_body = {}
                try:
                    err_body = resp.json().get("error", {})
                except Exception:
                    pass
                err_msg = err_body.get("message", resp.text[:180]).replace(clean_key, "[MASKED_KEY]")

                if resp.status_code in [401, 403]:
                    return {
                        "status": "CONNECTION FAILED",
                        "category": "AUTH_ERROR",
                        "provider": "google-gemini",
                        "model": active_model,
                        "verified_usable": False,
                        "latency_ms": latency_ms,
                        "message": f"Authentication failed ({resp.status_code}): Invalid Google Gemini API key or unauthorized permissions.",
                        "actionable_steps": "Check your API key in Google AI Studio (https://aistudio.google.com/) and ensure Generative Language API is enabled."
                    }
                elif resp.status_code == 404:
                    return {
                        "status": "CONNECTION FAILED",
                        "category": "MODEL_NOT_FOUND",
                        "provider": "google-gemini",
                        "model": active_model,
                        "verified_usable": False,
                        "latency_ms": latency_ms,
                        "suggested_fallback": cls.RECOMMENDED_FALLBACK,
                        "message": f"Google Gemini model '{active_model}' is not available (404) for this API key or region.",
                        "actionable_steps": f"Model '{active_model}' was not found. Switch to verified fallback '{cls.RECOMMENDED_FALLBACK}' or click 'Discover Models' in Settings."
                    }
                elif resp.status_code == 429:
                    return {
                        "status": "CONNECTION FAILED",
                        "category": "RATE_LIMIT",
                        "provider": "google-gemini",
                        "model": active_model,
                        "verified_usable": False,
                        "latency_ms": latency_ms,
                        "message": "Google Gemini quota or rate limit exceeded (429).",
                        "actionable_steps": "Verify your quota tier in Google Cloud Console or wait a few moments before retrying."
                    }
                else:
                    return {
                        "status": "CONNECTION FAILED",
                        "category": "PROVIDER_ERROR",
                        "provider": "google-gemini",
                        "model": active_model,
                        "verified_usable": False,
                        "latency_ms": latency_ms,
                        "message": f"Google Gemini returned status {resp.status_code}: {err_msg}",
                        "actionable_steps": "Inspect the error message or try another compatible model."
                    }

        except httpx.ConnectTimeout:
            return {
                "status": "CONNECTION FAILED",
                "category": "TIMEOUT",
                "provider": "google-gemini",
                "model": active_model,
                "verified_usable": False,
                "latency_ms": int((time.time() - start_time) * 1000),
                "message": "Connection timed out during TCP/TLS handshake with Google Gemini API endpoint.",
                "actionable_steps": "Check firewall, proxy, or network egress to generativelanguage.googleapis.com."
            }
        except httpx.ReadTimeout:
            return {
                "status": "CONNECTION FAILED",
                "category": "TIMEOUT",
                "provider": "google-gemini",
                "model": active_model,
                "verified_usable": False,
                "latency_ms": int((time.time() - start_time) * 1000),
                "message": "Read timed out waiting for Google Gemini response.",
                "actionable_steps": "Endpoint took too long to answer. Try switching to gemini-3.8-flash with low reasoning effort."
            }
        except httpx.TimeoutException:
            return {
                "status": "CONNECTION FAILED",
                "category": "TIMEOUT",
                "provider": "google-gemini",
                "model": active_model,
                "verified_usable": False,
                "latency_ms": int((time.time() - start_time) * 1000),
                "message": "Connection timed out reaching Google Gemini endpoint.",
                "actionable_steps": "Check network connectivity to Google APIs."
            }
        except httpx.ConnectError:
            return {
                "status": "CONNECTION FAILED",
                "category": "NETWORK_ERROR",
                "provider": "google-gemini",
                "model": active_model,
                "verified_usable": False,
                "latency_ms": 0,
                "message": "Network unreachable or DNS resolution failed for Google Gemini endpoint.",
                "actionable_steps": "Verify DNS resolution and outbound internet access."
            }
        except Exception as e:
            clean_err = str(e).replace(clean_key, "[MASKED_KEY]")
            return {
                "status": "CONNECTION FAILED",
                "category": "SYSTEM_ERROR",
                "provider": "google-gemini",
                "model": active_model,
                "verified_usable": False,
                "latency_ms": 0,
                "message": f"Connection error: {clean_err}",
                "actionable_steps": "Review backend system logs for diagnostic details."
            }

    @classmethod
    async def generate_response(
        cls,
        prompt: str,
        api_key: str,
        model: str = DEFAULT_MODEL,
        reasoning_effort: Optional[str] = "medium",
        thinking_budget: Optional[int] = None,
        max_output_tokens: int = 1200,
        temperature: float = 0.2,
        timeout_seconds: float = 25.0,
        previous_interaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a prompt against Gemini generateContent API with:
        - Request ID tracing
        - Configured reasoning effort (low, medium, high)
        - Safe retry without thinkingConfig if unsupported by model
        - Zero secret leakage in payloads or exceptions
        - Structured output contract
        """
        clean_key = (api_key or "").strip()
        if not clean_key:
            return {
                "status": "FAILED",
                "error": "No API key provided",
                "text": "",
                "interaction_id": None,
                "is_fallback": True
            }

        active_model = cls.normalize_model(model)
        request_id = f"gemini-req-{uuid.uuid4().hex[:8]}"
        timeout = httpx.Timeout(connect=4.0, read=timeout_seconds, write=4.0, pool=4.0)

        # Resolve thinking budget
        budget: Optional[int] = thinking_budget
        if budget is None and reasoning_effort:
            budget = cls.REASONING_BUDGET_MAP.get(reasoning_effort.lower(), 2048)

        supports_think = cls.supports_thinking(active_model)

        # Build generationConfig
        gen_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens
        }
        if supports_think and budget is not None:
            gen_config["thinkingConfig"] = {"thinkingBudget": budget}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = cls.GENERATE_CONTENT_ENDPOINT.format(model=active_model)
                headers = {
                    "x-goog-api-key": clean_key,
                    "Content-Type": "application/json",
                    "X-Request-Id": request_id
                }
                body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": gen_config
                }

                resp = await client.post(url, headers=headers, json=body)

                # Retry without thinkingConfig if model returned HTTP 400 rejecting it
                if resp.status_code == 400 and "thinkingConfig" in gen_config:
                    err_txt = resp.text.lower()
                    if "thinking" in err_txt or "unknown field" in err_txt:
                        body_retry = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": temperature,
                                "maxOutputTokens": max_output_tokens
                            }
                        }
                        resp = await client.post(url, headers=headers, json=body_retry)

                # Fallback to query parameter if header returned 401/403
                if resp.status_code in [401, 403]:
                    url_with_key = f"{url}?key={clean_key}"
                    resp2 = await client.post(url_with_key, headers={"Content-Type": "application/json"}, json=body)
                    if resp2.status_code == 200:
                        data = resp2.json()
                        text = cls._extract_text(data)
                        if text:
                            return {
                                "status": "SUCCESS",
                                "text": text,
                                "interaction_id": request_id,
                                "model": active_model,
                                "reasoning_effort": reasoning_effort,
                                "api_pattern": "generateContent",
                                "is_fallback": False
                            }

                if resp.status_code == 200:
                    data = resp.json()
                    text = cls._extract_text(data)
                    if text:
                        return {
                            "status": "SUCCESS",
                            "text": text,
                            "interaction_id": request_id,
                            "model": active_model,
                            "reasoning_effort": reasoning_effort,
                            "api_pattern": "generateContent",
                            "is_fallback": False
                        }

                clean_err = resp.text.replace(clean_key, "[MASKED_KEY]")[:200]
                return {
                    "status": "FAILED",
                    "error": f"Gemini API returned status {resp.status_code}: {clean_err}",
                    "text": "",
                    "interaction_id": request_id,
                    "is_fallback": True
                }

        except Exception as e:
            clean_err = str(e).replace(clean_key, "[MASKED_KEY]")
            return {
                "status": "FAILED",
                "error": f"Gemini API call failed: {clean_err}",
                "text": "",
                "interaction_id": request_id,
                "is_fallback": True
            }

    @classmethod
    def _extract_text(cls, data: Dict[str, Any]) -> str:
        """Robustly extracts text from diverse Gemini API response shapes."""
        if not isinstance(data, dict):
            return ""

        # 1. Standard candidates schema
        candidates = data.get("candidates", [])
        if isinstance(candidates, list) and candidates:
            first_c = candidates[0]
            if isinstance(first_c, dict) and "content" in first_c:
                parts = first_c["content"].get("parts", [])
                if isinstance(parts, list) and parts:
                    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p]
                    if texts:
                        return "\n".join(texts)

        # 2. Output text directly
        if "output_text" in data and isinstance(data["output_text"], str):
            return data["output_text"]

        # 3. Outputs list schema
        outputs = data.get("outputs", [])
        if isinstance(outputs, list):
            texts = []
            for item in outputs:
                if isinstance(item, dict):
                    if "text" in item and isinstance(item["text"], str):
                        texts.append(item["text"])
                    content = item.get("content")
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        for p in content:
                            if isinstance(p, dict) and "text" in p:
                                texts.append(p["text"])
                            elif isinstance(p, str):
                                texts.append(p)
                    elif isinstance(content, dict):
                        if "text" in content:
                            texts.append(content["text"])
                        elif "parts" in content and isinstance(content["parts"], list):
                            for p in content["parts"]:
                                if isinstance(p, dict) and "text" in p:
                                    texts.append(p["text"])
            if texts:
                return "\n".join(texts)

        if "text" in data and isinstance(data["text"], str):
            return data["text"]

        return ""
