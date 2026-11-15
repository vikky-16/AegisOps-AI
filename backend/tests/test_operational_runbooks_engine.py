import pytest
import asyncio
from backend.app.runbooks.operational_runbooks import operational_runbook_engine
from backend.app.monitoring.collector import collector

@pytest.mark.asyncio
async def test_all_16_runbooks_loaded():
    runbooks = operational_runbook_engine.list_runbooks()
    assert len(runbooks) >= 16
    
    expected_ids = [
        "RB-DB-POOL-01",
        "RB-REDIS-CONN-01",
        "RB-HTTP500-SURGE-01",
        "RB-HTTP502-GATEWAY-01",
        "RB-HTTP503-UNAVAIL-01",
        "RB-DB-TIMEOUT-01",
        "RB-LATENCY-SPIKE-01",
        "RB-REQ-TIMEOUT-01",
        "RB-SERVICE-CRASH-01",
        "RB-DEPENDENCY-FAIL-01",
        "RB-CACHE-FAIL-01",
        "RB-CPU-SPIKE-01",
        "RB-MEM-PRESSURE-01",
        "RB-NET-TIMEOUT-01",
        "RB-QUEUE-BACKLOG-01",
        "RB-DEPLOY-REGRESS-01"
    ]
    for r_id in expected_ids:
        rb = operational_runbook_engine.get_runbook(r_id)
        assert rb is not None, f"Missing expected runbook {r_id}"
        assert rb["name"]
        assert rb["version"]
        assert rb["diagnostic_steps"]
        assert rb["recovery_steps"]
        assert rb["verification_steps"]

@pytest.mark.asyncio
async def test_runbook_recommendation_for_db_pool():
    fake_incident = {
        "incident_id": "INC-TEST-001",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause": "Database connection pool exhaustion",
        "root_cause_summary": "Database connection pool exhaustion with 18x timeout spike",
        "recommended_action": "RESET_CONNECTION_POOL",
        "root_cause_confidence": 0.95,
        "affected_services": ["database-service", "service-b", "service-a"]
    }
    
    recommendations = operational_runbook_engine.find_recommended_runbook_for_incident(fake_incident)
    assert len(recommendations) > 0
    top_rec = recommendations[0]
    assert top_rec["runbook_id"] == "RB-DB-POOL-01"
    assert top_rec["match_score_pct"] >= 75.0
    assert "root_cause" in top_rec["why_this_action"]

@pytest.mark.asyncio
async def test_approval_gated_runbook_execution():
    fake_incident = {
        "incident_id": "INC-TEST-002",
        "primary_service": "service-a",
        "root_cause_service": "service-a",
        "status": "DETECTED",
        "approval_status": "PENDING_APPROVAL",
        "recommended_action": "RESTART_SERVICE"
    }
    
    # Executing HIGH risk runbook requiring approval (RB-DEPLOY-REGRESS-01) without approval should pause at AWAITING_APPROVAL
    res = await operational_runbook_engine.execute_runbook_for_incident(
        runbook_id="RB-DEPLOY-REGRESS-01",
        incident=fake_incident,
        caller="TestRunner"
    )
    assert res["status"] == "AWAITING_APPROVAL"
    assert not res["success"]
    
    # Now simulate approval
    fake_incident["approval_status"] = "APPROVED"
    fake_incident["status"] = "APPROVED"
    
    approved_res = await operational_runbook_engine.execute_runbook_for_incident(
        runbook_id="RB-DEPLOY-REGRESS-01",
        incident=fake_incident,
        caller="TestRunner"
    )
    assert approved_res["status"] == "RESOLVED"
    assert approved_res["success"] is True
    assert approved_res["execution"]["current_stage"] == "COMPLETE"
    assert len(approved_res["execution"]["steps"]) >= 6

@pytest.mark.asyncio
async def test_learning_statistics_update():
    stats = operational_runbook_engine.get_statistics()
    assert "total_runbooks" in stats
    assert "total_executions" in stats
    assert "global_success_rate_pct" in stats
    assert stats["total_runbooks"] == 16
    assert stats["global_success_rate_pct"] > 90.0
