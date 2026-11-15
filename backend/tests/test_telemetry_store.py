"""
Unit and Integration Tests for Multi-Tenant TelemetryStore Architecture
Validates:
- LocalMemoryTelemetryStore ring buffer per-tenant partitioning
- Strict multi-tenant isolation (Tenant A cannot see Tenant B data)
- Ring buffer FIFO eviction under capacity limits
- Log filtering (service, severity, text query)
- Metric timeseries querying
- Trace span waterfall queries
- Per-tenant storage statistics & adapter templates
"""

import pytest
import asyncio
from datetime import datetime, timezone
from backend.app.storage.telemetry_store import (
    TelemetryStore,
    LocalMemoryTelemetryStore,
    ClickHouseTelemetryStore,
    TimescaleDBTelemetryStore,
    telemetry_store
)
from backend.app.schemas.telemetry_contract import (
    UnifiedTelemetryEvent,
    TelemetryEventType,
    TelemetrySeverityLevel
)


@pytest.fixture
def store():
    """Create fresh isolated memory telemetry store with low capacity (50) for eviction testing."""
    return LocalMemoryTelemetryStore(capacity_per_tenant=50)


def create_event(
    tenant_id: str,
    event_type: str = "log",
    service_name: str = "order-service",
    severity: str = "INFO",
    message: str = "Test log message",
    metric_name: str = None,
    metric_value: float = None,
    trace_id: str = None,
    span_id: str = None,
    parent_span_id: str = None,
    latency: float = None,
    http_route: str = None
) -> UnifiedTelemetryEvent:
    return UnifiedTelemetryEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        service_name=service_name,
        severity=severity,
        message=message,
        metric_name=metric_name,
        metric_value=metric_value,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        latency=latency,
        http_route=http_route,
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment="production"
    )


@pytest.mark.asyncio
async def test_store_tenant_isolation(store):
    """Events stored for Tenant Alpha must never leak to Tenant Beta."""
    # Write 5 logs for Alpha
    alpha_events = [create_event(tenant_id="tenant-alpha", message=f"Alpha log {i}") for i in range(5)]
    await store.write_events(alpha_events)

    # Write 3 logs for Beta
    beta_events = [create_event(tenant_id="tenant-beta", message=f"Beta log {i}") for i in range(3)]
    await store.write_events(beta_events)

    # Query Alpha logs
    alpha_logs = await store.query_logs(tenant_id="tenant-alpha")
    assert len(alpha_logs) == 5
    for item in alpha_logs:
        assert "Alpha" in item["message"]

    # Query Beta logs
    beta_logs = await store.query_logs(tenant_id="tenant-beta")
    assert len(beta_logs) == 3
    for item in beta_logs:
        assert "Beta" in item["message"]


@pytest.mark.asyncio
async def test_ring_buffer_fifo_eviction(store):
    """When tenant exceeds capacity_per_tenant (50), oldest events are evicted."""
    # Write 60 events for tenant-alpha
    events = [
        create_event(tenant_id="tenant-alpha", message=f"Sequence {i:03d}")
        for i in range(60)
    ]
    await store.write_events(events)

    stats = store.get_storage_stats(tenant_id="tenant-alpha")
    assert stats["buffered_events"] == 50
    assert stats["max_capacity"] == 50

    # Query logs
    logs = await store.query_logs(tenant_id="tenant-alpha", limit=100)
    assert len(logs) == 50

    # Ring buffer deque appends from right; deque iteration order retains last 50
    messages = [log["message"] for log in logs]
    assert "Sequence 059" in messages
    assert "Sequence 000" not in messages  # Oldest evicted


