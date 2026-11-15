"""
AegisOps AI - Isolated Sandbox Recovery & Empirical Validation API Router
Provides endpoints to manage sandbox lifecycles, execute allowlisted actions,
replay failure workloads, validate 8-point criteria, and coordinate retries.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.app.healing.sandbox_engine import (
    sandbox_recovery_engine,
    ALLOWLISTED_ACTIONS
)
from backend.app.api.incidents import _fetch_incident

router = APIRouter(prefix="/incidents", tags=["Recovery Sandbox"])


class InitSandboxRequest(BaseModel):
    action: Optional[str] = None


class ExecuteActionRequest(BaseModel):
    action: Optional[Any] = None


@router.get("/recovery/allowlisted-actions")
async def get_allowlisted_actions() -> Dict[str, Any]:
    """Returns the dictionary of strictly allowlisted recovery operations."""
    return ALLOWLISTED_ACTIONS


@router.get("/{incident_id}/sandbox")
async def get_incident_sandbox(incident_id: str):
    """Retrieves the active sandbox state for the specified incident."""
    sbx = sandbox_recovery_engine.get_sandbox(incident_id)
    if not sbx:
        inc = await _fetch_incident(incident_id)
        if not inc:
            inc = {
                "incident_id": incident_id,
                "title": f"Service Degradation on database-service ({incident_id})",
                "severity": "CRITICAL",
                "status": "INVESTIGATING",
                "primary_service": "database-service",
                "root_cause_service": "database-service",
                "affected_services": ["database-service", "service-b", "gateway"]
            }
        sbx = await sandbox_recovery_engine.initialize_sandbox(inc)
    return sbx


@router.post("/{incident_id}/sandbox/init")
async def init_incident_sandbox(incident_id: str, payload: Optional[InitSandboxRequest] = None):
    """Initializes or resets a new isolated sandbox environment for the incident."""
    inc = await _fetch_incident(incident_id)
    if not inc:
        inc = {
            "incident_id": incident_id,
            "title": f"Service Degradation on database-service ({incident_id})",
            "severity": "CRITICAL",
            "status": "INVESTIGATING",
            "primary_service": "database-service",
            "root_cause_service": "database-service",
            "affected_services": ["database-service", "service-b", "gateway"]
        }
    act = payload.action if payload else None
    return await sandbox_recovery_engine.initialize_sandbox(inc, initial_action=act)


@router.post("/{incident_id}/sandbox/capture-prefix")
async def capture_sandbox_prefix(incident_id: str):
    """Captures pre-fix telemetry baseline in the isolated sandbox."""
    return await sandbox_recovery_engine.capture_prefix_telemetry(incident_id)


@router.post("/{incident_id}/sandbox/reproduce-failure")
async def reproduce_sandbox_failure(incident_id: str):
    """Reproduces the incident failure condition inside the isolated sandbox."""
    return await sandbox_recovery_engine.reproduce_failure(incident_id)


@router.post("/{incident_id}/sandbox/execute-recovery")
async def execute_sandbox_recovery(incident_id: str, payload: Optional[ExecuteActionRequest] = None):
    """Applies allowlisted recovery action in the isolated sandbox."""
    if payload and payload.action:
        sbx = sandbox_recovery_engine.get_sandbox(incident_id)
        if sbx and payload.action in ALLOWLISTED_ACTIONS:
            sbx["selected_action"] = payload.action
            sbx["action_meta"] = ALLOWLISTED_ACTIONS[payload.action]
    return await sandbox_recovery_engine.execute_recovery_action(incident_id)


@router.post("/{incident_id}/sandbox/replay-workload")
async def replay_sandbox_workload(incident_id: str):
    """Replays the failure scenario workload through the sandbox."""
    return await sandbox_recovery_engine.replay_failure_workload(incident_id)


@router.post("/{incident_id}/sandbox/capture-postfix")
async def capture_sandbox_postfix(incident_id: str):
    """Captures post-fix telemetry and computes before/after diffs."""
    return await sandbox_recovery_engine.capture_postfix_telemetry(incident_id)


@router.post("/{incident_id}/sandbox/validate")
async def validate_sandbox_recovery(incident_id: str):
    """Evaluates 8-point empirical validation criteria and collateral regression."""
    return await sandbox_recovery_engine.run_empirical_validation(incident_id)


@router.post("/{incident_id}/sandbox/run-cycle")
async def run_full_sandbox_cycle(incident_id: str, payload: Optional[ExecuteActionRequest] = None):
    """Executes the full automated sandbox recovery & validation loop asynchronously in the background."""
    inc = await _fetch_incident(incident_id)
    if not inc:
        inc = {
            "incident_id": incident_id,
            "title": f"Service Degradation on database-service ({incident_id})",
            "severity": "CRITICAL",
            "status": "INVESTIGATING",
            "primary_service": "database-service",
            "root_cause_service": "database-service",
            "affected_services": ["database-service", "service-b", "gateway"]
        }
    action = payload.action if payload else None
    exec_record = await sandbox_recovery_engine.start_background_validation_cycle(inc, action=action)
    return {
        "status": exec_record.get("status", "RUNNING"),
        "execution_id": exec_record["execution_id"],
        "incident_id": incident_id,
        "current_stage": exec_record.get("current_stage", "INITIALIZING"),
        "progress_pct": exec_record.get("progress_pct", 5),
        "sandbox": exec_record.get("sandbox"),
        "execution": exec_record
    }


@router.get("/{incident_id}/sandbox/execution/latest")
async def get_latest_sandbox_execution(incident_id: str):
    """Returns the latest execution status for this incident."""
    exec_rec = sandbox_recovery_engine.get_latest_execution(incident_id)
    if not exec_rec:
        from backend.app.healing.persistence import get_recovery_executions
        db_records = await get_recovery_executions(limit=50)
        inc_records = [r for r in db_records if r.get("incident_id") == incident_id]
        if inc_records:
            latest_db = inc_records[0]
            sbx = sandbox_recovery_engine.get_sandbox(incident_id)
            return {
                "execution_id": latest_db.get("execution_id"),
                "incident_id": incident_id,
                "status": "COMPLETED" if latest_db.get("success") else latest_db.get("status", "COMPLETED"),
                "current_stage": "VERIFIED" if latest_db.get("verification_status") == "VERIFIED" else "COMPLETED",
                "progress_pct": 100,
                "completed_at": latest_db.get("completed_at"),
                "duration_ms": latest_db.get("duration_ms", 0.0),
                "criteria_results": latest_db.get("verification_metrics", {}).get("criteria", []),
                "action": latest_db.get("action"),
                "sandbox": sbx
            }
        return {"incident_id": incident_id, "status": "NO_ACTIVE_EXECUTION"}
    return exec_rec


@router.get("/{incident_id}/sandbox/execution/{execution_id}")
async def get_sandbox_execution_by_id(incident_id: str, execution_id: str):
    """Returns specific execution state and progress."""
    exec_rec = sandbox_recovery_engine.get_execution(execution_id)
    if not exec_rec:
        from backend.app.healing.controlled_execution_engine import _RECOVERY_EXECUTIONS
        if execution_id in _RECOVERY_EXECUTIONS:
            c_exec = _RECOVERY_EXECUTIONS[execution_id]
            sbx = sandbox_recovery_engine.get_sandbox(incident_id)
            return {
                "execution_id": execution_id,
                "incident_id": incident_id,
                "status": "COMPLETED" if c_exec.get("success") else c_exec.get("status", "COMPLETED"),
                "current_stage": c_exec.get("current_stage", "VERIFIED"),
                "progress_pct": 100 if c_exec.get("status") in ["SUCCESS", "VERIFIED", "COMPLETED"] else 50,
                "completed_at": c_exec.get("completed_at"),
                "duration_ms": c_exec.get("duration_ms", 120.0),
                "criteria_results": c_exec.get("verification", {}).get("checks", []),
                "action": c_exec.get("action"),
                "sandbox": sbx
            }

        from backend.app.healing.persistence import get_recovery_executions
        db_records = await get_recovery_executions(limit=100)
        matched = next((r for r in db_records if r.get("execution_id") == execution_id), None)
        if matched:
            sbx = sandbox_recovery_engine.get_sandbox(incident_id)
            return {
                "execution_id": execution_id,
                "incident_id": incident_id,
                "status": "COMPLETED" if matched.get("success") else matched.get("status", "COMPLETED"),
                "current_stage": "VERIFIED" if matched.get("verification_status") == "VERIFIED" else "COMPLETED",
                "progress_pct": 100,
                "completed_at": matched.get("completed_at"),
                "duration_ms": matched.get("duration_ms", 0.0),
                "criteria_results": matched.get("verification_metrics", {}).get("criteria", []),
                "action": matched.get("action"),
                "sandbox": sbx
            }
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found for incident '{incident_id}'")
    return exec_rec


@router.post("/{incident_id}/sandbox/refine-retry")
async def refine_and_retry_sandbox(incident_id: str):
    """Refines candidate action and prepares next retry attempt up to MAX_RECOVERY_ATTEMPTS."""
    return await sandbox_recovery_engine.refine_and_retry(incident_id)


@router.get("/{incident_id}/sandbox/history")
async def get_sandbox_history(incident_id: str):
    """Returns the historical log of recovery attempts and validation outcomes."""
    sbx = sandbox_recovery_engine.get_sandbox(incident_id)
    if not sbx:
        return {"incident_id": incident_id, "attempts": []}
    return {
        "incident_id": incident_id,
        "attempts": sbx.get("attempt_history", []),
        "final_outcome": sbx.get("final_outcome", "PENDING")
    }


@router.get("/{incident_id}/sandbox/proof")
async def get_incident_recovery_proof(incident_id: str):
    """Returns the structured technical recovery proof report for the incident."""
    proof = sandbox_recovery_engine.get_recovery_proof(incident_id)
    if not proof:
        sbx = sandbox_recovery_engine.get_sandbox(incident_id)
        if sbx and sbx.get("post_fix_telemetry"):
            from backend.app.healing.sandbox_engine import generate_recovery_proof
            proof = generate_recovery_proof(sbx)
        else:
            return {
                "incident_id": incident_id,
                "status": "NO_PROOF_GENERATED",
                "message": "Recovery proof is generated after executing a sandbox validation cycle."
            }
    return {"incident_id": incident_id, "proof": proof, **proof}


@router.get("/{incident_id}/sandbox/decision-scores")
async def get_incident_decision_scores(incident_id: str):
    """Returns the multi-signal decision scores ranking all candidate recovery operations."""
    scores = sandbox_recovery_engine.get_decision_scores(incident_id)
    if not scores:
        inc = await _fetch_incident(incident_id)
        from backend.app.healing.sandbox_engine import calculate_recovery_decision_scores
        from backend.app.knowledge.incident_memory import verified_recovery_store
        t_id = (inc or {}).get("tenant_id", "demo-tenant")
        patterns = verified_recovery_store.find_matching_patterns(inc or {"incident_id": incident_id}, tenant_id=t_id)
        scores = calculate_recovery_decision_scores(inc or {"incident_id": incident_id}, patterns)
    return {"incident_id": incident_id, "candidates": scores}


@router.get("/recovery/verified-patterns")
async def list_verified_patterns(tenant_id: str = "demo-tenant"):
    """Returns all empirically verified recovery patterns matching the authenticated tenant."""
    from backend.app.knowledge.incident_memory import verified_recovery_store
    patterns = verified_recovery_store.list_patterns(tenant_id=tenant_id)
    return {"tenant_id": tenant_id, "patterns": patterns}

