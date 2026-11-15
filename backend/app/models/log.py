"""
Structured Log Entry Database Model
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from backend.app.core.database import Base


class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    service_name = Column(String(64), index=True, nullable=False)
    level = Column(String(16), index=True, nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    event_type = Column(String(64), index=True, nullable=False)
    message = Column(Text, nullable=False)
    trace_id = Column(String(64), index=True, nullable=True)
    fingerprint = Column(String(64), index=True, nullable=False)
    occurrence_count = Column(Integer, default=1)
    metadata_json = Column(Text, default="{}")

    __table_args__ = (
        Index("idx_logs_fingerprint_time", "fingerprint", "timestamp"),
    )
