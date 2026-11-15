"""
ShopSphere Order Service (Port 8101)
Coordinates the order fulfillment lifecycle:
- Reserves stock in Inventory Service
- Authorizes transaction via Payment Service
- Persists order records in PostgreSQL
- Triggers async customer notification via Notification Service
- Supports real DB latency injection for Phase 11 chaos testing
"""

import os
import sys
import time
import uuid
import httpx
from decimal import Decimal
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, Response, HTTPException, status
from pydantic import BaseModel

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shopsphere.common.logger import get_service_logger
from shopsphere.common.otel import setup_otel, TraceContextMiddleware, get_outgoing_headers
from shopsphere.common.database import (
    init_db_pool,
    close_db_pool,
    execute_query,
    fetch_row,
    fetch_rows,
    check_db_health,
    set_failure_simulation,
    get_failure_status
)

SERVICE_NAME = "order-service"
PORT = int(os.getenv("PORT", 8101))
IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_INVENTORY_URL = "http://inventory-service:8102" if IN_DOCKER else "http://127.0.0.1:8102"
DEFAULT_PAYMENT_URL = "http://payment-service:8103" if IN_DOCKER else "http://127.0.0.1:8103"
DEFAULT_NOTIF_URL = "http://notification-service:8104" if IN_DOCKER else "http://127.0.0.1:8104"
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", DEFAULT_INVENTORY_URL).rstrip("/")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", DEFAULT_PAYMENT_URL).rstrip("/")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", DEFAULT_NOTIF_URL).rstrip("/")

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"ShopSphere - {SERVICE_NAME}",
    description="E-Commerce Order Orchestration & Management Service",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

http_client: Optional[httpx.AsyncClient] = None


class OrderItemSchema(BaseModel):
    sku: str
    quantity: int
    price: float


class CreateOrderSchema(BaseModel):
    customer_id: str
    items: List[OrderItemSchema]
    payment_method: Optional[str] = "credit_card"


class FailureInjectionSchema(BaseModel):
    latency_ms: float = 0.0
    exhaust_connections: bool = False


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=8.0)
    try:
        await init_db_pool()
        logger.info("Order Service connected to PostgreSQL", extra={"service": SERVICE_NAME, "event_type": "db_connected"})
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}", extra={"service": SERVICE_NAME, "event_type": "db_error"})


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    await close_db_pool()


@app.get("/health")
async def health():
    db_status = await check_db_health()
    is_healthy = db_status["status"] == "HEALTHY"
    return {
        "status": "HEALTHY" if is_healthy else "DEGRADED",
        "service": SERVICE_NAME,
        "database": db_status,
        "chaos_status": get_failure_status()
    }


