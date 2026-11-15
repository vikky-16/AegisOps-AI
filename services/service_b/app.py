"""
Service B (Payment & Inventory Service) - Port 8003
Processes payments and calls Database Service for ledger updates.
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

service_b = BaseService(
    name="service-b",
    port=8003,
    role="Payment & Ledger Processor",
    dependencies=["database-service"]
)
app = service_b.app

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://127.0.0.1:8004")


@app.get("/work")
@app.post("/work")
async def handle_payment(request: Request):
    """
    Simulates payment ledger authorization and invokes Database Service query.
    """
    trace_id = request.headers.get("X-Trace-ID")
    start_time = time.time()
    service_b.log_event("INFO", "PAYMENT_PROCESSING", "Executing financial payment ledger transaction", trace_id)
    
    headers = {"X-Trace-ID": trace_id} if trace_id else {}
    
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(f"{DATABASE_SERVICE_URL}/query", headers=headers)
            elapsed = (time.time() - start_time) * 1000
            
            if resp.status_code >= 500:
                service_b.log_event(
                    "ERROR",
                    "DATABASE_QUERY_FAILED",
                    f"Database query execution failed with HTTP {resp.status_code}",
                    trace_id,
                    {"status": resp.status_code, "latency_ms": elapsed}
                )
                return Response(
                    content=resp.text,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    media_type="application/json"
                )
            
            service_b.log_event("INFO", "PAYMENT_SETTLED", "Payment settled and record locked in ledger", trace_id)
            return {
                "service": "service-b",
                "payment_id": f"PAY-{int(time.time()*1000) % 1000000}",
                "status": "SETTLED",
                "latency_ms": round(elapsed, 2),
                "database_record": resp.json()
            }
            
    except httpx.TimeoutException:
        service_b.log_event("ERROR", "DATABASE_TIMEOUT", "Database Service timed out executing SQL query", trace_id)
        return Response(
            content='{"error": "Database Connection Timeout", "failed_dependency": "database-service"}',
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            media_type="application/json"
        )
    except httpx.RequestError as exc:
        service_b.log_event("ERROR", "DATABASE_UNREACHABLE", f"Cannot connect to Database Service: {str(exc)}", trace_id)
        return Response(
            content=f'{{"error": "Database Service unreachable", "details": "{str(exc)}"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="warning")
