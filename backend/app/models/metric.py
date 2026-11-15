"""
Metric Snapshot Database Model
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from backend.app.core.database import Base


class MetricSnapshot(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = Column(String(32), default="HEALTHY")
    cpu_percent = Column(Float, default=0.0)
    memory_mb = Column(Float, default=0.0)
    request_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    latency_p50_ms = Column(Float, default=0.0)
    latency_p95_ms = Column(Float, default=0.0)
    latency_p99_ms = Column(Float, default=0.0)
    active_connections = Column(Integer, default=0)
    anomaly_score = Column(Float, default=0.0)
    is_anomaly = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_metrics_service_time", "service_name", "timestamp"),
    )


class LogFeature(Base):
    """
    Real-time windowed telemetry feature aggregates (Parts 4 & 42).
    Tracks error rate, 5xx rate, 4xx rate, timeout rate, latency percentiles, and dynamics.
    """
    __tablename__ = "log_features"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    company = Column(String(64), index=True, default="shopsphere", nullable=False)
    service = Column(String(64), index=True, nullable=False)
    endpoint = Column(String(128), index=True, nullable=True)
    window_sec = Column(Float, default=30.0)

    request_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    warning_rate = Column(Float, default=0.0)
    five_xx_rate = Column(Float, default=0.0)
    four_xx_rate = Column(Float, default=0.0)
    timeout_count = Column(Integer, default=0)
    exception_count = Column(Integer, default=0)
    unique_error_patterns = Column(Integer, default=0)

    average_latency = Column(Float, default=0.0)
    p95_latency = Column(Float, default=0.0)
    p99_latency = Column(Float, default=0.0)

    error_rate_change = Column(Float, default=0.0)
    latency_change = Column(Float, default=0.0)
    traffic_change = Column(Float, default=0.0)

    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("idx_log_features_tenant_service_ts", "tenant_id", "service", "timestamp"),
    )

    def to_dict(self):
        return {
            "tenant_id": self.tenant_id,
            "company": self.company,
            "service": self.service,
            "endpoint": self.endpoint,
            "window_sec": self.window_sec,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "warning_rate": self.warning_rate,
            "five_xx_rate": self.five_xx_rate,
            "four_xx_rate": self.four_xx_rate,
            "timeout_count": self.timeout_count,
            "exception_count": self.exception_count,
            "average_latency": self.average_latency,
            "p95_latency": self.p95_latency,
            "p99_latency": self.p99_latency,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

