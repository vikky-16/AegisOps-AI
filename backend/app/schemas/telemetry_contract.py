"""
AegisOps AI - Unified Telemetry Event Contract
Normalized data model for all incoming logs, metrics, traces, and operational events.
Compatible with OpenTelemetry (OTLP), Kafka streaming, REST ingestion, and cloud monitors.
Includes full enterprise context, multi-tenancy tags, and PII masking.
"""

import uuid
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.app.core.pii_masker import pii_masker


class TelemetrySourceType(str, Enum):
    OTEL = "otel"
    KAFKA = "kafka"
    REST = "rest"
    WEBHOOK = "webhook"
    PROMETHEUS = "prometheus"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    FLUENT_BIT = "fluent-bit"
    SYSLOG = "syslog"
    CLOUD_INGEST = "cloud-ingest"
    DEMO_GENERATOR = "demo-generator"


class TelemetrySourceMode(str, Enum):
    LIVE_EXTERNAL_TENANT = "LIVE_EXTERNAL_TENANT"
    LIVE_DEMO_ENVIRONMENT = "LIVE_DEMO_ENVIRONMENT"
    SIMULATED_DEMO = "SIMULATED_DEMO"


class TelemetryEventType(str, Enum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    HEALTH_CHECK = "health_check"
    ANOMALY_SIGNAL = "anomaly_signal"


class TelemetrySeverityLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class UnifiedTelemetryEvent(BaseModel):
    # Core Identification
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    tenant_id: str = Field(default="demo-tenant", description="Tenant identifier for multi-tenancy isolation")
    company_id: Optional[str] = Field(default=None, description="Company identifier (defaults to tenant_id)")
    source_id: Optional[str] = Field(default=None, description="Ingestion integration source identifier")
    integration_id: Optional[str] = Field(default=None, description="Customer OpenTelemetry integration identifier")
    source_mode: str = Field(
        default=TelemetrySourceMode.LIVE_DEMO_ENVIRONMENT.value,
        description="LIVE_EXTERNAL_TENANT | LIVE_DEMO_ENVIRONMENT | SIMULATED_DEMO"
    )
    
    # Timestamps
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    collector_timestamp: Optional[str] = Field(default=None, description="Timestamp recorded by OpenTelemetry Collector")
    broker_timestamp: Optional[str] = Field(default=None, description="Timestamp recorded by Redpanda/Kafka broker")
    ingestion_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processing_timestamp: Optional[str] = Field(default=None, description="Timestamp when AegisOps engine processed the event")

    # Classification & Severity
    event_type: str = Field(default="log", description="metric | log | trace | event | health_check | anomaly_signal")
    severity: str = Field(default="INFO", description="INFO | WARN | WARNING | ERROR | CRITICAL")
    source: str = Field(default="otel", description="Telemetry ingestion protocol/source")

    # Infrastructure & Topology Context
    service_name: str = Field(default="unknown-service", description="Originating service or component name")
    service_instance: Optional[str] = Field(default=None, description="Pod or host instance identifier")
    environment: str = Field(default="development", description="development | staging | production")
    cloud_provider: Optional[str] = Field(default=None, description="aws | gcp | onprem | baremetal")
    region: Optional[str] = Field(default="us-east-1", description="Cloud or datacenter region")
    host: str = Field(default="localhost", description="Host or node name")
    container: Optional[str] = Field(default=None, description="Container name or ID")
    namespace: Optional[str] = Field(default="default", description="Kubernetes namespace")
    k8s_pod_name: Optional[str] = Field(default=None, description="Kubernetes pod name")

    # Distributed Tracing
    trace_id: Optional[str] = Field(default=None, description="OpenTelemetry W3C trace ID (32 hex characters)")
    span_id: Optional[str] = Field(default=None, description="OpenTelemetry span ID (16 hex characters)")
    parent_span_id: Optional[str] = Field(default=None, description="Parent span ID for causal tree construction")
    request_id: Optional[str] = Field(default=None, description="HTTP or RPC correlation ID")

    # Payload & Message
    message: str = Field(default="", description="Human-readable log or event message (PII masked)")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="OpenTelemetry attributes & resource tags")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Multi-metric key-value pairs")
    exception: Optional[Dict[str, Any]] = Field(default=None, description="Structured exception details (type, message, stacktrace)")

    # HTTP & Network Protocol Context
    http_method: Optional[str] = Field(default=None, description="HTTP method: GET, POST, PUT, DELETE, etc.")
    http_route: Optional[str] = Field(default=None, description="Normalized HTTP route e.g. /api/v1/checkout")
    http_status: Optional[int] = Field(default=None, description="HTTP response status code e.g. 200, 500, 503")
    latency: Optional[float] = Field(default=None, description="Request duration or query latency in milliseconds")

    # Metrics & Resources
    metric_name: Optional[str] = Field(default=None, description="Primary metric name e.g. cpu_percent, error_rate")
    metric_value: Optional[float] = Field(default=None, description="Primary numerical metric value")
    database: Optional[Dict[str, Any]] = Field(default=None, description="Database operation context (table, pool, slow query)")
    resource_usage: Optional[Dict[str, float]] = Field(default=None, description="Resource utilization metrics (cpu_percent, memory_mb)")

    # Graph & Topology Dependencies
    dependency: Optional[str] = Field(default=None, description="Target dependency invoked during this event")
    dependencies: List[str] = Field(default_factory=list, description="Observed downstream dependencies")

    schema_version: str = Field(default="2.0", description="Contract schema version")

    def model_post_init(self, __context: Any) -> None:
        """Apply PII/secret masking and synchronize company_id."""
        if not self.company_id:
            self.company_id = self.tenant_id
        if self.message:
            self.message = pii_masker.mask_text(self.message)

    def to_log_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "ingestion_timestamp": self.ingestion_timestamp,
            "tenant_id": self.tenant_id,
            "source_mode": self.source_mode,
            "service": self.service_name,
            "service_name": self.service_name,
            "service_instance": self.service_instance,
            "level": self.severity,
            "severity": self.severity,
            "event_type": self.event_type,
            "message": self.message,
            "event_id": self.event_id,
            "request_id": self.request_id or "",
            "trace_id": self.trace_id or "",
            "span_id": self.span_id or "",
            "source": self.source,
            "collector_timestamp": self.collector_timestamp,
            "broker_timestamp": self.broker_timestamp,
            "processing_timestamp": self.processing_timestamp,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metrics": self.metrics,
            "http_status": self.http_status,
            "latency": self.latency,
            "metadata": self.attributes
        }

    def to_normalized_contract_dict(self) -> Dict[str, Any]:
        """
        Part 1 Contract Specification:
        Canonical normalized dictionary containing exactly the contract fields without fabricated data.
        """
        err_type = None
        if self.attributes and self.attributes.get("error_type"):
            err_type = self.attributes.get("error_type")
        elif self.http_status and self.http_status >= 400:
            err_type = f"HTTP_{self.http_status}"

        exc_type = None
        if isinstance(self.exception, dict):
            exc_type = self.exception.get("type") or self.exception.get("error_type")
        elif isinstance(self.exception, str):
            exc_type = self.exception

        endpoint = self.http_route
        if not endpoint and self.attributes:
            endpoint = self.attributes.get("http.target") or self.attributes.get("route")

        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "company": self.company_id or self.tenant_id,
            "timestamp": self.timestamp,
            "service": self.service_name,
            "host": self.host,
            "level": self.severity,
            "message": self.message,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "status_code": self.http_status,
            "latency_ms": self.latency,
            "error_type": err_type,
            "exception_type": exc_type,
            "endpoint": endpoint
        }


