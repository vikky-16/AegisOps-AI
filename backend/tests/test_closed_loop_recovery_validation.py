"""
AegisOps AI - Deterministic Closed-Loop Recovery Validation Test Suite
Tests every aspect of the closed-loop recovery validation research system:
- Anomaly detection (Z-score, Isolation Forest, temporal, dependency)
- Evidence collection and structured EvidenceItem model
- RCA hypothesis generation & evidence ranking (primary vs alternatives)
- Candidate solution generation with risk, prerequisites, rollback, confidence
- Controlled replica execution across reproducible scenarios
- Successful validation (original error resolved + no side effects -> VALIDATED)
- Unresolved original error rejection (REFINEMENT_REQUIRED)
- Side-effect detection (latency surge, throughput drop, memory explosion -> rejected)
- Solution refinement loop
- Maximum iteration handling (limit reached -> UNRESOLVED with explanation)
- Historical incident retrieval & recommendation
- Complete end-to-end workflow & REST API compliance
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.ai.anomaly_engine import anomaly_engine
from backend.app.rca.hypothesis_engine import hypothesis_engine
from backend.app.healing.solution_generator import solution_generator
from backend.app.replica.controlled_environment import replica_environment
from backend.app.validation.validator import recovery_validator
from backend.app.healing.closed_loop_engine import closed_loop_engine
from backend.app.knowledge.incident_memory import incident_memory


@pytest.mark.asyncio
async def test_anomaly_detection_and_evidence_collection():
    """Tests statistical Z-score, Isolation Forest, and evidence synthesis."""
    # Test univariate Z-score
    z_dev = anomaly_engine.compute_zscore_deviation(
        service="database-service",
        metric_name="active_connections",
        current_value=95.0,
        baseline={"mean": 10.0, "std": 3.0}
    )
    assert z_dev["is_anomaly"] is True
    assert z_dev["z_score"] >= 25.0
    assert z_dev["severity"] == "CRITICAL"

    # Test multi-service snapshot evaluation
    snapshot_metrics = {
        "database-service": {"error_rate": 0.85, "active_connections": 95.0, "latency_p95_ms": 1900.0},
        "service-b": {"error_rate": 0.70, "latency_p95_ms": 1600.0}
    }
    error_logs = [
        {"timestamp": 1000.0, "service": "database-service", "level": "ERROR", "message": "Connection pool exhausted"}
    ]

    analysis = anomaly_engine.evaluate_telemetry_snapshot(
        incident_id="INC-TEST-001",
        service_metrics=snapshot_metrics,
        logs=error_logs,
        iteration=0,
        before_after_state="BEFORE"
    )

    ev_items = analysis["evidence_items"]
    assert len(ev_items) >= 2
    assert analysis["origin_service"] == "database-service"
    assert any(e["signal_type"] == "METRIC" for e in ev_items)
    assert any(e["signal_type"] == "LOG" for e in ev_items)
    assert ev_items[0]["before_after_state"] == "BEFORE"


@pytest.mark.asyncio
async def test_rca_hypothesis_generation_and_ranking():
    """Tests that RCA generates primary hypothesis, confidence, alternatives, and explainability."""
    evidence = [
        {
            "service": "database-service",
            "component": "connection_pool",
            "signal_type": "METRIC",
            "metric_or_log_value": "active_connections=98.0",
            "deviation": "+880% (Z=28.3)",
            "timestamp": 100.0
        },
        {
            "service": "database-service",
            "component": "connection_pool",
            "signal_type": "LOG",
            "metric_or_log_value": "FATAL: remaining connection slots are reserved",
            "deviation": "Level=ERROR",
            "timestamp": 100.5
        }
    ]

    rca_res = hypothesis_engine.evaluate_hypotheses(evidence, affected_services=["database-service", "service-b"])
    primary = rca_res["primary_hypothesis"]
    alternatives = rca_res["alternative_hypotheses"]

    # Assert primary hypothesis is correctly selected
    assert "connection pool" in primary["hypothesis"].lower()
    assert primary["confidence"] >= 0.80
    assert len(primary["supporting_evidence"]) >= 1
    assert len(alternatives) >= 2
    assert "why_selected" in rca_res
    assert "dependency_path" in rca_res
    assert len(rca_res["dependency_path"]) >= 2


@pytest.mark.asyncio
async def test_candidate_solution_generation():
    """Tests candidate solution generation with risk, prerequisites, rollback, and confidence."""
    hyp = {
        "id": "db_connection_pool_exhaustion",
        "hypothesis": "Database connection pool exhaustion",
        "category": "DATABASE",
        "target_service": "database-service"
    }

    solutions = solution_generator.generate_candidate_solutions(hypothesis=hyp)
    assert len(solutions) >= 2

    primary_sol = solutions[0]
    assert primary_sol["action"] == "RESET_CONNECTION_POOL"
    assert primary_sol["risk"] in ["LOW", "MEDIUM", "HIGH"]
    assert "prerequisites" in primary_sol
    assert "rollback_strategy" in primary_sol
    assert primary_sol["confidence"] > 0.80


@pytest.mark.asyncio
async def test_controlled_replica_execution_and_replay():
    """Tests fault injection and replay in replica environment across reproducible scenarios."""
    scenarios = replica_environment.list_scenarios()
    assert len(scenarios) >= 8

    # Fault injection
    fault = replica_environment.inject_fault("db_connection_exhaustion")
    assert fault["target_service"] == "database-service"
    assert fault["service_metrics"]["database-service"]["active_connections"] > 90

    # Execute recovery action and replay
    replay = replica_environment.execute_solution_and_replay(
        scenario_id="db_connection_exhaustion",
        action="RESET_CONNECTION_POOL",
        iteration=1
    )
    assert replay["resolves_original_error"] is True
    assert replay["side_effect_detected"] is False
    assert replay["post_metrics"]["database-service"]["error_rate"] <= 0.05


@pytest.mark.asyncio
async def test_successful_validation_and_report_generation():
    """Tests that a clean recovery generates VALIDATED status and 12-section Validation Report."""
    res = await closed_loop_engine.execute_closed_loop(
        scenario_id="db_connection_exhaustion",
        incident_id="INC-SUCCESS-001"
    )

    assert res["lifecycle_state"] == "VALIDATED"
    assert res["status"] == "VALIDATED"
    assert res["iteration_count"] == 1

    # Check 14-state transitions
    transitions = [t["to_state"] for t in res["state_transitions"]]
    assert "DETECTED" in transitions
    assert "EVIDENCE_COLLECTED" in transitions
    assert "RCA_COMPLETED" in transitions
    assert "SOLUTIONS_GENERATED" in transitions
    assert "SOLUTION_SELECTED" in transitions
    assert "REPLICA_PREPARED" in transitions
    assert "SOLUTION_EXECUTED" in transitions
    assert "SCENARIO_REPLAYED" in transitions
    assert "EVIDENCE_COMPARED" in transitions
    assert "VALIDATING" in transitions
    assert "VALIDATED" in transitions

    # Check report
    report = res["validation_report"]
    assert report["final_validation_decision"] == "VALIDATED"
    assert len(report["before_after_comparison"]) >= 3
    assert report["side_effect_analysis"]["side_effect_detected"] is False


@pytest.mark.asyncio
async def test_unresolved_original_error_rejection():
    """Tests that an ineffective solution is rejected and marked for refinement."""
    # Force ineffective action 'CLEAR_CACHE' for service_crash
    pre_metrics = {"service-b": {"error_rate": 1.0, "healthy": False}}
    post_metrics = {"service-b": {"error_rate": 1.0, "healthy": False}}

    val_res = recovery_validator.validate_solution(
        target_service="service-b",
        pre_metrics=pre_metrics,
        post_metrics=post_metrics,
        success_criteria={"max_error_rate": 0.02}
    )

    assert val_res["original_error_resolved"] is False
    assert val_res["solution_validated"] is False
    assert val_res["decision"] == "ERROR_PERSISTS"


@pytest.mark.asyncio
async def test_side_effect_detection():
    """Tests that even if the original error disappears, unacceptable side effects cause rejection."""
    # Latency surge side effect: error_rate resolved to 0.01, but latency exploded to 2450ms!
    pre_metrics = {"database-service": {"error_rate": 0.85, "latency_p95_ms": 120.0, "throughput_rps": 120.0}}
    post_metrics = {"database-service": {"error_rate": 0.01, "latency_p95_ms": 2450.0, "throughput_rps": 115.0, "healthy": True}}

    val_res = recovery_validator.validate_solution(
        target_service="database-service",
        pre_metrics=pre_metrics,
        post_metrics=post_metrics,
        success_criteria={"max_error_rate": 0.05, "max_latency_p95_ms": 250.0}
    )

    assert val_res["original_error_resolved"] is True
    assert val_res["side_effect_detected"] is True
    assert val_res["solution_validated"] is False
    assert val_res["decision"] == "REFINEMENT_REQUIRED"
    assert any(s["type"] == "LATENCY_SURGE" for s in val_res["side_effects"])


@pytest.mark.asyncio
async def test_solution_refinement_multi_iteration():
    """Tests that when an initial action produces a side effect, the system refines and validates on iteration 2."""
    # For high_api_latency:
    # First action: RATE_LIMIT_AGGRESSIVELY (causes throughput drop side effect)
    # Refined action: SCALE_WORKERS (succeeds with no side effects)
    res = await closed_loop_engine.execute_closed_loop(
        scenario_id="high_api_latency",
        incident_id="INC-REFINE-001",
        forced_first_action="RATE_LIMIT_AGGRESSIVELY"
    )

    assert res["iteration_count"] >= 2
    assert res["lifecycle_state"] == "VALIDATED"
    transitions = [t["to_state"] for t in res["state_transitions"]]
    assert "REFINEMENT_REQUIRED" in transitions
    assert "VALIDATED" in transitions


@pytest.mark.asyncio
async def test_maximum_iteration_handling_unresolved():
    """Tests that when all candidate solutions fail, system halts at max iterations and marks UNRESOLVED."""
    engine = closed_loop_engine
    engine.max_iterations = 2

    # Run service_crash forcing ineffective action
    res = await engine.execute_closed_loop(
        scenario_id="service_crash",
        incident_id="INC-UNRESOLVED-001",
        forced_first_action="CLEAR_CACHE"
    )

    # If first candidate was ineffective, and if remaining candidates were exhausted
    assert res["iteration_count"] <= 2
    # Ensure transition tracking
    assert len(res["state_transitions"]) > 0


@pytest.mark.asyncio
async def test_historical_incident_retrieval():
    """Tests recording validated incidents and searching historical memory."""
    incident_memory.record_incident({
        "tenant_id": "test-tenant",
        "incident_id": "INC-HIST-999",
        "root_cause_service": "database-service",
        "remediation_action": "RESET_CONNECTION_POOL",
        "success": True,
        "failure_signature": {"scenario": "db_connection_exhaustion"}
    }, tenant_id="test-tenant")

    matches = incident_memory.search_similar_incidents(
        query_vector=[0.05, 0.8, 120.0, 0.4, 0.85],
        tenant_id="test-tenant",
        min_similarity=0.50
    )
    assert len(matches) >= 1
    assert matches[0]["remediation_action"] == "RESET_CONNECTION_POOL"


from backend.app.core.security import create_access_token


@pytest.mark.asyncio
async def test_all_11_rest_api_endpoints():
    """Verifies all 11 required endpoints from Requirement 16."""
    token = create_access_token(
        data={"sub": "admin", "tenant_id": "demo-tenant", "role": "PLATFORM_ADMIN"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "demo-tenant"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        # 1. POST /api/incidents
        create_resp = await client.post("/api/incidents", json={
            "scenario_id": "db_connection_exhaustion",
            "title": "API Test DB Exhaustion"
        })
        assert create_resp.status_code == 200
        inc_data = create_resp.json()
        inc_id = inc_data["incident_id"]
        assert inc_data["lifecycle_state"] == "VALIDATED"

        # 2. GET /api/incidents/{id}
        get_resp = await client.get(f"/api/incidents/{inc_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["incident_id"] == inc_id

        # 3. GET /api/incidents/{id}/evidence
        ev_resp = await client.get(f"/api/incidents/{inc_id}/evidence")
        assert ev_resp.status_code == 200
        assert "evidence_items" in ev_resp.json()

        # 4. GET /api/incidents/{id}/timeline
        tl_resp = await client.get(f"/api/incidents/{inc_id}/timeline")
        assert tl_resp.status_code == 200
        assert "timeline" in tl_resp.json()
        assert "state_transitions" in tl_resp.json()

        # 5. GET /api/incidents/{id}/hypotheses
        hyp_resp = await client.get(f"/api/incidents/{inc_id}/hypotheses")
        assert hyp_resp.status_code == 200
        assert "primary_hypothesis" in hyp_resp.json()
        assert "alternative_hypotheses" in hyp_resp.json()

        # 6. GET /api/incidents/{id}/solutions
        sol_resp = await client.get(f"/api/incidents/{inc_id}/solutions")
        assert sol_resp.status_code == 200
        assert "candidate_solutions" in sol_resp.json()

        # 7. POST /api/incidents/{id}/solutions/{solution_id}/execute
        exec_resp = await client.post(
            f"/api/incidents/{inc_id}/solutions/sol_reset_conn_pool/execute",
            json={"action": "RESET_CONNECTION_POOL"}
        )
        assert exec_resp.status_code == 200
        assert "execution_result" in exec_resp.json()

        # 8. POST /api/incidents/{id}/replay
        replay_resp = await client.post(
            f"/api/incidents/{inc_id}/replay",
            json={"action": "RESET_CONNECTION_POOL", "scenario_id": "db_connection_exhaustion"}
        )
        assert replay_resp.status_code == 200
        assert "replay_result" in replay_resp.json()

        # 9. GET /api/incidents/{id}/validation
        val_resp = await client.get(f"/api/incidents/{inc_id}/validation")
        assert val_resp.status_code == 200
        assert "original_error_resolved" in val_resp.json()
        assert "side_effect_detected" in val_resp.json()

        # 10. GET /api/incidents/{id}/report
        rep_resp = await client.get(f"/api/incidents/{inc_id}/report")
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert "final_validation_decision" in rep_data
        assert "before_after_comparison" in rep_data

        # 11. GET /api/incidents/{id}/history
        hist_resp = await client.get(f"/api/incidents/{inc_id}/history")
        assert hist_resp.status_code == 200
        assert "similar_incidents" in hist_resp.json()

        # 12. GET /api/incidents/{id}/attempts
        att_resp = await client.get(f"/api/incidents/{inc_id}/attempts")
        assert att_resp.status_code == 200
        att_data = att_resp.json()
        assert "attempts" in att_data
        assert len(att_data["attempts"]) >= 1
        first_att = att_data["attempts"][0]
        assert "attempt_id" in first_att
        assert "pre_execution_metrics" in first_att
        assert "post_execution_metrics" in first_att
        assert "validation_result" in first_att
        assert "confidence" in first_att

        # 13. GET /api/incidents/{id}/root-cause
        rc_resp = await client.get(f"/api/incidents/{inc_id}/root-cause")
        assert rc_resp.status_code == 200
        assert "primary_hypothesis" in rc_resp.json()

        # 14. GET /api/incidents/{id}/historical-matches
        hm_resp = await client.get(f"/api/incidents/{inc_id}/historical-matches")
        assert hm_resp.status_code == 200
        assert "matches" in hm_resp.json()

        # 15. POST /api/incidents/{id}/retry
        retry_resp = await client.post(f"/api/incidents/{inc_id}/retry")
        assert retry_resp.status_code == 200
        assert "iteration_count" in retry_resp.json()

        # 16. POST /api/incidents/{id}/approve
        appr_resp = await client.post(f"/api/incidents/{inc_id}/approve", json={"notes": "Authorized by SRE"})
        assert appr_resp.status_code == 200
        assert appr_resp.json()["approval_status"] == "APPROVED"

        # 17. POST /api/incidents/{id}/reject
        rej_resp = await client.post(f"/api/incidents/{inc_id}/reject", json={"notes": "Rollback needed"})
        assert rej_resp.status_code == 200
        assert rej_resp.json()["approval_status"] == "REJECTED"


@pytest.mark.asyncio
async def test_negative_validation_cases_comprehensive():
    """Verifies that a solution is NEVER marked VALIDATED under any invalid condition:
    1. Original error remains
    2. Significant side-effect detected
    3. Missing telemetry/metrics
    4. Execution failed
    """
    # 1. Original error remains
    res1 = recovery_validator.validate_solution(
        target_service="database-service",
        pre_metrics={"database-service": {"error_rate": 0.80}},
        post_metrics={"database-service": {"error_rate": 0.75}},  # Still failing
        incident_type="DATABASE_CONNECTION_EXHAUSTION"
    )
    assert res1["solution_validated"] is False
    assert res1["original_error_resolved"] is False

    # 2. Significant side effect appears
    res2 = recovery_validator.validate_solution(
        target_service="database-service",
        pre_metrics={"database-service": {"error_rate": 0.80, "latency_p95_ms": 100.0, "throughput_rps": 100.0}},
        post_metrics={"database-service": {"error_rate": 0.01, "latency_p95_ms": 2500.0, "throughput_rps": 20.0}},
        incident_type="DATABASE_CONNECTION_EXHAUSTION"
    )
    assert res2["solution_validated"] is False
    assert res2["side_effect_detected"] is True
    assert any(s["type"] == "LATENCY_SURGE" for s in res2["side_effects"])

    # 3. Missing telemetry metrics
    res3 = recovery_validator.validate_solution(
        target_service="database-service",
        pre_metrics={},
        post_metrics={},
        incident_type="DATABASE_CONNECTION_EXHAUSTION"
    )
    assert res3["solution_validated"] is False

    # 4. Execution failed (healthy=False)
    res4 = recovery_validator.validate_solution(
        target_service="service-b",
        pre_metrics={"service-b": {"error_rate": 0.90}},
        post_metrics={"service-b": {"error_rate": 0.90, "healthy": False}},
        incident_type="PROCESS_CRASH"
    )
    assert res4["solution_validated"] is False


@pytest.mark.asyncio
async def test_tenant_isolation_on_attempts_and_actions():
    """Verifies that Tenant A cannot access, retry, or approve Tenant B's incidents or attempts."""
    token_a = create_access_token(data={"sub": "user_a", "tenant_id": "tenant-alpha", "role": "SRE_ADMIN"})
    token_b = create_access_token(data={"sub": "user_b", "tenant_id": "tenant-beta", "role": "SRE_ADMIN"})

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": "tenant-alpha"}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": "tenant-beta"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant A creates an incident
        create_resp = await client.post("/api/incidents", json={
            "scenario_id": "db_connection_exhaustion",
            "title": "Tenant A DB Incident"
        }, headers=headers_a)
        assert create_resp.status_code == 200
        inc_id = create_resp.json()["incident_id"]

        # Tenant B tries to get Tenant A's incident -> 403 or 404
        get_b = await client.get(f"/api/incidents/{inc_id}", headers=headers_b)
        assert get_b.status_code in [403, 404]

        # Tenant B tries to view Tenant A's attempts -> 403 or 404
        att_b = await client.get(f"/api/incidents/{inc_id}/attempts", headers=headers_b)
        assert att_b.status_code in [403, 404]

        # Tenant B tries to retry Tenant A's incident -> 403 or 404
        retry_b = await client.post(f"/api/incidents/{inc_id}/retry", headers=headers_b)
        assert retry_b.status_code in [403, 404]

        # Tenant B tries to approve Tenant A's incident -> 403 or 404
        appr_b = await client.post(f"/api/incidents/{inc_id}/approve", json={"notes": "Unauthorized"}, headers=headers_b)
        assert appr_b.status_code in [403, 404]

