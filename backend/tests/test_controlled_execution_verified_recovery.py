"""
AegisOps AI - Comprehensive Test Suite for Controlled Execution & Verified Recovery Engine
Validates:
1. Standard success scenario (DB pool exhaustion -> Reset -> Verify -> Resolved)
2. Multi-attempt refinement scenario (Attempt 1 insufficient -> Refine -> Attempt 2 succeeds -> Resolved)
3. Unresolvable failure scenario (3 attempts fail -> Max attempts reached -> UNRESOLVED)
4. Approval gate enforcement (Missing approval -> 403 / AWAITING_APPROVAL)
5. Pre/Post telemetry snapshot and comparison calculations
6. Weighted verification score and side-effect detection
7. AI SRE Assistant operational recovery queries
"""

import pytest
import asyncio
from backend.app.healing.controlled_execution_engine import (
    controlled_execution_engine,
    ALLOWLISTED_ACTIONS
)
from backend.app.ai.assistant_engine import OperationsAssistantEngine
from backend.app.monitoring.collector import collector


@pytest.fixture
def sample_db_incident():
    return {
        "incident_id": "INC-TEST-DB-001",
        "title": "Database Connection Pool Saturation on database-service",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "service-b", "service-a"],
        "status": "OPEN",
        "lifecycle_state": "OPEN",
        "recommended_action": "RESET_CONNECTION_POOL",
        "recommended_runbook_id": "RB-DB-POOL-01",
        "action_risk_level": "LOW",
        "root_cause_confidence": 0.95,
        "rca_confidence": 0.95,
        "approval_status": "APPROVED",  # Pre-approved for standard test
        "timeline": []
    }


@pytest.mark.asyncio
async def test_all_allowlisted_actions_registered():
    """Verify all 6 core allowlisted actions are properly configured with metadata."""
    actions = controlled_execution_engine.get_allowlisted_actions()
    assert len(actions) >= 6
    required_keys = [
        "RESET_CONNECTION_POOL",
        "RECONNECT_DATABASE",
        "CLEAR_CACHE",
        "RESTART_CONTROLLED_SERVICE",
        "SCALE_WORKERS",
        "ROLLBACK_CONTROLLED_DEPLOYMENT"
    ]
    for k in required_keys:
        assert k in actions
        spec = actions[k]
        assert spec["name"]
        assert spec["description"]
        assert spec["risk"] in ["LOW", "MEDIUM", "HIGH"]
        assert len(spec["supported_services"]) > 0
        assert spec["timeout_sec"] > 0
        assert spec["max_attempts"] > 0


@pytest.mark.asyncio
async def test_safety_check_evaluation(sample_db_incident):
    """Verify all 9 safety checks evaluate accurately."""
    safety = controlled_execution_engine.evaluate_safety_checks(
        incident=sample_db_incident,
        action="RESET_CONNECTION_POOL"
    )
    assert safety["all_passed"] is True
    assert safety["status"] == "SAFETY_CHECKS_PASSED"
    assert "incident_active" in safety["checks"]
    assert "rca_confidence" in safety["checks"]
    assert "target_service_healthy_enough" in safety["checks"]
    assert "action_supported" in safety["checks"]
    assert "approval_present" in safety["checks"]
    assert "no_conflicting_recovery" in safety["checks"]

    # Test safety block on resolved incident
    sample_db_incident["status"] = "RESOLVED"
    blocked_safety = controlled_execution_engine.evaluate_safety_checks(
        incident=sample_db_incident,
        action="RESET_CONNECTION_POOL"
    )
    assert blocked_safety["all_passed"] is False
    assert blocked_safety["status"] == "EXECUTION_BLOCKED"
    assert "RESOLVED" in blocked_safety["primary_blocked_reason"]


@pytest.mark.asyncio
async def test_approval_gate_enforcement():
    """Verify high-risk actions without approval are blocked from executing."""
    unapproved_incident = {
        "incident_id": "INC-TEST-APPROV-001",
        "title": "Severe deployment regression on service-a",
        "primary_service": "service-a",
        "root_cause_service": "service-a",
        "affected_services": ["service-a", "gateway"],
        "status": "OPEN",
        "recommended_action": "RESTART_CONTROLLED_SERVICE",  # MEDIUM risk requires approval
        "action_risk_level": "MEDIUM",
        "approval_status": "PENDING_APPROVAL",
        "timeline": []
    }

    result = await controlled_execution_engine.execute_controlled_recovery(
        incident=unapproved_incident,
        action_override="RESTART_CONTROLLED_SERVICE",
        caller="TestRunner"
    )
    assert result["success"] is False
    assert result["status"] == "AWAITING_APPROVAL"
    assert unapproved_incident["status"] == "AWAITING_APPROVAL"


