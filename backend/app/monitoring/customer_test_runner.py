"""
AegisOps AI - Controlled Customer Test Environment (Customer A)
Simulates a realistic customer infrastructure generating OpenTelemetry logs, metrics, and traces:
- gateway (API ingress)
- orders (Business logic)
- payments (Checkout & billing)
- auth (Identity & token verification)
- database (Relational PostgreSQL/Aurora cluster)
- redis (Distributed cache)
STRICTLY LABELED AS 'CONTROLLED CUSTOMER TEST ENVIRONMENT'.
"""

import time
import uuid
import random
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent, TelemetrySourceMode
from backend.app.monitoring.collector import collector
from backend.app.api.ingestion_gateway import ingestion_tracker
from backend.app.storage.telemetry_store import telemetry_store
from backend.app.api.websocket import ws_manager


class CustomerTestRunner:
    """Orchestrates the Controlled Customer Test Environment (Customer A)."""

    SERVICES = ["gateway", "orders", "payments", "auth", "database", "redis"]
    DEFAULT_TENANT = "tenant-alpha"

    def __init__(self, tenant_id: str = "tenant-alpha"):
        self.tenant_id = tenant_id
        self.is_running = False
        self.failure_injected = False
        self.failure_type: Optional[str] = None
        self._runner_task: Optional[asyncio.Task] = None

    def generate_normal_transaction_flow(self) -> List[UnifiedTelemetryEvent]:
        """Simulates end-to-end distributed trace across gateway -> orders/payments -> database/redis."""
        now_iso = datetime.now(timezone.utc).isoformat()
        trace_id = f"trc-{uuid.uuid4().hex}"
        gateway_span = f"spn-{uuid.uuid4().hex[:16]}"
        order_span = f"spn-{uuid.uuid4().hex[:16]}"
        db_span = f"spn-{uuid.uuid4().hex[:16]}"
        user_id = f"usr_{random.randint(1000, 9999)}"

        events = []

        # 1. Gateway Entry Span & Metric
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="trace",
            service_name="gateway",
            trace_id=trace_id,
            span_id=gateway_span,
            http_method="POST",
            http_route="/api/v1/checkout",
            http_status=200,
            latency=round(random.uniform(25.0, 45.0), 2),
            timestamp=now_iso,
            severity="INFO",
            environment="production-customer-a",
            attributes={"service.name": "gateway", "customer.env": "CONTROLLED_CUSTOMER_TEST"}
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="gateway",
            metric_name="http_requests_total",
            metric_value=float(random.randint(120, 240)),
            timestamp=now_iso,
            severity="INFO",
            environment="production-customer-a"
        ))

        # 2. Orders Service Child Span & Metric
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="trace",
            service_name="orders",
            trace_id=trace_id,
            span_id=order_span,
            parent_span_id=gateway_span,
            http_method="POST",
            http_route="/orders/create",
            http_status=200,
            latency=round(random.uniform(15.0, 25.0), 2),
            timestamp=now_iso,
            severity="INFO",
            environment="production-customer-a",
            attributes={"service.name": "orders", "order.user_id": user_id}
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="log",
            service_name="orders",
            message=f"Order created successfully for customer {user_id}",
            trace_id=trace_id,
            span_id=order_span,
            severity="INFO",
            timestamp=now_iso,
            environment="production-customer-a"
        ))

        # 3. Database Service Span & Pool Metric (Healthy: 12-18 connections)
        db_conns = random.randint(12, 18)
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="trace",
            service_name="database",
            trace_id=trace_id,
            span_id=db_span,
            parent_span_id=order_span,
            latency=round(random.uniform(4.0, 9.0), 2),
            http_status=200,
            timestamp=now_iso,
            severity="INFO",
            environment="production-customer-a",
            attributes={"service.name": "database", "db.statement": "INSERT INTO orders ..."}
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="database",
            metric_name="active_connections",
            metric_value=float(db_conns),
            timestamp=now_iso,
            severity="INFO",
            environment="production-customer-a"
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="database",
            metric_name="latency_p95_ms",
            metric_value=round(random.uniform(8.0, 14.0), 2),
            timestamp=now_iso,
            severity="INFO",
            environment="production-customer-a"
        ))

        return events

    def generate_failure_cascade(self) -> List[UnifiedTelemetryEvent]:
        """
        Simulates: Database Connection Exhaustion Failure.
        The failure originates at the database level and causes upstream timeouts on orders/payments.
        Follows the strict chain:
        FAILURE -> SERVICE BEHAVIOR CHANGES -> TELEMETRY CHANGES -> ML ANOMALY -> CORRELATION -> INCIDENT -> RCA.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        trace_id = f"trc-fail-{uuid.uuid4().hex}"
        gateway_span = f"spn-{uuid.uuid4().hex[:16]}"
        order_span = f"spn-{uuid.uuid4().hex[:16]}"
        db_span = f"spn-{uuid.uuid4().hex[:16]}"

        events = []

        # 1. ROOT CAUSE ONSET: Database pool exhausted (100/100 active connections)
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="database",
            metric_name="active_connections",
            metric_value=100.0,
            timestamp=now_iso,
            severity="CRITICAL",
            environment="production-customer-a",
            attributes={"service.name": "database", "pool.max": 100, "pool.active": 100}
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="database",
            metric_name="latency_p95_ms",
            metric_value=1240.0,  # Baseline was ~12ms
            timestamp=now_iso,
            severity="CRITICAL",
            environment="production-customer-a"
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="log",
            service_name="database",
            message="CRITICAL: Connection pool exhausted [100/100]. Remaining requests queued. Timeout waiting for connection.",
            severity="CRITICAL",
            timestamp=now_iso,
            trace_id=trace_id,
            span_id=db_span,
            environment="production-customer-a"
        ))

        # 2. CASCADE EFFECT 1: Orders service fails waiting on database
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="orders",
            metric_name="error_rate",
            metric_value=0.78,
            timestamp=now_iso,
            severity="ERROR",
            environment="production-customer-a"
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="trace",
            service_name="orders",
            trace_id=trace_id,
            span_id=order_span,
            parent_span_id=gateway_span,
            http_method="POST",
            http_route="/orders/create",
            http_status=504,
            latency=1520.0,
            timestamp=now_iso,
            severity="ERROR",
            environment="production-customer-a",
            message="Database dependency timed out after 1500ms"
        ))

        # 3. CASCADE EFFECT 2: Gateway returns HTTP 502 Bad Gateway to clients
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="trace",
            service_name="gateway",
            trace_id=trace_id,
            span_id=gateway_span,
            http_method="POST",
            http_route="/api/v1/checkout",
            http_status=502,
            latency=1580.0,
            timestamp=now_iso,
            severity="ERROR",
            environment="production-customer-a",
            message="Upstream dependency orders timed out"
        ))
        events.append(UnifiedTelemetryEvent(
            tenant_id=self.tenant_id,
            source_mode=TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value,
            event_type="metric",
            service_name="gateway",
            metric_name="error_rate",
            metric_value=0.65,
            timestamp=now_iso,
            severity="ERROR",
            environment="production-customer-a"
        ))

        return events

    async def emit_batch(self, events: List[UnifiedTelemetryEvent]):
        """Delivers events directly into the central platform pipeline."""
        now_dt = datetime.now(timezone.utc)
        await telemetry_store.write_events(events)

        for ev in events:
            collector.ingest_unified_event(ev)
            ingestion_tracker.add_service(self.tenant_id, ev.service_name)
            await ws_manager.broadcast_tenant_event(self.tenant_id, ev.to_log_dict())

        # Update stats
        ingestion_tracker.record_ingest(self.tenant_id, len(events), sum(len(str(e.message)) for e in events))

    def inject_database_exhaustion(self):
        """Triggers controlled failure injection."""
        self.failure_injected = True
        self.failure_type = "DATABASE_CONNECTION_EXHAUSTION"

    def heal_failure(self):
        """Resolves controlled failure injection."""
        self.failure_injected = False
        self.failure_type = None


customer_test_runner = CustomerTestRunner(tenant_id="tenant-alpha")
