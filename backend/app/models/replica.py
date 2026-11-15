"""
AegisOps AI - Digital Replica & Testing Lab Models
Persistent storage for isolated digital twin replicas and controlled remediation experiments.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index
from backend.app.core.database import Base


class ReplicaInstance(Base):
    """
    Represents an isolated replica / test environment instance.
    Supports Synthetic, Container, Staging, and Infrastructure-backed modes.
    """
    __tablename__ = "replica_instances"

    id = Column(Integer, primary_key=True, index=True)
    replica_id = Column(String(64), unique=True, index=True, nullable=False)
    tenant_id = Column(String(64), index=True, nullable=False, default="demo-tenant")
    name = Column(String(128), nullable=False)
    environment_type = Column(String(32), nullable=False, default="SYNTHETIC")  # SYNTHETIC, CONTAINER, STAGING, INFRASTRUCTURE_BACKED
    fidelity_level = Column(Float, nullable=False, default=0.98)  # 0.0 - 1.0 scale
    status = Column(String(32), nullable=False, default="HEALTHY")  # HEALTHY, DEGRADED, FAULT_INJECTED, BUSY, STOPPED
    target_service = Column(String(64), nullable=False, default="database-service")
    target_component = Column(String(64), nullable=True, default="connection_pool")
    active_scenario_id = Column(String(64), nullable=True)
    isolation_boundaries_json = Column(Text, default="{}")
    limitations_json = Column(Text, default="[]")
    data_source_json = Column(Text, default="{}")
    current_metrics_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_replica_tenant_status", "tenant_id", "status"),
        Index("idx_replica_service", "target_service"),
    )

    def to_dict(self) -> Dict[str, Any]:
        def parse_json(raw: Optional[str], default: Any) -> Any:
            if not raw:
                return default
            try:
                return json.loads(raw)
            except Exception:
                return default

        return {
            "replica_id": self.replica_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "environment_type": self.environment_type,
            "fidelity_level": self.fidelity_level,
            "status": self.status,
            "target_service": self.target_service,
            "target_component": self.target_component,
            "active_scenario_id": self.active_scenario_id,
            "isolation_boundaries": parse_json(self.isolation_boundaries_json, {}),
            "limitations": parse_json(self.limitations_json, []),
            "data_source": parse_json(self.data_source_json, {}),
            "current_metrics": parse_json(self.current_metrics_json, {}),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReplicaExperiment(Base):
    """
    Represents a full controlled experiment run inside a Digital Replica.
    Records 17-step lifecycle: baseline, candidates, hypotheses, fault injection,
    workload re-runs, quantitative evaluation (PASS/FAIL/INCONCLUSIVE/BLOCKED/ERROR),
    approval history, target execution, and validation.
    """
    __tablename__ = "replica_experiments"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, nullable=False, default="demo-tenant")
    replica_id = Column(String(64), index=True, nullable=False)
    environment_type = Column(String(32), nullable=False, default="SYNTHETIC")
    fidelity_level = Column(Float, nullable=False, default=0.98)
    scenario_id = Column(String(64), nullable=False)
    scenario_name = Column(String(128), nullable=False)
    target_service = Column(String(64), nullable=False, default="database-service")
    stage = Column(String(32), nullable=False, default="COMPLETED")  # INITIALIZING, FAULT_INJECTED, BASELINE_CAPTURED, CANDIDATE_TESTING, EVALUATING, AWAITING_APPROVAL, APPROVED, EXECUTED_ON_TARGET, VALIDATED, COMPLETED, FAILED
    status = Column(String(32), nullable=False, default="COMPLETED")  # RUNNING, COMPLETED, FAILED, CANCELLED
    evaluation_verdict = Column(String(32), nullable=False, default="PASS")  # PASS, FAIL, INCONCLUSIVE, BLOCKED, ERROR
    confidence_score = Column(Float, nullable=False, default=0.94)

    initial_conditions_json = Column(Text, default="{}")
    baseline_metrics_json = Column(Text, default="{}")
    candidate_remediations_json = Column(Text, default="[]")
    selected_candidate_id = Column(String(64), nullable=True)
    applied_changes_json = Column(Text, default="{}")
    test_workload_json = Column(Text, default="{}")
    before_after_metrics_json = Column(Text, default="{}")
    regression_checks_json = Column(Text, default="[]")
    resource_usage_json = Column(Text, default="{}")
    logs_json = Column(Text, default="[]")
    evidence_references_json = Column(Text, default="[]")
    ai_provider_model_json = Column(Text, default="{}")
    approval_history_json = Column(Text, default="[]")
    target_deployment_json = Column(Text, default="{}")
    limitations_notes = Column(Text, default="")
    duration_ms = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_experiment_tenant_inc", "tenant_id", "incident_id"),
        Index("idx_experiment_replica", "replica_id"),
        Index("idx_experiment_verdict", "evaluation_verdict"),
    )

    def to_dict(self) -> Dict[str, Any]:
        def parse_json(raw: Optional[str], default: Any) -> Any:
            if not raw:
                return default
            try:
                return json.loads(raw)
            except Exception:
                return default

        return {
            "experiment_id": self.experiment_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "replica_id": self.replica_id,
            "environment_type": self.environment_type,
            "fidelity_level": self.fidelity_level,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "target_service": self.target_service,
            "stage": self.stage,
            "status": self.status,
            "evaluation_verdict": self.evaluation_verdict,
            "confidence_score": self.confidence_score,
            "initial_conditions": parse_json(self.initial_conditions_json, {}),
            "baseline_metrics": parse_json(self.baseline_metrics_json, {}),
            "candidate_remediations": parse_json(self.candidate_remediations_json, []),
            "selected_candidate_id": self.selected_candidate_id,
            "applied_changes": parse_json(self.applied_changes_json, {}),
            "test_workload": parse_json(self.test_workload_json, {}),
            "before_after_metrics": parse_json(self.before_after_metrics_json, {}),
            "regression_checks": parse_json(self.regression_checks_json, []),
            "resource_usage": parse_json(self.resource_usage_json, {}),
            "logs": parse_json(self.logs_json, []),
            "evidence_references": parse_json(self.evidence_references_json, []),
            "ai_provider_model": parse_json(self.ai_provider_model_json, {}),
            "approval_history": parse_json(self.approval_history_json, []),
            "target_deployment": parse_json(self.target_deployment_json, {}),
            "limitations_notes": self.limitations_notes,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