@pytest.mark.asyncio
async def test_log_filtering(store):
    """Logs can be filtered by severity, service, and search query."""
    ev_info = create_event(
        tenant_id="tenant-alpha",
        service_name="checkout-service",
        severity="INFO",
        message="Checkout succeeded for cart #1029"
    )
    ev_warn = create_event(
        tenant_id="tenant-alpha",
        service_name="payment-service",
        severity="WARN",
        message="Payment gateway high latency 450ms"
    )
    ev_err = create_event(
        tenant_id="tenant-alpha",
        service_name="payment-service",
        severity="ERROR",
        message="Payment gateway timed out during capture"
    )

    await store.write_events([ev_info, ev_warn, ev_err])

    # Filter by service
    payment_logs = await store.query_logs(tenant_id="tenant-alpha", service="payment-service")
    assert len(payment_logs) == 2

    # Filter by severity
    err_logs = await store.query_logs(tenant_id="tenant-alpha", severity="ERROR")
    assert len(err_logs) == 1
    assert "timed out" in err_logs[0]["message"]

    # Filter by search term
    search_logs = await store.query_logs(tenant_id="tenant-alpha", query="cart")
    assert len(search_logs) == 1
    assert search_logs[0]["service"] == "checkout-service"


@pytest.mark.asyncio
async def test_metrics_query(store):
    """Metrics timeseries can be retrieved with service and metric_name filters."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    metric_events = [
        create_event(
            tenant_id="tenant-alpha",
            event_type="metric",
            service_name="order-service",
            metric_name="http.server.duration_ms",
            metric_value=val
        )
        for val in values
    ]
    await store.write_events(metric_events)

    # Query metrics
    metrics = await store.query_metrics(
        tenant_id="tenant-alpha",
        metric_name="http.server.duration_ms"
    )
    assert len(metrics) == 5
    retrieved_vals = [m["value"] for m in metrics]
    assert 10.0 in retrieved_vals
    assert 50.0 in retrieved_vals


@pytest.mark.asyncio
async def test_trace_waterfall_and_spans(store):
    """Trace spans can be queried as a whole trace with parent/child relationship."""
    trace_id = "trace-4f9e8a1b2c3d4e5f"
    span_root = create_event(
        tenant_id="tenant-alpha",
        event_type="trace",
        service_name="api-gateway",
        trace_id=trace_id,
        span_id="span-root-001",
        latency=120.5,
        http_route="/api/v1/orders"
    )
    span_child1 = create_event(
        tenant_id="tenant-alpha",
        event_type="trace",
        service_name="auth-service",
        trace_id=trace_id,
        span_id="span-child-002",
        parent_span_id="span-root-001",
        latency=25.0
    )
    span_child2 = create_event(
        tenant_id="tenant-alpha",
        event_type="trace",
        service_name="db-service",
        trace_id=trace_id,
        span_id="span-child-003",
        parent_span_id="span-root-001",
        latency=45.2
    )

    await store.write_events([span_root, span_child1, span_child2])

    # Query full trace waterfall
    trace_spans = await store.query_traces(tenant_id="tenant-alpha", trace_id=trace_id)
    assert len(trace_spans) == 3
    span_ids = [s["span_id"] for s in trace_spans]
    assert "span-root-001" in span_ids
    assert "span-child-002" in span_ids
    assert "span-child-003" in span_ids

    # Query trace with wrong tenant returns empty
    cross_trace = await store.query_traces(tenant_id="tenant-beta", trace_id=trace_id)
    assert len(cross_trace) == 0


@pytest.mark.asyncio
async def test_global_singleton_instance():
    """Global telemetry_store singleton is ready and tracks global stats."""
    stats = telemetry_store.get_storage_stats()
    assert stats["backend"] == "LocalMemoryTelemetryStore"
    assert "active_tenants" in stats


@pytest.mark.asyncio
async def test_production_adapters_instantiation():
    """ClickHouse and TimescaleDB store adapters instantiate with schema templates."""
    ch_store = ClickHouseTelemetryStore(host="clickhouse.production.internal", port=9000)
    assert ch_store.host == "clickhouse.production.internal"
    assert ch_store.port == 9000
    assert "CREATE TABLE IF NOT EXISTS aegisops_telemetry" in ch_store.DDL_SCHEMA

    ts_store = TimescaleDBTelemetryStore(connection_dsn="postgresql://user:secret@timescale.internal:5432/aegisops")
    assert "timescale.internal" in ts_store.dsn
    assert "hypertable" in ts_store.DDL_SCHEMA
