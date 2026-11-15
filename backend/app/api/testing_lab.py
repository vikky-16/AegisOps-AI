"""
AegisOps AI - Testing & Simulation Lab API Endpoints (Part 33)
Provides enterprise testing & simulation REST APIs:
- Environmental safety status
- 12-category failure scenario catalog
- Controlled test execution runner
- Test history & before/after evidence comparisons
- Chaos / Failure Matrix generator
"""

from fastapi import APIRouter, Query, HTTPException, Path, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from backend.app.analytics.simulation_lab import simulation_lab
from backend.app.replica.remediation_lab import remediation_lab
from backend.app.validation.nine_layer_validator import nine_layer_validator
from backend.app.validation.independent_validator import independent_validator
from backend.app.rca.dual_solution_engine import DualSolutionRCAEngine

router = APIRouter(prefix="/testing", tags=["Testing & Simulation Lab"])


class TestExecutionRequest(BaseModel):
    scenario_id: str
    service: Optional[str] = None
    severity: Optional[str] = None
    duration_sec: int = 30
    tenant_id: str = "shopsphere"
    simulate_refinement: bool = False
    simulate_unresolved: bool = False
    simulate_side_effect: bool = False


@router.get("/status")
async def get_lab_status():
    """Returns environment isolation and safety indicators."""
    return simulation_lab.get_environment_status()


@router.get("/scenarios")
async def list_scenarios():
    """Returns all 12 operational failure scenarios in the catalog."""
    return simulation_lab.get_catalog()


