"""
CloudDesk Notification Service (Port 8305)
Dispatches infrastructure alerts, instance status changes, and DevOps webhook notifications.
"""

import os
import sys
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from clouddesk.common.logger import get_service_logger
from clouddesk.common.otel import setup_otel, TraceContextMiddleware
from clouddesk.common.database import init_db_pool, close_db_pool, execute_query, check_db_health

SERVICE_NAME = "notification-service"
PORT = int(os.getenv("PORT", 8305))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"CloudDesk - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class NotificationSchema(BaseModel):
    user_id: str
    channel: Optional[str] = "SLACK"
    subject: str
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
        INSERT INTO notifications (notification_id, user_id, channel, status, subject, message)
        VALUES ($1, $2, $3, 'DELIVERED', $4, $5)
        """,
        notif_id, payload.user_id, payload.channel, payload.subject, payload.message
    )

    logger.info(
        f"Notification {notif_id} dispatched: '{payload.subject}' to {payload.user_id} via {payload.channel}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "cloud_alert_sent",
            "request_id": req_id,
            "trace_id": trace_id,
            "notification_id": notif_id
        }
    )

    return {"notification_id": notif_id, "status": "DELIVERED", "channel": payload.channel}
