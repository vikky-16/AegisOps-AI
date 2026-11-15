"""
AegisOps AI - Anomaly Episode Database Model (Phase 34)
Stores deduplicated anomaly episodes per tenant.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Index
from backend.app.core.database import Base


class AnomalyEpisodeModel(Base):
    __tablename__ = "anomaly_episodes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(String(64), unique=True, index=True, nullable=False)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    service = Column(String(64), index=True, nullable=False)
    feature = Column(String(64), index=True, nullable=False)
    severity = Column(String(32), default="MEDIUM", index=True)
    
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    duration_seconds = Column(Float, default=0.0)
    
    peak_score = Column(Float, default=0.0)
    current_score = Column(Float, default=0.0)
    event_count = Column(Integer, default=1)
    
    status = Column(String(32), default="ACTIVE", index=True)  # ACTIVE, CORRELATED, EXPIRED, RESOLVED
    incident_id = Column(String(64), index=True, nullable=True)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "episode_id": self.episode_id,
            "tenant_id": self.tenant_id,
            "company": self.tenant_id,
            "service": self.service,
            "feature": self.feature,
            "severity": self.severity,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "duration_seconds": self.duration_seconds,
            "peak_score": self.peak_score,
            "current_score": self.current_score,
            "event_count": self.event_count,
            "status": self.status,
            "incident_id": self.incident_id
        }
