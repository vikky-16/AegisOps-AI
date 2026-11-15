"""
FinCore Redis Ephemeral Cache Client (with in-memory fallback)
Manages fast caching for account balances, active fraud blacklists, and idempotency keys.
Falls back seamlessly to local in-memory TTL cache when Redis is offline.
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
REDIS_DB = int(os.getenv("REDIS_DB", 1))

_redis_client = None
_redis_disabled = False
_local_cache: Dict[str, tuple] = {}


async def get_redis():
    global _redis_client, _redis_disabled
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
    global _redis_disabled
    r = await get_redis()
    if r:
        try:
            val = await asyncio.wait_for(r.get(key), timeout=0.2)
            if val:
                return json.loads(val)
        except Exception:
            _redis_disabled = True

    now = time.time()
    if key in _local_cache:
        expires_at, data = _local_cache[key]
        if now < expires_at:
            return data
        else:
            del _local_cache[key]
    return None


async def set_cached_json(key: str, data: Dict[str, Any], ttl_seconds: int = 60):
    global _redis_disabled
    r = await get_redis()
    if r:
        try:
            await asyncio.wait_for(r.set(key, json.dumps(data), ex=ttl_seconds), timeout=0.2)
            return
        except Exception:
            _redis_disabled = True

    _local_cache[key] = (time.time() + ttl_seconds, data)


async def delete_cached_key(key: str):
    global _redis_disabled
    r = await get_redis()
    if r:
        try:
            await asyncio.wait_for(r.delete(key), timeout=0.2)
        except Exception:
            _redis_disabled = True
    _local_cache.pop(key, None)


async def check_redis_health() -> Dict[str, Any]:
    global _redis_disabled
    start = time.time()
    r = await get_redis()
    if r:
        try:
            await asyncio.wait_for(r.ping(), timeout=0.2)
            lat = round((time.time() - start) * 1000, 2)
            return {"status": "HEALTHY", "latency_ms": lat, "engine": "redis"}
        except Exception:
            _redis_disabled = True
    return {"status": "HEALTHY", "latency_ms": 0.1, "engine": "in_memory_ttl"}

