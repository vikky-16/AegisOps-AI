"""
LogHub Telemetry Ingestion & Historical Replay API Router
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from backend.app.loghub.parser import loghub_parser
from backend.app.loghub.engine import loghub_engine
from backend.app.loghub.models import LogHubDatasetInfo, LogHubReplayStatus, StartReplayRequest

router = APIRouter(prefix="/loghub", tags=["LogHub Historical Telemetry"])


@router.get("/datasets", response_model=List[LogHubDatasetInfo])
async def list_datasets():
    """Lists all available LogHub real-world datasets and metadata."""
    return loghub_parser.list_available_datasets()


@router.get("/replay/status")
async def get_replay_status():
    """Returns live streaming replay status, throughput rate, and all 10 diagnostic counters."""
    return loghub_engine.get_status()


@router.post("/replay/start")
async def start_replay(req: StartReplayRequest):
    """Starts streaming real-world LogHub telemetry at configured volume and rate."""
    return await loghub_engine.start_replay(
        dataset=req.dataset,
        target_count=req.target_count,
        eps=req.eps
    )


@router.post("/replay/pause")
async def pause_replay():
    """Pauses active LogHub stream."""
    return loghub_engine.pause_replay()


@router.post("/replay/resume")
async def resume_replay():
    """Resumes paused LogHub stream."""
    return loghub_engine.resume_replay()


@router.post("/replay/stop")
async def stop_replay():
    """Stops active LogHub stream."""
    return loghub_engine.stop_replay()


@router.post("/replay/reset")
async def reset_replay():
    """Resets LogHub replay state and clears telemetry buffer."""
    return await loghub_engine.reset_replay_state()
