"""
AegisOps AI - Historical Incident, Scenario History & Learning Database Models
Persists resolved incidents, signature vectors, and executed failure scenarios in SQLite.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from backend.app.core.database import Base


class HistoricalIncident(Base):
    """
    Persistent repository of resolved incidents for Case-Based Reasoning (CBR),
    vector similarity matching, and repeated failure pattern learning.
    """
    __tablename__ = "historical_incidents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    incident_id = Column(String(64), unique=True, index=True, nullable=False)
    failure_type = Column(String(64), index=True, nullable=False)
    failure_category = Column(String(64), index=True, nullable=False)  # Infrastructure, Database, Network, Dependency, Application, Resource, Performance, Availability, Behavioral
    primary_service = Column(String(64), index=True, nullable=False)
    affected_services_json = Column(Text, default="[]")
    
    # Normalized Telemetry Signature (JSON serialized feature vector)
    telemetry_signature_json = Column(Text, nullable=True)
    
    # RCA Details
    root_cause = Column(String(256), nullable=False)
    rca_confidence = Column(Float, default=0.0)
    
    # Remediation & Verification
    remediation_action = Column(String(128), nullable=False)
    remediation_result = Column(Text, nullable=True)
    verification_status = Column(String(32), default="VERIFIED")
    verification_details_json = Column(Text, default="{}")
    
    # Operational Durations (Seconds)
    time_to_detect_sec = Column(Float, default=0.0)
    time_to_recover_sec = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    
    created_at = Column(String(64), nullable=False)
    resolved_at = Column(String(64), nullable=False)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "incident_id": self.incident_id,
            "failure_type": self.failure_type,
            "failure_category": self.failure_category,
            "primary_service": self.primary_service,
            "affected_services": json.loads(self.affected_services_json or "[]"),
            "telemetry_signature": json.loads(self.telemetry_signature_json or "{}"),
            "root_cause": self.root_cause,
            "rca_confidence": self.rca_confidence,
            "remediation_action": self.remediation_action,
            "remediation_result": self.remediation_result,
            "verification_status": self.verification_status,
            "time_to_detect_sec": self.time_to_detect_sec,
            "time_to_recover_sec": self.time_to_recover_sec,
            "retry_count": self.retry_count,
            "success": self.success,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at
        }


class FailureScenarioRecord(Base):
    """
    Audit log of all scheduled and manually triggered failure scenarios.
    """
    __tablename__ = "failure_scenarios_history"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    failure_id = Column(String(64), index=True, nullable=False)
    scenario_type = Column(String(64), index=True, nullable=False)
    target_service = Column(String(64), index=True, nullable=False)
    severity = Column(String(32), default="HIGH")
    duration_sec = Column(Integer, default=45)
    lifecycle_state = Column(String(32), default="INJECTING")  # INJECTING, ACTIVE, DETECTED, INVESTIGATING, RCA, REMEDIATING, VERIFYING, RESOLVED, LEARNED
    
    associated_incident_id = Column(String(64), nullable=True)
    execution_mode = Column(String(32), default="CONTROLLED_DEMO")
    
    started_at = Column(String(64), nullable=False)
    resolved_at = Column(String(64), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "failure_id": self.failure_id,
            "scenario_type": self.scenario_type,
            "target_service": self.target_service,
            "severity": self.severity,
            "duration_sec": self.duration_sec,
            "lifecycle_state": self.lifecycle_state,
            "associated_incident_id": self.associated_incident_id,
            "execution_mode": self.execution_mode,
            "started_at": self.started_at,
            "resolved_at": self.resolved_at
        }


class VerifiedRecoveryPatternRecord(Base):
    """
    Persistent store of validated, empirically proven recovery solutions.
    Only stored when all 8 empirical validation criteria and side-effect checks pass.
    Strict tenant isolation enforced.
    """
    __tablename__ = "verified_recovery_patterns"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(String(64), unique=True, index=True, nullable=False)
    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    incident_type = Column(String(64), index=True, nullable=False)
    failure_signature_json = Column(Text, nullable=True)
    root_cause_category = Column(String(64), index=True, nullable=False)
    root_cause_description = Column(Text, nullable=False)
    origin_service = Column(String(64), index=True, nullable=False)
    affected_services_json = Column(Text, default="[]")
    relevant_metrics_json = Column(Text, default="{}")
    relevant_log_signatures_json = Column(Text, default="[]")
    relevant_trace_signatures_json = Column(Text, default="[]")
    dependency_context_json = Column(Text, default="{}")
    recovery_action = Column(String(128), index=True, nullable=False)
    recovery_reason = Column(Text, nullable=False)
    attempts_required = Column(Integer, default=1)
    pre_fix_metrics_json = Column(Text, default="{}")
    post_fix_metrics_json = Column(Text, default="{}")
    validation_results_json = Column(Text, default="[]")
    side_effect_results_json = Column(Text, default="[]")
    recovery_duration_sec = Column(Float, default=0.0)
    verified_at = Column(String(64), nullable=False)
    verification_score = Column(Float, default=1.0)
    environment_type = Column(String(32), default="CONTROLLED_SANDBOX")
    sandbox_id = Column(String(64), nullable=False)
    source_execution_id = Column(String(64), nullable=True)
    confidence = Column(Float, default=0.95)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "pattern_id": self.pattern_id,
            "tenant_id": self.tenant_id,
            "incident_id": self.incident_id,
            "incident_type": self.incident_type,
            "failure_signature": json.loads(self.failure_signature_json or "{}"),
            "root_cause_category": self.root_cause_category,
            "root_cause_description": self.root_cause_description,
            "origin_service": self.origin_service,
            "affected_services": json.loads(self.affected_services_json or "[]"),
            "relevant_metrics": json.loads(self.relevant_metrics_json or "{}"),
            "relevant_log_signatures": json.loads(self.relevant_log_signatures_json or "[]"),
            "relevant_trace_signatures": json.loads(self.relevant_trace_signatures_json or "[]"),
            "dependency_context": json.loads(self.dependency_context_json or "{}"),
            "recovery_action": self.recovery_action,
            "recovery_reason": self.recovery_reason,
            "attempts_required": self.attempts_required,
            "pre_fix_metrics": json.loads(self.pre_fix_metrics_json or "{}"),
            "post_fix_metrics": json.loads(self.post_fix_metrics_json or "{}"),
            "validation_results": json.loads(self.validation_results_json or "[]"),
            "side_effect_results": json.loads(self.side_effect_results_json or "[]"),
            "recovery_duration_sec": self.recovery_duration_sec,
            "verified_at": self.verified_at,
            "verification_score": self.verification_score,
            "environment_type": self.environment_type,
            "sandbox_id": self.sandbox_id,
            "source_execution_id": self.source_execution_id,
            "confidence": self.confidence
        }
