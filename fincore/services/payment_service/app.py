"""
FinCore Payment Service (Port 8203)
PCI-compliant payment clearance, ACH routing, and card settlement service.
Features real failure simulation for Payment Service timeouts (Phase 11 & live incident testing).
"""

import os
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fincore.common.logger import get_service_logger
from fincore.common.otel import setup_otel, TraceContextMiddleware
from fincore.common.database import init_db_pool, close_db_pool, execute_query, check_db_health

SERVICE_NAME = "payment-service"
PORT = int(os.getenv("PORT", 8203))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"FinCore - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

_injected_timeout: bool = False
_injected_delay_seconds: float = 0.0


class ProcessPaymentSchema(BaseModel):
    transaction_id: str
    amount: float
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = "ACH"


class TimeoutInjectionSchema(BaseModel):
    enabled: bool = True
    delay_seconds: float = 8.0


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("Payment Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


@app.on_event("shutdown")
async def shutdown():
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    return {
        "status": "DEGRADED" if _injected_timeout else "HEALTHY",
        "service": SERVICE_NAME,
        "timeout_injected": _injected_timeout,
        "delay_seconds": _injected_delay_seconds,
        "database": db
    }


# Chaos / Failure Injection Endpoints
@app.post("/inject/timeout")
async def inject_timeout(payload: TimeoutInjectionSchema = TimeoutInjectionSchema()):
    global _injected_timeout, _injected_delay_seconds
    _injected_timeout = payload.enabled
    _injected_delay_seconds = payload.delay_seconds if payload.enabled else 0.0
    logger.warning(
        f"CHAOS INJECTION: Payment Service timeout set to {_injected_timeout} ({_injected_delay_seconds}s)",
        extra={
            "service": SERVICE_NAME,
            "event_type": "chaos_injection_activated",
            "error_type": "SimulatedTimeout"
        }
    )
    return {"status": "SUCCESS", "timeout_injected": _injected_timeout, "delay_seconds": _injected_delay_seconds}


@app.post("/inject/reset")
async def reset_failure():
    global _injected_timeout, _injected_delay_seconds
    _injected_timeout = False
    _injected_delay_seconds = 0.0
    logger.info("CHAOS RESET: Payment Service restored to healthy state", extra={"service": SERVICE_NAME, "event_type": "chaos_reset"})
    return {"status": "SUCCESS", "timeout_injected": False, "delay_seconds": 0.0}


@app.post("/payments/process")
async def process_payment(payload: ProcessPaymentSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    payment_id = f"pay-{uuid.uuid4().hex[:10]}"
    gateway_ref = f"gw-ach-{uuid.uuid4().hex[:8]}"

    # Check for active failure injection
    if _injected_timeout:
        logger.error(
            f"Payment clearance TIMEOUT triggered for transaction {payload.transaction_id} (delaying {_injected_delay_seconds}s)",
            extra={
                "service": SERVICE_NAME,
                "event_type": "payment_gateway_timeout",
                "request_id": req_id,
                "trace_id": trace_id,
                "transaction_id": payload.transaction_id,
                "error_type": "GatewayTimeout",
                "error_message": f"Payment clearinghouse failed to respond after {_injected_delay_seconds}s"
            }
        )
        await asyncio.sleep(_injected_delay_seconds)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Payment network clearinghouse timeout after {_injected_delay_seconds}s"
        )

    # Normal clearance flow
    await execute_query(
        """
        INSERT INTO payments (payment_id, transaction_id, gateway_ref, amount, currency, status, payment_method)
        VALUES ($1, $2, $3, $4, $5, 'SETTLED', $6)
        """,
        payment_id, payload.transaction_id, gateway_ref, payload.amount, payload.currency, payload.payment_method
    )

    logger.info(
        f"Payment {payment_id} cleared via {payload.payment_method} (${payload.amount} {payload.currency})",
        extra={
            "service": SERVICE_NAME,
            "event_type": "payment_settled",
            "request_id": req_id,
            "trace_id": trace_id,
            "transaction_id": payload.transaction_id,
            "payment_id": payment_id,
            "amount": payload.amount
        }
    )

    return {
        "payment_id": payment_id,
        "transaction_id": payload.transaction_id,
        "gateway_ref": gateway_ref,
        "amount": payload.amount,
        "currency": payload.currency,
        "status": "SETTLED"
    }
