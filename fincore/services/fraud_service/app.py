"""
FinCore Fraud Detection Service (Port 8204)
Performs real-time anomaly analysis, velocity checks, and risk scoring on financial transfers.
Supports chaos injection for evaluating system resilience under high evaluation latency.
"""

import os
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fincore.common.logger import get_service_logger
from fincore.common.otel import setup_otel, TraceContextMiddleware
from fincore.common.database import init_db_pool, close_db_pool, execute_query, check_db_health

SERVICE_NAME = "fraud-detection-service"
PORT = int(os.getenv("PORT", 8204))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"FinCore - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

_injected_latency_ms: float = 0.0


class FraudCheckSchema(BaseModel):
    transaction_id: str
    from_account: str
    amount: float


class LatencyInjectionSchema(BaseModel):
    latency_ms: float = 1200.0


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("Fraud Detection Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


@app.on_event("shutdown")
async def shutdown():
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    return {
        "status": "DEGRADED" if _injected_latency_ms > 0 else "HEALTHY",
        "service": SERVICE_NAME,
        "injected_latency_ms": _injected_latency_ms,
        "database": db
    }


@app.post("/inject/latency")
async def inject_latency(payload: LatencyInjectionSchema):
    global _injected_latency_ms
    _injected_latency_ms = payload.latency_ms
    logger.warning(
        f"CHAOS INJECTION: Fraud Service latency set to {_injected_latency_ms}ms",
        extra={"service": SERVICE_NAME, "event_type": "chaos_latency_injected", "latency_ms": _injected_latency_ms}
    )
    return {"status": "SUCCESS", "injected_latency_ms": _injected_latency_ms}


@app.post("/inject/reset")
async def reset_failure():
    global _injected_latency_ms
    _injected_latency_ms = 0.0
    logger.info("CHAOS RESET: Fraud Service restored to 0ms latency", extra={"service": SERVICE_NAME, "event_type": "chaos_reset"})
    return {"status": "SUCCESS", "injected_latency_ms": 0.0}


@app.post("/fraud/check")
async def check_fraud(payload: FraudCheckSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    check_id = f"chk-{uuid.uuid4().hex[:10]}"

    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    # Heuristic scoring
    risk_score = 0.04
    action = "ALLOW"
    rule = "NORMAL_VELOCITY"

    if payload.amount > 50000.0:
        risk_score = 0.88
        action = "BLOCK"
        rule = "HIGH_VALUE_THRESHOLD"
    elif payload.amount > 20000.0:
        risk_score = 0.45
        action = "REVIEW"
        rule = "MEDIUM_VALUE_WATCH"

    await execute_query(
        """
        INSERT INTO fraud_checks (check_id, transaction_id, risk_score, action, rules_triggered)
        VALUES ($1, $2, $3, $4, $5)
        """,
        check_id, payload.transaction_id, risk_score, action, rule
    )

    logger.info(
        f"Fraud risk evaluation for {payload.transaction_id}: score={risk_score}, action={action}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "fraud_evaluated",
            "request_id": req_id,
            "trace_id": trace_id,
            "transaction_id": payload.transaction_id,
            "fraud_score": risk_score,
            "rule_matched": rule,
            "latency_ms": _injected_latency_ms
        }
    )

    return {
        "check_id": check_id,
        "transaction_id": payload.transaction_id,
        "risk_score": risk_score,
        "action": action,
        "rules_triggered": rule
    }
