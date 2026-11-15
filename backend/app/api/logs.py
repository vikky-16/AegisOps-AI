"""
Log Intelligence API Endpoints
High-throughput pagination, server-side search, fingerprint grouping, and 10,000+ log simulation.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from backend.app.logs.processor import log_processor, generate_simulated_logs
from backend.app.monitoring.collector import collector

router = APIRouter(prefix="/logs", tags=["Logs"])


class GenerateLogsRequest(BaseModel):
    count: int = Field(default=10000, ge=100, le=100000)
    scenario: str = Field(default="database_storm", description="database_storm, high_cpu, storage_pressure, or normal")
    trigger_anomaly: bool = Field(default=True, description="Whether to trigger automated incident correlation")


@router.get("")
async def get_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    service: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    grouped: bool = Query(default=False)
):
    """
    Returns paginated logs with server-side filtering, or aggregated fingerprinted event groups.
    Handles 10,000+ to 100,000+ logs smoothly without freezing browser UI.
    """
    if grouped:
        fingerprints = log_processor.get_fingerprints()
        return {
            "grouped": True,
            "total_groups": len(fingerprints),
            "items": fingerprints
        }

    return log_processor.query_logs(
        page=page,
        page_size=page_size,
        service=service,
        level=level,
        event_type=event_type,
        search=search
    )


@router.get("/summary")
async def get_log_summary():
    """Returns log distribution across levels, services, and unique fingerprints."""
    return log_processor.get_summary()


@router.get("/fingerprints")
async def get_log_fingerprints():
    """Returns deduplicated event fingerprint groups with total occurrences."""
    return log_processor.get_fingerprints()


@router.post("/generate")
async def generate_logs_endpoint(req: GenerateLogsRequest):
    """
    Generates and processes 10,000 to 100,000+ log events in batches.
    Feeds logs through fingerprinting, deduplication, and anomaly correlation.
    """
    logs = generate_simulated_logs(count=req.count, scenario=req.scenario)
    res = await log_processor.ingest_batch(logs)

    # If error logs were generated, trigger automated telemetry and incident evaluation
    if req.trigger_anomaly:
        try:
            await collector.poll_cycle()
        except Exception:
            pass

    return {
        "success": True,
        "message": f"Successfully generated and processed {req.count:,} logs under '{req.scenario}' scenario.",
        "ingestion_stats": res
    }


@router.post("/clear")
async def clear_logs_endpoint():
    """Clears in-memory log buffer and fingerprint stats."""
    log_processor.clear()
    return {"success": True, "message": "Log buffer and fingerprint groups cleared."}
