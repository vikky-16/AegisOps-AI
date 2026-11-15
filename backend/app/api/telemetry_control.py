"""
Telemetry Control & Diagnostics API Router
Provides endpoints for operating mode toggling (LIVE_STREAM vs CONTROLLED_DEMO),
throughput pacing (25 - 5000 EPS), failure scheduler controls, manual failure injections,
and live event diagnostics with ingestion latency metrics.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from backend.app.monitoring.collector import collector
from backend.app.monitoring.continuous_telemetry import continuous_telemetry
from backend.app.monitoring.failure_scheduler import failure_scheduler, FAILURE_SCENARIOS, ALL_FAILURE_SCENARIOS

router = APIRouter(prefix="/telemetry", tags=["Telemetry Control & Diagnostics"])


class SetModeRequest(BaseModel):
    mode: str = Field(..., description="Target mode: LIVE_STREAM or CONTROLLED_DEMO")


class SetRateRequest(BaseModel):
    eps: int = Field(..., ge=1, le=1000000, description="Events per second (10, 100, 1000, 10000, 100000+)")


class SetSchedulerRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = Field(None, ge=10, le=600)
    scenario_id: Optional[str] = Field(None, description="Specific scenario ID or AUTO_ROTATE")


class TriggerFailureRequest(BaseModel):
    scenario: str = Field(..., description="Failure scenario ID (e.g. DATABASE_CONNECTION_FAILURE)")


@router.get("/status")
async def get_telemetry_status():
    """Returns the unified status of operating mode, continuous telemetry, and failure scheduler."""
    ct_status = continuous_telemetry.get_status()
    return {
        "operating_mode": collector.operating_mode,
        "continuous_telemetry": ct_status,
        "telemetry_stats": {
            "events_per_sec": ct_status.get("events_per_sec", 0.0),
            "events_per_min": ct_status.get("events_per_min", 0.0),
            "total_events": ct_status.get("total_events", 0),
            "kafka_throughput_mb_s": ct_status.get("kafka_throughput_mb_s", 0.0),
            "consumer_lag": ct_status.get("consumer_lag", 0),
            "pipeline_latency_ms": ct_status.get("pipeline_latency_ms", 0.0)
        },
        "failure_scheduler": failure_scheduler.get_status(),
        "total_active_incidents": len(collector.active_incidents),
        "system_health_score": collector.system_health_score
    }


@router.post("/mode")
async def set_operating_mode(req: SetModeRequest):
    """Switches the operating mode between LIVE_STREAM and CONTROLLED_DEMO."""
    valid_modes = ["LIVE_STREAM", "CONTROLLED_DEMO"]
    if req.mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of {valid_modes}")
    
    collector.operating_mode = req.mode
    collector.append_feed_event(
        phase="MODE_SWITCHED",
        service="orchestrator",
        message=f"Operating mode switched to: {req.mode}",
        severity="INFO"
    )
    return {"success": True, "operating_mode": collector.operating_mode}


@router.post("/rate")
async def set_telemetry_rate(req: SetRateRequest):
    """Configures the events/sec generation rate for the continuous telemetry engine."""
    continuous_telemetry.set_eps_rate(req.eps)
    collector.append_feed_event(
        phase="RATE_ADJUSTED",
        service="telemetry-engine",
        message=f"Continuous telemetry throughput set to {req.eps} EPS.",
        severity="INFO"
    )
    return {"success": True, "configured_eps": continuous_telemetry.configured_eps}


@router.post("/failure-scheduler")
async def configure_failure_scheduler(req: SetSchedulerRequest):
    """Configures the automated failure scheduler interval, enabled state, and scenario mode."""
    failure_scheduler.set_config(
        enabled=req.enabled,
        interval_seconds=req.interval_seconds,
        scenario_id=req.scenario_id
    )
    collector.append_feed_event(
        phase="SCHEDULER_CONFIGURED",
        service="failure-scheduler",
        message=f"Failure scheduler set: enabled={failure_scheduler.is_enabled}, interval={failure_scheduler.interval_seconds}s, scenario={failure_scheduler.selected_scenario_id or 'AUTO_ROTATE'}",
        severity="INFO"
    )
    return failure_scheduler.get_status()


@router.post("/trigger-failure")
async def trigger_failure(req: TriggerFailureRequest):
    """Manually triggers one of the 10 failure cascade scenarios."""
    res = await failure_scheduler.trigger_manual_scenario(req.scenario)
    collector.append_feed_event(
        phase="MANUAL_FAILURE_INJECTED",
        service=res["primary_service"],
        message=f"Manual failure cascade triggered: '{res['scenario']}'. Downstream: {res['downstream']}",
        severity="WARNING"
    )
    return res


@router.get("/diagnostics")
async def get_telemetry_diagnostics(limit: int = Query(default=30, ge=1, le=100)):
    """Returns live diagnostic telemetry events with exact source timestamp, received timestamp, and ingestion latency."""
    return {
        "operating_mode": collector.operating_mode,
        "avg_ingestion_latency_ms": continuous_telemetry.avg_ingestion_latency_ms,
        "current_eps": continuous_telemetry.actual_eps,
        "total_events": continuous_telemetry.total_events_generated,
        "total_errors": continuous_telemetry.total_errors_generated,
        "events": continuous_telemetry.get_recent_diagnostics(limit)
    }


@router.get("/scenarios")
async def get_failure_scenarios(all_scenarios: bool = True):
    """Returns the catalog of all available failure cascade scenarios (33 scenarios across 10 categories)."""
    return ALL_FAILURE_SCENARIOS if all_scenarios else FAILURE_SCENARIOS
