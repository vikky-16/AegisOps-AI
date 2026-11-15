"""
Storage Snapshot & Archival Database Models
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from backend.app.core.database import Base


class StorageSnapshot(Base):
    __tablename__ = "storage_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    total_gb = Column(Float, default=100.0)
    used_gb = Column(Float, default=82.0)
    free_gb = Column(Float, default=18.0)
    used_percentage = Column(Float, default=82.0)
    
    growth_rate_gb_per_hour = Column(Float, default=1.8)
    predicted_critical_hours = Column(Float, default=10.0)
    
    log_files_count = Column(Integer, default=4)
    total_log_size_mb = Column(Float, default=1240.0)
    archive_size_mb = Column(Float, default=350.0)
    top_consumers_json = Column(Text, default="[]")


class ArchiveRecord(Base):
    __tablename__ = "archive_records"

    id = Column(Integer, primary_key=True, index=True)
    archive_id = Column(String(64), unique=True, index=True, nullable=False)
    file_name = Column(String(256), nullable=False)
    source_service = Column(String(64), nullable=False)
    original_size_bytes = Column(Integer, nullable=False)
    compressed_size_bytes = Column(Integer, nullable=False)
    compression_ratio = Column(Float, default=0.0)
    archive_path = Column(String(512), nullable=False)
    archived_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