@app.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(order_data: CreateOrderSchema, request: Request):
    """
    Main checkout pipeline:
    1. Reserve stock in Inventory Service
    2. Process payment in Payment Service
    3. Persist order in PostgreSQL
    4. Trigger notification in Notification Service
    """
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    span_id = getattr(request.state, "span_id", None)
    headers = get_outgoing_headers(request)

    order_id = f"ord-{uuid.uuid4().hex[:10]}"
    total_amount = sum(item.price * item.quantity for item in order_data.items)

    logger.info(
        f"Processing new order {order_id} for customer {order_data.customer_id} (Total: ${total_amount:.2f})",
        extra={
            "service": SERVICE_NAME,
            "event_type": "order_started",
            "request_id": req_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "order_id": order_id,
            "customer_id": order_data.customer_id
        }
    )

    # Step 1: Reserve Inventory
    start_inv = time.time()
    try:
        reserve_payload = {
            "order_id": order_id,
            "items": [{"sku": it.sku, "quantity": it.quantity} for it in order_data.items]
        }
        inv_resp = await http_client.post(
            f"{INVENTORY_SERVICE_URL}/inventory/reserve",
            json=reserve_payload,
            headers=headers,
            timeout=10.0
        )
        if inv_resp.status_code != 200:
            logger.warning(
                f"Inventory reservation failed for {order_id}",
                extra={
                    "service": SERVICE_NAME,
                    "event_type": "inventory_insufficient",
                    "request_id": req_id,
                    "trace_id": trace_id,
                    "order_id": order_id,
                    "dependency": "inventory-service"
                }
            )
            raise HTTPException(status_code=400, detail="Insufficient inventory for one or more items")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Inventory Service unavailable")

    # Step 2: Process Payment
    try:
        pay_payload = {
            "order_id": order_id,
            "customer_id": order_data.customer_id,
            "amount": total_amount,
            "payment_method": order_data.payment_method
        }
        pay_resp = await http_client.post(
            f"{PAYMENT_SERVICE_URL}/payments/process",
            json=pay_payload,
            headers=headers,
            timeout=10.0
        )
        if pay_resp.status_code != 200:
            raise HTTPException(status_code=402, detail="Payment authorization declined")
        payment_info = pay_resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Payment Service unavailable")

    # Step 3: Persist Order in PostgreSQL (Real Database Queries)
    start_db = time.time()
    try:
        await execute_query(
            """
            INSERT INTO orders (order_id, customer_id, total_amount, status)
            VALUES ($1, $2, $3, $4)
            """,
            order_id, order_data.customer_id, Decimal(str(round(total_amount, 2))), "CONFIRMED"
        )

        for item in order_data.items:
            await execute_query(
                """
                INSERT INTO order_items (order_id, sku, quantity, price)
                VALUES ($1, $2, $3, $4)
                """,
                order_id, item.sku, item.quantity, Decimal(str(round(item.price, 2)))
            )
        db_duration = round((time.time() - start_db) * 1000, 2)
        logger.info(
            f"Persisted order {order_id} to PostgreSQL in {db_duration}ms",
            extra={
                "service": SERVICE_NAME,
                "event_type": "db_query",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "postgresql",
                "latency_ms": db_duration,
                "order_id": order_id
            }
        )
    except Exception as exc:
        db_duration = round((time.time() - start_db) * 1000, 2)
        logger.error(
            f"PostgreSQL order insert failed: {str(exc)}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "db_error",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "postgresql",
                "latency_ms": db_duration,
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Database write failed")

    # Step 4: Dispatch Notification
    try:
        notif_payload = {
            "order_id": order_id,
            "recipient": f"{order_data.customer_id}@example.com",
            "channel": "EMAIL",
            "message": f"Your ShopSphere order {order_id} for ${total_amount:.2f} has been confirmed!"
        }
        await http_client.post(
            f"{NOTIFICATION_SERVICE_URL}/notifications/send",
            json=notif_payload,
            headers=headers,
            timeout=3.0
        )
    except Exception as e:
        # Notifications are non-blocking for order fulfillment
        logger.warning(f"Async notification failed for {order_id}: {e}")

    logger.info(
        f"Order {order_id} fulfilled successfully",
        extra={
            "service": SERVICE_NAME,
            "event_type": "order_created",
            "request_id": req_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "order_id": order_id,
            "status_code": 201
        }
    )

    return {
        "order_id": order_id,
        "customer_id": order_data.customer_id,
        "total_amount": round(total_amount, 2),
        "status": "CONFIRMED",
        "payment_id": payment_info.get("payment_id"),
        "items": [it.dict() for it in order_data.items]
    }


@app.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    
    start_db = time.time()
    row = await fetch_row("SELECT * FROM orders WHERE order_id = $1", order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
        
    items = await fetch_rows("SELECT sku, quantity, price FROM order_items WHERE order_id = $1", order_id)
    db_duration = round((time.time() - start_db) * 1000, 2)
    
    logger.info(
        f"Retrieved order {order_id} from PostgreSQL in {db_duration}ms",
        extra={
            "service": SERVICE_NAME,
            "event_type": "db_query",
            "request_id": req_id,
            "trace_id": trace_id,
            "dependency": "postgresql",
            "latency_ms": db_duration,
            "order_id": order_id
        }
    )
    return {
        "order_id": row["order_id"],
        "customer_id": row["customer_id"],
        "total_amount": float(row["total_amount"]),
        "status": row["status"],
        "created_at": (row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"])) if row["created_at"] else None,
        "items": [{"sku": r["sku"], "quantity": r["quantity"], "price": float(r["price"])} for r in items]
    }


@app.get("/orders")
async def list_orders(limit: int = 20):
    rows = await fetch_rows("SELECT order_id, customer_id, total_amount, status, created_at FROM orders ORDER BY created_at DESC LIMIT $1", limit)
    return [
        {
            "order_id": r["order_id"],
            "customer_id": r["customer_id"],
            "total_amount": float(r["total_amount"]),
            "status": r["status"],
            "created_at": (r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"])) if r["created_at"] else None
        }
        for r in rows
    ]


# Phase 11 Real Chaos Injection Endpoints
@app.post("/inject/db-latency")
async def inject_db_latency(params: FailureInjectionSchema):
    """
    Directly injects real database query latency or connection pool exhaustion.
    Causes queries to block for `latency_ms` milliseconds, creating real cascading latency.
    """
    set_failure_simulation(latency_ms=params.latency_ms, exhaust_connections=params.exhaust_connections, target_service=SERVICE_NAME)
    logger.warning(
        f"Injected REAL database latency: {params.latency_ms}ms (exhaust={params.exhaust_connections})",
        extra={
            "service": SERVICE_NAME,
            "event_type": "chaos_injection",
            "dependency": "postgresql",
            "latency_ms": params.latency_ms
        }
    )
    return {"status": "INJECTED", "chaos_status": get_failure_status()}


@app.post("/inject/db-reset")
async def reset_db_latency():
    set_failure_simulation(latency_ms=0.0, exhaust_connections=False)
    logger.info("Reset database failure injection to normal", extra={"service": SERVICE_NAME, "event_type": "chaos_reset"})
    return {"status": "RESET", "chaos_status": get_failure_status()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("shopsphere.services.order_service.app:app", host="0.0.0.0", port=PORT, reload=False)
