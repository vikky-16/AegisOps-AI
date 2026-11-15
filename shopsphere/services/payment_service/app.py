"""
ShopSphere Payment Service (Port 8103)
Handles payment authorization, transaction settlement, and ledger logging.
Writes transaction records directly to PostgreSQL payments table.
"""

import os
import sys
import time
import uuid
import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shopsphere.common.logger import get_service_logger
from shopsphere.common.otel import setup_otel, TraceContextMiddleware
from shopsphere.common.database import init_db_pool, close_db_pool, execute_query, fetch_row, check_db_health

SERVICE_NAME = "payment-service"
PORT = int(os.getenv("PORT", 8103))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"ShopSphere - {SERVICE_NAME}",
    description="PCI-DSS Compliant Payment Gateway & Transaction Ledger",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class PaymentRequest(BaseModel):
    order_id: str
    customer_id: str
    amount: float
    payment_method: Optional[str] = "credit_card"


@app.on_event("startup")
async def startup():
    try:
        await init_db_pool()
        logger.info("Payment Service connected to PostgreSQL", extra={"service": SERVICE_NAME, "event_type": "db_connected"})
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")


@app.on_event("shutdown")
async def shutdown():
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    return {
        "status": "HEALTHY" if db["status"] == "HEALTHY" else "DEGRADED",
        "service": SERVICE_NAME,
        "database": db
    }


@app.post("/payments/process")
async def process_payment(req: PaymentRequest, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    payment_id = f"pay-{uuid.uuid4().hex[:12]}"
    transaction_ref = f"txn-{uuid.uuid4().hex[:16]}"

    # Simulate realistic gateway network round-trip (10-25ms)
    await asyncio.sleep(0.015)

    start_db = time.time()
    try:
        await execute_query(
            """
            INSERT INTO payments (payment_id, order_id, amount, status, transaction_ref)
            VALUES ($1, $2, $3, $4, $5)
            """,
            payment_id, req.order_id, Decimal(str(round(req.amount, 2))), "AUTHORIZED", transaction_ref
        )
        db_dur = round((time.time() - start_db) * 1000, 2)
        logger.info(
            f"Payment {payment_id} authorized for order {req.order_id} (${req.amount:.2f}) [DB: {db_dur}ms]",
            extra={
                "service": SERVICE_NAME,
                "event_type": "payment_authorized",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "postgresql",
                "latency_ms": db_dur,
                "order_id": req.order_id
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to record payment in database: {e}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "payment_failed",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "postgresql",
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise HTTPException(status_code=500, detail="Database write failure during payment")

    return {
        "payment_id": payment_id,
        "order_id": req.order_id,
        "amount": round(req.amount, 2),
        "status": "AUTHORIZED",
        "transaction_ref": transaction_ref
    }


@app.get("/payments/{payment_id}")
async def get_payment(payment_id: str):
    row = await fetch_row("SELECT payment_id, order_id, amount, status, transaction_ref, created_at FROM payments WHERE payment_id = $1", payment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Payment record not found")
    return {
        "payment_id": row["payment_id"],
        "order_id": row["order_id"],
        "amount": float(row["amount"]),
        "status": row["status"],
        "transaction_ref": row["transaction_ref"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("shopsphere.services.payment_service.app:app", host="0.0.0.0", port=PORT, reload=False)
