"""
CloudDesk Project Service (Port 8302)
Manages cloud tenant workspaces, project configurations, and resource quota policies.
"""

import os
import sys
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from clouddesk.common.logger import get_service_logger
from clouddesk.common.otel import setup_otel, TraceContextMiddleware
from clouddesk.common.database import init_db_pool, close_db_pool, fetch_row, execute_query, check_db_health
from clouddesk.common.cache import get_cached_json, set_cached_json, check_redis_health

SERVICE_NAME = "project-service"
PORT = int(os.getenv("PORT", 8302))

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(title=f"CloudDesk - {SERVICE_NAME}", version="1.0.0")
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)


class CreateProjectSchema(BaseModel):
    name: str
    owner_id: str
    plan: Optional[str] = "TEAM_PRO"


@app.on_event("startup")
async def startup():
    await init_db_pool()
    logger.info("Project Service started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


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


@app.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(payload: CreateProjectSchema, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)
    project_id = f"prj-{uuid.uuid4().hex[:10]}"

    await execute_query(
        """
        INSERT INTO projects (project_id, name, owner_id, plan, status)
        VALUES ($1, $2, $3, $4, 'ACTIVE')
        """,
        project_id, payload.name, payload.owner_id, payload.plan
    )

    logger.info(
        f"Project created: {project_id} ('{payload.name}', Owner: {payload.owner_id})",
        extra={
            "service": SERVICE_NAME,
            "event_type": "project_created",
            "request_id": req_id,
            "trace_id": trace_id,
            "project_id": project_id,
            "user_id": payload.owner_id
        }
    )

    return {"project_id": project_id, "name": payload.name, "owner_id": payload.owner_id, "status": "ACTIVE"}


@app.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    req_id = getattr(request.state, "request_id", None)
    trace_id = getattr(request.state, "trace_id", None)

    row = await fetch_row("SELECT project_id, name, owner_id, plan, status, created_at FROM projects WHERE project_id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info(
        f"Retrieved project {project_id}",
        extra={"service": SERVICE_NAME, "event_type": "project_lookup", "request_id": req_id, "project_id": project_id}
    )
    return dict(row)
