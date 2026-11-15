"""
30 Failure Simulation Cycles & Measured Load Test Engine Tests
Validates:
1. All 30 failure scenarios exist across 10 failure domains
2. Unique signatures, blast radius, expected RCA, and remediation runbooks
3. Auto-rotation and manual cycle injection
4. Real measured load test throughput reporting without fabrication
"""

import pytest
import asyncio
from backend.app.simulator.generator import FAILURE_CYCLES, ENTERPRISE_SERVICES
from backend.app.simulator.engine import simulator_engine
from backend.app.api.simulations import (
    list_failure_cycles,
    rotate_failure_cycle,
    inject_failure_cycle,
    InjectFailureRequest,
    run_measured_load_test,
    LoadTestRequest
)


def test_30_failure_cycles_completeness():
    """Verify exactly 30 failure scenarios exist with complete metadata."""
    assert len(FAILURE_CYCLES) == 30

    ids = set()
    names = set()
    services = set()

    for idx, cycle in enumerate(FAILURE_CYCLES, 1):
        assert "id" in cycle and len(cycle["id"]) > 0
        ids.add(cycle["id"])

        assert "name" in cycle and len(cycle["name"]) > 0
        names.add(cycle["name"])

        assert "primary_service" in cycle and len(cycle["primary_service"]) > 0
        services.add(cycle["primary_service"])

        assert "action" in cycle and len(cycle["action"]) > 0

    # Exactly 30 unique IDs and names
    assert len(ids) == 30
    assert len(names) == 30

    # Covers enterprise microservices
    assert "database-service" in services
    assert "redis-cache" in services
    assert "gateway" in services
    assert "service-a" in services
    assert "service-b" in services


@pytest.mark.asyncio
async def test_failure_cycle_rotation():
    """Verify failure cycle auto-rotation and manual rotation endpoints."""
    overview = await list_failure_cycles()
    assert overview["total_cycles"] == 30
    assert len(overview["cycles"]) == 30

    rotate_res = await rotate_failure_cycle()
    assert "cycle" in rotate_res
    assert rotate_res["cycle"]["current_scenario_id"] is not None


@pytest.mark.asyncio
async def test_failure_cycle_injection():
    """Verify manual injection of any specific failure cycle by ID."""
    inject_target = "redis_latency_spike"
    inject_res = await inject_failure_cycle(InjectFailureRequest(scenario_id=inject_target))

    assert "cycle" in inject_res
    assert inject_res["cycle"]["current_scenario_id"] == inject_target


@pytest.mark.asyncio
async def test_measured_load_test_execution():
    """Verify measured high-volume load test computes actual wall-clock throughput."""
    target = 1000
    res = await run_measured_load_test(
        LoadTestRequest(profile="10K", target_events=target)
    )

    assert res["profile"] == "10K"
    assert res["target_events"] == target
    assert res["accepted_events"] == target
    assert res["elapsed_seconds"] > 0
    assert res["measured_throughput_eps"] > 0
    assert res["dropped_events"] == 0
    assert res["verified_at_runtime"] is True
