"""
CloudDesk Billing Service (Port 8304)
Aggregates real-time cloud resource consumption, compute hours, storage GBs, and billing invoices.
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
from clouddesk.common.database import init_db_pool, close_db_pool, execute_query, fetch_rows, check_db_health

SERVICE_NAME = "billing-service"
PORT = int(os.getenv("PORT", 8304))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"CloudDesk - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class MeterRecordSchema(BaseModel):
    project_id: str
    resource_type: str
    units_consumed: float
    cost: float


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("Billing Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


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


@app.post("/billing/meter")
async def meter_resource(payload: MeterRecordSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    record_id = f"bill-{uuid.uuid4().hex[:10]}"

    await execute_query(
        """
        INSERT INTO billing_records (record_id, project_id, resource_type, units_consumed, cost)
        VALUES ($1, $2, $3, $4, $5)
        """,
        record_id, payload.project_id, payload.resource_type, payload.units_consumed, payload.cost
    )

    logger.info(
        f"Metered usage for {payload.project_id}: {payload.units_consumed} {payload.resource_type} = ${payload.cost}",
        extra={
            "service": SERVICE_NAME,
            "event_type": "resource_metered",
            "request_id": req_id,
            "trace_id": trace_id,
            "project_id": payload.project_id,
            "resource_type": payload.resource_type,
            "cost": payload.cost
        }
    )

    return {"record_id": record_id, "status": "RECORDED", "cost": payload.cost}


@app.get("/billing/project/{project_id}")
async def get_project_billing(project_id: str):
    rows = await fetch_rows(
        "SELECT record_id, resource_type, units_consumed, cost, timestamp FROM billing_records WHERE project_id = $1 ORDER BY timestamp DESC LIMIT 20",
        project_id
    )
    total_cost = sum(r["cost"] for r in rows)
    return {"project_id": project_id, "total_cost": round(total_cost, 2), "records": [dict(r) for r in rows]}
