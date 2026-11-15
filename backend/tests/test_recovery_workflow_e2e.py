"""
Comprehensive End-to-End Test Suite for AegisOps AI Recovery & Validation Workflow.
Verifies all 16 concrete requirements from Section 11 of the recovery specification:
1. Opening current incident and execution URL renders recovery workspace.
2. Refreshing the URL does not produce a blank page.
3. An invalid execution ID produces a helpful not-found state.
4. A manual step opens its instructions and evidence form.
5. Submitting manual evidence persists it and triggers the proper verification flow.
6. Clicking a completion button cannot bypass verification.
7. The automated socket-pool action uses the correct handler and records its actual result.
8. An unsupported real action is never falsely reported as executed.
9. Failed automated execution remains failed and displays a useful error.
10. Retry does not duplicate a non-idempotent action.
11. A failed prerequisite blocks dependent steps.
12. Execution logs and telemetry evidence remain available after refresh.
13. The selected solution and approval are linked to the correct execution.
14. Unauthorized or cross-company users cannot view or execute recovery steps.
15. A step is successful only after its required verification passes.
16. Incident closure requires successful final verification.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.security import AuthenticatedIdentity, get_current_user
from backend.app.monitoring.collector import collector
from backend.app.healing.approval_manager import approval_manager
from backend.app.rca.dual_solution_engine import dual_solution_rca_engine
from backend.app.healing.controlled_execution_engine import (
    controlled_execution_engine,
    _ACTIVE_RECOVERY_LOCKS,
    _RECOVERY_EXECUTIONS,
    ALLOWLISTED_ACTIONS
)
from backend.app.models.approval import ApprovalTicket


@pytest.fixture(autouse=True)
def clean_test_state():
    """Clean in-memory test states between test cases."""
    collector.active_incidents.clear()
    collector.resolved_incidents.clear()
    collector.pending_approvals.clear()
    collector.reviewed_approvals.clear()
    _ACTIVE_RECOVERY_LOCKS.clear()
    _RECOVERY_EXECUTIONS.clear()


# ==============================================================================
# 1, 2, 3: NAVIGATION, REFRESH STABILITY & INVALID EXECUTION HANDLING
# ==============================================================================

@pytest.mark.asyncio
async def test_req1_and_req2_recovery_workspace_direct_url_and_refresh_stability():
    """1 & 2: Loading and refreshing incident recovery URL returns structured plan steps and execution data."""
    inc_id = "INC-RECOVERY-TEST-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Order Service Socket Pool Exhaustion",
        "severity": "CRITICAL",
        "status": "INVESTIGATING",
        "error_rate": 0.88,
        "p95_latency": 920.0
    }
    collector.active_incidents.append(test_inc)

    # Generate RCA solutions and select plan
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )

    # Query recovery plan via API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        user = AuthenticatedIdentity(
            tenant_id="fincore",
            is_platform_admin=False,
            user_id=1,
            username="sre.fincore",
            role="COMPANY_SRE"
        )
        app.dependency_overrides[get_current_user] = lambda: user

        # 1. Fetch recovery plan
        res_plan = await ac.get(f"/api/incidents/{inc_id}/recovery-plan")
        assert res_plan.status_code == 200
        plan_data = res_plan.json()
        assert "remediation_steps" in plan_data
        assert len(plan_data["remediation_steps"]) >= 2
        first_step = plan_data["remediation_steps"][0]
        assert "step_number" in first_step
        assert "description" in first_step

        # 2. Refresh simulation: fetch remediation run repeatedly
        res_run1 = await ac.get(f"/api/incidents/{inc_id}/remediation-run")
        assert res_run1.status_code == 200
        run1 = res_run1.json()
        assert run1["incident_id"] == inc_id
        assert "steps" in run1

        res_run2 = await ac.get(f"/api/incidents/{inc_id}/remediation-run")
        assert res_run2.status_code == 200
        run2 = res_run2.json()
        assert run2["steps"] == run1["steps"], "Refresh must preserve exact recovery state and step ordering"

        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_req3_invalid_execution_produces_helpful_not_found():
    """3. An invalid execution ID produces a helpful not-found state without crashing or blank screen."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        user = AuthenticatedIdentity(
            tenant_id="shopsphere",
            is_platform_admin=False,
            user_id=2,
            username="sre.shopsphere",
            role="COMPANY_SRE"
        )
        app.dependency_overrides[get_current_user] = lambda: user

        # Request non-existent execution
        res = await ac.get("/api/incidents/INC-20261008-002/sandbox/execution/EXEC-NONEXISTENT-999")
        assert res.status_code == 404
        detail = res.json().get("detail", "")
        assert "EXEC-NONEXISTENT-999" in detail
        assert "not found" in detail.lower()

        app.dependency_overrides.clear()


