"""
CloudDesk User Service (Port 8301)
Manages cloud identity, SSO logins, organization memberships, and developer credentials.
Uses Redis for session token verification and PostgreSQL for account storage.
"""

import os
import sys
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from clouddesk.common.logger import get_service_logger
from clouddesk.common.otel import setup_otel, TraceContextMiddleware
from clouddesk.common.database import init_db_pool, close_db_pool, fetch_row, execute_query, check_db_health
from clouddesk.common.cache import get_cached_json, set_cached_json, check_redis_health

SERVICE_NAME = "user-service"
PORT = int(os.getenv("PORT", 8301))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"CloudDesk - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class LoginSchema(BaseModel):
    email: str
    password: Optional[str] = "secret123"


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("User Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


@app.on_event("shutdown")
async def shutdown():
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    redis = await check_redis_health()
    return {
        "status": "HEALTHY" if db["status"] == "HEALTHY" else "DEGRADED",
        "service": SERVICE_NAME,
        "database": db,
        "cache": redis
    }


@app.post("/users/login")
async def login(payload: LoginSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    row = await fetch_row("SELECT user_id, email, name, organization_id, role, status FROM users WHERE email = $1", payload.email)
    if not row:
        logger.warning(
            f"Failed login attempt for {payload.email}",
            extra={"service": SERVICE_NAME, "event_type": "login_failed", "request_id": req_id}
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = dict(row)
    session_token = f"sess-{uuid.uuid4().hex[:16]}"
    try:
        await set_cached_json(f"cloud:session:{session_token}", user, ttl_seconds=3600)
    except Exception as exc:
        logger.warning(f"Session token cache write failed: {exc}")

    logger.info(
        f"User logged in: {user['user_id']} ({user['email']}) [Role: {user['role']}]",
        extra={
            "service": SERVICE_NAME,
            "event_type": "user_login",
            "request_id": req_id,
            "trace_id": trace_id,
            "user_id": user["user_id"]
        }
    )

    return {"status": "SUCCESS", "user_id": user["user_id"], "session_token": session_token, "role": user["role"]}


@app.get("/users/{user_id}")
async def get_user(user_id: str, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    row = await fetch_row("SELECT user_id, email, name, organization_id, role, status, created_at FROM users WHERE user_id = $1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(
        f"Retrieved profile for user {user_id}",
        extra={"service": SERVICE_NAME, "event_type": "user_profile_lookup", "request_id": req_id, "user_id": user_id}
    )
    return dict(row)
