"""
AegisOps AI - Testing & Simulation Lab Test Suite (Part 34: 15+ Tests)
Tests testing lab features:
- Environmental safety indicators (Part 15)
- 12-category failure scenario catalog (Part 16)
- Test execution engine & real event timeline (Part 17)
- Before / After metric telemetry comparisons (Part 18)
- Chaos / Failure Matrix calculations (Part 19)
- Test history persistence & filtering (Part 20)
- Multi-attempt refinement & UNRESOLVED state transition (Part 21 & 36)
- Side effect verification
"""

import pytest
import asyncio
from backend.app.analytics.simulation_lab import simulation_lab, FAILURE_SCENARIO_CATALOG


# -------------------------------------------------------------
# 1. Environment Status & Catalog Tests
# -------------------------------------------------------------

def test_environment_status():
    """Validates header environmental indicators adhere to Part 15 specifications."""
    status = simulation_lab.get_environment_status()
    assert status["environment"] == "CONTROLLED_CUSTOMER_TEST"
    assert status["safety"] == "ISOLATED"
    assert status["telemetry"] == "LIVE"
    assert status["recovery"] == "CONTROLLED"
    assert status["approval"] == "ENFORCED"


def test_scenario_catalog_categories():
    """Validates catalog covers all 12 operational categories."""
    catalog = simulation_lab.get_catalog()
    assert len(catalog) == 12
    categories = {s["category"] for s in catalog}
    expected = {
        "NETWORK", "DATABASE", "CACHE", "SERVICE", "HTTP", "PERFORMANCE",
        "RESOURCE", "DEPENDENCY", "DEPLOYMENT", "SECURITY", "CASCADING", "TRAFFIC"
    }
    assert expected == categories


def test_scenario_catalog_metadata():
    """Validates each scenario contains all mandated fields."""
    for sc in simulation_lab.get_catalog():
        assert "id" in sc
        assert "name" in sc
        assert "category" in sc
        assert "description" in sc
        assert "target_service" in sc
        assert "expected_symptoms" in sc
        assert "expected_detection" in sc
        assert "expected_rca" in sc
        assert "expected_recovery" in sc
        assert "risk" in sc
        assert "verification_method" in sc


# -------------------------------------------------------------
# 2. Test Execution & Real Event Timeline Tests (Async)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_database_connection_exhaustion():
    """Validates happy path execution generates real timeline events and passes verification."""
    run = await simulation_lab.execute_scenario(
        scenario_id="DATABASE_CONNECTION_EXHAUSTION",
        service="database-service",
        tenant_id="shopsphere"
    )
    assert run["status"] == "PASSED"
    assert run["detection_result"] == "PASSED"
    assert run["rca_result"] == "PASSED"
    assert run["recovery_result"] == "PASSED"
    assert run["verification_result"] == "PASSED"
    assert run["attempts"] == 1
    assert run["duration_sec"] > 0.0

    # Validate real timeline events exist
    events = [e["event"] for e in run["timeline"]]
    assert "test.started" in events
    assert "test.failure_injected" in events
    assert "test.anomaly_detected" in events
    assert "test.rca_completed" in events
    assert "test.verification_passed" in events
    assert "test.completed" in events


@pytest.mark.asyncio
async def test_execute_before_after_metrics():
    """Validates Before / After comparison exhibits metric restoration."""
    run = await simulation_lab.execute_scenario(
        scenario_id="HTTP_500_SPIKE",
        service="order-service",
        tenant_id="shopsphere"
    )
    metrics = run["before_after_metrics"]
    assert "error_rate" in metrics
    assert "latency_p95_ms" in metrics
    assert metrics["error_rate"]["before"] > metrics["error_rate"]["after"]


@pytest.mark.asyncio
async def test_execute_multi_attempt_refinement():
    """Validates multi-attempt refinement scenario (Attempt 1 fails -> refined recovery -> Attempt 2 passes)."""
    run = await simulation_lab.execute_scenario(
        scenario_id="DATABASE_CONNECTION_EXHAUSTION",
        simulate_refinement=True
    )
    assert run["status"] == "PASSED"
    assert run["attempts"] == 2
    events = [e["event"] for e in run["timeline"]]
    assert "test.verification_failed" in events
    assert "test.refinement" in events
    assert "test.recovery_attempt_2" in events


@pytest.mark.asyncio
async def test_execute_unresolved_state_transition():
    """Validates max attempts exhaustion transitions incident to UNRESOLVED state (Part 36)."""
    run = await simulation_lab.execute_scenario(
        scenario_id="SERVICE_CRASH",
        simulate_unresolved=True
    )
    assert run["status"] == "UNRESOLVED"
    assert run["verification_result"] == "FAILED"
    events = [e["event"] for e in run["timeline"]]
    assert "test.unresolved" in events
    assert "test.max_attempts" in events


@pytest.mark.asyncio
async def test_execute_side_effect_detection():
    """Validates side effect detection is captured in test record."""
    run = await simulation_lab.execute_scenario(
        scenario_id="CACHE_FAILURE",
        simulate_side_effect=True
    )
    assert run["side_effects"] != "NONE"


# -------------------------------------------------------------
# 3. Chaos / Failure Matrix & History Tests
# -------------------------------------------------------------

def test_chaos_matrix_generation():
    """Validates chaos matrix computes real coverage across categories."""
    matrix = simulation_lab.get_matrix()
    assert len(matrix) >= 5
    for row in matrix:
        assert "category" in row
        assert "total_runs" in row
        assert "detection" in row
        assert "rca" in row
        assert "recovery" in row
        assert "verification" in row
        assert "success_rate_pct" in row


def test_test_history_filtering():
    """Validates test history filters by service and result."""
    history = simulation_lab.get_test_history(limit=50)
    assert len(history) > 0

    filtered_svc = simulation_lab.get_test_history(service="database-service")
    for r in filtered_svc:
        assert r["service"] == "database-service"

    filtered_res = simulation_lab.get_test_history(result="PASSED")
    for r in filtered_res:
        assert r["status"] == "PASSED"
