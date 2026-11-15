"""
LogHub Dataset Metadata and Telemetry Replay Data Models
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class LogHubDatasetInfo(BaseModel):
    id: str
    name: str
    category: str
    description: str
    total_raw_records: int
    components: List[str]
    sample_message: str
    has_structured_csv: bool


class LogHubReplayStatus(BaseModel):
    status: str = Field(default="IDLE", description="IDLE, STREAMING, PAUSED, COMPLETED, ERROR")
    dataset: str = Field(default="HDFS")
    events_available: int = 0
    events_sent: int = 0
    events_received: int = 0
    events_processed: int = 0
    processing_rate: float = 0.0
    configured_eps: int = 500
    target_count: int = 100000
    progress_percentage: float = 0.0
    elapsed_seconds: float = 0.0
    errors: int = 0
    anomalies: int = 0
    correlated_events: int = 0
    incidents: int = 0
    critical_incidents: int = 0
    is_streaming: bool = False
    is_paused: bool = False


class StartReplayRequest(BaseModel):
    dataset: str = Field(default="HDFS", description="HDFS, Linux, OpenStack, BGL, Spark, Zookeeper, Apache, Hadoop")
    target_count: int = Field(default=100000, description="10000, 50000, 100000")
    eps: int = Field(default=1000, description="100, 250, 500, 1000")
