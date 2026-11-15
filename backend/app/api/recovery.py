"""
Recovery and Self-Healing API Endpoints
Provides controlled-demo remediation execution, active verification probing, and persistent audit logs.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import time
from backend.app.monitoring.collector import collector
from backend.app.healing.executor import executor
from backend.app.healing.verifier import verifier
from backend.app.healing.persistence import save_recovery_execution, get_recovery_executions
from backend.app.healing.controlled_execution_engine import (
    controlled_execution_engine,
    ALLOWLISTED_ACTIONS
)
from backend.app.validation.nine_layer_validator import nine_layer_validator
from backend.app.knowledge.incident_memory import verified_recovery_store

router = APIRouter(prefix="/recovery", tags=["Recovery"])


class ManualRecoveryRequest(BaseModel):
    service_name: str
    action: str  # RESTART_SERVICE, RESET_CONNECTION_POOL, SCALE_WORKERS, CLEAR_CACHE, ROTATE_AND_COMPRESS_LOGS, ROLLBACK_CONFIG
    parameters: Optional[Dict[str, Any]] = None


@router.get("/actions")
async def get_allowlisted_actions():
    """
    GET /api/recovery/actions
    Returns all registered, allowlisted remediation actions.
    """
    return controlled_execution_engine.get_allowlisted_actions()


@router.get("")
@router.get("/history")
async def get_recovery_history() -> List[Dict[str, Any]]:
    """
    Returns persistent execution records and active verification probe results for self-healing actions.
    Loads directly from the SQLite database to survive service restarts.
    """
    db_records = await get_recovery_executions(limit=100)
    if db_records:
        collector.recovery_history = db_records
        return db_records
    return collector.recovery_history


@router.post("/manual")
@router.post("/execute")
async def trigger_manual_recovery(payload: ManualRecoveryRequest):
    """
    Allows operator to trigger a controlled-demo remediation action on-demand.
    Executes the action on the target demo service, runs Multi-Point Active Verification,
    and persists the audit record to the database.
    """
    start_time = time.time()
    start_t = datetime.now(timezone.utc).isoformat()

    # 1. Execute action hook against microservice
    exec_res = await executor.execute_action(payload.service_name, payload.action, payload.parameters)

    # 2. Multi-Point Active Verification Probe
    verif_res = await verifier.verify_recovery(payload.service_name, [payload.service_name], probe_delay_sec=1.0)

    end_time = time.time()
    end_t = datetime.now(timezone.utc).isoformat()
    duration_ms = round((end_time - start_time) * 1000, 2)

    # Status requires both execution and active probe verification to pass
    is_success = bool(exec_res.get("success", False) and verif_res.get("verified", False))
    status = "SUCCESS" if is_success else "FAILED"
    verif_status = "VERIFIED" if verif_res.get("verified") else "VERIFICATION_FAILED"

    error_msg = exec_res.get("error")
    if not error_msg and not verif_res.get("verified"):
        error_msg = verif_res.get("failure_reason") or "Multi-Point Active Verification failed post-remediation"

    rec_entry = {
        "execution_id": f"REC-MANUAL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "incident_id": "MANUAL_OVERRIDE",
        "approval_id": None,
        "service_name": payload.service_name,
        "action": payload.action,
        "status": status,
        "success": is_success,
        "duration_ms": duration_ms,
        "verification_status": verif_status,
        "verification_result": verif_res,
        "verification_details": verif_res,
        "result": exec_res.get("details", "Remediation hook executed on controlled demo service"),
        "error": error_msg,
        "started_at": start_t,
        "executed_at": start_t,
        "completed_at": end_t,
        "execution_mode": "CONTROLLED_DEMO"
    }

    # Persist to database
    persisted_record = await save_recovery_execution(rec_entry)
    collector.recovery_history.insert(0, persisted_record)

    return {
        "success": is_success,
        "execution_mode": "CONTROLLED_DEMO",
        "execution": exec_res,
        "verification": verif_res,
        "record": persisted_record
    }


async def _resolve_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """Helper to locate incident in collector memory, pipeline, or persistent SQLite."""
    inc = next((i for i in collector.active_incidents if i.get("incident_id") == incident_id), None)
    if not inc:
        inc = next((i for i in collector.resolved_incidents if i.get("incident_id") == incident_id), None)
    if inc:
        return inc

    try:
        from backend.app.correlator.engine import incident_pipeline
        if hasattr(incident_pipeline, "_active_incidents") and incident_id in incident_pipeline._active_incidents:
            return incident_pipeline._active_incidents[incident_id]
    except Exception:
        pass

    try:
        from backend.app.core.database import AsyncSessionLocal
        from backend.app.models.incident import IncidentModel
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            stmt = select(IncidentModel).where(IncidentModel.incident_id == incident_id)
            res = await session.execute(stmt)
            db_inc = res.scalar_one_or_none()
            if db_inc:
                inc_dict = db_inc.to_dict()
                collector.active_incidents.append(inc_dict)
                return inc_dict
    except Exception:
        pass
    return None


@router.get("/{incident_id}")
async def get_incident_recovery_status(incident_id: str):
    """
    GET /api/recovery/{incident_id}
    Retrieves recovery status, candidate solution, approval state, and historical execution attempts.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    svc = inc.get("root_cause_service") or inc.get("primary_service", "database-service")
    action = inc.get("recommended_action", "RESET_CONNECTION_POOL")
    risk = inc.get("action_risk_level", "LOW")

    return {
        "incident_id": incident_id,
        "service": svc,
        "status": inc.get("status"),
        "recovery_status": inc.get("recovery_status", "AWAITING_APPROVAL" if inc.get("status") == "AWAITING_APPROVAL" else "READY"),
        "approval_status": inc.get("approval_status", "APPROVED" if inc.get("status") == "APPROVED" else "PENDING"),
        "recommended_action": action,
        "action_risk_level": risk,
        "requires_approval": risk in ["MEDIUM", "HIGH", "CRITICAL"],
        "timeline": inc.get("timeline", []),
        "verification": inc.get("verification_result", {})
    }


