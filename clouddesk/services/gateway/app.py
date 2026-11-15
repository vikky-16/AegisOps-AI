"""
CloudDesk API Gateway (Port 8300)
Edge ingress and API router for CloudDesk SaaS & Cloud Infrastructure Platform.
Routes requests to User, Project, Compute, Billing, and Notification microservices,
propagating W3C TraceContext and X-Request-ID headers.
"""

import os
import sys
import time
import httpx
from fastapi import FastAPI, Request, Response, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from clouddesk.common.logger import get_service_logger
from clouddesk.common.otel import setup_otel, TraceContextMiddleware, get_outgoing_headers

SERVICE_NAME = "api-gateway"
PORT = int(os.getenv("PORT", 8300))
IN_DOCKER = os.path.exists("/.dockerenv")

DEFAULT_USER_URL = "http://user-service:8301" if IN_DOCKER else "http://127.0.0.1:8301"
DEFAULT_PROJECT_URL = "http://project-service:8302" if IN_DOCKER else "http://127.0.0.1:8302"
DEFAULT_COMPUTE_URL = "http://compute-service:8303" if IN_DOCKER else "http://127.0.0.1:8303"
DEFAULT_BILLING_URL = "http://billing-service:8304" if IN_DOCKER else "http://127.0.0.1:8304"
DEFAULT_NOTIF_URL = "http://notification-service:8305" if IN_DOCKER else "http://127.0.0.1:8305"

USER_URL = os.getenv("USER_SERVICE_URL", DEFAULT_USER_URL).rstrip("/")
PROJECT_URL = os.getenv("PROJECT_SERVICE_URL", DEFAULT_PROJECT_URL).rstrip("/")
COMPUTE_URL = os.getenv("COMPUTE_SERVICE_URL", DEFAULT_COMPUTE_URL).rstrip("/")
BILLING_URL = os.getenv("BILLING_SERVICE_URL", DEFAULT_BILLING_URL).rstrip("/")
NOTIF_URL = os.getenv("NOTIFICATION_SERVICE_URL", DEFAULT_NOTIF_URL).rstrip("/")

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"CloudDesk - {SERVICE_NAME}",
    description="CloudDesk Cloud Edge API Gateway",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

http_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    logger.info("CloudDesk API Gateway started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()


@app.get("/health")
async def health():
    return {
        "status": "HEALTHY",
        "service": SERVICE_NAME,
        "tenant_id": "clouddesk",
        "company": "CloudDesk",
        "timestamp": time.time()
    }


# User routes
@app.post("/api/v1/users/login")
async def user_login(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{USER_URL}/users/login", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"User Service unavailable: {str(exc)}")


@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(f"{USER_URL}/users/{user_id}", headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"User Service unavailable: {str(exc)}")


# Project routes
@app.post("/api/v1/projects", status_code=status.HTTP_201_CREATED)
async def create_project(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{PROJECT_URL}/projects", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Project Service unavailable: {str(exc)}")


@app.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(f"{PROJECT_URL}/projects/{project_id}", headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Project Service unavailable: {str(exc)}")


# Compute routes
@app.post("/api/v1/compute/instances", status_code=status.HTTP_201_CREATED)
async def create_instance(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{COMPUTE_URL}/compute/instances", json=body, headers=headers, timeout=8.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Compute Service unavailable: {str(exc)}")


@app.get("/api/v1/compute/instances/{instance_id}/status")
async def get_instance_status(instance_id: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(f"{COMPUTE_URL}/compute/instances/{instance_id}/status", headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Compute Service unavailable: {str(exc)}")


# Billing routes
@app.post("/api/v1/billing/meter")
async def meter_billing(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{BILLING_URL}/billing/meter", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Billing Service unavailable: {str(exc)}")


# Notification routes
@app.post("/api/v1/notifications/send")
async def send_notification(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{NOTIF_URL}/notifications/send", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Notification Service unavailable: {str(exc)}")
