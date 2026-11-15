"""
Auth Microservice - Port 8005
Handles token validation, user authentication, and session management.
"""

import sys
import os
import time
import httpx
import uvicorn
from fastapi import Request, HTTPException, status
from pydantic import BaseModel

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services.base_service import BaseService

auth_service = BaseService(
    name="auth-service",
    port=8005,
    role="Authentication & Session Validator",
    dependencies=["database-service"]
)
app = auth_service.app

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://127.0.0.1:8004")


class AuthRequest(BaseModel):
    user_id: str = "usr-1001"
    token: str = "jwt-session-token-valid"


@app.get("/work")
@app.post("/work")
@app.post("/verify")
async def verify_token(request: Request, body: AuthRequest = None):
    """
    Simulates token and session authorization against the database service.
    """
    trace_id = request.headers.get("X-Trace-ID")
    start_time = time.time()
    
    # Check failure simulation state
    if not auth_service.is_running or auth_service.failure_mode == "crash":
        auth_service.log_event("CRITICAL", "PROCESS_CRASHED", "Auth service worker process terminated unexpectedly", trace_id)
        raise HTTPException(status_code=503, detail="Auth Service Unavailable")
        
    if auth_service.failure_mode == "error_spike":
        auth_service.log_event("ERROR", "AUTH_TOKEN_INVALID", "Token signature mismatch or revoked", trace_id)
        raise HTTPException(status_code=401, detail="Unauthorized Token Verification Failure")

    if auth_service.failure_mode == "latency_spike":
        time.sleep(1.5)

    auth_service.log_event("INFO", "AUTH_VERIFY_REQUEST", "Verifying token against user session repository", trace_id)

    # Call downstream database service to check session table
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            headers = {"X-Trace-ID": trace_id} if trace_id else {}
            resp = await client.get(f"{DATABASE_SERVICE_URL}/query", headers=headers)
            if resp.status_code != 200:
                auth_service.log_event("ERROR", "DOWNSTREAM_AUTH_DB_ERROR", f"Database returned status {resp.status_code}", trace_id)
                raise HTTPException(status_code=502, detail="Database Service Error during Auth Lookup")
    except httpx.RequestError as e:
        auth_service.log_event("ERROR", "DOWNSTREAM_DB_UNREACHABLE", f"Failed to reach Database: {str(e)}", trace_id)
        raise HTTPException(status_code=504, detail="Database Unreachable from Auth Service")

    dur_ms = round((time.time() - start_time) * 1000, 2)
    auth_service.log_event("INFO", "AUTH_SUCCESS", f"Authentication token verified in {dur_ms}ms", trace_id)
    return {
        "status": "AUTHENTICATED",
        "service": "auth-service",
        "user_id": body.user_id if body else "usr-1001",
        "duration_ms": dur_ms
    }


if __name__ == "__main__":
    uvicorn.run("services.auth_service.app:app", host="127.0.0.1", port=8005, log_level="warning")
