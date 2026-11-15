"""
Live Operations Center API Endpoints
Streams real-time operational events, active RCA investigations, and environment mode status.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.app.monitoring.collector import collector

router = APIRouter(prefix="/operations", tags=["Operations Center"])


class SetEnvironmentRequest(BaseModel):
    environment_mode: str  # DEMO, STAGING, PRODUCTION-CONNECTED


@router.get("/feed")
async def get_live_operations_feed(limit: int = 50):
    """Returns chronological live operational event stream for the Operations Center ticker."""
    feed = list(collector.live_operations_feed)
    return feed[:limit]


@router.get("/status")
async def get_operations_status():
    """Returns high-level operational status across services, active incidents, and pipelines."""
    return {
        "health_score": collector.system_health_score,
        "environment_mode": collector.environment_mode,
        "active_incidents": len(collector.active_incidents),
        "pending_approvals": len(collector.pending_approvals),
        "services_online": sum(1 for h in collector.latest_health.values() if h.get("healthy", False)),
        "total_monitored_services": len(collector.latest_health) or 4,
        "telemetry_stream_status": "ACTIVE_STREAMING"
    }


@router.post("/environment")
async def set_environment_mode(req: SetEnvironmentRequest):
    """Switches operational environment mode (DEMO, STAGING, PRODUCTION-CONNECTED)."""
    collector.environment_mode = req.environment_mode.upper()
    collector.append_feed_event(
        phase="ENVIRONMENT_CHANGED",
        service="orchestrator",
        message=f"Operational environment switched to {collector.environment_mode}.",
        severity="INFO"
    )
    return {"success": True, "environment_mode": collector.environment_mode}
