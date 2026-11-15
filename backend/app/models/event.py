"""
Operational Event Database Model
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from backend.app.core.database import Base


class OperationalEvent(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    service_name = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), index=True, nullable=False)
    severity = Column(String(32), default="INFO")  # INFO, WARNING, ERROR, CRITICAL
    score = Column(Float, default=0.0)
    summary = Column(String(256), nullable=False)
    details_json = Column(Text, default="{}")
    incident_id = Column(String(64), index=True, nullable=True)
    is_correlated = Column(Integer, default=0)


class IncidentEvent(Base):
    """
    Chronological operational events correlated into incidents (Parts 8 & 42).
    """
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    service = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), index=True, nullable=False)  # LOG, ANOMALY, TRANSITION, RECOVERY
    severity = Column(String(32), default="INFO", index=True)
    message = Column(Text, nullable=False)
    trace_id = Column(String(64), index=True, nullable=True)
    latency_ms = Column(Float, nullable=True)
    details_json = Column(Text, default="{}")

