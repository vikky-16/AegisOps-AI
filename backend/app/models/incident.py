"""
Incident Database Model
Comprehensive entity supporting the full automated response lifecycle:
Detection -> Incident -> Correlation -> RCA -> Approval -> Remediation -> Verification -> Resolution
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from backend.app.core.database import Base


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(64), unique=True, index=True, nullable=False)  # e.g., INC-2026-0042
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(32), default="MEDIUM", index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # 10 Standard Statuses
    # OPEN, INVESTIGATING, ROOT_CAUSE_IDENTIFIED, AWAITING_APPROVAL, APPROVED, REMEDIATING, VERIFYING, RESOLVED, REJECTED, REMEDIATION_FAILED
    status = Column(String(32), default="OPEN", index=True)
    
    # Affected Services & Resources
    primary_service = Column(String(64), index=True, nullable=False)
    affected_services_json = Column(Text, default="[]")  # JSON list of service names
    affected_resources_json = Column(Text, default="[]")  # JSON list of cloud workload resource IDs
    affected_dependencies_json = Column(Text, default="[]")  # JSON list of downstream impacted dependencies
    
    # Correlation & Event IDs
    correlation_id = Column(String(64), index=True, nullable=True)
    event_ids_json = Column(Text, default="[]")  # List of real event IDs supporting the incident
    correlated_event_count = Column(Integer, default=1)
    
    # Telemetry & Error Metrics
    error_rate = Column(Float, default=0.0)  # Current error rate (e.g., 87/min)
    baseline_error_rate = Column(Float, default=0.01)  # Baseline error rate (e.g., 1/min)
    anomaly_score = Column(Float, default=0.0)
    
    # Explainable Root Cause Analysis (RCA) Results
    root_cause = Column(String(256), nullable=True)  # Explainable root cause description
    root_cause_service = Column(String(64), nullable=True)  # Specific root cause service
    root_cause_category = Column(String(128), nullable=True)
    root_cause_summary = Column(Text, nullable=True)
    root_cause_confidence = Column(Float, default=0.0)  # 0.0 to 1.0 (e.g. 0.94)
    rca_confidence = Column(Float, default=0.0)  # Alias for backward compatibility
    rca_evidence_json = Column(Text, default="[]")  # List of evidence points citing actual event IDs
    
    # Business Impact & SLA
    business_impact_score = Column(Float, default=0.0)  # 0 to 100
    estimated_users_affected = Column(Integer, default=0)
    sla_breach_risk = Column(String(32), default="LOW")  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Remediation, Approval & Verification
    recommended_action = Column(String(128), nullable=True)
    alternative_action = Column(String(128), nullable=True)
    action_risk_level = Column(String(32), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    
    approval_status = Column(String(32), default="NONE")  # NONE, REQUIRED, APPROVED, REJECTED, DEFERRED
    remediation_status = Column(String(32), default="NONE")  # NONE, PENDING, EXECUTING, SUCCESS, FAILED
    verification_status = Column(String(32), default="NONE")  # NONE, WAITING_FOR_TELEMETRY, VERIFIED, FAILED
    recovery_status = Column(String(32), default="NONE")  # NONE, PENDING_APPROVAL, IN_PROGRESS, SUCCESS, FAILED, ESCALATED
    
    # 14 Closed-Loop Lifecycle States:
    # DETECTED, EVIDENCE_COLLECTED, CLASSIFIED, RCA_COMPLETED, SOLUTIONS_GENERATED,
    # SOLUTION_SELECTED, REPLICA_PREPARED, SOLUTION_EXECUTED, SCENARIO_REPLAYED,
    # EVIDENCE_COMPARED, VALIDATING, VALIDATED, REFINEMENT_REQUIRED, UNRESOLVED
    lifecycle_state = Column(String(32), default="DETECTED", index=True)
    state_transitions_json = Column(Text, default="[]")  # Chronological list of state transition records
    
    # Hypotheses & Explanations (Primary vs Alternatives with Supporting & Contradictory evidence)
    hypotheses_json = Column(Text, default="{}")
    
    # Candidate Solutions & Selection
    candidate_solutions_json = Column(Text, default="[]")
    selected_solution_json = Column(Text, default="{}")
    selected_solution_source = Column(String(32), nullable=True)  # AI_PROPOSED, KNOWLEDGE_BASE
    dual_solutions_json = Column(Text, default="{}")
    rca_id = Column(String(64), nullable=True, index=True)
    
    # Closed-Loop Execution, Replay & Validation Details
    iteration_count = Column(Integer, default=0)
    max_iterations = Column(Integer, default=3)
    scenario_id = Column(String(64), nullable=True)  # Replica scenario ID if applicable
    execution_history_json = Column(Text, default="[]")  # Pre/post comparisons across iterations
    validation_report_json = Column(Text, default="{}")  # Comprehensive validation report
    side_effects_detected_json = Column(Text, default="[]")
    unresolved_explanation = Column(Text, nullable=True)

    # Visual Chronological Timeline (events -> detection -> RCA -> approval -> remediation -> verification -> resolved)
    timeline_json = Column(Text, default="[]")
    
    # Multi-Tenancy & Source Classification
    tenant_id = Column(String(64), index=True, default="demo-tenant", nullable=False)
    telemetry_source_mode = Column(String(32), default="LIVE_DEMO_ENVIRONMENT", nullable=False)  # LIVE_EXTERNAL_TENANT, LIVE_DEMO_ENVIRONMENT, SIMULATED_DEMO
    is_synthetic = Column(Boolean, default=True)

    # Timestamps & Audit
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        import json
        def _parse(field, default_val=None):
            if default_val is None:
                default_val = []
            if not field:
                return default_val
            try:
                return json.loads(field) if isinstance(field, str) else field
            except Exception:
                return default_val

        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "telemetry_source_mode": self.telemetry_source_mode,
            "is_synthetic": bool(self.is_synthetic if self.is_synthetic is not None else True),
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "lifecycle_state": self.lifecycle_state or self.status,
            "state_transitions": _parse(self.state_transitions_json, []),
            "hypotheses": _parse(self.hypotheses_json, {}),
            "candidate_solutions": _parse(self.candidate_solutions_json, []),
            "selected_solution": _parse(self.selected_solution_json, {}),
            "selected_solution_source": self.selected_solution_source,
            "dual_solutions": _parse(self.dual_solutions_json, {}),
            "rca_id": self.rca_id,
            "iteration_count": self.iteration_count or 0,
            "max_iterations": self.max_iterations or 3,
            "scenario_id": self.scenario_id,
            "execution_history": _parse(self.execution_history_json, []),
            "validation_report": _parse(self.validation_report_json, {}),
            "side_effects_detected": _parse(self.side_effects_detected_json, []),
            "unresolved_explanation": self.unresolved_explanation,
            "primary_service": self.primary_service,
            "affected_services": _parse(self.affected_services_json, []),
            "affected_resources": _parse(self.affected_resources_json, []),
            "affected_dependencies": _parse(self.affected_dependencies_json, []),
            "correlation_id": self.correlation_id,
            "event_ids": _parse(self.event_ids_json, []),
            "correlated_event_count": self.correlated_event_count,
            "error_rate": self.error_rate,
            "baseline_error_rate": self.baseline_error_rate,
            "anomaly_score": self.anomaly_score,
            "root_cause": self.root_cause,
            "root_cause_service": self.root_cause_service,
            "root_cause_category": self.root_cause_category,
            "root_cause_summary": self.root_cause_summary,
            "rca_confidence": self.rca_confidence or self.root_cause_confidence,
            "rca_evidence": _parse(self.rca_evidence_json, []),
            "business_impact_score": self.business_impact_score,
            "estimated_users_affected": self.estimated_users_affected,
            "sla_breach_risk": self.sla_breach_risk,
            "recommended_action": self.recommended_action,
            "alternative_action": self.alternative_action,
            "action_risk_level": self.action_risk_level,
            "approval_status": self.approval_status,
            "remediation_status": self.remediation_status,
            "verification_status": self.verification_status,
            "recovery_status": self.recovery_status,
            "timeline": _parse(self.timeline_json, []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


class IncidentAttempt(Base):
    """
    Dedicated entity tracking each closed-loop remediation attempt, telemetry metrics,
    side-effects, and refinement decisions.
    """
    __tablename__ = "incident_attempts"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    iteration = Column(Integer, default=1, index=True)
    solution_id = Column(String(64), nullable=True)
    action = Column(String(128), nullable=False)
    target_component = Column(String(128), nullable=True)
    timestamp = Column(Float, default=lambda: datetime.now(timezone.utc).timestamp(), index=True)
    
    pre_execution_metrics_json = Column(Text, default="{}")
    post_execution_metrics_json = Column(Text, default="{}")
    execution_logs_json = Column(Text, default="[]")
    execution_result_json = Column(Text, default="{}")
    validation_result_json = Column(Text, default="{}")
    
    original_error_resolved = Column(Boolean, default=False)
    side_effect_detected = Column(Boolean, default=False)
    solution_validated = Column(Boolean, default=False)
    
    unresolved_conditions_json = Column(Text, default="[]")
    side_effects_json = Column(Text, default="[]")
    improved_conditions_json = Column(Text, default="[]")
    
    confidence = Column(Float, default=0.8)
    reasoning = Column(Text, nullable=True)
    next_action = Column(String(64), default="VALIDATED")  # VALIDATED, REFINEMENT_REQUIRED, RETRY_NEXT_CANDIDATE, UNRESOLVED_ESCALATE
    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        import json
        def _parse(field, default_val=None):
            if default_val is None:
                default_val = {}
            if not field:
                return default_val
            try:
                return json.loads(field) if isinstance(field, str) else field
            except Exception:
                return default_val

        return {
            "id": self.id,
            "attempt_id": self.attempt_id,
            "incident_id": self.incident_id,
            "iteration": self.iteration,
            "solution_id": self.solution_id,
            "action": self.action,
            "target_component": self.target_component,
            "timestamp": self.timestamp,
            "pre_execution_metrics": _parse(self.pre_execution_metrics_json, {}),
            "post_execution_metrics": _parse(self.post_execution_metrics_json, {}),
            "execution_logs": _parse(self.execution_logs_json, []),
            "execution_result": _parse(self.execution_result_json, {}),
            "validation_result": _parse(self.validation_result_json, {}),
            "original_error_resolved": self.original_error_resolved,
            "side_effect_detected": self.side_effect_detected,
            "solution_validated": self.solution_validated,
            "unresolved_conditions": _parse(self.unresolved_conditions_json, []),
            "side_effects": _parse(self.side_effects_json, []),
            "improved_conditions": _parse(self.improved_conditions_json, []),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "next_action": self.next_action,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


