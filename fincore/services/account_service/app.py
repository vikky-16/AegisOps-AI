"""
FinCore Account Service (Port 8201)
Manages customer bank accounts, balances, credit limits, and account lifecycle.
Uses Redis for low-latency balance caching and PostgreSQL as the authoritative ledger.
"""

import os
import sys
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fincore.common.logger import get_service_logger
from fincore.common.otel import setup_otel, TraceContextMiddleware
from fincore.common.database import init_db_pool, close_db_pool, fetch_row, execute_query, check_db_health
from fincore.common.cache import get_cached_json, set_cached_json, delete_cached_key, check_redis_health

SERVICE_NAME = "account-service"
PORT = int(os.getenv("PORT", 8201))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"FinCore - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class UpdateBalanceSchema(BaseModel):
    amount_delta: float
    reason: Optional[str] = "transaction"


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("Account Service connected to DB", extra={"service": SERVICE_NAME, "event_type": "db_connected"})


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


@app.get("/accounts/{account_id}")
async def get_account(account_id: str, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    cache_key = f"fin:acc:{account_id}"

    # 1. Cache lookup
    cached = await get_cached_json(cache_key)
    if cached:
        logger.info(
            f"Cache hit for account {account_id}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "cache_hit",
                "request_id": req_id,
                "trace_id": trace_id,
                "account_id": account_id,
                "dependency": "redis"
            }
        )
        return cached

    # 2. DB lookup
    row = await fetch_row(
        "SELECT account_id, customer_id, account_type, balance, currency, status FROM accounts WHERE account_id = $1",
        account_id
    )
    if not row:
        logger.warning(
            f"Account not found: {account_id}",
            extra={"service": SERVICE_NAME, "event_type": "account_not_found", "account_id": account_id}
        )
        raise HTTPException(status_code=404, detail="Account not found")

    res = dict(row)
    await set_cached_json(cache_key, res, ttl_seconds=30)
    logger.info(
        f"Retrieved account {account_id}: balance {res['balance']} {res['currency']}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "account_lookup",
            "request_id": req_id,
            "trace_id": trace_id,
            "account_id": account_id,
            "amount": res["balance"]
        }
    )
    return res


@app.put("/accounts/{account_id}/balance")
async def update_balance(account_id: str, payload: UpdateBalanceSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    row = await fetch_row("SELECT balance, status FROM accounts WHERE account_id = $1", account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    new_balance = round(row["balance"] + payload.amount_delta, 2)
    if new_balance < 0:
        logger.error(
            f"Insufficient funds for account {account_id}: requested {payload.amount_delta}, available {row['balance']}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "insufficient_funds",
                "request_id": req_id,
                "trace_id": trace_id,
                "account_id": account_id,
                "amount": payload.amount_delta
            }
        )
        raise HTTPException(status_code=400, detail="Insufficient funds")

    await execute_query("UPDATE accounts SET balance = $1, updated_at = CURRENT_TIMESTAMP WHERE account_id = $2", new_balance, account_id)
    await delete_cached_key(f"fin:acc:{account_id}")

    logger.info(
        f"Updated balance for account {account_id}: delta {payload.amount_delta} -> new balance {new_balance}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "balance_updated",
            "request_id": req_id,
            "trace_id": trace_id,
            "account_id": account_id,
            "amount": new_balance
        }
    )
    return {"account_id": account_id, "new_balance": new_balance, "delta": payload.amount_delta, "status": "SUCCESS"}
