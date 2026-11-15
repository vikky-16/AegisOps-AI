"""
FinCore Transaction Service (Port 8202)
Orchestrates financial funds transfers and payments:
- Validates transaction limits and account status
- Calls Fraud Detection Service for real-time risk assessment
- Interacts with Payment Service for clearing/settlement
- Updates ledger in PostgreSQL and triggers customer notification
"""

import os
import sys
import time
import uuid
import httpx
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, Response, HTTPException, status
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fincore.common.logger import get_service_logger
from fincore.common.otel import setup_otel, TraceContextMiddleware, get_outgoing_headers
from fincore.common.database import init_db_pool, close_db_pool, execute_query, fetch_row, fetch_rows, check_db_health

SERVICE_NAME = "transaction-service"
PORT = int(os.getenv("PORT", 8202))
IN_DOCKER = os.path.exists("/.dockerenv")

DEFAULT_ACCOUNT_URL = "http://account-service:8201" if IN_DOCKER else "http://127.0.0.1:8201"
DEFAULT_PAYMENT_URL = "http://payment-service:8203" if IN_DOCKER else "http://127.0.0.1:8203"
DEFAULT_FRAUD_URL = "http://fraud-service:8204" if IN_DOCKER else "http://127.0.0.1:8204"
DEFAULT_NOTIF_URL = "http://notification-service:8205" if IN_DOCKER else "http://127.0.0.1:8205"

ACCOUNT_URL = os.getenv("ACCOUNT_SERVICE_URL", DEFAULT_ACCOUNT_URL).rstrip("/")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", DEFAULT_PAYMENT_URL).rstrip("/")
FRAUD_URL = os.getenv("FRAUD_SERVICE_URL", DEFAULT_FRAUD_URL).rstrip("/")
NOTIF_URL = os.getenv("NOTIFICATION_SERVICE_URL", DEFAULT_NOTIF_URL).rstrip("/")

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"FinCore - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

http_client: Optional[httpx.AsyncClient] = None


class CreateTransactionSchema(BaseModel):
    from_account: str
    to_account: str
    amount: float
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = "ACH"


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=8.0)
    await init_db_pool()
    logger.info("Transaction Service connected to DB", extra={"service": SERVICE_NAME, "event_type": "db_connected"})


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    return {
        "status": "HEALTHY" if db["status"] == "HEALTHY" else "DEGRADED",
        "service": SERVICE_NAME,
        "database": db
    }


