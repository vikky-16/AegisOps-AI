"""
AegisOps AI - Early Warning Alerts API Endpoints (Requirement 4 & 24)
"""

from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any

from backend.app.analytics.early_warning import early_warning_engine

router = APIRouter(prefix="/early-warnings", tags=["Early Warning Alerts"])


@router.get("")
@router.get("/alerts")
async def get_early_warning_alerts(
    tenant_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Returns recent early warning degradation alerts."""
    return early_warning_engine.get_recent_alerts(tenant_id=tenant_id, limit=limit)


@router.get("/summary")
async def get_early_warning_summary(
    tenant_id: Optional[str] = Query(default=None)
):
    """Returns early warning summary metrics (warnings, degrading, critical counts)."""
    return early_warning_engine.get_summary(tenant_id=tenant_id)
