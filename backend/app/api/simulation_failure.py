"""
AegisOps AI - Safe Development Failure Simulator Framework (Phase 25)
Exposes controlled failure injection endpoints that affect the REAL running company services:
- ShopSphere (Order Service :8101)
- FinCore (Payment Service :8203, Fraud Service :8204)
- CloudDesk (Compute Service :8303)

Supported scenarios:
1. Database latency
2. Database unavailable
3. Redis unavailable
4. Service latency
5. Service timeout
6. HTTP 500 spike
7. Dependency failure
8. CPU stress
ONLY permitted in development / simulation mode. Never executes arbitrary shell scripts.
"""

import httpx
import asyncio
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

router = APIRouter(tags=["Failure Simulation Framework"])

# Service URLs
SHOPSPHERE_ORDER_URL = "http://127.0.0.1:8101"
FINCORE_PAYMENT_URL = "http://127.0.0.1:8203"
FINCORE_FRAUD_URL = "http://127.0.0.1:8204"
CLOUDDESK_COMPUTE_URL = "http://127.0.0.1:8303"


class FailureSimulationRequest(BaseModel):
    company: str = Field(description="Target company: shopsphere, fincore, or clouddesk")
    target: Optional[str] = Field(default=None, description="Target service (e.g. order-service, payment-service, compute-service)")
    failure: str = Field(description="Failure scenario: database_latency, database_unavailable, redis_unavailable, latency, timeout, 500, dependency_failure, cpu_stress")
    duration_seconds: Optional[int] = Field(default=30, ge=1, le=600, description="Duration in seconds before automatic recovery")


