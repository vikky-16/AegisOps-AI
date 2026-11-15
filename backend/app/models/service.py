"""
Service Registry Model
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from backend.app.core.database import Base


class ServiceRegistry(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    role = Column(String(128), nullable=False)
    port = Column(Integer, nullable=False)
    url = Column(String(256), nullable=False)
    health_endpoint = Column(String(128), default="/health")
    metrics_endpoint = Column(String(128), default="/metrics")
    dependencies_json = Column(Text, default="[]")  # JSON list of dependency names
    criticality = Column(String(32), default="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    sla_target_pct = Column(Float, default=99.9)
    status = Column(String(32), default="HEALTHY")  # HEALTHY, DEGRADED, UNHEALTHY, CRASHED
    is_monitored = Column(Boolean, default=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