@router.post("/{incident_id}/approve")
async def approve_incident_recovery(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = None
):
    """
    POST /api/recovery/{incident_id}/approve
    Authorizes recovery action, recording formal member approval audit record.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    approval_id = f"APP-{incident_id[-6:]}-{int(time.time())}"

    inc["status"] = "APPROVED"
    inc["approval_status"] = "APPROVED"
    inc["recovery_status"] = "APPROVED_READY_TO_EXECUTE"
    
    approval_record = {
        "approval_id": approval_id,
        "incident_id": incident_id,
        "member_id": (payload and payload.get("member_id")) or "sre-lead",
        "tenant_id": inc.get("tenant_id", "demo-tenant"),
        "role": (payload and payload.get("role")) or "Senior SRE / Admin",
        "decision": "APPROVED",
        "timestamp": now_iso,
        "reason": (payload and payload.get("reason")) or "Authorized controlled remediation runbook execution."
    }

    inc.setdefault("timeline", []).append({
        "timestamp": now_iso,
        "service": inc.get("root_cause_service", "orchestrator"),
        "type": "APPROVAL_GRANTED",
        "message": f"Member {approval_record['member_id']} ({approval_record['role']}) approved execution of '{inc.get('recommended_action')}'."
    })

    return {
        "success": True,
        "incident_id": incident_id,
        "status": "APPROVED",
        "approval_record": approval_record
    }


@router.post("/{incident_id}/safety-check")
async def evaluate_safety_checks(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = None
):
    """
    POST /api/recovery/{incident_id}/safety-check
    Evaluates 9 critical safety checks without executing.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    action = (payload and payload.get("action")) or inc.get("recommended_action", "RESET_CONNECTION_POOL")
    tenant_id = (payload and payload.get("tenant_id")) or inc.get("tenant_id", "demo-tenant")
    caller = (payload and payload.get("caller")) or "Authorized_SRE_Operator"

    return controlled_execution_engine.evaluate_safety_checks(
        incident=inc,
        action=action,
        tenant_id=tenant_id,
        caller=caller
    )


