"""
ShopSphere Notification Service (Port 8104)
Dispatches and records email and SMS order confirmations.
Persists communication delivery events in PostgreSQL notifications table.
"""

import os
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shopsphere.common.logger import get_service_logger
from shopsphere.common.otel import setup_otel, TraceContextMiddleware
from shopsphere.common.database import init_db_pool, close_db_pool, execute_query, fetch_rows, check_db_health

SERVICE_NAME = "notification-service"
PORT = int(os.getenv("PORT", 8104))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"ShopSphere - {SERVICE_NAME}",
    description="Customer Communication & Notification Engine",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class NotificationRequest(BaseModel):
    order_id: str
    recipient: str
    channel: Optional[str] = "EMAIL"
    message: str


@app.on_event("startup")
async def startup():
    try:
        await init_db_pool()
        logger.info("Notification Service connected to PostgreSQL", extra={"service": SERVICE_NAME, "event_type": "db_connected"})
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


@app.post("/notifications/send")
async def send_notification(req: NotificationRequest, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    notif_id = f"notif-{uuid.uuid4().hex[:12]}"

    # Simulate fast async delivery dispatch (5ms)
    await asyncio.sleep(0.005)

    start_db = time.time()
    try:
        await execute_query(
            """
            INSERT INTO notifications (notification_id, order_id, recipient, channel, status, message)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            notif_id, req.order_id, req.recipient, req.channel or "EMAIL", "SENT", req.message
        )
        db_dur = round((time.time() - start_db) * 1000, 2)
        logger.info(
            f"Notification {notif_id} dispatched via {req.channel} for order {req.order_id} [DB: {db_dur}ms]",
            extra={
                "service": SERVICE_NAME,
                "event_type": "notification_sent",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "postgresql",
                "latency_ms": db_dur,
                "order_id": req.order_id
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to record notification: {e}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "notification_failed",
                "request_id": req_id,
                "trace_id": trace_id,
                "dependency": "postgresql",
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise HTTPException(status_code=500, detail="Database write failure during notification")

    return {
        "notification_id": notif_id,
        "order_id": req.order_id,
        "status": "SENT",
        "channel": req.channel
    }


@app.get("/notifications/order/{order_id}")
async def get_order_notifications(order_id: str):
    rows = await fetch_rows("SELECT notification_id, order_id, recipient, channel, status, message, created_at FROM notifications WHERE order_id = $1", order_id)
    return [
        {
            "notification_id": r["notification_id"],
            "order_id": r["order_id"],
            "recipient": r["recipient"],
            "channel": r["channel"],
            "status": r["status"],
            "message": r["message"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None
        }
        for r in rows
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("shopsphere.services.notification_service.app:app", host="0.0.0.0", port=PORT, reload=False)
