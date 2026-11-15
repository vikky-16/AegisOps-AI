"""
CloudDesk Compute Service (Port 8303)
Orchestrates cloud virtual machines, containers, and serverless compute nodes.
Interacts with Redis for instance heartbeat registration and PostgreSQL for cluster inventory.
Features real failure simulation for Redis outages and compute CPU/latency pressure.
"""

import os
import sys
import time
import uuid
import random
import asyncio
import httpx
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from clouddesk.common.logger import get_service_logger
from clouddesk.common.otel import setup_otel, TraceContextMiddleware, get_outgoing_headers
from clouddesk.common.database import init_db_pool, close_db_pool, fetch_row, execute_query, check_db_health
from clouddesk.common.cache import (
    get_cached_json,
    set_cached_json,
    check_redis_health,
    set_chaos_redis_down,
    get_chaos_redis_down
)

SERVICE_NAME = "compute-service"
PORT = int(os.getenv("PORT", 8303))
IN_DOCKER = os.path.exists("/.dockerenv")

DEFAULT_BILLING_URL = "http://billing-service:8304" if IN_DOCKER else "http://127.0.0.1:8304"
DEFAULT_NOTIF_URL = "http://notification-service:8305" if IN_DOCKER else "http://127.0.0.1:8305"
BILLING_URL = os.getenv("BILLING_SERVICE_URL", DEFAULT_BILLING_URL).rstrip("/")
NOTIF_URL = os.getenv("NOTIFICATION_SERVICE_URL", DEFAULT_NOTIF_URL).rstrip("/")

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"CloudDesk - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

http_client: Optional[httpx.AsyncClient] = None
_injected_latency_ms: float = 0.0


class CreateInstanceSchema(BaseModel):
    project_id: str
    name: str
    instance_type: Optional[str] = "c5.large"
    cpu_cores: Optional[int] = 4
    memory_gb: Optional[int] = 16


