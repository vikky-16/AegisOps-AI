"""
Normalized Unified Telemetry Event Model
Standard data envelope for all incoming logs, metrics, traces, and domain signals.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


class TelemetryType(str, Enum):
    LOG = "LOG"
    METRIC = "METRIC"
    TRACE = "TRACE"
    EVENT = "EVENT"
    HEALTH_CHECK = "HEALTH_CHECK"
    DATABASE_SIGNAL = "DATABASE_SIGNAL"
    PAYMENT_SIGNAL = "PAYMENT_SIGNAL"
    DATA_PIPELINE_SIGNAL = "DATA_PIPELINE_SIGNAL"
    INFRASTRUCTURE_SIGNAL = "INFRASTRUCTURE_SIGNAL"


class TelemetrySeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class NormalizedTelemetryEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tenant_id: Optional[str] = Field(default="demo-tenant", description="Tenant isolation identifier")
    source: str = Field(default="unknown-source", description="Source identifier e.g. payment-api-01, k8s-node-04")
    environment: str = Field(default="production", description="demo, staging, or production")
    service: str = Field(default="general", description="Service or component name")
    type: TelemetryType = Field(default=TelemetryType.LOG)
    severity: TelemetrySeverity = Field(default=TelemetrySeverity.INFO)
    event_type: str = Field(default="GENERIC_TELEMETRY")
    message: str = Field(default="")
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    host: Optional[str] = "localhost"
    http_method: Optional[str] = None
    route: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    dependency: Optional[str] = None
    metrics: Optional[Dict[str, float]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