def classify_operational_event(data: Dict[str, Any]) -> str:
    """
    Part 2 Operational Event Classifier:
    Deterministically classifies logs and telemetry into:
    REQUEST, RESPONSE, DATABASE, CACHE, NETWORK, AUTHENTICATION, DEPENDENCY, DEPLOYMENT, TIMEOUT, EXCEPTION.
    """
    msg = str(data.get("message", "") or "").lower()
    evt_type = str(data.get("event_type", "") or "").lower()
    dep = str(data.get("dependency", "") or "").lower()
    status_code = data.get("status_code") or data.get("http_status")
    status_int = int(status_code) if (status_code is not None and str(status_code).isdigit()) else None

    # 1. DEPLOYMENT
    if any(k in msg or k in evt_type for k in ("deploy", "deployment", "release", "rollout", "build", "canary")):
        return "DEPLOYMENT"

    # 2. TIMEOUT
    if status_int == 504 or any(k in msg or k in evt_type for k in ("timeout", "timed out", "deadline exceeded")):
        return "TIMEOUT"

    # 3. DATABASE
    if any(k in msg or k in evt_type or k in dep for k in ("database", "postgresql", "postgres", "sql", "db_", "query", "connection pool", "psycopg")):
        return "DATABASE"

    # 4. CACHE
    if any(k in msg or k in evt_type or k in dep for k in ("redis", "cache", "memcached", "keydb")):
        return "CACHE"

    # 5. AUTHENTICATION
    if status_int in (401, 403) or any(k in msg or k in evt_type for k in ("auth", "unauthorized", "forbidden", "jwt", "token expired", "login failed")):
        return "AUTHENTICATION"

    # 6. EXCEPTION
    if any(k in msg or k in evt_type for k in ("exception", "traceback", "stacktrace", "unhandled error", "panic")):
        return "EXCEPTION"

    # 7. NETWORK
    if any(k in msg or k in evt_type for k in ("connection refused", "econnreset", "socket", "network unreachable", "dns", "broken pipe")):
        return "NETWORK"

    # 8. DEPENDENCY
    if dep or "dependency" in evt_type or "upstream" in msg:
        return "DEPENDENCY"

    # 9. RESPONSE
    if status_int is not None or "response" in evt_type or "completed" in msg:
        return "RESPONSE"

    # 10. REQUEST (Default for incoming operations)
    return "REQUEST"
