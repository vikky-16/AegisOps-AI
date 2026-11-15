"""
AegisOps AI - RCA Dual-Solution Database Model
Persists AI-proposed solutions, real knowledge base matches, comparison matrix,
solution selection history, and linked recovery executions.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from backend.app.core.database import Base


class IncidentRCARecord(Base):
    """
    Persistent audit record for an incident's RCA analysis and dual solutions.
    Ensures that reopening an incident restores previously generated solutions
    without unnecessary duplicate AI calls or re-retrieval.
    """
    __tablename__ = "incident_rca_records"

    id = Column(Integer, primary_key=True, index=True)
    rca_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, default="demo-tenant", nullable=False)

    root_cause_service = Column(String(64), nullable=True)
    root_cause_category = Column(String(64), nullable=True)
    root_cause_summary = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)

    # Solution A — AI-Proposed Solution JSON
    ai_solution_json = Column(Text, default="{}")

    # Solution B — Knowledge Base Solution JSON
    kb_solution_json = Column(Text, default="{}")

    # Comparison Matrix JSON
    comparison_json = Column(Text, default="{}")

    # Selection & Lifecycle State
    selected_solution_source = Column(String(32), nullable=True)  # AI_PROPOSED, KNOWLEDGE_BASE
    selected_solution_json = Column(Text, default="{}")
    selection_history_json = Column(Text, default="[]")

    # Linkage to Recovery & Approvals
    recovery_plan_id = Column(String(64), nullable=True)
    recovery_execution_id = Column(String(64), nullable=True)
    approval_id = Column(String(64), nullable=True)
    approval_status = Column(String(32), default="NONE")  # NONE, REQUIRED, APPROVED, REJECTED
    validation_result_json = Column(Text, default="{}")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        def _parse(field, default_val):
            if not field:
                return default_val
            try:
                return json.loads(field) if isinstance(field, str) else field
            except Exception:
                return default_val

        selection_obj = None
        if self.selected_solution_source:
            selection_obj = {
                "selected_source": self.selected_solution_source,
                "selected_solution": _parse(self.selected_solution_json, {}),
                "plan_id": self.recovery_plan_id,
                "execution_id": self.recovery_execution_id,
                "approval_id": self.approval_id,
                "approval_status": self.approval_status,
                "validation_result": _parse(self.validation_result_json, {}),
            }

        return {
            "id": self.id,
            "rca_id": self.rca_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "root_cause_service": self.root_cause_service,
            "root_cause_category": self.root_cause_category,
            "root_cause_summary": self.root_cause_summary,
            "confidence": self.confidence,
            "ai_solution": _parse(self.ai_solution_json, {}),
            "kb_solution": _parse(self.kb_solution_json, {}),
            "comparison": _parse(self.comparison_json, {}),
            "selected_solution_source": self.selected_solution_source,
            "selected_solution": _parse(self.selected_solution_json, {}),
            "selection": selection_obj,
            "selection_history": _parse(self.selection_history_json, []),
            "recovery_plan_id": self.recovery_plan_id,
            "recovery_execution_id": self.recovery_execution_id,
            "approval_id": self.approval_id,
            "approval_status": self.approval_status,
            "validation_result": _parse(self.validation_result_json, {}),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
