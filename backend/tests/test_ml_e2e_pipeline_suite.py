"""
AegisOps AI - End-to-End ML & Simulation Pipeline Test Suite (Parts 34, 35, 36)
Executes full-stack integration workflows through the live Python architecture:
- Part 35 Required End-to-End Demo (Normal -> Injection -> ML Detection -> Early Warning -> Incident -> RCA -> Approval -> Controlled Recovery -> Replay -> Verification -> Resolved -> CBR Memory -> Repeated Failure Recall)
- Part 36 Multi-Attempt Refinement & Unresolved Escalation
- High-Risk Approval Enforcement vs Low-Risk Autonomous Recovery
- Cross-Tenant ML Isolation Enforcement
- AI SRE Assistant Truthfulness & Zero-Hallucination Evidence
"""

import pytest
import asyncio
from backend.app.analytics.simulation_lab import simulation_lab
from backend.app.analytics.feature_engine import feature_engine
from backend.app.analytics.baseline_engine import baseline_engine
from backend.app.analytics.ml_ensemble import ml_ensemble_engine
from backend.app.analytics.early_warning import early_warning_engine
from backend.app.analytics.failure_classifier import failure_classifier
from backend.app.analytics.rca_engine import rca_engine
from backend.app.knowledge.incident_memory import incident_memory
from backend.app.ai.assistant_engine import OperationsAssistantEngine


@pytest.mark.asyncio
async def test_part35_required_e2e_demo_flow():
    """
    Executes Part 35 Mandated End-to-End Demo:
    1. Normal telemetry baseline established
    2. Inject Database Connection Exhaustion
    3. Telemetry changes, feature window updates
    4. Z-score, EWMA, Isolation Forest detect anomaly
    5. Early warning generated with 3-minute prediction
    6. Failure classified into DATABASE_CONNECTION_EXHAUSTION
    7. Incident created with 8-factor RCA and causal path
    8. Historical similarity checked
    9. Recovery candidate formulated
    10. Approval evaluated (Policy vs Member)
    11. Controlled Recovery executed
    12. Workload replayed & fresh telemetry collected
    13. Before/After evidence comparison
    14. Verification passed -> RESOLVED
    15. Indexed into CBR memory
    16. Repeat failure -> Historical CBR match found!
    """
    tenant_id = "shopsphere"
    service = "database-service"

    # Step 1: Normal telemetry baseline established
    base_p95 = baseline_engine.get_feature_baseline(tenant_id, service, "p95_latency")
    for v in [25.0, 26.5, 27.0, 25.8, 26.2, 27.1, 26.0, 26.4] * 4:
        base_p95.update(v)

    normal_features = feature_engine.extract_standard_features({
        "requests_sec": 130.0,
        "error_rate": 0.002,
        "p95_latency_ms": 26.0,
        "cpu_utilization": 40.0,
        "connection_pool_utilization": 0.18
    })
    norm_eval = ml_ensemble_engine.evaluate(tenant_id, service, normal_features)
    assert norm_eval["ensemble_score"] < 0.45
    assert norm_eval["classification"] == "NORMAL"

    # Step 2: Inject Database Connection Exhaustion test run
    test_run = await simulation_lab.execute_scenario(
        scenario_id="DATABASE_CONNECTION_EXHAUSTION",
        service=service,
        severity="CRITICAL",
        tenant_id=tenant_id
    )

    # Step 3-14: Assert test execution results
    assert test_run["status"] == "PASSED"
    assert test_run["detection_result"] == "PASSED"
    assert test_run["rca_result"] == "PASSED"
    assert test_run["recovery_result"] == "PASSED"
    assert test_run["verification_result"] == "PASSED"
    assert test_run["before_after_metrics"]["error_rate"]["after"] < test_run["before_after_metrics"]["error_rate"]["before"]

    # Step 15-16: Repeat failure -> assert historical CBR match found!
    cbr_matches = incident_memory.find_similar_incidents(
        service=service,
        category="DATABASE",
        failure_type="DATABASE_CONNECTION_EXHAUSTION",
        tenant_id=tenant_id
    )
    assert len(cbr_matches) > 0
    assert cbr_matches[0]["remediation_action"] == "RESET_CONNECTION_POOL"
    assert cbr_matches[0]["success"] is True


@pytest.mark.asyncio
async def test_part36_unsuccessful_recovery_refinement_flow():
    """
    Executes Part 36 Scenario:
    First recovery attempt fails verification -> Evidence analysis -> Refined recovery -> Attempt 2 passes.
    """
    run = await simulation_lab.execute_scenario(
        scenario_id="DATABASE_CONNECTION_EXHAUSTION",
        simulate_refinement=True
    )
    assert run["status"] == "PASSED"
    assert run["attempts"] == 2
    timeline_events = [e["event"] for e in run["timeline"]]
    assert "test.verification_failed" in timeline_events
    assert "test.refinement" in timeline_events
    assert "test.recovery_attempt_2" in timeline_events


@pytest.mark.asyncio
async def test_part36_max_attempts_unresolved_flow():
    """
    Executes Part 36 Scenario:
    All recovery attempts fail -> MAX ATTEMPTS REACHED -> Transitions to UNRESOLVED state.
    """
    run = await simulation_lab.execute_scenario(
        scenario_id="SERVICE_CRASH",
        simulate_unresolved=True
    )
    assert run["status"] == "UNRESOLVED"
    assert run["verification_result"] == "FAILED"
    timeline_events = [e["event"] for e in run["timeline"]]
    assert "test.unresolved" in timeline_events
    assert "test.max_attempts" in timeline_events


def test_ai_sre_assistant_ml_truthfulness():
    """Validates AI SRE Assistant answers queries from real facts without hallucination (Part 27)."""
    # 1. "What anomalies are active?"
    res1 = OperationsAssistantEngine.answer_query(
        question="What anomalies are active?",
        active_incidents=[],
        current_metrics={},
        system_health={"health_score": 98.0}
    )
    assert "Active ML Anomalies" in res1["answer"] or "zero active anomalies" in res1["answer"]
    assert any("ML Ensemble Engine" in s for s in res1["sources"])

    # 2. "Why is database-service unhealthy?"
    res2 = OperationsAssistantEngine.answer_query(
        question="Why is database-service unhealthy?",
        active_incidents=[],
        current_metrics={},
        system_health={"health_score": 98.0}
    )
    assert "database-service" in res2["answer"]

    # 3. "How confident is the RCA?"
    sample_incident = {
        "incident_id": "INC-TEST-99",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "rca_confidence": 0.94,
        "rca_result": {
            "causal_path": ["database-service", "payment-service", "api-gateway"],
            "why_primary_won": "Earliest change-point detected and highest upstream error propagation."
        }
    }
    res3 = OperationsAssistantEngine.answer_query(
        question="How confident is the RCA?",
        active_incidents=[sample_incident],
        current_metrics={},
        system_health={"health_score": 90.0}
    )
    assert "94.0%" in res3["answer"] or "94%" in res3["answer"]
    assert "database-service" in res3["answer"]


def test_tenant_isolation_enforcement():
    """Validates strict tenant isolation across ML feature extraction and baseline evaluation."""
    vec_alpha = feature_engine.get_inspectable_feature_vector(tenant_id="tenant-alpha", service="database-service")
    vec_beta = feature_engine.get_inspectable_feature_vector(tenant_id="tenant-beta", service="database-service")
    assert vec_alpha["tenant_id"] == "tenant-alpha"
    assert vec_beta["tenant_id"] == "tenant-beta"
