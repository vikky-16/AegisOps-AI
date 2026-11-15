"""
Telemetry Simulator & Failure Orchestrator API Endpoints
Controls synthetic enterprise stream generation and the 20-scenario Failure Orchestrator.
Supports live lifecycle tracking, manual triggers, pause/resume, skip, and interval configuration.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from backend.app.simulator.engine import simulator_engine
from backend.app.monitoring.failure_scheduler import failure_scheduler

router = APIRouter(prefix="/simulator", tags=["Simulator"])


class StartStreamRequest(BaseModel):
    scenario: str = Field(default="normal_traffic", description="Scenario identifier e.g. database_exhaustion, cpu_saturation, log_storm_100k")
    target_count: int = Field(default=10000, description="10000, 50000, 100000, or 500000")
    eps: int = Field(default=500, description="Events per second: 100, 250, 500, 1000")


class ForceScenarioRequest(BaseModel):
    scenario_id: str = Field(description="Scenario ID from 20 supported failure classes")


class ConfigOrchestratorRequest(BaseModel):
    interval_seconds: Optional[int] = Field(default=None, ge=10, le=3600)
    auto_mode: Optional[bool] = Field(default=None)


# -------------------------------------------------------------
# Streaming Load Simulator Endpoints (Existing Functionality)
# -------------------------------------------------------------

@router.get("/status")
async def get_simulator_status():
    """Returns real-time streaming progress, current throughput (EPS), and active scenario."""
    return simulator_engine.get_status()


@router.post("/start")
async def start_streaming(req: StartStreamRequest):
    """Starts streaming synthetic enterprise telemetry at configured volume and rate."""
    return await simulator_engine.start_stream(
        scenario=req.scenario,
        target_count=req.target_count,
        eps=req.eps
    )


@router.post("/pause")
async def pause_streaming():
    """Pauses active streaming loop."""
    return simulator_engine.pause_stream()


@router.post("/resume")
async def resume_streaming():
    """Resumes paused streaming loop."""
    return simulator_engine.resume_stream()


@router.post("/stop")
async def stop_streaming():
    """Terminates active streaming loop."""
    return simulator_engine.stop_stream()


@router.post("/reset")
async def reset_simulator_state():
    """Resets simulator progress and operational platform state to clean baseline."""
    return await simulator_engine.reset_environment()


# -------------------------------------------------------------
# Failure Orchestrator Endpoints (New 20-Scenario Autonomous System)
# -------------------------------------------------------------

@router.get("/orchestrator/status")
async def get_orchestrator_status():
    """Returns complete state of the 20-scenario Failure Orchestrator."""
    return failure_scheduler.get_status()


@router.get("/orchestrator/scenarios")
async def list_orchestrator_scenarios():
    """Returns all 33 distinct failure scenarios across 10 categories with signatures and remedies."""
    scenarios_list = failure_scheduler.list_scenarios()
    return {
        "total_scenarios": len(scenarios_list),
        "scenarios": scenarios_list
    }


@router.post("/orchestrator/trigger")
async def trigger_next_orchestrator_scenario():
    """Manually triggers the next failure scenario in sequence (respects non-overlapping rule)."""
    res = await failure_scheduler.trigger_next_scenario()
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Cannot inject scenario"))
    return res


@router.post("/orchestrator/force")
async def force_orchestrator_scenario(req: ForceScenarioRequest):
    """Forces injection of a specific failure scenario by scenario_id."""
    res = await failure_scheduler.force_scenario(req.scenario_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to force scenario"))
    return res


@router.post("/orchestrator/pause")
async def pause_orchestrator():
    """Pauses automatic failure injection timer."""
    return failure_scheduler.pause()


@router.post("/orchestrator/resume")
async def resume_orchestrator():
    """Resumes automatic failure injection timer."""
    return failure_scheduler.resume()


@router.post("/orchestrator/skip")
async def skip_orchestrator_scenario():
    """Skips the currently active scenario and resets target service to clean baseline."""
    return await failure_scheduler.skip_current()


@router.post("/orchestrator/config")
async def config_orchestrator(req: ConfigOrchestratorRequest):
    """Updates orchestrator interval or auto-injection mode."""
    if req.interval_seconds is not None:
        failure_scheduler.set_interval(req.interval_seconds)
    if req.auto_mode is not None:
        failure_scheduler.set_auto_mode(req.auto_mode)
    return failure_scheduler.get_status()


@router.get("/orchestrator/history")
async def get_orchestrator_history(limit: int = 50):
    """Returns historical execution records of failure scenarios."""
    return {
        "history": failure_scheduler.history[:limit]
    }