class LatencyInjectionSchema(BaseModel):
    latency_ms: float = 1500.0


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=8.0)
    await init_db_pool()
    logger.info("Compute Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    redis = await check_redis_health()
    is_healthy = db["status"] == "HEALTHY" and redis["status"] == "HEALTHY"
    return {
        "status": "HEALTHY" if is_healthy else "DEGRADED",
        "service": SERVICE_NAME,
        "redis_down_injected": get_chaos_redis_down(),
        "injected_latency_ms": _injected_latency_ms,
        "database": db,
        "cache": redis
    }


# Chaos / Failure Injection Endpoints
@app.post("/inject/redis-down")
async def inject_redis_down():
    set_chaos_redis_down(True)
    logger.error(
        "CHAOS INJECTION: Redis outage simulated! Redis connections will be refused.",
        extra={
            "service": SERVICE_NAME,
            "event_type": "chaos_redis_down",
            "error_type": "RedisConnectionRefused",
            "error_message": "Connection refused to redis://127.0.0.1:6379"
        }
    )
    return {"status": "SUCCESS", "redis_down": True}


@app.post("/inject/latency")
async def inject_latency(payload: LatencyInjectionSchema = LatencyInjectionSchema()):
    global _injected_latency_ms
    _injected_latency_ms = payload.latency_ms
    logger.warning(
        f"CHAOS INJECTION: Compute Service latency set to {_injected_latency_ms}ms",
        extra={"service": SERVICE_NAME, "event_type": "chaos_latency_injected", "latency_ms": _injected_latency_ms}
    )
    return {"status": "SUCCESS", "injected_latency_ms": _injected_latency_ms}


@app.post("/inject/reset")
async def reset_failures():
    global _injected_latency_ms
    set_chaos_redis_down(False)
    _injected_latency_ms = 0.0
    logger.info("CHAOS RESET: Compute Service and Redis restored to healthy operation", extra={"service": SERVICE_NAME, "event_type": "chaos_reset"})
    return {"status": "SUCCESS", "redis_down": False, "injected_latency_ms": 0.0}


@app.post("/compute/instances", status_code=status.HTTP_201_CREATED)
async def create_instance(payload: CreateInstanceSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    instance_id = f"inst-{uuid.uuid4().hex[:10]}"
    ip_addr = f"10.240.{random.randint(1, 254)}.{random.randint(1, 254)}"
    headers = get_outgoing_headers(request)

    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    logger.info(
        f"Provisioning compute instance {instance_id} ('{payload.name}', Type: {payload.instance_type})",
        extra={
            "service": SERVICE_NAME,
            "event_type": "compute_provisioning",
            "request_id": req_id,
            "trace_id": trace_id,
            "instance_id": instance_id,
            "project_id": payload.project_id,
            "cpu_cores": payload.cpu_cores,
            "memory_gb": payload.memory_gb
        }
    )

    # 1. Step: Register in Redis Cache (fails if Redis outage is active)
    try:
        await set_cached_json(
            f"cloud:inst:{instance_id}",
            {"instance_id": instance_id, "status": "RUNNING", "ip_address": ip_addr},
            ttl_seconds=300
        )
    except Exception as exc:
        logger.error(
            f"Failed to register instance in Redis: {str(exc)}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "redis_failure",
                "request_id": req_id,
                "trace_id": trace_id,
                "instance_id": instance_id,
                "dependency": "redis",
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            }
        )
        if get_chaos_redis_down():
            raise HTTPException(status_code=503, detail="Critical Cache Error: Redis connection refused. Compute state registry offline.")

    # 2. Step: Record in PostgreSQL database
    await execute_query(
        """
        INSERT INTO compute_instances (instance_id, project_id, name, instance_type, cpu_cores, memory_gb, status, ip_address)
        VALUES ($1, $2, $3, $4, $5, $6, 'RUNNING', $7)
        """,
        instance_id, payload.project_id, payload.name, payload.instance_type, payload.cpu_cores, payload.memory_gb, ip_addr
    )

    # 3. Step: Trigger Billing Metering
    cost_per_hour = round(payload.cpu_cores * 0.045 + payload.memory_gb * 0.008, 3)
    try:
        await http_client.post(
            f"{BILLING_URL}/billing/meter",
            json={
                "project_id": payload.project_id,
                "resource_type": "compute_hour",
                "units_consumed": 1.0,
                "cost": cost_per_hour
            },
            headers=headers,
            timeout=4.0
        )
    except Exception as exc:
        logger.warning(f"Billing metering async post error: {exc}")

    # 4. Step: Notification
    try:
        await http_client.post(
            f"{NOTIF_URL}/notifications/send",
            json={
                "user_id": payload.project_id,
                "channel": "SLACK",
                "subject": "Compute Instance Online",
                "message": f"Instance {payload.name} ({instance_id}) provisioned successfully on {ip_addr}"
            },
            headers=headers,
            timeout=3.0
        )
    except Exception:
        pass

    logger.info(
        f"Compute instance {instance_id} is RUNNING on {ip_addr}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "compute_provisioned",
            "request_id": req_id,
            "trace_id": trace_id,
            "instance_id": instance_id,
            "status": "RUNNING"
        }
    )

    return {
        "instance_id": instance_id,
        "name": payload.name,
        "project_id": payload.project_id,
        "instance_type": payload.instance_type,
        "ip_address": ip_addr,
        "status": "RUNNING",
        "cpu_cores": payload.cpu_cores,
        "memory_gb": payload.memory_gb
    }


@app.get("/compute/instances/{instance_id}/status")
async def get_instance_status(instance_id: str, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    # Try cache
    try:
        cached = await get_cached_json(f"cloud:inst:{instance_id}")
        if cached:
            return cached
    except Exception as exc:
        if get_chaos_redis_down():
            logger.error(f"Redis lookup failed for {instance_id}: {exc}")
            raise HTTPException(status_code=503, detail="Redis connection refused")

    row = await fetch_row(
        "SELECT instance_id, project_id, name, instance_type, cpu_cores, memory_gb, status, ip_address FROM compute_instances WHERE instance_id = $1",
        instance_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Instance not found")

    return dict(row)