@pytest.mark.asyncio
async def test_standard_recovery_and_empirical_verification(sample_db_incident):
    """
    Test 1: Standard Success Scenario.
    Executes controlled recovery, collects fresh telemetry, replays workflow,
    compares before/after metrics, computes >=85% score, verifies, and resolves incident.
    """
    result = await controlled_execution_engine.execute_controlled_recovery(
        incident=sample_db_incident,
        action_override="RESET_CONNECTION_POOL",
        caller="TestRunner"
    )

    assert result["success"] is True
    assert result["status"] == "RESOLVED"
    assert result["attempts"] == 1
    
    exec_record = result["execution"]
    assert exec_record["current_stage"] == "VERIFIED"
    assert exec_record["pre_execution_snapshot"] is not None
    assert exec_record["post_execution_snapshot"] is not None
    assert exec_record["comparison"] is not None

    # Before / After Comparison validation
    comp = exec_record["comparison"]
    assert "error_rate" in comp
    assert "latency_p95" in comp
    assert "database_timeouts" in comp
    assert comp["database_timeouts"]["after"] == "0/sec"

    # Verification Score
    verif = result["verification"]
    assert verif["verified"] is True
    assert verif["verdict"] == "RECOVERY_VERIFIED"
    assert verif["verification_score_pct"] >= 85.0
    assert verif["original_problem"]["passed"] is True
    assert verif["workflow_replay"]["passed"] is True
    assert verif["dependencies"]["passed"] is True
    assert verif["side_effects_detected"] is False

    # Incident state synchronized to RESOLVED only after verified recovery
    assert sample_db_incident["status"] == "RESOLVED"
    assert sample_db_incident["recovery_status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_two_attempt_recovery_refinement(sample_db_incident):
    """
    Test 2: Multi-Attempt Refinement Scenario.
    Attempt 1 is intentionally insufficient (Payment Service connection remains stale).
    System detects VERIFICATION_FAILED, analyzes failure, refines candidate to RECONNECT_DATABASE,
    executes attempt 2, verifies, and resolves incident.
    """
    sample_db_incident["status"] = "OPEN"
    sample_db_incident["approval_status"] = "APPROVED"

    result = await controlled_execution_engine.execute_controlled_recovery(
        incident=sample_db_incident,
        action_override="RESET_CONNECTION_POOL",
        caller="TestRunner",
        simulate_insufficient_attempt=True
    )

    assert result["success"] is True
    assert result["status"] == "RESOLVED"
    assert result["attempts"] == 2
    
    exec_record = result["execution"]
    assert len(exec_record["attempts_history"]) == 2
    assert exec_record["attempts_history"][0]["status"] == "FAILED"
    assert exec_record["attempts_history"][1]["status"] == "VERIFIED"
    assert sample_db_incident["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_max_attempts_reached_unresolved(sample_db_incident):
    """
    Test 3: Unresolvable Failure Scenario.
    All 3 attempts fail. System does NOT loop forever and does NOT mark incident resolved.
    Transitions to MAX_ATTEMPTS_REACHED -> UNRESOLVED.
    """
    sample_db_incident["status"] = "OPEN"
    sample_db_incident["approval_status"] = "APPROVED"

    result = await controlled_execution_engine.execute_controlled_recovery(
        incident=sample_db_incident,
        action_override="RESET_CONNECTION_POOL",
        caller="TestRunner",
        simulate_unresolvable=True
    )

    assert result["success"] is False
    assert result["status"] == "UNRESOLVED"
    assert result["attempts"] == 3
    
    exec_record = result["execution"]
    assert exec_record["current_stage"] == "UNRESOLVED"
    assert sample_db_incident["status"] == "UNRESOLVED"
    assert sample_db_incident["recovery_status"] == "FAILED"


@pytest.mark.asyncio
async def test_ai_sre_assistant_recovery_queries(sample_db_incident):
    """
    Test 4: AI SRE Assistant Integration.
    Verifies that AI assistant answers key operational recovery questions with grounded facts.
    """
    sample_db_incident["status"] = "REMEDIATING"
    active_incidents = [sample_db_incident]

    # 1. "What is the recovery doing?"
    r1 = OperationsAssistantEngine.answer_query(
        question="What is the recovery doing?",
        active_incidents=active_incidents
    )
    assert "RESET_CONNECTION_POOL" in r1["answer"]
    assert "REMEDIATING" in r1["answer"]

    # 2. "How are we verifying it?"
    r2 = OperationsAssistantEngine.answer_query(
        question="How are we verifying it?",
        active_incidents=active_incidents
    )
    assert "Multi-Point Active Verification" in r2["answer"]
    assert "Workflow Replay" in r2["answer"]
    assert "85%" in r2["answer"]

    # 3. "What evidence proves recovery?"
    r3 = OperationsAssistantEngine.answer_query(
        question="What evidence proves recovery?",
        active_incidents=active_incidents
    )
    assert "Error Rate Reduction" in r3["answer"] or "post-remedy" in r3["answer"]

    # 4. "What failed during the first attempt?"
    r4 = OperationsAssistantEngine.answer_query(
        question="What failed during the first attempt?",
        active_incidents=active_incidents
    )
    assert "First Attempt Failure Analysis" in r4["answer"]
    assert "service-b" in r4["answer"]

    # 5. "What is the next recovery option?"
    r5 = OperationsAssistantEngine.answer_query(
        question="What is the next recovery option?",
        active_incidents=active_incidents
    )
    assert "Candidate Action" in r5["answer"]
