"""
Audit Log Database Model (Immutable Action Trail)
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from backend.app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_identifier = Column(String(128), default="system_automator", index=True)
    action = Column(String(128), nullable=False, index=True)  # e.g., APPROVE_RECOVERY, SIMULATE_FAILURE, ROTATE_LOGS
    target_resource = Column(String(128), nullable=False)
    details_json = Column(Text, default="{}")
    ip_address = Column(String(64), nullable=True)
