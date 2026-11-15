"""
Service A (Order Processing Service) - Port 8002
Processes orders and calls Service B (Payment & Inventory).
"""

import sys
import os
import time
import httpx
import uvicorn
from typing import Optional
from fastapi import Request, Response, HTTPException, status

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services.base_service import BaseService

service_a = BaseService(
    name="service-a",
    port=8002,
    role="Order Processing Engine",
    dependencies=["service-b"]
)
app = service_a.app

SERVICE_B_URL = os.environ.get("SERVICE_B_URL", "http://127.0.0.1:8003")


@app.get("/work")
@app.post("/work")
async def handle_order(request: Request):
    """
    Simulates processing an order and invoking downstream Service B.
    """
    trace_id = request.headers.get("X-Trace-ID")
    start_time = time.time()
    service_a.log_event("INFO", "ORDER_INITIATED", "Processing order transaction in Service A", trace_id)
    
    headers = {"X-Trace-ID": trace_id} if trace_id else {}
    
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(f"{SERVICE_B_URL}/work", headers=headers)
            elapsed = (time.time() - start_time) * 1000
            
            if resp.status_code >= 500:
                service_a.log_event(
                    "ERROR",
                    "DEPENDENCY_PAYMENT_FAILURE",
                    f"Service B payment processing failed with HTTP {resp.status_code}",
                    trace_id,
                    {"status": resp.status_code}
                )
                return Response(
                    content=resp.text,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    media_type="application/json"
                )
            
            service_a.log_event("INFO", "ORDER_COMPLETED", "Order successfully verified and authorized", trace_id)
            return {
                "service": "service-a",
                "order_id": f"ORD-{int(time.time()*1000) % 1000000}",
                "status": "APPROVED",
                "latency_ms": round(elapsed, 2),
                "downstream_payment": resp.json()
            }
            
    except httpx.TimeoutException:
        service_a.log_event("ERROR", "PAYMENT_SERVICE_TIMEOUT", "Service B timed out during payment authorization", trace_id)
        return Response(
            content='{"error": "Payment Service Timeout", "failed_dependency": "service-b"}',
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            media_type="application/json"
        )
    except httpx.RequestError as exc:
        service_a.log_event("ERROR", "PAYMENT_SERVICE_UNREACHABLE", f"Cannot connect to Service B: {str(exc)}", trace_id)
        return Response(
            content=f'{{"error": "Service B unreachable", "details": "{str(exc)}"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="warning")
