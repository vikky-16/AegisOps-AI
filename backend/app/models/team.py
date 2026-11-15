"""
AegisOps AI - Enterprise Team and Membership Models
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from backend.app.core.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(256), nullable=True)
    lead_user = Column(String(128), nullable=True)
    assigned_services_json = Column(Text, default="[]", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def get_assigned_services(self) -> List[str]:
        if not self.assigned_services_json:
            return []
        try:
            return json.loads(self.assigned_services_json)
        except Exception:
            return []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "organization_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "lead_user": self.lead_user,
            "assigned_services": self.get_assigned_services(),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(String(64), ForeignKey("teams.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    role_in_team = Column(String(32), default="MEMBER", nullable=False)  # LEAD, MEMBER, ON_CALL
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "role_in_team": self.role_in_team,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None
        }
