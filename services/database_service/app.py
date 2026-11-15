"""
Database Service (Persistence & Ledger Layer) - Port 8004
Simulates SQL query execution, transaction locking, connection pools, and table storage.
"""

import sys
import os
import time
import random
import asyncio
import uvicorn
from typing import Optional, Dict, Any
from fastapi import Request, Response, HTTPException, status
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services.base_service import BaseService

db_service = BaseService(
    name="database-service",
    port=8004,
    role="Relational Persistence & Ledger Database",
    dependencies=[]
)
app = db_service.app

# Database specific state
MAX_CONNECTIONS = 20
current_pool_connections = 4
storage_used_bytes = 82 * 1024 * 1024 * 1024  # 82 GB simulated
storage_total_bytes = 100 * 1024 * 1024 * 1024 # 100 GB simulated
is_locked = False


@app.get("/query")
@app.post("/query")
async def execute_query(request: Request):
    """
    Simulates executing an ACID database transaction / SQL query.
    """
    global current_pool_connections, storage_used_bytes
    trace_id = request.headers.get("X-Trace-ID")
    start_time = time.time()
    
    # Check failure conditions
    db_service.check_failure_expiration()
    
    if db_service.failure_mode == "connection_exhaustion":
        db_service.log_event("CRITICAL", "CONNECTION_POOL_EXHAUSTION", "Database connection pool exhausted (20/20 active connections)", trace_id)
        return Response(
            content='{"error": "FATAL: remaining connection slots are reserved for non-replication superuser connections (Pool Exhausted)", "code": "53300"}',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json"
        )

    if db_service.failure_mode == "db_timeout":
        # Simulate query hanging and timing out
        await asyncio.sleep(4.0)
        db_service.log_event("ERROR", "TRANSACTION_TIMEOUT", "Lock wait timeout exceeded; try restarting transaction", trace_id)
        return Response(
            content='{"error": "Lock wait timeout exceeded in InnoDB engine", "code": "1205"}',
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            media_type="application/json"
        )

    if db_service.failure_mode == "storage_pressure":
        # Simulate storage exhaustion
        storage_used_bytes = int(98.5 * 1024 * 1024 * 1024)
        db_service.log_event("WARNING", "DISK_SPACE_CRITICAL", "Database tablespace volume reached 98.5% capacity", trace_id)

    # Normal simulation
    simulated_query_time = random.uniform(0.005, 0.035)  # 5ms to 35ms
    await asyncio.sleep(simulated_query_time)
    
    storage_used_bytes += random.randint(1024, 4096)  # slight growth
    elapsed = (time.time() - start_time) * 1000
    
    db_service.log_event("DEBUG", "QUERY_EXECUTED", f"SELECT/UPDATE committed in {round(elapsed, 2)}ms", trace_id)
    
    return {
        "status": "SUCCESS",
        "rows_affected": 1,
        "execution_time_ms": round(elapsed, 2),
        "database": "aegis_core_ledger",
        "pool_usage": f"{min(MAX_CONNECTIONS, current_pool_connections)}/{MAX_CONNECTIONS}"
    }


@app.get("/storage_info")
async def get_storage_info():
    """
    Returns detailed simulated database storage metrics.
    """
    percent_used = (storage_used_bytes / storage_total_bytes) * 100
    return {
        "total_gb": round(storage_total_bytes / (1024**3), 2),
        "used_gb": round(storage_used_bytes / (1024**3), 2),
        "free_gb": round((storage_total_bytes - storage_used_bytes) / (1024**3), 2),
        "used_percentage": round(percent_used, 2),
        "tables": [
            {"table_name": "audit_logs", "size_mb": 42500, "row_count": 85000000},
            {"table_name": "transaction_ledger", "size_mb": 25400, "row_count": 31200000},
            {"table_name": "telemetry_snapshots", "size_mb": 11200, "row_count": 14000000},
            {"table_name": "service_registry", "size_mb": 45, "row_count": 120}
        ]
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="warning")