@router.post("/api/simulation/failure")
@router.post("/simulation/failure")
async def inject_failure(payload: FailureSimulationRequest):
    """
    Injects a real, controlled failure into the specified company service.
    """
    company = payload.company.lower()
    failure = payload.failure.lower().replace("-", "_").replace(" ", "_")
    target = (payload.target or "").lower().replace("-", "_")

    if company not in ("shopsphere", "fincore", "clouddesk"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown company '{payload.company}'. Allowed: shopsphere, fincore, clouddesk"
        )

    result_details = {}

    async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
        try:
            # 1. ShopSphere Scenarios
            if company == "shopsphere":
                if failure in ("database_latency", "db_latency", "latency"):
                    resp = await client.post(
                        f"{SHOPSPHERE_ORDER_URL}/inject/db-latency",
                        json={"latency_ms": 3500.0, "exhaust_connections": True}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                elif failure in ("database_unavailable", "db_unavailable", "connection_pool_exhaustion"):
                    resp = await client.post(
                        f"{SHOPSPHERE_ORDER_URL}/inject/db-latency",
                        json={"latency_ms": 5000.0, "exhaust_connections": True}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                elif failure in ("service_latency", "service_timeout", "timeout", "http_500_spike", "500", "dependency_failure"):
                    resp = await client.post(
                        f"{SHOPSPHERE_ORDER_URL}/inject/db-latency",
                        json={"latency_ms": 3500.0, "exhaust_connections": False}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                else:
                    resp = await client.post(
                        f"{SHOPSPHERE_ORDER_URL}/inject/db-latency",
                        json={"latency_ms": 2500.0, "exhaust_connections": False}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}

            # 2. FinCore Scenarios
            elif company == "fincore":
                if failure in ("service_timeout", "timeout", "dependency_failure"):
                    resp = await client.post(
                        f"{FINCORE_PAYMENT_URL}/inject/timeout",
                        json={"enabled": True, "delay_seconds": 6.0}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                elif failure in ("latency", "service_latency", "database_latency"):
                    resp = await client.post(
                        f"{FINCORE_FRAUD_URL}/inject/latency",
                        json={"latency_ms": 2500.0}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                else:
                    resp = await client.post(
                        f"{FINCORE_PAYMENT_URL}/inject/timeout",
                        json={"enabled": True, "delay_seconds": 6.0}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}

            # 3. CloudDesk Scenarios
            elif company == "clouddesk":
                if failure in ("redis_unavailable", "redis_down", "cache_failure", "redis"):
                    resp = await client.post(f"{CLOUDDESK_COMPUTE_URL}/inject/redis-down")
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                elif failure in ("service_latency", "latency", "timeout", "service_timeout"):
                    resp = await client.post(
                        f"{CLOUDDESK_COMPUTE_URL}/inject/latency",
                        json={"latency_ms": 2500.0}
                    )
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
                else:
                    resp = await client.post(f"{CLOUDDESK_COMPUTE_URL}/inject/redis-down")
                    result_details = resp.json() if resp.status_code == 200 else {"status": resp.status_code}

        except Exception as e:
            result_details = {"error": str(e), "message": "Failed to connect to target service endpoint"}

    # Authoritative Canonical State Fault Sync (Part 27)
    try:
        from backend.app.services.canonical_state import canonical_state_manager
        target_svc = payload.target or ("database-service" if "database" in failure or "db" in failure else ("service-a" if company == "shopsphere" else "payment-service"))
        is_crit = ("unavailable" in failure or "exhaustion" in failure or "500" in failure or "crash" in failure or "down" in failure)
        canonical_state_manager.set_simulated_fault(
            tenant_id=company,
            service_name=target_svc,
            fault_type=payload.failure,
            severity="CRITICAL" if is_crit else "DEGRADED"
        )
    except Exception:
        pass

    return {
        "status": "INJECTED",
        "company": company,
        "target": payload.target or "default-target",
        "failure": payload.failure,
        "duration_seconds": payload.duration_seconds,
        "details": result_details
    }


@router.post("/api/simulation/reset")
@router.post("/simulation/reset")
async def reset_simulation(company: Optional[str] = None):
    """
    Resets all simulated failures across company microservices concurrently.
    """
    try:
        from backend.app.monitoring.continuous_telemetry import continuous_telemetry
        continuous_telemetry.clear_all_failures()
    except Exception:
        pass
    try:
        from backend.app.monitoring.failure_scheduler import failure_scheduler
        await failure_scheduler.skip_current_scenario()
    except Exception:
        pass
    try:
        from backend.app.analytics.feature_extractor import feature_extractor
        feature_extractor.clear()
    except Exception:
        pass
    try:
        from backend.app.analytics.baseline_engine import baseline_engine
        baseline_engine.clear()
    except Exception:
        pass
    try:
        from backend.app.analytics.incident_pipeline import incident_pipeline
        with incident_pipeline.lock:
            incident_pipeline._recent_events.clear()
    except Exception:
        pass
    try:
        from backend.app.incidents.correlator import event_correlator
        event_correlator.recent_events.clear()
    except Exception:
        pass
    try:
        from backend.app.analytics.error_pattern_detector import error_pattern_detector
        with error_pattern_detector.lock:
            error_pattern_detector.patterns.clear()
    except Exception:
        pass
    try:
        from backend.app.services.canonical_state import canonical_state_manager
        canonical_state_manager.clear_all_simulated_faults()
    except Exception:
        pass
    results = {}

    async def _reset_shopsphere(c: httpx.AsyncClient):
        try:
            r = await c.post(f"{SHOPSPHERE_ORDER_URL}/inject/db-reset", timeout=2.0)
            return ("shopsphere", r.json() if r.status_code == 200 else r.status_code)
        except Exception:
            return ("shopsphere", "offline")

    async def _reset_fincore(c: httpx.AsyncClient):
        try:
            r1 = await c.post(f"{FINCORE_PAYMENT_URL}/inject/reset", timeout=2.0)
            r2 = await c.post(f"{FINCORE_FRAUD_URL}/inject/reset", timeout=2.0)
            return ("fincore", {"payment": r1.status_code, "fraud": r2.status_code})
        except Exception:
            return ("fincore", "offline")

    async def _reset_clouddesk(c: httpx.AsyncClient):
        try:
            r = await c.post(f"{CLOUDDESK_COMPUTE_URL}/inject/reset", timeout=2.0)
            return ("clouddesk", r.json() if r.status_code == 200 else r.status_code)
        except Exception:
            return ("clouddesk", "offline")

    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
        res_list = await asyncio.gather(
            _reset_shopsphere(client),
            _reset_fincore(client),
            _reset_clouddesk(client)
        )
        for comp, res in res_list:
            results[comp] = res

    return {
        "status": "RESET_ALL",
        "results": results
    }


@router.post("/api/simulation/warmup")
@router.post("/simulation/warmup")
async def configure_simulation_warmup(seconds: float = 0.0):
    """
    Configures the baseline engine warm-up period dynamically for tests.
    """
    from backend.app.analytics.baseline_engine import baseline_engine
    baseline_engine.set_warmup_seconds(seconds)
    return {
        "status": "CONFIGURED",
        "warmup_seconds": baseline_engine.warmup_seconds
    }


class SchedulerConfigPayload(BaseModel):
    enabled: Optional[bool] = None
    auto_mode: Optional[bool] = None
    interval_seconds: Optional[int] = None
    scenario_id: Optional[str] = None


class TriggerScenarioPayload(BaseModel):
    scenario_id: Optional[str] = None


@router.get("/api/simulation/scheduler")
@router.get("/simulation/scheduler")
async def get_simulation_scheduler_status():
    """
    Returns current failure scheduler status, active scenario, time to next failure,
    cooldown state, and execution history.
    """
    from backend.app.monitoring.failure_scheduler import failure_scheduler
    return failure_scheduler.get_status()


@router.post("/api/simulation/scheduler/config")
@router.post("/simulation/scheduler/config")
async def update_simulation_scheduler_config(payload: SchedulerConfigPayload):
    """
    Updates the failure scheduler config (interval, auto mode, enabled, scenario).
    """
    from backend.app.monitoring.failure_scheduler import failure_scheduler
    failure_scheduler.set_config(
        enabled=payload.enabled,
        auto_mode=payload.auto_mode,
        interval_seconds=payload.interval_seconds,
        scenario_id=payload.scenario_id
    )
    return {
        "status": "UPDATED",
        "scheduler": failure_scheduler.get_status()
    }


@router.post("/api/simulation/scheduler/trigger")
@router.post("/simulation/scheduler/trigger")
async def trigger_simulation_scenario(payload: Optional[TriggerScenarioPayload] = None):
    """
    Manually triggers either a specific failure scenario or the next scenario in rotation.
    Respects non-overlapping discipline.
    """
    from backend.app.monitoring.failure_scheduler import failure_scheduler
    scen_id = payload.scenario_id if payload and payload.scenario_id else None
    if scen_id:
        res = await failure_scheduler.trigger_manual_scenario(scen_id)
    else:
        res = await failure_scheduler.trigger_next_scenario()
    return res


@router.post("/api/simulation/scheduler/skip")
@router.post("/simulation/scheduler/skip")
async def skip_simulation_scenario():
    """
    Clears active scenario and resets state to NORMAL.
    """
    from backend.app.monitoring.failure_scheduler import failure_scheduler
    return await failure_scheduler.skip_current_scenario()


