"""
Knowledge Base & Incident Memory Database Model
"""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from backend.app.core.database import Base


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    incident_code = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(256), nullable=False)
    primary_service = Column(String(64), index=True, nullable=False)
    symptoms_summary = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=False)
    recommended_remedy = Column(String(128), nullable=False)
    recovery_action_taken = Column(String(128), nullable=False)
    recovery_duration_sec = Column(Float, default=0.0)
    outcome = Column(String(32), default="RESOLVED")  # RESOLVED, MITIGATED, ESCALATED
    historical_success_rate = Column(Float, default=90.0)  # percentage
    
    tags_json = Column(Text, default="[]")
    vector_features_json = Column(Text, default="{}")  # Features for vector similarity
    times_referenced = Column(Integer, default=1)
    
    # Structured remediation steps, prerequisites, and risks
    remediation_steps_json = Column(Text, default="[]")
    prerequisites_json = Column(Text, default="[]")
    risks_and_rollback_json = Column(Text, default="[]")
    verified_outcome_details = Column(Text, nullable=True)
    version = Column(String(32), default="v1.0")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def article_id(self):
        return self.incident_code

    def to_dict(self):
        def _parse(field, default_val):
            if not field:
                return default_val
            try:
                return json.loads(field) if isinstance(field, str) else field
            except Exception:
                return default_val

        tags = _parse(self.tags_json, [])
        category = tags[0] if tags and len(tags) > 0 else "SERVICE_DEGRADATION"

        return {
            "id": self.id,
            "article_id": self.incident_code,
            "tenant_id": self.tenant_id,
            "incident_code": self.incident_code,
            "category": category,
            "title": self.title,
            "primary_service": self.primary_service,
            "symptoms_summary": self.symptoms_summary,
            "root_cause": self.root_cause,
            "recommended_remedy": self.recommended_remedy,
            "recovery_action_taken": self.recovery_action_taken,
            "recovery_duration_sec": self.recovery_duration_sec,
            "outcome": self.outcome,
            "historical_success_rate": self.historical_success_rate,
            "tags": _parse(self.tags_json, []),
            "remediation_steps": _parse(self.remediation_steps_json, []),
            "prerequisites": _parse(self.prerequisites_json, []),
            "risks_and_rollback": _parse(self.risks_and_rollback_json, []),
            "verified_outcome_details": self.verified_outcome_details,
            "version": self.version or "v1.0",
            "times_referenced": self.times_referenced,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else (self.created_at.isoformat() if self.created_at else None)
        }