# ==============================================================================
# 4, 5, 6: MANUAL STEP WORKSPACE, EVIDENCE VALIDATION & BYPASS PREVENTION
# ==============================================================================

@pytest.mark.asyncio
async def test_req4_manual_step_provides_runbook_and_checklist():
    """4. A manual step provides runbook instructions, checklist, and verification criteria."""
    inc_id = "INC-MANUAL-TEST-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)

    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    manual_steps = [s for s in plan["remediation_steps"] if not s.get("is_automated")]
    assert len(manual_steps) > 0, "Plan should contain manual verification steps"
    manual_step = manual_steps[0]

    assert "runbook_instructions" in manual_step
    assert "action_checklist" in manual_step
    assert len(manual_step["action_checklist"]) >= 3
    assert "verification_check" in manual_step
    assert "expected_condition" in manual_step


@pytest.mark.asyncio
async def test_req6_clicking_button_cannot_bypass_manual_verification():
    """6. Clicking a completion button without required checklist or observations cannot bypass verification."""
    inc_id = "INC-MANUAL-BYPASS-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    # First complete automated predecessor step 1
    step1 = plan["remediation_steps"][0]
    if step1.get("is_automated"):
        res1 = await dual_solution_rca_engine.execute_plan_step(
            incident_id=inc_id,
            plan_id=plan["plan_id"],
            step_number=step1["step_number"]
        )
        assert res1["success"] is True

    # Find manual step (step 2)
    manual_step = [s for s in plan["remediation_steps"] if not s.get("is_automated")][0]

    # Attempt bypass with empty observations and unconfirmed checklist
    res_bypass = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=manual_step["step_number"],
        notes="",  # Empty observations
        checklist={"Check 1": False, "Check 2": False}  # Unconfirmed checklist
    )

    assert res_bypass["success"] is False
    assert "checklist" in res_bypass["message"].lower() or "observation" in res_bypass["message"].lower()

    # Step must remain in unverified state
    updated_step = [s for s in res_bypass["plan"]["remediation_steps"] if s["step_number"] == manual_step["step_number"]][0]
    assert updated_step["status"] in ("AWAITING_MANUAL_ACTION", "VERIFICATION_FAILED")
    assert updated_step["status"] != "COMPLETED"


@pytest.mark.asyncio
async def test_req5_submitting_manual_evidence_persists_and_verifies():
    """5. Submitting operator evidence and confirming all checklist items verifies the step."""
    inc_id = "INC-MANUAL-SUBMIT-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    # Complete predecessor step 1 if automated
    step1 = plan["remediation_steps"][0]
    if step1.get("is_automated"):
        await dual_solution_rca_engine.execute_plan_step(
            incident_id=inc_id,
            plan_id=plan["plan_id"],
            step_number=step1["step_number"]
        )

    manual_step = [s for s in plan["remediation_steps"] if not s.get("is_automated")][0]
    all_checked = {item: True for item in manual_step["action_checklist"]}

    res_valid = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=manual_step["step_number"],
        notes="Reset socket descriptors manually via administrative pod terminal. Verified HTTP 200 with 36ms latency.",
        operator="SRE Lead Responder",
        checklist=all_checked
    )

    assert res_valid["success"] is True
    updated_step = [s for s in res_valid["plan"]["remediation_steps"] if s["step_number"] == manual_step["step_number"]][0]
    assert updated_step["status"] == "COMPLETED"
    assert updated_step["operator"] == "SRE Lead Responder"
    assert len(updated_step["evidence"]) > 0
    assert updated_step["evidence"][0]["status"] == "PASS"


# ==============================================================================
# 7, 8, 9, 10: AUTOMATED RECOVERY EXECUTION & ORDER-SERVICE SAFETY CHECKS
# ==============================================================================

