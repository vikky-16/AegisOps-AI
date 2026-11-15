"""
FinCore Notification Service (Port 8205)
Dispatches transaction receipts, security login alerts, and compliance notices via SMS/Email/Push.
"""

import os
import sys
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fincore.common.logger import get_service_logger
from fincore.common.otel import setup_otel, TraceContextMiddleware
from fincore.common.database import init_db_pool, close_db_pool, execute_query, check_db_health

SERVICE_NAME = "notification-service"
PORT = int(os.getenv("PORT", 8205))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"FinCore - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class NotificationSchema(BaseModel):
    recipient: str
    channel: Optional[str] = "SMS"
    message: str


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("Notification Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


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
async def send_notification(payload: NotificationSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    notif_id = f"notif-{uuid.uuid4().hex[:10]}"

    await execute_query(
        """
        INSERT INTO notifications (notification_id, recipient, channel, status, message)
        VALUES ($1, $2, $3, 'DELIVERED', $4)
        """,
        notif_id, payload.recipient, payload.channel, payload.message
    )

    logger.info(
        f"Notification {notif_id} dispatched to {payload.recipient} via {payload.channel}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "notification_sent",
            "request_id": req_id,
            "trace_id": trace_id,
            "notification_id": notif_id
        }
    )

    return {"notification_id": notif_id, "status": "DELIVERED", "channel": payload.channel}
