"""
Gateway Microservice - Port 8001
Ingress point for distributed requests. Forwards to Service A.
"""

import sys
import os
import time
import uuid
import httpx
import uvicorn
from typing import Optional
from fastapi import Request, Response, HTTPException, status
from pydantic import BaseModel

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services.base_service import BaseService

gateway_service = BaseService(
    name="gateway",
    port=8001,
    role="API Gateway & Ingress Router",
    dependencies=["auth-service", "service-a"]
)
app = gateway_service.app

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:8005")
SERVICE_A_URL = os.environ.get("SERVICE_A_URL", "http://127.0.0.1:8002")


@app.get("/work")
@app.post("/work")
async def handle_work(request: Request):
    """
    Ingress endpoint simulating client web/API traffic.
    Authenticates with Auth Service, then invokes Service A (Orders).
    """
    trace_id = request.headers.get("X-Trace-ID") or uuid.uuid4().hex
    start_time = time.time()
    gateway_service.log_event("INFO", "REQUEST_RECEIVED", "Incoming ingress request at Gateway", trace_id)
    
    headers = {"X-Trace-ID": trace_id}
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # 1. Step: Verify credentials with Auth Service
            auth_resp = await client.get(f"{AUTH_SERVICE_URL}/work", headers=headers)
            if auth_resp.status_code >= 400:
                gateway_service.log_event(
                    "ERROR",
                    "AUTH_VERIFICATION_FAILED",
                    f"Auth Service returned HTTP {auth_resp.status_code}",
                    trace_id,
                    {"status": auth_resp.status_code}
                )
                return Response(
                    content=auth_resp.text,
                    status_code=auth_resp.status_code,
                    media_type="application/json"
                )

            # 2. Step: Forward to Service A (Order Engine)
            resp = await client.get(f"{SERVICE_A_URL}/work", headers=headers)
            elapsed = (time.time() - start_time) * 1000
            
            if resp.status_code >= 500:
                gateway_service.log_event(
                    "ERROR",
                    "UPSTREAM_SERVICE_ERROR",
                    f"Upstream Service A returned HTTP {resp.status_code}",
                    trace_id,
                    {"upstream_status": resp.status_code, "latency_ms": elapsed}
                )
                return Response(
                    content=resp.text,
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    media_type="application/json"
                )
            
            gateway_service.log_event("INFO", "REQUEST_SUCCESS", "Ingress request routed and completed successfully across topology", trace_id)
            return {
                "message": "Gateway successfully routed request through full microservices topology (gateway -> auth -> orders -> payment -> database)",
                "trace_id": trace_id,
                "latency_ms": round(elapsed, 2),
                "auth_status": "VERIFIED",
                "order_data": resp.json()
            }
            
    except httpx.TimeoutException:
        gateway_service.log_event("ERROR", "UPSTREAM_TIMEOUT", "Gateway timed out waiting for Service A", trace_id)
        return Response(
            content='{"error": "Gateway Timeout (504)", "failed_upstream": "service-a"}',
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            media_type="application/json"
        )
    except httpx.RequestError as exc:
        gateway_service.log_event("ERROR", "UPSTREAM_UNREACHABLE", f"Cannot connect to Service A: {str(exc)}", trace_id)
        return Response(
            content=f'{{"error": "Bad Gateway (502) - Service A unreachable", "details": "{str(exc)}"}}',
            status_code=status.HTTP_502_BAD_GATEWAY,
            media_type="application/json"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")