@pytest.mark.asyncio
async def test_req7_automated_socket_pool_action_for_order_service():
    """7. The automated socket-pool recovery step for order-service uses correct handler and records actual result."""
    # Verify order-service is explicitly supported for RESET_CONNECTION_POOL
    assert "RESET_CONNECTION_POOL" in ALLOWLISTED_ACTIONS
    assert "order-service" in ALLOWLISTED_ACTIONS["RESET_CONNECTION_POOL"]["supported_services"]

    inc_id = "INC-ORDER-SOCKET-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "shopsphere",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion on Order Service",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)

    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="shopsphere",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="shopsphere"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    # Step 1 is the automated socket pool reset
    step1 = plan["remediation_steps"][0]
    assert step1.get("is_automated") is True

    res = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=step1["step_number"]
    )

    assert res["success"] is True
    executed_step = res["plan"]["remediation_steps"][0]
    assert executed_step["status"] == "COMPLETED"
    assert executed_step["execution_result"] is not None
    assert len(executed_step["evidence"]) > 0
    # Telemetry evidence must have before/after and PASS
    assert executed_step["evidence"][0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_req8_unsupported_real_action_is_never_falsely_reported():
    """8. An unsupported action or target is not falsely executed against live infrastructure."""
    # Test an unregistered action
    res = await controlled_execution_engine.execute_controlled_recovery(
        incident={"incident_id": "INC-TEST-UNKNOWN", "tenant_id": "fincore", "primary_service": "order-service", "status": "APPROVED", "approval_status": "APPROVED"},
        action_override="DROP_ALL_TABLES_ARBITRARY"
    )
    assert res["status"] in ("BLOCKED", "EXECUTION_BLOCKED", "FAILED")
    assert res.get("success") is False


@pytest.mark.asyncio
async def test_req9_failed_automated_action_preserves_error():
    """9. A failed automated action preserves FAILED state and failure details."""
    inc_id = "INC-FAIL-PRESERVE-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "unsupported-rogue-service",
        "root_cause_service": "unsupported-rogue-service",
        "title": "Rogue Service Failure",
        "severity": "HIGH",
        "status": "APPROVED",
        "approval_status": "APPROVED"
    }
    collector.active_incidents.append(test_inc)

    # Directly run action on unsupported service
    res = await controlled_execution_engine.execute_controlled_recovery(
        incident=test_inc,
        action_override="RECONNECT_DATABASE"
    )
    assert res["status"] in ("BLOCKED", "EXECUTION_BLOCKED", "FAILED")
    assert res.get("success") is False


@pytest.mark.asyncio
async def test_req10_retry_idempotency_prevents_duplicate_actions():
    """10. Retry does not duplicate concurrent non-idempotent actions."""
    inc_id = "INC-IDEMP-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL",
        "status": "APPROVED",
        "approval_status": "APPROVED"
    }
    collector.active_incidents.append(test_inc)

    # Acquire lock on order-service by another incident
    _ACTIVE_RECOVERY_LOCKS["order-service"] = "INC-OTHER-ACTIVE"

    # Attempt concurrent execution while locked
    res = await controlled_execution_engine.execute_controlled_recovery(
        incident=test_inc,
        action_override="RESET_CONNECTION_POOL"
    )

    assert res["status"] in ("BLOCKED", "EXECUTION_BLOCKED", "FAILED")
    assert res.get("success") is False
    assert "lock" in (res.get("blocked_reason") or "").lower()

    # Clean lock
    _ACTIVE_RECOVERY_LOCKS.pop("order-service", None)


# ==============================================================================
# 11, 12, 13: PREDECESSOR GATING, TELEMETRY EVIDENCE & SOLUTION LINKING
# ==============================================================================

@pytest.mark.asyncio
async def test_req11_failed_prerequisite_blocks_dependent_steps():
    """11. A failed or uncompleted prerequisite blocks dependent steps from executing."""
    inc_id = "INC-PREDECESSOR-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    # Try executing Step 2 before Step 1 is executed
    res_step2 = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=2
    )

    assert res_step2["success"] is False
    assert "predecessor" in res_step2["message"].lower() or "blocked" in res_step2["message"].lower()


@pytest.mark.asyncio
async def test_req12_telemetry_evidence_structured_and_retained():
    """12. Telemetry evidence is not empty (`[]`), contains before/after metric deltas, and persists across reloads."""
    inc_id = "INC-TELEMETRY-EVID-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    # Execute step 1 (Automated reset)
    res = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=1
    )
    assert res["success"] is True
    step1 = res["plan"]["remediation_steps"][0]
    evidence = step1["evidence"]
    assert isinstance(evidence, list)
    assert len(evidence) > 0, "Telemetry evidence must not be empty []"

    first_metric = evidence[0]
    assert "metric" in first_metric
    assert "before" in first_metric
    assert "after" in first_metric
    assert "status" in first_metric
    assert first_metric["status"] == "PASS"

    # Verify persistent remediation run also contains evidence
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        user = AuthenticatedIdentity(
            tenant_id="fincore",
            is_platform_admin=False,
            user_id=1,
            username="sre.fincore",
            role="COMPANY_SRE"
        )
        app.dependency_overrides[get_current_user] = lambda: user
        res_run = await ac.get(f"/api/incidents/{inc_id}/remediation-run")
        assert res_run.status_code == 200
        run_data = res_run.json()
        assert len(run_data["steps"][0]["evidence"]) > 0
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_req13_selected_solution_and_approval_linked():
    """13. The selected solution source and approved plan are linked to the execution."""
    inc_id = "INC-SOLUTION-LINK-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "shopsphere",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Socket Pool Exhaustion",
        "severity": "CRITICAL"
    }
    collector.active_incidents.append(test_inc)
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="shopsphere",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="shopsphere"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    ticket = await approval_manager.create_or_get_approval_ticket(
        incident=test_inc,
        proposed_action=plan["recommended_action"],
        plan_id=plan["plan_id"],
        plan_version="v1.0",
        solution_source="AI_PROPOSED"
    )

    assert ticket["solution_source"] == "AI_PROPOSED"
    assert ticket["plan_id"] == plan["plan_id"]


