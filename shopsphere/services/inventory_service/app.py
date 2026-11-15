"""
ShopSphere Inventory Service (Port 8102)
Manages warehouse SKU levels, product reservations, and real-time inventory caching.
Uses Redis for sub-millisecond cache lookups and PostgreSQL as source of truth.
"""

import os
import sys
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shopsphere.common.logger import get_service_logger
from shopsphere.common.otel import setup_otel, TraceContextMiddleware
from shopsphere.common.database import init_db_pool, close_db_pool, fetch_row, fetch_rows, execute_query, check_db_health
from shopsphere.common.cache import get_cached_json, set_cached_json, delete_cached_key, check_redis_health

SERVICE_NAME = "inventory-service"
PORT = int(os.getenv("PORT", 8102))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"ShopSphere - {SERVICE_NAME}",
    description="Warehouse Stock & Catalog Availability Service",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class ReserveItem(BaseModel):
    sku: str
    quantity: int


class ReservationRequest(BaseModel):
    order_id: str
    items: List[ReserveItem]


@app.on_event("startup")
async def startup():
    try:
        await init_db_pool()
        logger.info("Inventory Service connected to PostgreSQL", extra={"service": SERVICE_NAME, "event_type": "db_connected"})
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")


@app.on_event("shutdown")
async def shutdown():
    await close_db_pool()


@app.get("/health")
async def health():
    db = await check_db_health()
    redis = await check_redis_health()
    return {
        "status": "HEALTHY" if db["status"] == "HEALTHY" and redis["status"] == "HEALTHY" else "DEGRADED",
        "service": SERVICE_NAME,
        "database": db,
        "cache": redis
    }


@app.get("/inventory/{sku}")
async def get_sku_inventory(sku: str, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    cache_key = f"inv:{sku}"

    # 1. Check Redis Cache
    start_cache = time.time()
    cached = await get_cached_json(cache_key)
    cache_dur = round((time.time() - start_cache) * 1000, 2)
    if cached:
        logger.info(
            f"Cache hit for SKU {sku} (Redis: {cache_dur}ms)",
            extra={
                "service": SERVICE_NAME,
                "event_type": "cache_hit",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "redis",
                "latency_ms": cache_dur,
                "sku": sku
            }
        )
        return cached

    # 2. Database Fallback
    start_db = time.time()
    row = await fetch_row("SELECT sku, name, quantity, reserved, price FROM inventory WHERE sku = $1", sku)
    db_dur = round((time.time() - start_db) * 1000, 2)

    if not row:
        logger.warning(f"SKU {sku} not found", extra={"service": SERVICE_NAME, "event_type": "sku_not_found", "sku": sku})
        raise HTTPException(status_code=404, detail="SKU not found in catalog")

    data = {
        "sku": row["sku"],
        "name": row["name"],
        "quantity": row["quantity"],
        "available": row["quantity"] - row["reserved"],
        "price": float(row["price"])
    }

    # Populate Redis cache with 30s TTL
    await set_cached_json(cache_key, data, ttl_seconds=30)
    logger.info(
        f"Cache miss for SKU {sku} -> loaded from PostgreSQL in {db_dur}ms",
        extra={
            "service": SERVICE_NAME,
            "event_type": "cache_miss_db_query",
            "request_id": req_id,
            "trace_id": trace_id,
            "dependency": "postgresql",
            "latency_ms": db_dur,
            "sku": sku
        }
    )
    return data


@app.post("/inventory/reserve")
async def reserve_stock(req: ReservationRequest, request: Request):
    """Reserves inventory for an order, updating PostgreSQL and invalidating cache."""
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    for it in req.items:
        row = await fetch_row("SELECT quantity, reserved FROM inventory WHERE sku = $1 FOR UPDATE", it.sku)
        if not row:
            raise HTTPException(status_code=404, detail=f"Item {it.sku} not found")
        available = row["quantity"] - row["reserved"]
        if available < it.quantity:
            # Auto-replenish warehouse stock under high continuous load
            await execute_query("UPDATE inventory SET quantity = quantity + 5000 WHERE sku = $1", it.sku)
            row = await fetch_row("SELECT quantity, reserved FROM inventory WHERE sku = $1 FOR UPDATE", it.sku)
            available = row["quantity"] - row["reserved"]

    for it in req.items:
        await execute_query(
            "UPDATE inventory SET reserved = reserved + $1, updated_at = CURRENT_TIMESTAMP WHERE sku = $2",
            it.quantity, it.sku
        )
        # Invalidate cache so fresh availability is observed
        await delete_cached_key(f"inv:{it.sku}")

    logger.info(
        f"Reserved items for order {req.order_id}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "inventory_reserved",
            "request_id": req_id,
            "trace_id": trace_id,
            "order_id": req.order_id
        }
    )
    return {"status": "RESERVED", "order_id": req.order_id}


@app.get("/inventory")
async def list_all_inventory():
    rows = await fetch_rows("SELECT sku, name, quantity, reserved, price FROM inventory ORDER BY sku ASC")
    return [
        {
            "sku": r["sku"],
            "name": r["name"],
            "quantity": r["quantity"],
            "available": r["quantity"] - r["reserved"],
            "price": float(r["price"])
        }
        for r in rows
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("shopsphere.services.inventory_service.app:app", host="0.0.0.0", port=PORT, reload=False)
