"""
ShopSphere API Gateway (Port 8100)
Entry point for external client traffic and traffic generator.
Routes requests to Order Service and Inventory Service, propagating W3C trace context.
"""

import os
import sys
import time
import httpx
from fastapi import FastAPI, Request, Response, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shopsphere.common.logger import get_service_logger
from shopsphere.common.otel import setup_otel, TraceContextMiddleware, get_outgoing_headers

SERVICE_NAME = "api-gateway"
PORT = int(os.getenv("PORT", 8100))
IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_ORDER_URL = "http://order-service:8101" if IN_DOCKER else "http://127.0.0.1:8101"
DEFAULT_INVENTORY_URL = "http://inventory-service:8102" if IN_DOCKER else "http://127.0.0.1:8102"
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", DEFAULT_ORDER_URL).rstrip("/")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", DEFAULT_INVENTORY_URL).rstrip("/")

logger = get_service_logger(SERVICE_NAME)
tracer, meter = setup_otel(SERVICE_NAME)

app = FastAPI(
    title=f"ShopSphere - {SERVICE_NAME}",
    description="E-Commerce API Gateway & Edge Ingress",
    version="1.0.0"
)
app.add_middleware(TraceContextMiddleware, service_name=SERVICE_NAME, logger=logger)

http_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    logger.info("ShopSphere API Gateway started", extra={"service": SERVICE_NAME, "event_type": "service_startup"})


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
        "tenant_id": "shopsphere",
        "timestamp": time.time()
    }


@app.post("/api/v1/orders", status_code=status.HTTP_201_CREATED)
async def create_order(request: Request):
    """Entry point for checkout / order placement."""
    body = await request.json()
    headers = get_outgoing_headers(request)
    
    logger.info(
        f"Gateway routing create_order request to Order Service",
        extra={
            "service": SERVICE_NAME,
            "event_type": "gateway_route",
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "span_id": getattr(request.state, "span_id", None),
            "dependency": "order-service",
            "customer_id": body.get("customer_id")
        }
    )

    try:
        resp = await http_client.post(
            f"{ORDER_SERVICE_URL}/orders",
            json=body,
            headers=headers,
            timeout=8.0
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.json() if resp.content else "Order error")
        return resp.json()
    except httpx.RequestError as exc:
        logger.error(
            f"Gateway failed to reach Order Service: {str(exc)}",
            extra={
                "service": SERVICE_NAME,
                "event_type": "dependency_failure",
                "request_id": getattr(request.state, "request_id", None),
                "trace_id": getattr(request.state, "trace_id", None),
                "dependency": "order-service",
                "http_status": 503,
                "status_code": 503,
                "latency_ms": 4000.0,
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            }
        )
        raise HTTPException(status_code=503, detail="Order Service unavailable")


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(
            f"{ORDER_SERVICE_URL}/orders/{order_id}",
            headers=headers,
            timeout=5.0
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.json() if resp.content else "Order not found")
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Order Service unavailable")


@app.get("/api/v1/inventory/{sku}")
async def get_inventory(sku: str, request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(
            f"{INVENTORY_SERVICE_URL}/inventory/{sku}",
            headers=headers,
            timeout=5.0
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.json() if resp.content else "Inventory error")
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Inventory Service unavailable")


@app.get("/api/v1/catalog")
async def get_catalog(request: Request):
    headers = get_outgoing_headers(request)
    try:
        resp = await http_client.get(
            f"{INVENTORY_SERVICE_URL}/inventory",
            headers=headers,
            timeout=5.0
        )
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Inventory Service unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("shopsphere.services.gateway.app:app", host="0.0.0.0", port=PORT, reload=False)
