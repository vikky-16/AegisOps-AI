"""
CloudDesk Redis Ephemeral Cache Client
Manages session tokens, ephemeral compute instance state, and resource quotas.
Features real failure simulation for Redis outages (Phase 11 & live incident testing).
"""

import os
import json
import time
import asyncio
from typing import Optional, Any, Dict

IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_REDIS_HOST = "redis" if IN_DOCKER else "127.0.0.1"
REDIS_HOST = os.getenv("REDIS_HOST", DEFAULT_REDIS_HOST)
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 2))

_redis_client = None
_redis_disabled = False
_local_cache: Dict[str, tuple] = {}
_chaos_redis_down: bool = False


def set_chaos_redis_down(is_down: bool):
    global _chaos_redis_down
    _chaos_redis_down = is_down


def get_chaos_redis_down() -> bool:
    return _chaos_redis_down


async def get_redis():
    global _redis_client, _redis_disabled
    if _chaos_redis_down:
        raise ConnectionError("RedisConnectionError: Error 111 connecting to 127.0.0.1:6379. Connection refused.")
    if _redis_disabled:
        return None
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=0.4,
                socket_connect_timeout=0.4
            )
        except Exception:
            _redis_disabled = True
            return None
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None


async def get_cached_json(key: str) -> Optional[Dict[str, Any]]:
    if _chaos_redis_down:
        raise ConnectionError("RedisConnectionError: Error 111 connecting to Redis. Connection refused.")

    r = await get_redis()
    if r:
        try:
            val = await asyncio.wait_for(r.get(key), timeout=0.3)
            if val:
                return json.loads(val)
        except Exception:
            pass

    now = time.time()
    if key in _local_cache:
        expires_at, data = _local_cache[key]
        if now < expires_at:
            return data
        else:
            del _local_cache[key]
    return None


async def set_cached_json(key: str, data: Dict[str, Any], ttl_seconds: int = 60):
    if _chaos_redis_down:
        raise ConnectionError("RedisConnectionError: Error 111 connecting to Redis. Connection refused.")

    r = await get_redis()
    if r:
        try:
            await asyncio.wait_for(r.set(key, json.dumps(data), ex=ttl_seconds), timeout=0.3)
            return
        except Exception:
            pass

    _local_cache[key] = (time.time() + ttl_seconds, data)


async def delete_cached_key(key: str):
    if _chaos_redis_down:
        raise ConnectionError("RedisConnectionError: Error 111 connecting to Redis. Connection refused.")

    r = await get_redis()
    if r:
        try:
            await asyncio.wait_for(r.delete(key), timeout=0.3)
        except Exception:
            pass
    _local_cache.pop(key, None)


async def check_redis_health() -> Dict[str, Any]:
    start = time.time()
    if _chaos_redis_down:
        lat = round((time.time() - start) * 1000, 2)
        return {
            "status": "UNHEALTHY",
            "latency_ms": lat,
            "error": "RedisConnectionError: Connection refused (redis://127.0.0.1:6379)"
        }

    r = await get_redis()
    if r:
        try:
            await asyncio.wait_for(r.ping(), timeout=0.3)
            lat = round((time.time() - start) * 1000, 2)
            return {"status": "HEALTHY", "latency_ms": lat, "engine": "redis"}
        except Exception:
            pass
    return {"status": "HEALTHY", "latency_ms": 0.1, "engine": "in_memory_ttl"}