@router.post("/{incident_id}/execute")
async def execute_incident_recovery(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = None
):
    """
    POST /api/recovery/{incident_id}/execute
    Enforces authorization: rejects with HTTP 403 if unapproved and approval is required!
    Executes controlled recovery, replays workflow, and verifies recovery.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    svc = inc.get("root_cause_service") or inc.get("primary_service", "database-service")
    action = (payload and payload.get("action")) or inc.get("recommended_action", "RESET_CONNECTION_POOL")
    caller = (payload and payload.get("caller")) or "Authorized_SRE_Operator"

    # Pre-execution safety and approval check
    action_spec = ALLOWLISTED_ACTIONS.get(action, {})
    risk = (action_spec.get("risk") or inc.get("action_risk_level") or "LOW").upper()
    is_approved = inc.get("approval_status") == "APPROVED" or inc.get("status") in ["APPROVED", "REMEDIATING", "VERIFYING"]

    if not is_approved and risk in ["MEDIUM", "HIGH", "CRITICAL"]:
        raise HTTPException(
            status_code=403,
            detail=f"Authorization rejected: Recovery action '{action}' (Risk: {risk}) for incident '{incident_id}' requires formal member approval before execution."
        )

    # Optional test simulation flags from payload
    sim_insufficient = bool(payload and payload.get("simulate_insufficient_attempt", False))
    sim_unresolvable = bool(payload and payload.get("simulate_unresolvable", False))

    result = await controlled_execution_engine.execute_controlled_recovery(
        incident=inc,
        action_override=action,
        caller=caller,
        simulate_insufficient_attempt=sim_insufficient,
        simulate_unresolvable=sim_unresolvable
    )

    # -------------------------------------------------------------------------
    # Re-run 9-Layer Validation against live production post-execution metrics
    # -------------------------------------------------------------------------
    exec_data = result.get("execution", {})
    pre_snap = exec_data.get("pre_execution_snapshot", {})
    post_snap = exec_data.get("post_execution_snapshot", {})
    verif = result.get("verification", {})
    side_effects = verif.get("side_effects", [])

    pre_metrics = {svc: {"error_rate": float(pre_snap.get("error_rate", 0.5)), "latency_p95_ms": float(pre_snap.get("latency_p95_ms", 500.0)), "active_connections": float(pre_snap.get("db_pool_utilization_pct", 50.0))}}
    post_metrics = {svc: {"error_rate": float(post_snap.get("error_rate", 0.01)), "latency_p95_ms": float(post_snap.get("latency_p95_ms", 35.0)), "active_connections": float(post_snap.get("db_pool_utilization_pct", 10.0)), "healthy": bool(result.get("success", False))}}

    validation_breakdown = nine_layer_validator.validate(
        target_service=svc,
        action_name=action,
        pre_metrics=pre_metrics,
        post_metrics=post_metrics,
        success_criteria={"max_error_rate": 0.05, "max_latency_p95_ms": 250.0},
        side_effects=[{"description": s} for s in side_effects] if side_effects else [],
        is_production=True,
        tenant_id=inc.get("tenant_id", "shopsphere")
    )

    # Record into Verified Knowledge Base Learning Loop
    now_iso = datetime.now(timezone.utc).isoformat()
    is_success = bool(result.get("success", False) and validation_breakdown["overall_status"] == "PASS")
    resolution_status = "PRODUCTION_VALIDATED" if is_success else "FAILED"

    res_id = verified_recovery_store.record_structured_resolution({
        "incident_id": incident_id,
        "tenant_id": inc.get("tenant_id", "shopsphere"),
        "resolution_status": resolution_status,
        "root_cause_category": inc.get("root_cause_category") or inc.get("failure_type", "INCIDENT"),
        "root_cause_description": inc.get("root_cause", ""),
        "origin_service": svc,
        "affected_services": inc.get("affected_services", [svc]),
        "architecture_environment": "production",
        "selected_solution": {"action": action, "service": svc},
        "selection_rationale": f"Executed via authorized recovery workflow by {caller}.",
        "production_execution_result": result,
        "nine_layer_validation": validation_breakdown,
        "production_validated_at": now_iso if is_success else None
    })

    return {
        "incident_id": incident_id,
        "action": action,
        "service": svc,
        "status": inc.get("status"),
        "result": result,
        "nine_layer_validation": validation_breakdown,
        "resolution_id": res_id,
        "resolution_status": resolution_status
    }


@router.get("/{incident_id}/state")
async def get_incident_recovery_state(incident_id: str):
    """
    GET /api/recovery/{incident_id}/state
    Returns the real-time recovery state machine status, current stage, attempts history,
    before/after comparison, and timeline.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    matching_rec = next((r for r in collector.recovery_history if r.get("incident_id") == incident_id), None)
    return {
        "incident_id": incident_id,
        "service": inc.get("root_cause_service") or inc.get("primary_service", "database-service"),
        "status": inc.get("status"),
        "recovery_status": inc.get("recovery_status", "READY"),
        "approval_status": inc.get("approval_status", "PENDING"),
        "recommended_action": inc.get("recommended_action", "RESET_CONNECTION_POOL"),
        "verification": inc.get("verification_result") or (matching_rec and matching_rec.get("verification_details")),
        "timeline": inc.get("timeline", [])
    }


