"""
AegisOps AI - Architecture & Operational Workflow REST APIs
Provides tenant-scoped endpoints for architecture topology, business workflows,
coverage gap metrics, and authorized discovery jobs.
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, Dict, Any

from backend.app.analytics.architecture_discovery import architecture_discovery
from backend.app.logger import realtime_logger

router = APIRouter(prefix="/architecture", tags=["Company Architecture & Workflows"])


@router.get("/inventory")
async def get_architecture_inventory(
    tenant_id: str = Query(default="shopsphere", description="Authorized Tenant ID")
) -> Dict[str, Any]:
    """
    Returns full tenant-scoped architecture model:
    - Services, databases, caches, queues, and platforms
    - Dependencies, ownership, on-call teams, maintenance windows
    - Critical business workflows and SLO targets
    - Truthful architecture coverage score and coverage gap analysis
    """
    try:
        return await architecture_discovery.get_tenant_inventory(tenant_id=tenant_id)
    except Exception as e:
        realtime_logger.error(f"Error retrieving architecture inventory for {tenant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load architecture inventory: {str(e)}")


@router.get("/workflows")
async def get_tenant_workflows(
    tenant_id: str = Query(default="shopsphere", description="Authorized Tenant ID")
) -> Dict[str, Any]:
    """Returns critical operational business workflows for the specified tenant."""
    inv = await architecture_discovery.get_tenant_inventory(tenant_id=tenant_id)
    return {
        "tenant_id": tenant_id,
        "workflows": inv.get("workflows", []),
        "total_workflows": inv.get("total_critical_workflows", 0),
        "verified_workflows": inv.get("verified_workflows", 0)
    }


@router.post("/discover")
async def trigger_architecture_discovery(
    tenant_id: str = Query(default="shopsphere", description="Authorized Tenant ID"),
    source: str = Query(default="AUTHORIZED_CLOUD_PROBE", description="Authorized discovery source")
) -> Dict[str, Any]:
    """
    Executes an authorized discovery refresh for the tenant.
    Updates resource freshness, recalculates confidence, and identifies coverage gaps.
    """
    try:
        return await architecture_discovery.run_discovery_job(tenant_id=tenant_id, discovery_source=source)
    except Exception as e:
        realtime_logger.error(f"Failed to execute discovery job for {tenant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Discovery job failed: {str(e)}")
