"""
FinCore API Gateway (Port 8200)
Edge ingress and API router for FinCore Financial Services.
Routes requests to Account, Transaction, Payment, Fraud, and Notification microservices,
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

from fincore.common.logger import get_service_logger
from fincore.common.otel import setup_otel, TraceContextMiddleware, get_outgoing_headers

SERVICE_NAME = "api-gateway"
PORT = int(os.getenv("PORT", 8200))
IN_DOCKER = os.path.exists("/.dockerenv")

DEFAULT_ACCOUNT_URL = "http://account-service:8201" if IN_DOCKER else "http://127.0.0.1:8201"
DEFAULT_TX_URL = "http://transaction-service:8202" if IN_DOCKER else "http://127.0.0.1:8202"
DEFAULT_PAYMENT_URL = "http://payment-service:8203" if IN_DOCKER else "http://127.0.0.1:8203"
DEFAULT_FRAUD_URL = "http://fraud-service:8204" if IN_DOCKER else "http://127.0.0.1:8204"
DEFAULT_NOTIF_URL = "http://notification-service:8205" if IN_DOCKER else "http://127.0.0.1:8205"

ACCOUNT_URL = os.getenv("ACCOUNT_SERVICE_URL", DEFAULT_ACCOUNT_URL).rstrip("/")
TX_URL = os.getenv("TRANSACTION_SERVICE_URL", DEFAULT_TX_URL).rstrip("/")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", DEFAULT_PAYMENT_URL).rstrip("/")
FRAUD_URL = os.getenv("FRAUD_SERVICE_URL", DEFAULT_FRAUD_URL).rstrip("/")
NOTIF_URL = os.getenv("NOTIFICATION_SERVICE_URL", DEFAULT_NOTIF_URL).rstrip("/")

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"FinCore - {SERVICE_NAME}",
    description="FinCore Financial API Gateway",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

http_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    logger.info("FinCore API Gateway started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


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
        "tenant_id": "fincore",
        "company": "FinCore",
        "timestamp": time.time()
    }


# Account routes
@app.get("/api/v1/accounts/{account_id}")
async def get_account(account_id: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(f"{ACCOUNT_URL}/accounts/{account_id}", headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Account Service unavailable: {str(exc)}")


@app.put("/api/v1/accounts/{account_id}/balance")
async def update_balance(account_id: str, request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.put(f"{ACCOUNT_URL}/accounts/{account_id}/balance", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Account Service unavailable: {str(exc)}")


# Transaction routes
@app.post("/api/v1/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{TX_URL}/transactions", json=body, headers=headers, timeout=8.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Transaction Service unavailable: {str(exc)}")


@app.post("/api/v1/transactions/validate")
async def validate_transaction(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{TX_URL}/transactions/validate", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Transaction Service unavailable: {str(exc)}")


@app.get("/api/v1/transactions/history/{account_id}")
async def get_history(account_id: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(f"{TX_URL}/transactions/history/{account_id}", headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Transaction Service unavailable: {str(exc)}")


# Payment route
@app.post("/api/v1/payments/process")
async def process_payment(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{PAYMENT_URL}/payments/process", json=body, headers=headers, timeout=8.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Payment Service unavailable: {str(exc)}")


# Fraud check route
@app.post("/api/v1/fraud/check")
async def fraud_check(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{FRAUD_URL}/fraud/check", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Fraud Service unavailable: {str(exc)}")


# Notification route
@app.post("/api/v1/notifications/send")
async def send_notification(request: Request):
    body = await request.json()
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.post(f"{NOTIF_URL}/notifications/send", json=body, headers=headers, timeout=6.0)
        return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Notification Service unavailable: {str(exc)}")
