"""
Storage Intelligence API Endpoints
"""

from fastapi import APIRouter
from backend.app.storage.manager import storage_manager

router = APIRouter(prefix="/storage", tags=["Storage Intelligence"])


@router.get("")
async def get_storage_metrics():
    """Returns storage analytics, growth rates, time-to-critical projections, and top consumers."""
    return storage_manager.get_storage_status()


@router.post("/optimize")
async def optimize_storage():
    """Executes log rotation, gzip compression, and table compaction."""
    return storage_manager.execute_storage_optimization()