@router.get("/scenarios/{scenario_id}")
async def get_scenario_detail(
    scenario_id: str = Path(..., description="Scenario ID")
):
    """Returns specific scenario definition."""
    sc = simulation_lab.get_scenario(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return sc


@router.post("/run")
async def run_scenario(payload: TestExecutionRequest):
    """Executes a controlled failure test asynchronously through the real backend pipeline."""
    try:
        result = await simulation_lab.start_scenario(
            scenario_id=payload.scenario_id,
            service=payload.service,
            severity=payload.severity,
            duration_sec=payload.duration_sec,
            tenant_id=payload.tenant_id,
            simulate_refinement=payload.simulate_refinement,
            simulate_unresolved=payload.simulate_unresolved,
            simulate_side_effect=payload.simulate_side_effect
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/runs/active")
async def get_active_test_run():
    """Returns currently active test execution, if any."""
    active = simulation_lab.get_active_run()
    if not active:
        return {"status": "IDLE", "active": False}
    return active



@router.get("/runs")
async def list_test_runs(
    service: Optional[str] = Query(default=None),
    failure_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Returns past test execution records with filters."""
    return simulation_lab.get_test_history(
        service=service,
        failure_type=failure_type,
        severity=severity,
        result=result,
        limit=limit
    )


@router.get("/runs/{test_id}")
async def get_test_run_detail(
    test_id: str = Path(..., description="Test Execution ID")
):
    """Returns complete test execution details, timeline events, and before/after metrics."""
    run = simulation_lab.get_test_run(test_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Test run '{test_id}' not found")
    return run


@router.get("/matrix")
async def get_chaos_matrix():
    """Returns Chaos / Failure Matrix calculated from actual test history."""
    return simulation_lab.get_matrix()


# =========================================================================
# Adaptive Autonomous SRE Remediation Lab Endpoints
# =========================================================================

class MultiCandidateTrialRequest(BaseModel):
    incident_id: str
    tenant_id: str = "shopsphere"
    candidates: Optional[List[Dict[str, Any]]] = None
    incident_context: Optional[Dict[str, Any]] = None


class NineLayerValidationRequest(BaseModel):
    target_service: str
    action_name: str
    pre_metrics: Dict[str, Dict[str, Any]]
    post_metrics: Dict[str, Dict[str, Any]]
    pre_logs: Optional[List[Dict[str, Any]]] = None
    post_logs: Optional[List[Dict[str, Any]]] = None
    success_criteria: Optional[Dict[str, Any]] = None
    side_effects: Optional[List[Dict[str, Any]]] = None
    is_production: bool = False
    tenant_id: str = "shopsphere"
    policy_overrides: Optional[Dict[str, Dict[str, Any]]] = None


class IndependentReviewRequest(BaseModel):
    incident_id: str
    tenant_id: str = "shopsphere"
    target_service: str
    candidate_solution: Dict[str, Any]
    replica_test_result: Dict[str, Any]
    validation_layers: Dict[str, Any]
    pre_metrics: Dict[str, Any]
    post_metrics: Dict[str, Any]


@router.post("/remediation-trial")
async def run_multi_candidate_remediation_trial(payload: MultiCandidateTrialRequest):
    """
    Executes a complete isolated remediation trial for an incident:
    1. Prepares clean ephemeral sandbox replica with synthetic telemetry.
    2. Reproduces failure conditions with confirmed fidelity.
    3. Independently tests each candidate from a clean state (resets state between runs).
    4. Evaluates 9-layer validation and independent AI peer review.
    5. Computes measured comparison matrix and selects safest effective solution.
    """
    candidates = payload.candidates or []

    # If no candidates provided, auto-generate/retrieve from DualSolutionRCAEngine
    if not candidates:
        try:
            dual = await DualSolutionRCAEngine.get_or_generate_dual_solutions(
                incident_id=payload.incident_id,
                tenant_id=payload.tenant_id
            )
            ai_sol = dual.get("ai_solution", {})
            kb_sol = dual.get("kb_solution", {})

            if ai_sol and ai_sol.get("status") != "FAILED":
                candidates.append({
                    "candidate_id": f"{payload.incident_id}-ai",
                    "title": f"AI Solution ({ai_sol.get('proposed_action', 'RESET_CONNECTION_POOL')})",
                    "source": "AI_PROPOSED",
                    "action": ai_sol.get("proposed_action", "RESET_CONNECTION_POOL"),
                    "steps": ai_sol.get("implementation_steps", []),
                    "risk": ai_sol.get("risk_and_side_effects", "LOW")
                })

            if kb_sol and kb_sol.get("status") == "AVAILABLE":
                candidates.append({
                    "candidate_id": f"{payload.incident_id}-kb",
                    "title": f"KB Solution ({kb_sol.get('action', 'RESTART_SERVICE')})",
                    "source": "KNOWLEDGE_BASE",
                    "action": kb_sol.get("action", "RESTART_SERVICE"),
                    "steps": kb_sol.get("remediation_steps", []),
                    "risk": "MEDIUM"
                })

            # Add an alternative candidate to ensure thorough multi-candidate comparison
            candidates.append({
                "candidate_id": f"{payload.incident_id}-alt",
                "title": "Alternative Scale Workers",
                "source": "ALTERNATIVE_OPERATOR",
                "action": "SCALE_WORKERS",
                "steps": ["Increase concurrency limits", "Scale horizontal replicas"],
                "risk": "HIGH"
            })
        except Exception as e:
            # Fallback candidates if retrieval fails
            candidates = [
                {
                    "candidate_id": f"{payload.incident_id}-cand1",
                    "title": "Candidate A: Reset Connection Pool",
                    "source": "AI_PROPOSED",
                    "action": "RESET_CONNECTION_POOL",
                    "steps": ["Purge leaked handles", "Reset pool size"],
                    "risk": "LOW"
                },
                {
                    "candidate_id": f"{payload.incident_id}-cand2",
                    "title": "Candidate B: Restart Service",
                    "source": "KNOWLEDGE_BASE",
                    "action": "RESTART_SERVICE",
                    "steps": ["Graceful pod restart"],
                    "risk": "MEDIUM"
                },
                {
                    "candidate_id": f"{payload.incident_id}-cand3",
                    "title": "Candidate C: Scale Workers",
                    "source": "ALTERNATIVE_OPERATOR",
                    "action": "SCALE_WORKERS",
                    "steps": ["Increase worker count"],
                    "risk": "HIGH"
                }
            ]

    result = await remediation_lab.execute_multi_candidate_trial(
        incident_id=payload.incident_id,
        tenant_id=payload.tenant_id,
        candidates=candidates,
        incident_context=payload.incident_context
    )
    return result


@router.get("/remediation-trials")
async def list_remediation_trials(limit: int = Query(default=20, ge=1, le=100)):
    """Returns list of past remediation lab trials."""
    return remediation_lab.list_runs(limit=limit)


@router.get("/remediation-trials/active")
async def get_active_remediation_trial():
    """Returns currently running remediation trial, if any."""
    active = remediation_lab.get_active_run()
    if not active:
        return {"active": False, "status": "IDLE"}
    return {"active": True, "trial": active}


@router.get("/remediation-trials/{run_id}")
async def get_remediation_trial_detail(run_id: str = Path(..., description="Remediation Trial Run ID")):
    """Returns full remediation trial details including multi-candidate comparison matrix."""
    run = remediation_lab.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Remediation trial '{run_id}' not found")
    return run


@router.post("/validate-nine-layers")
async def validate_nine_layers(payload: NineLayerValidationRequest):
    """
    Direct endpoint for evaluating 9-layer validation against before/after telemetry.
    """
    return nine_layer_validator.validate(
        target_service=payload.target_service,
        action_name=payload.action_name,
        pre_metrics=payload.pre_metrics,
        post_metrics=payload.post_metrics,
        pre_logs=payload.pre_logs,
        post_logs=payload.post_logs,
        success_criteria=payload.success_criteria,
        side_effects=payload.side_effects,
        is_production=payload.is_production,
        tenant_id=payload.tenant_id,
        policy_overrides=payload.policy_overrides
    )


@router.post("/independent-review")
async def request_independent_review(payload: IndependentReviewRequest):
    """
    Direct endpoint for requesting independent AI validation review.
    """
    return await independent_validator.review_remediation(
        incident_id=payload.incident_id,
        tenant_id=payload.tenant_id,
        target_service=payload.target_service,
        candidate_solution=payload.candidate_solution,
        replica_test_result=payload.replica_test_result,
        validation_layers=payload.validation_layers,
        pre_metrics=payload.pre_metrics,
        post_metrics=payload.post_metrics
    )


# =========================================================================
# Verified Knowledge Base Learning Loop Endpoints
# =========================================================================

@router.post("/resolutions")
async def record_incident_resolution(payload: Dict[str, Any] = Body(...)):
    """
    Records a structured incident resolution in the Verified Knowledge Base.
    Explicit statuses: PROPOSED, REPLICA_TESTED, REPLICA_VALIDATED, PRODUCTION_EXECUTED, PRODUCTION_VALIDATED, ROLLED_BACK, FAILED, UNRESOLVED.
    """
    from backend.app.knowledge.incident_memory import verified_recovery_store
    res_id = verified_recovery_store.record_structured_resolution(payload)
    return {
        "success": True,
        "resolution_id": res_id,
        "status": payload.get("resolution_status", "PROPOSED")
    }


@router.get("/resolutions")
async def list_incident_resolutions(
    tenant_id: Optional[str] = Query(default=None),
    incident_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100)
):
    """Returns structured resolutions filtered by tenant and verification status."""
    from backend.app.knowledge.incident_memory import verified_recovery_store
    return verified_recovery_store.get_structured_resolutions(
        tenant_id=tenant_id,
        incident_id=incident_id,
        status=status,
        limit=limit
    )


@router.get("/resolutions/search")
async def search_resolutions_get(
    q: Optional[str] = Query(default=None),
    tenant_id: Optional[str] = Query(default=None)
):
    """GET search for historical resolutions with query and tenant filter."""
    from backend.app.knowledge.incident_memory import verified_recovery_store
    incident = {"root_cause": q or "", "root_cause_category": q or ""}
    return verified_recovery_store.search_knowledge_with_compatibility(
        incident=incident,
        tenant_id=tenant_id or "shopsphere"
    )


@router.post("/resolutions/search")
async def search_resolutions_with_compatibility(
    payload: Dict[str, Any] = Body(...)
):
    """
    Searches historical resolutions with architecture compatibility checks.
    Enforces tenant isolation and distinguishes replica-tested from production-validated fixes.
    """
    from backend.app.knowledge.incident_memory import verified_recovery_store
    tenant_id = payload.get("tenant_id", "shopsphere")
    incident = payload.get("incident", {})
    return verified_recovery_store.search_knowledge_with_compatibility(
        incident=incident,
        tenant_id=tenant_id
    )