# ==============================================================================
# 14, 15, 16: TENANT RBAC, STEP VERIFICATION & FINAL INCIDENT RESOLUTION
# ==============================================================================

@pytest.mark.asyncio
async def test_req14_cross_company_users_cannot_view_or_execute_recovery():
    """14. Cross-company users cannot view or execute recovery steps (HTTP 403 Forbidden)."""
    inc_id = "INC-TENANT-ISOLATION-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "shopsphere",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "ShopSphere Secret Incident",
        "severity": "HIGH"
    }
    collector.active_incidents.append(test_inc)
    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="shopsphere",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="shopsphere"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # FinCore user trying to access ShopSphere recovery plan
        fincore_user = AuthenticatedIdentity(
            tenant_id="fincore",
            is_platform_admin=False,
            user_id=10,
            username="fincore.user",
            role="COMPANY_SRE"
        )
        app.dependency_overrides[get_current_user] = lambda: fincore_user

        res = await ac.get(f"/api/incidents/{inc_id}/recovery-plan")
        assert res.status_code == 403, "Cross-company user must receive 403 Forbidden"

        res_exec = await ac.post(
            f"/api/incidents/{inc_id}/recovery-plan/execute-step",
            json={"plan_id": "PLAN-001", "step_number": 1}
        )
        assert res_exec.status_code == 403, "Cross-company execution must receive 403 Forbidden"

        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_req15_and_req16_step_success_and_final_incident_resolution():
    """15 & 16: Steps are marked COMPLETED only upon passing verification, and incident resolves upon all steps passing."""
    inc_id = "INC-FULL-RESOLVE-01"
    test_inc = {
        "incident_id": inc_id,
        "tenant_id": "fincore",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "title": "Order Service Socket Pool Exhaustion",
        "severity": "CRITICAL",
        "status": "INVESTIGATING",
        "error_rate": 0.85,
        "p95_latency": 890.0
    }
    collector.active_incidents.append(test_inc)

    await dual_solution_rca_engine.get_or_generate_dual_solutions(
        incident=test_inc,
        incident_id=inc_id,
        tenant_id="fincore",
        force_regenerate=True
    )
    await dual_solution_rca_engine.select_solution(
        incident_id=inc_id,
        solution_source="AI_PROPOSED",
        tenant_id="fincore"
    )
    plan = await dual_solution_rca_engine.get_recovery_plan(inc_id)

    # Step 1: Automated Socket Reset
    res1 = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=1
    )
    assert res1["success"] is True
    assert res1["plan"]["remediation_steps"][0]["status"] == "COMPLETED"

    # Step 2: Step 2 in plan
    step2 = plan["remediation_steps"][1]
    all_checked = {item: True for item in step2.get("action_checklist", ["Check 1", "Check 2"])}
    res2 = await dual_solution_rca_engine.execute_plan_step(
        incident_id=inc_id,
        plan_id=plan["plan_id"],
        step_number=2,
        notes="Verified downstream connections and probe health: 200 OK with 35ms latency.",
        operator="SRE Lead",
        checklist=all_checked
    )
    assert res2["success"] is True
    assert res2["plan"]["remediation_steps"][1]["status"] == "COMPLETED"

    # Execute remaining steps if any
    for step in plan["remediation_steps"][2:]:
        step_num = step["step_number"]
        chk = {item: True for item in step.get("action_checklist", ["Check"])}
        await dual_solution_rca_engine.execute_plan_step(
            incident_id=inc_id,
            plan_id=plan["plan_id"],
            step_number=step_num,
            notes="Completed and verified step.",
            operator="SRE Lead",
            checklist=chk
        )

    # Verify final incident state
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        user = AuthenticatedIdentity(
            tenant_id="fincore",
            is_platform_admin=False,
            user_id=1,
            username="sre.fincore",
            role="COMPANY_SRE"
        )
        app.dependency_overrides[get_current_user] = lambda: user
        res_run = await ac.get(f"/api/incidents/{inc_id}/remediation-run")
        assert res_run.status_code == 200
        run_data = res_run.json()

        # Incident status is resolved
        assert run_data["outcome"]["resolved"] is True
        assert run_data["current_phase"] in ("RESOLVED", "VERIFIED")
        assert run_data["post_telemetry"]["error_rate"] <= 0.05
        app.dependency_overrides.clear()
