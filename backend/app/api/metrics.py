"""
Metrics & Telemetry API Endpoints
"""

from fastapi import APIRouter
from typing import Dict, Any, List
from backend.app.monitoring.collector import collector

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
async def get_all_metrics():
    """Returns current metrics snapshot for all microservices."""
    return {
        "health_score": collector.system_health_score,
        "metrics": collector.latest_metrics,
        "history": collector.metric_history
    }


@router.get("/{service_name}/history")
async def get_service_metric_history(service_name: str):
    """Returns time-series telemetry points for a specific service."""
    return collector.metric_history.get(service_name, [])