@app.post("/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(payload: CreateTransactionSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    tx_id = f"tx-{uuid.uuid4().hex[:12]}"
    headers = get_outgoing_headers(request)

    logger.info(
        f"Processing financial transfer {tx_id}: {payload.from_account} -> {payload.to_account} (${payload.amount})",
        extra={
            "service": SERVICE_NAME,
            "event_type": "transaction_initiated",
            "request_id": req_id,
            "trace_id": trace_id,
            "transaction_id": tx_id,
            "account_id": payload.from_account,
            "amount": payload.amount,
            "currency": payload.currency
        }
    )

    # 1. Step: Fraud Risk Scoring
    fraud_score = 0.05
    try:
        fraud_resp = await http_client.post(
            f"{FRAUD_URL}/fraud/check",
            json={"transaction_id": tx_id, "from_account": payload.from_account, "amount": payload.amount},
            headers=headers,
            timeout=4.0
        )
        if fraud_resp.status_code == 200:
            fraud_data = fraud_resp.json()
            fraud_score = fraud_data.get("risk_score", 0.05)
            if fraud_data.get("action") == "BLOCK":
                logger.error(
                    f"Transaction {tx_id} BLOCKED by Fraud Engine: risk_score={fraud_score}",
                    extra={
                        "service": SERVICE_NAME,
                        "event_type": "transaction_fraud_blocked",
                        "request_id": req_id,
                        "trace_id": trace_id,
                        "transaction_id": tx_id,
                        "fraud_score": fraud_score
                    }
                )
                raise HTTPException(status_code=403, detail="Transaction blocked due to elevated fraud risk")
    except httpx.RequestError as exc:
        logger.warning(f"Fraud check bypassed due to network error: {exc}", extra={"service": SERVICE_NAME, "event_type": "fraud_timeout"})

    # 2. Step: Payment Clearance
    payment_id = f"pay-{uuid.uuid4().hex[:10]}"
    try:
        pay_resp = await http_client.post(
            f"{PAYMENT_URL}/payments/process",
            json={
                "transaction_id": tx_id,
                "amount": payload.amount,
                "currency": payload.currency,
                "payment_method": payload.payment_method
            },
            headers=headers,
            timeout=5.0
        )
        if pay_resp.status_code != 200:
            logger.error(
                f"Payment processing failed for {tx_id}: HTTP {pay_resp.status_code}",
                extra={
                    "service": SERVICE_NAME,
                    "event_type": "payment_failure",
                    "request_id": req_id,
                    "trace_id": trace_id,
                    "transaction_id": tx_id,
                    "http_status": pay_resp.status_code
                }
            )
            raise HTTPException(status_code=pay_resp.status_code, detail="Payment processing rejected by gateway")
    except httpx.TimeoutException:
        logger.error(
            f"Payment processing TIMEOUT for {tx_id}: Payment Service unresponsive",
            extra={
                "service": SERVICE_NAME,
                "event_type": "payment_timeout",
                "request_id": req_id,
                "trace_id": trace_id,
                "transaction_id": tx_id,
                "error_type": "TimeoutException",
                "error_message": "Payment clearance upstream timeout"
            }
        )
        raise HTTPException(status_code=504, detail="Payment clearance upstream gateway timeout")

    # 3. Step: Update Account Balances
    try:
        await http_client.put(
            f"{ACCOUNT_URL}/accounts/{payload.from_account}/balance",
            json={"amount_delta": -payload.amount, "reason": f"Transfer {tx_id}"},
            headers=headers,
            timeout=4.0
        )
    except Exception as exc:
        logger.error(f"Failed to deduct sender balance: {exc}")

    # 4. Step: Persist Transaction Record in PostgreSQL
    await execute_query(
        """
        INSERT INTO transactions (transaction_id, from_account, to_account, amount, currency, type, status, fraud_score)
        VALUES ($1, $2, $3, $4, $5, 'TRANSFER', 'COMPLETED', $6)
        """,
        tx_id, payload.from_account, payload.to_account, payload.amount, payload.currency, fraud_score
    )

    # 5. Step: Async Customer Notification
    try:
        await http_client.post(
            f"{NOTIF_URL}/notifications/send",
            json={
                "recipient": f"customer-{payload.from_account}",
                "channel": "SMS",
                "message": f"FinCore Alert: Transfer of ${payload.amount} to {payload.to_account} successful. Ref: {tx_id}"
            },
            headers=headers,
            timeout=3.0
        )
    except Exception:
        pass

    logger.info(
        f"Transaction {tx_id} successfully completed",
        extra={
            "service": SERVICE_NAME,
            "event_type": "transaction_completed",
            "request_id": req_id,
            "trace_id": trace_id,
            "transaction_id": tx_id,
            "amount": payload.amount,
            "status": "COMPLETED"
        }
    )

    return {
        "transaction_id": tx_id,
        "from_account": payload.from_account,
        "to_account": payload.to_account,
        "amount": payload.amount,
        "currency": payload.currency,
        "status": "COMPLETED",
        "fraud_score": fraud_score,
        "payment_id": payment_id
    }


@app.post("/transactions/validate")
async def validate_transaction(payload: CreateTransactionSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    is_valid = payload.amount > 0 and payload.amount <= 100000.0 and payload.from_account != payload.to_account
    logger.info(
        f"Transaction validation: amount={payload.amount} valid={is_valid}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "transaction_validation",
            "request_id": req_id,
            "trace_id": trace_id,
            "amount": payload.amount
        }
    )
    return {"valid": is_valid, "limit_exceeded": payload.amount > 100000.0}


@app.get("/transactions/history/{account_id}")
async def get_history(account_id: str, request: Request):
    rows = await fetch_rows(
        "SELECT transaction_id, from_account, to_account, amount, currency, status, created_at FROM transactions WHERE from_account = $1 OR to_account = $1 ORDER BY created_at DESC LIMIT 20",
        account_id
    )
    return {"account_id": account_id, "transactions": [dict(r) for r in rows]}
