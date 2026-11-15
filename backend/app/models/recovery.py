"""
Recovery Action Execution Database Model
Persists full audit trail of executed runbooks, steps, rollback status, and verification metrics.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from backend.app.core.database import Base


class RecoveryExecution(Base):
    __tablename__ = "recovery_executions"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(64), unique=True, index=True, nullable=False)  # REC-xxx
    incident_id = Column(String(64), index=True, nullable=False)
    approval_id = Column(String(64), nullable=True)
    service_name = Column(String(64), nullable=False)
    runbook_id = Column(String(64), nullable=True)
    
    action = Column(String(128), nullable=False)
    risk_level = Column(String(32), default="LOW")
    execution_mode = Column(String(32), default="CONTROLLED_DEMO")  # CONTROLLED_DEMO, AUTONOMOUS, HUMAN_APPROVED, MANUAL
    executor = Column(String(64), default="AegisOps_Remediation_Engine")
    
    status = Column(String(32), default="EXECUTING", index=True)  # EXECUTING, VERIFYING, SUCCESS, FAILED, ESCALATED
    success = Column(Boolean, default=True)
    duration_ms = Column(Float, default=0.0)
    
    verification_status = Column(String(32), default="VERIFIED")  # VERIFIED, VERIFICATION_FAILED, SKIPPED
    verification_metrics_json = Column(Text, default="{}")  # Structured checks
    
    steps_json = Column(Text, default="[]")  # Step-by-step execution log
    result_json = Column(Text, default="{}")  # Result payload
    error_message = Column(Text, nullable=True)
    rollback_status = Column(String(32), default="NONE")  # NONE, NOT_NEEDED, EXECUTED, FAILED
    
    pre_health_score = Column(Float, default=0.0)
    post_health_score = Column(Float, default=0.0)
    
    plan_id = Column(String(64), nullable=True)
    plan_version = Column(String(32), default="v1.0")
    solution_source = Column(String(32), nullable=True)  # AI_PROPOSED, KNOWLEDGE_BASE
    remediation_run_id = Column(String(64), nullable=True)
    is_simulated = Column(Boolean, default=False)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    def to_dict(self):
        try:
            verif_res = json.loads(self.verification_metrics_json) if self.verification_metrics_json else {}
        except Exception:
            verif_res = {}

        try:
            result_val = json.loads(self.result_json) if self.result_json else {}
        except Exception:
            result_val = self.result_json

        try:
            steps_val = json.loads(self.steps_json) if self.steps_json else []
        except Exception:
            steps_val = []

        return {
            "execution_id": self.execution_id,
            "incident_id": self.incident_id,
            "approval_id": self.approval_id,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version or "v1.0",
            "solution_source": self.solution_source,
            "remediation_run_id": self.remediation_run_id,
            "is_simulated": bool(self.is_simulated),
            "service_name": self.service_name,
            "runbook_id": self.runbook_id,
            "action": self.action,
            "risk_level": self.risk_level,
            "execution_mode": self.execution_mode,
            "executor": self.executor,
            "status": self.status,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "verification_status": self.verification_status,
            "verification_result": verif_res,
            "verification_details": verif_res,
            "steps": steps_val,
            "result": result_val,
            "error": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else (self.started_at.isoformat() if self.started_at else None),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None
        }


class RecoveryPlan(Base):
    """
    Candidate recovery strategy plan for an incident (Parts 22-24, 42).
    """
    __tablename__ = "recovery_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    
    recommended_action = Column(String(128), nullable=False)
    candidate_solutions_json = Column(Text, default="[]")
    recovery_score = Column(Float, default=0.85)
    confidence = Column(Float, default=0.85)
    status = Column(String(32), default="PLANNED", index=True)  # PLANNED, APPROVED, EXECUTED, SUPERSEDED
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        try:
            cand_data = json.loads(self.candidate_solutions_json or "{}")
        except Exception:
            cand_data = {}

        if isinstance(cand_data, list):
            candidate_solutions = cand_data
            remediation_steps = []
            selected_source = None
            selected_solution = cand_data[0] if cand_data else None
            execution_id = None
            approval_id = None
            validation_result = {}
            target_service = None
            risk_level = "LOW"
        else:
            candidate_solutions = cand_data.get("candidate_solutions") or ([cand_data.get("selected_solution")] if cand_data.get("selected_solution") else [])
            remediation_steps = cand_data.get("remediation_steps", [])
            selected_source = cand_data.get("selected_source") or cand_data.get("selected_solution_source")
            selected_solution = cand_data.get("selected_solution")
            execution_id = cand_data.get("execution_id")
            approval_id = cand_data.get("approval_id")
            validation_result = cand_data.get("validation_result", {})
            target_service = cand_data.get("target_service")
            risk_level = cand_data.get("risk_level", "LOW")

        sol_id = None
        if isinstance(selected_solution, dict):
            sol_id = selected_solution.get("article_id") or selected_solution.get("solution_id")
        if not sol_id and isinstance(cand_data, dict):
            sol_id = cand_data.get("solution_id")

        return {
            "plan_id": self.plan_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "recommended_action": self.recommended_action,
            "solution_id": sol_id,
            "candidate_solutions": candidate_solutions,
            "remediation_steps": remediation_steps,
            "selected_source": selected_source,
            "selected_solution_source": selected_source,
            "selected_solution": selected_solution,
            "target_service": target_service,
            "risk_level": risk_level,
            "execution_id": execution_id,
            "approval_id": approval_id,
            "validation_result": validation_result,
            "recovery_score": self.recovery_score,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class RecoveryAction(Base):
    """
    Controlled safe recovery execution record (Parts 25-26, 42).
    Tracks exact action executed, target service, risk, duration, and outcome.
    """
    __tablename__ = "recovery_actions"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    
    action_type = Column(String(128), index=True, nullable=False)  # RESTART_SERVICE, RECONNECT_DATABASE, etc.
    target = Column(String(64), index=True, nullable=False)
    reason = Column(Text, nullable=True)
    risk = Column(String(32), default="LOW")
    status = Column(String(32), default="SUCCESS", index=True)  # SUCCESS, FAILED
    result = Column(Text, nullable=True)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    finished_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "action_id": self.action_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "action_type": self.action_type,
            "target": self.target,
            "reason": self.reason,
            "risk": self.risk,
            "status": self.status,
            "result": self.result,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None
        }


class ValidationRun(Base):
    """
    Post-recovery verification run (Parts 28-31, 42).
    Compares telemetry before vs after recovery, records error reduction,
    latency reduction, availability improvement, and collateral side effects.
    """
    __tablename__ = "validation_runs"

    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    action_id = Column(String(64), index=True, nullable=True)
    iteration = Column(Integer, default=1)

    pre_metrics_json = Column(Text, default="{}")
    post_metrics_json = Column(Text, default="{}")
    comparison_table_json = Column(Text, default="[]")

    error_reduction = Column(Float, default=0.0)
    latency_reduction = Column(Float, default=0.0)
    availability_improvement = Column(Float, default=0.0)
    
    original_error_resolved = Column(Boolean, default=True)
    side_effect_detected = Column(Boolean, default=False)
    side_effects_json = Column(Text, default="[]")
    
    status = Column(String(32), default="VALIDATED", index=True)  # VALIDATED, SIDE_EFFECT, FAILED, UNRESOLVED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "validation_id": self.validation_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "action_id": self.action_id,
            "iteration": self.iteration,
            "error_reduction": self.error_reduction,
            "latency_reduction": self.latency_reduction,
            "availability_improvement": self.availability_improvement,
            "original_error_resolved": self.original_error_resolved,
            "side_effect_detected": self.side_effect_detected,
            "side_effects": json.loads(self.side_effects_json or "[]"),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


