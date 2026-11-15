"""
Human Approval Ticket Database Model
Supports Role-Based Access Control (RBAC) and complete audit trails.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from backend.app.core.database import Base


class ApprovalTicket(Base):
    __tablename__ = "approvals"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(String(64), unique=True, index=True, nullable=False)  # APP-xxx
    incident_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), default="demo-tenant", index=True)
    service_name = Column(String(64), nullable=False)
    
    proposed_action = Column(String(128), nullable=False)
    action_parameters_json = Column(Text, default="{}")
    risk_level = Column(String(32), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL
    risk_score = Column(Float, default=75.0)
    required_role = Column(String(32), default="APPROVER")  # OPERATOR, APPROVER, ADMIN, SRE_LEAD
    
    reason = Column(Text, nullable=False)
    expected_outcome = Column(Text, nullable=True)
    estimated_downtime_sec = Column(Integer, default=0)
    rollback_plan = Column(Text, nullable=True)
    details_json = Column(Text, default="{}")
    
    status = Column(String(32), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, DEFERRED, EXECUTED, FAILED
    decision = Column(String(32), nullable=True)  # APPROVED, REJECTED, DEFERRED
    requested_by = Column(String(64), default="AegisOps_Policy_Engine")
    reviewed_by = Column(String(64), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    plan_id = Column(String(64), nullable=True)
    plan_version = Column(String(32), default="v1.0")
    solution_source = Column(String(32), default="AI_PROPOSED")
    is_consumed = Column(Boolean, default=False)
    is_simulated = Column(Boolean, default=False)
    
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        details = {}
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except Exception:
                details = {}

        data = {
            "id": self.id,
            "approval_id": self.approval_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id or "demo-tenant",
            "company": self.tenant_id or "demo-tenant",
            "plan_id": self.plan_id,
            "plan_version": self.plan_version or "v1.0",
            "solution_source": self.solution_source or "AI_PROPOSED",
            "is_consumed": bool(self.is_consumed),
            "is_simulated": bool(self.is_simulated),
            "service": self.service_name,
            "service_name": self.service_name,
            "proposed_action": self.proposed_action,
            "recommended_action": self.proposed_action,
            "action": self.proposed_action,
            "proposed_recovery_action": self.proposed_action,
            "risk_level": self.risk_level or "MEDIUM",
            "risk_score": self.risk_score or 50.0,
            "required_role": self.required_role or "SRE_LEAD",
            "approver_role": self.required_role or "SRE_LEAD",
            "approver_role_requirement": self.required_role or "SRE_LEAD",
            "reason": self.reason,
            "why_selected": details.get("why_selected", self.reason),
            "expected_outcome": self.expected_outcome,
            "expected_result": self.expected_outcome,
            "estimated_downtime_sec": self.estimated_downtime_sec,
            "rollback_plan": self.rollback_plan,
            "rollback_available": bool(self.rollback_plan and self.rollback_plan != "NONE"),
            "status": self.status or "PENDING",
            "decision": self.decision,
            "requested_by": self.requested_by,
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }
        # Merge extra rich fields from details
        for k, v in details.items():
            if k not in data or not data[k]:
                data[k] = v
        return data