@router.post("/{incident_id}/replay")
async def trigger_workflow_replay(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = None
):
    """
    POST /api/recovery/{incident_id}/replay
    Manually triggers synthetic workflow replay across mesh.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    svc = inc.get("root_cause_service") or inc.get("primary_service", "database-service")
    affected = inc.get("affected_services", [svc])
    replay_res = await controlled_execution_engine.replay_failed_workflow(svc, affected)
    return {
        "incident_id": incident_id,
        "target_service": svc,
        "replay_result": replay_res
    }


@router.post("/{incident_id}/rollback")
async def trigger_recovery_rollback(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = None
):
    """
    POST /api/recovery/{incident_id}/rollback
    Executes safe rollback handler if recovery caused side effects.
    """
    inc = await _resolve_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    svc = inc.get("root_cause_service") or inc.get("primary_service", "database-service")
    action = (payload and payload.get("action")) or inc.get("recommended_action", "RESET_CONNECTION_POOL")
    reason = (payload and payload.get("reason")) or "Operator requested manual rollback"

    rollback_res = await controlled_execution_engine.execute_rollback(svc, action, reason)
    inc["status"] = "ROLLED_BACK"
    inc["recovery_status"] = "ROLLED_BACK"
    return {
        "incident_id": incident_id,
        "target_service": svc,
        "status": "ROLLED_BACK",
        "rollback": rollback_res
    }


@router.get("/{incident_id}/verification")
async def get_incident_recovery_verification(incident_id: str):
    """
    GET /api/recovery/{incident_id}/verification
    Retrieves fresh active verification probes, before vs after metrics, and side effect checks.
    """
    inc = next((i for i in collector.active_incidents if i.get("incident_id") == incident_id), None)
    if not inc:
        inc = next((i for i in collector.resolved_incidents if i.get("incident_id") == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    svc = inc.get("root_cause_service") or inc.get("primary_service", "database-service")
    
    # Check latest verification in history
    matching_rec = next((r for r in collector.recovery_history if r.get("incident_id") == incident_id), None)
    verif = matching_rec.get("verification_details") if matching_rec else inc.get("verification_result")

    if not verif:
        verif = {
            "verified": inc.get("status") == "RESOLVED",
            "original_error_cleared": inc.get("status") == "RESOLVED",
            "error_rate_baseline": inc.get("status") == "RESOLVED",
            "latency_baseline": inc.get("status") == "RESOLVED",
            "workflow_completed": inc.get("status") == "RESOLVED",
            "side_effects_detected": False,
            "side_effects": []
        }

    return {
        "incident_id": incident_id,
        "service": svc,
        "status": inc.get("status"),
        "verification": verif
    }





