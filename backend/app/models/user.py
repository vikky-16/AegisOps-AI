"""
User Database Model
"""

from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from backend.app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), index=True, nullable=True)
    organization_id = Column(String(64), nullable=True, index=True)
    is_platform_admin = Column(Boolean, default=False, nullable=False)
    # Enterprise Roles: SUPER_ADMIN, ORG_ADMIN, CEO, CTO, SRE_LEAD, DEVOPS_ENGINEER, SECURITY_ENGINEER, DEVELOPER, INCIDENT_COMMANDER, VIEWER
    # (Legacy mappings: PLATFORM_ADMIN -> SUPER_ADMIN, TENANT_ADMIN -> ORG_ADMIN, SRE_MANAGER -> SRE_LEAD, SRE_ENGINEER -> DEVOPS_ENGINEER, OPERATOR -> DEVOPS_ENGINEER)
    role = Column(String(32), default="VIEWER", nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(64), nullable=True)
    phone = Column(String(32), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    must_change_password = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    password_reset_token = Column(String(128), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    invitation_token = Column(String(128), nullable=True)
    invitation_expires_at = Column(DateTime, nullable=True)
    session_revoked_at = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "tenant_id": self.tenant_id or self.organization_id,
            "organization_id": self.organization_id or self.tenant_id,
            "is_platform_admin": self.is_platform_admin,
            "role": self.role,
            "mfa_enabled": bool(self.mfa_enabled),
            "phone": self.phone,
            "is_active": self.is_active,
            "must_change_password": bool(self.must_change_password),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

