"""
Dev Log Simulator API Endpoints
Provides start, stop, status, and config controls for the continuous dummy log traffic generator.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from backend.app.dev_tools.log_simulator import log_simulator

router = APIRouter(prefix="/dev/logs/simulate", tags=["Dev Log Simulator"])


class SimulatorConfigRequest(BaseModel):
    log_rate_per_sec: Optional[float] = Field(default=8.0, ge=0.5, le=100.0, description="Logs generated per second (default: 8)")
    failure_rate_per_min: Optional[float] = Field(default=5.0, ge=0.0, le=60.0, description="Random failures per minute (default: 5)")
    max_logs: Optional[int] = Field(default=None, description="Optional cap on total logs (None for unlimited)")


@router.get("/status")
async def get_simulator_status():
    """Returns current state, speed, error counts, and metrics of the continuous log simulator."""
    return {
        "success": True,
        **log_simulator.get_status()
    }


@router.post("/start")
async def start_simulator(
    rate: Optional[float] = Query(default=None, description="Logs per second"),
    failures: Optional[float] = Query(default=None, description="Failures per minute"),
    max_logs: Optional[int] = Query(default=None, description="Max total logs"),
    req: Optional[SimulatorConfigRequest] = None
):
    """
    Starts the continuous dummy log generator in the background.
    Feeds structured logs, failures, and resolutions directly into real-time streams.
    """
    new_rate = (req.log_rate_per_sec if req and req.log_rate_per_sec is not None else rate)
    new_failures = (req.failure_rate_per_min if req and req.failure_rate_per_min is not None else failures)
    new_max = (req.max_logs if req and req.max_logs is not None else max_logs)

    log_simulator.update_config(
        log_rate_per_sec=new_rate,
        failure_rate_per_min=new_failures,
        max_logs=new_max
    )

    started = await log_simulator.start()
    return {
        "success": True,
        "message": "Continuous log simulator started." if started else "Simulator is already running.",
        "status": log_simulator.get_status()
    }


@router.post("/stop")
async def stop_simulator():
    """Stops the continuous dummy log generator."""
    stopped = log_simulator.stop()
    return {
        "success": True,
        "message": "Continuous log simulator stopped." if stopped else "Simulator was not running.",
        "status": log_simulator.get_status()
    }


@router.post("/config")
async def configure_simulator(req: SimulatorConfigRequest):
    """Dynamically updates the log generation rate and failure injection rate."""
    log_simulator.update_config(
        log_rate_per_sec=req.log_rate_per_sec,
        failure_rate_per_min=req.failure_rate_per_min,
        max_logs=req.max_logs
    )
    return {
        "success": True,
        "message": "Simulator configuration updated.",
        "status": log_simulator.get_status()
    }
