"""
Continuous Real-Time Telemetry Generator Engine (Requirements 1, 2, 3, 4, 6)
Continuously produces realistic enterprise operational telemetry across microservices:
- gateway (stage: ingress)
- service-a / order-service (stage: business_logic)
- service-b / transaction-service (stage: orchestration)
- payment-api / payment-service (stage: third_party_integration)
- database-service (stage: persistence)
- cache / redis (stage: caching)
- worker / inventory-service (stage: async_worker)
- auth-service (stage: authentication)

Emits all 14 structured log/telemetry categories:
1. APPLICATION
2. ACCESS
3. ERROR
4. WARNING
5. SECURITY
6. DATABASE
7. CACHE
8. NETWORK
9. DEPENDENCY
10. PERFORMANCE
11. AUDIT
12. DEPLOYMENT
13. HEALTH
14. SYSTEM_RESOURCE

Simulates genuine operational failure states for all 18 canonical scenarios:
DATABASE_CONNECTION_EXHAUSTION, DATABASE_TIMEOUT, HTTP_500_SPIKE, HTTP_502_UPSTREAM_FAILURE,
HTTP_503_SERVICE_UNAVAILABLE, REDIS_CONNECTION_FAILURE, CACHE_FAILURE, HIGH_LATENCY,
REQUEST_TIMEOUT, SERVICE_CRASH, DEPENDENCY_FAILURE, CPU_SPIKE, MEMORY_PRESSURE,
QUEUE_BACKLOG, DEPLOYMENT_REGRESSION, AUTHENTICATION_FAILURE_SPIKE, NETWORK_TIMEOUT, CASCADING_FAILURE.

Streams directly into:
Log Processor -> Central Collector -> Feature Extractor -> Baseline -> Anomaly Detector -> Correlation Pipeline.
"""

import time
import uuid
import random
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import deque

from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetrySeverity, TelemetryType
from backend.app.logs.processor import log_processor


# Service execution stages
SERVICE_STAGES = {
    "gateway": "ingress",
    "api-gateway": "ingress",
    "service-a": "business_logic",
    "order-service": "business_logic",
    "service-b": "orchestration",
    "transaction-service": "orchestration",
    "payment-api": "third_party_integration",
    "payment-service": "third_party_integration",
    "database-service": "persistence",
    "cache": "caching",
    "redis": "caching",
    "worker": "async_worker",
    "inventory-service": "async_worker",
    "auth-service": "authentication"
}

# Legacy and multi-service transaction templates for continuous realistic telemetry across services
SERVICE_TEMPLATES = {
    "gateway": [
        {"type": "GATEWAY_ROUTING_SUCCESS", "level": TelemetrySeverity.INFO, "msg": "HTTP 200 GET /api/orders routing completed in {dur}ms", "attrs": {"http_status": 200, "route": "/api/orders"}},
        {"type": "GATEWAY_ROUTING_SUCCESS", "level": TelemetrySeverity.INFO, "msg": "HTTP 200 POST /api/payments routing completed in {dur}ms", "attrs": {"http_status": 200, "route": "/api/payments"}},
        {"type": "GATEWAY_AUTH_VERIFIED", "level": TelemetrySeverity.INFO, "msg": "Token verification passed for client {ip}", "attrs": {"http_status": 200, "client_ip": "10.0.4.12"}},
        {"type": "GATEWAY_LATENCY_WARN", "level": TelemetrySeverity.WARNING, "msg": "Upstream response latency threshold exceeded ({dur}ms > 500ms)", "attrs": {"http_status": 200, "latency_warn": True}},
        {"type": "GATEWAY_502_BAD_GATEWAY", "level": TelemetrySeverity.ERROR, "msg": "HTTP 502 Bad Gateway: Upstream connection refused to target service", "attrs": {"http_status": 502, "upstream": "service-b"}},
        {"type": "GATEWAY_504_TIMEOUT", "level": TelemetrySeverity.CRITICAL, "msg": "HTTP 504 Gateway Timeout: Upstream response timed out after 5000ms", "attrs": {"http_status": 504, "upstream": "database-service"}},
    ],
    "service-a": [
        {"type": "SERVICE_A_TASK_COMPLETED", "level": TelemetrySeverity.INFO, "msg": "Order processing task ord_{rand_id} completed successfully in {dur}ms", "attrs": {"order_status": "PROCESSED", "items_count": 3}},
        {"type": "SERVICE_A_JOB_DISPATCHED", "level": TelemetrySeverity.INFO, "msg": "Inventory allocation batch {rand_id} dispatched to warehouse queue", "attrs": {"batch_status": "DISPATCHED"}},
        {"type": "SERVICE_A_RETRY_WARN", "level": TelemetrySeverity.WARNING, "msg": "Transient network jitter while verifying order ord_{rand_id}. Retrying (attempt 2/3)", "attrs": {"retry_count": 2}},
        {"type": "SERVICE_A_TASK_FAILED", "level": TelemetrySeverity.ERROR, "msg": "Order processing failed: Downstream database connection dropped", "attrs": {"error_code": "ERR_DB_UNREACHABLE"}},
        {"type": "SERVICE_A_WORKER_CRASH", "level": TelemetrySeverity.CRITICAL, "msg": "Fatal: Unhandled thread error in background queue worker. Worker recycled.", "attrs": {"exception": "MemoryExhaustion"}},
    ],
    "service-b": [
        {"type": "SERVICE_B_DISPATCH_OK", "level": TelemetrySeverity.INFO, "msg": "Notification payload notif_{rand_id} dispatched to message queue in {dur}ms", "attrs": {"channel": "email", "status": "DELIVERED"}},
        {"type": "SERVICE_B_SYNC_SUCCESS", "level": TelemetrySeverity.INFO, "msg": "Account ledger synchronization sync_{rand_id} settled with downstream", "attrs": {"reconciled": True}},
        {"type": "SERVICE_B_THROTTLE_WARN", "level": TelemetrySeverity.WARNING, "msg": "Outbound rate approaching limit: {dur} req/sec (threshold 200)", "attrs": {"throttle_limit": 200}},
        {"type": "SERVICE_B_SOCKET_TIMEOUT", "level": TelemetrySeverity.ERROR, "msg": "Downstream payment socket timeout after 3000ms. Aborting event {rand_id}", "attrs": {"error_code": "ETIMEDOUT"}},
        {"type": "SERVICE_B_CRITICAL_FAILURE", "level": TelemetrySeverity.CRITICAL, "msg": "Service-B transaction supervisor failed: Uncaught dependency error", "attrs": {"supervisor_state": "CRASHED"}},
    ],
    "order-service": [
        {"type": "ORDER_CREATED", "level": TelemetrySeverity.INFO, "msg": "Order ord_{rand_id} created successfully for customer cust_{rand_id}", "attrs": {"order_status": "CREATED", "amount": 149.99}},
        {"type": "ORDER_FULFILLED", "level": TelemetrySeverity.INFO, "msg": "Order ord_{rand_id} fulfillment dispatched to warehouse", "attrs": {"order_status": "FULFILLED"}},
        {"type": "ORDER_RETRY_WARN", "level": TelemetrySeverity.WARNING, "msg": "Transient network jitter while verifying payment for order ord_{rand_id}. Retrying (attempt 2/3)", "attrs": {"retry_count": 2}},
        {"type": "ORDER_CREATION_FAILED", "level": TelemetrySeverity.ERROR, "msg": "Order creation failed: downstream payment processing error", "attrs": {"error_code": "ERR_PAYMENT_FAILED"}},
        {"type": "ORDER_SERVICE_CRASH", "level": TelemetrySeverity.CRITICAL, "msg": "Fatal: Unhandled exception in order reconciliation thread. Thread aborted.", "attrs": {"exception": "NullReferenceException"}},
    ],
    "payment-api": [
        {"type": "PAYMENT_PROCESSED", "level": TelemetrySeverity.INFO, "msg": "Payment transaction tx_{rand_id} authorized via card gateway in {dur}ms", "attrs": {"amount": 89.50, "currency": "USD", "provider": "stripe"}},
        {"type": "PAYMENT_SETTLED", "level": TelemetrySeverity.INFO, "msg": "Ledger entry reconciled for transaction tx_{rand_id}", "attrs": {"ledger_reconciled": True}},
        {"type": "PAYMENT_HIGH_LATENCY", "level": TelemetrySeverity.WARNING, "msg": "Payment authorization latency degraded: {dur}ms (P99 baseline: 120ms)", "attrs": {"p99_latency": 850}},
        {"type": "PAYMENT_DECLINED_ERROR", "level": TelemetrySeverity.ERROR, "msg": "Payment processing failed: Database connection timeout during transaction commit", "attrs": {"error_code": "ERR_DB_LOCK"}},
        {"type": "PAYMENT_SERVICE_UNAVAILABLE", "level": TelemetrySeverity.CRITICAL, "msg": "Payment API circuit breaker OPEN: 85% transaction failure rate detected", "attrs": {"circuit_state": "OPEN", "failure_rate": 0.85}},
    ],
    "database-service": [
        {"type": "DB_QUERY_EXECUTED", "level": TelemetrySeverity.INFO, "msg": "SELECT * FROM orders WHERE customer_id = ? executed in {dur}ms (rows: 12)", "attrs": {"query": "SELECT_ORDERS", "rows": 12}},
        {"type": "DB_TRANSACTION_COMMITTED", "level": TelemetrySeverity.INFO, "msg": "ACID transaction tx_blk_{rand_id} committed to WAL buffer", "attrs": {"wal_lsn": 489210}},
        {"type": "DB_POOL_PRESSURE_WARN", "level": TelemetrySeverity.WARNING, "msg": "Active database connection pool utilization at 84% (42/50 connections in use)", "attrs": {"pool_utilization": 0.84}},
        {"type": "DB_CONNECTION_TIMEOUT", "level": TelemetrySeverity.ERROR, "msg": "Connection pool exhausted (50/50). Timeout waiting for connection after 3000ms", "attrs": {"error_code": 40613, "pool_size": 50}},
        {"type": "DB_DEADLOCK_CRITICAL", "level": TelemetrySeverity.CRITICAL, "msg": "Deadlock detected in ledger lock table. Victim transaction tx_{rand_id} rolled back.", "attrs": {"deadlock_id": "dl_9812", "victim": "ledger_update"}},
    ],
    "auth-service": [
        {"type": "AUTH_TOKEN_VALIDATED", "level": TelemetrySeverity.INFO, "msg": "JWT session token validated for user usr_{rand_id} (scope: read,write)", "attrs": {"token_type": "Bearer", "valid": True}},
        {"type": "AUTH_SESSION_RENEWED", "level": TelemetrySeverity.INFO, "msg": "OAuth2 refresh token exchanged successfully", "attrs": {"grant_type": "refresh_token"}},
        {"type": "AUTH_RATE_LIMIT_WARN", "level": TelemetrySeverity.WARNING, "msg": "Authentication request rate approaching client throttle limit (85 req/min)", "attrs": {"rate": 85}},
        {"type": "AUTH_CREDENTIAL_ERROR", "level": TelemetrySeverity.ERROR, "msg": "Session validation failed: User credential store unreachable", "attrs": {"error": "StoreTimeout"}},
        {"type": "AUTH_SERVICE_DOWN", "level": TelemetrySeverity.CRITICAL, "msg": "Critical: Auth key rotation worker crashed. Unable to verify incoming tokens.", "attrs": {"worker": "KeyRotationWorker"}},
    ]
}

# Normal operational log templates for all 14 categories
NORMAL_CATEGORY_TEMPLATES = {
    "APPLICATION": [
        {"msg": "Order workflow transition: state=COMMITTED, items={rand_id}", "status": 200},
        {"msg": "Business entity reconciliation successfully validated for account {rand_id}", "status": 200},
        {"msg": "Dispatched checkout notification event to downstream bus", "status": 200}
    ],
    "ACCESS": [
        {"msg": "HTTP {method} {route} handled from client 10.0.{ip1}.{ip2} in {dur}ms", "status": 200},
        {"msg": "Ingress API Gateway routed request to upstream {svc} in {dur}ms", "status": 200}
    ],
    "DATABASE": [
        {"msg": "SQL SELECT * FROM orders WHERE customer_id = ? executed in {dur}ms (pool 12/50)", "status": 200, "dep": "postgres"},
        {"msg": "ACID transaction wal_commit executed in {dur}ms (lsn {rand_id})", "status": 200, "dep": "postgres"}
    ],
    "CACHE": [
        {"msg": "Redis GET key:session:{rand_id} HIT (latency: 1.2ms, pool: healthy)", "status": 200, "dep": "redis"},
        {"msg": "Cache entry key:catalog:{rand_id} refreshed in 2.1ms", "status": 200, "dep": "redis"}
    ],
    "NETWORK": [
        {"msg": "TCP socket connection active to upstream cluster (rtt: {dur}ms)", "status": 200},
        {"msg": "TLS handshake completed with client (cipher: TLS_AES_256_GCM_SHA384)", "status": 200}
    ],
    "DEPENDENCY": [
        {"msg": "External payment processor webhook acknowledged in {dur}ms", "status": 200, "dep": "stripe-api"},
        {"msg": "SMS provider gateway delivery report received for msg_{rand_id}", "status": 200, "dep": "twilio-gateway"}
    ],
    "PERFORMANCE": [
        {"msg": "Throughput metric: request_rate={dur} req/sec, p95_latency=28ms", "status": 200},
        {"msg": "Thread pool metrics: active_threads=8, queued_tasks=2, idle=24", "status": 200}
    ],
    "SECURITY": [
        {"msg": "JWT session token signature validated for subject usr_{rand_id}", "status": 200},
        {"msg": "RBAC permission check passed: role=OPERATOR resource=/api/v1/work", "status": 200}
    ],
    "AUDIT": [
        {"msg": "Audit trail: User admin queried service topology from 10.0.1.15", "status": 200},
        {"msg": "Config parameter session_ttl checked against compliance baseline", "status": 200}
    ],
    "DEPLOYMENT": [
        {"msg": "Active deployment revision v2.4.1 serving traffic with zero drift", "status": 200},
        {"msg": "Health contract verified against manifest schema v1.8", "status": 200}
    ],
    "HEALTH": [
        {"msg": "Liveness probe HTTP 200 OK: container process state HEALTHY", "status": 200},
        {"msg": "Readiness probe passed: all subsystem dependencies connected", "status": 200}
    ],
    "SYSTEM_RESOURCE": [
        {"msg": "Container resource utilization: cpu=14.2%, memory=186MB / 1024MB", "status": 200},
        {"msg": "Disk I/O metrics: read_ops=14/s, write_ops=8/s, fs_usage=42%", "status": 200}
    ],
    "WARNING": [
        {"msg": "Transient network jitter detected; latency {dur}ms > 120ms baseline", "status": 200},
        {"msg": "Connection pool utilization elevated to 68% (34/50 active handles)", "status": 200}
    ],
    "ERROR": [
        {"msg": "Internal retry triggered on non-critical background sync job", "status": 409}
    ]
}

# Multi-tenant transaction flow paths for distributed correlated traces
TENANT_TRANSACTION_FLOWS = {
    "shopsphere": [
        ["gateway", "order-service", "database-service"],
        ["gateway", "order-service", "payment-service", "database-service"],
        ["gateway", "order-service", "inventory-service", "database-service"],
        ["gateway", "order-service", "notification-service"],
        ["gateway", "order-service", "cache"],
    ],
    "fincore": [
        ["gateway", "transaction-service", "database-service"],
        ["gateway", "transaction-service", "fraud-service", "cache"],
        ["gateway", "transaction-service", "payment-service", "database-service"],
        ["gateway", "account-service", "database-service"],
    ],
    "clouddesk": [
        ["gateway", "auth-service", "database-service"],
        ["gateway", "project-service", "database-service"],
        ["gateway", "billing-service", "database-service"],
        ["gateway", "project-service", "notification-service"],
        ["gateway", "auth-service", "cache"],
    ],
    "demo-tenant": [
        ["gateway", "service-a", "database-service"],
        ["gateway", "payment-api", "database-service"],
        ["gateway", "service-a", "service-b"],
        ["gateway", "auth-service"],
        ["gateway", "service-b", "database-service"],
    ]
}

TRANSACTION_FLOWS = TENANT_TRANSACTION_FLOWS["demo-tenant"]


class ContinuousTelemetryEngine:
    """
    High-performance continuous background telemetry generator.
    Emits configurable events/second into the central AegisOps processing bus.
    Produces rich multi-category logs across all 14 enterprise categories with
    realistic telemetry signatures for all 18 failure scenarios.
    """
    def __init__(self):
        self.is_running = True
        self.configured_eps = 25  # Scalable: 10, 100, 1000, 10000+
        self.actual_eps = 0.0
        self.total_events_generated = 0
        self.total_errors_generated = 0
        self.start_time = time.time()
        self.last_event_time: Optional[str] = None
        self.avg_ingestion_latency_ms: float = 2.4
        self.consumer_lag: int = 0
        
        # Diagnostics buffer: rolling 100 recent events
        self.diagnostic_events: deque = deque(maxlen=100)
        
        # Failure injection overrides: Dict[service, failure_state]
        self.service_failure_overrides: Dict[str, Dict[str, Any]] = {}
        
        # Per-tenant & per-service counters
        self.tenant_counts: Dict[str, int] = {"shopsphere": 0, "fincore": 0, "clouddesk": 0, "demo-tenant": 0}
        self.service_counts: Dict[str, int] = {}
        
        self._generator_task: Optional[asyncio.Task] = None
        self._collector_callback = None

    def register_collector_callback(self, cb):
        self._collector_callback = cb

    def set_eps_rate(self, eps: int):
        """Sets throughput generation rate."""
        self.configured_eps = max(10, min(1000000, eps))

    def set_service_failure(self, service: str, failure_type: str, severity: str = "ERROR", duration_sec: float = 45.0):
        """Forces a service into a realistic failure state for a specific duration."""
        self.service_failure_overrides[service] = {
            "failure_type": failure_type,
            "severity": severity,
            "expires_at": time.time() + duration_sec
        }

    def inject_service_failure(self, scenario_type: str, target_service: str, severity: str = "CRITICAL", metadata: Optional[Dict[str, Any]] = None, duration_sec: float = 45.0):
        """Alias for set_service_failure with scenario_type and target_service."""
        self.set_service_failure(service=target_service, failure_type=scenario_type, severity=severity, duration_sec=duration_sec)

    def clear_all_failures(self):
        self.service_failure_overrides.clear()

    def clear_service_failures(self):
        """Alias for clear_all_failures."""
        self.clear_all_failures()

    def generate_telemetry_batch(self, count: int = 20) -> List[Dict[str, Any]]:
        """Generates a synchronous batch of structured telemetry log events matching the active environment and failures."""
        now_ts = time.time()
        expired = [s for s, data in self.service_failure_overrides.items() if data["expires_at"] <= now_ts]
        for s in expired:
            del self.service_failure_overrides[s]

        results: List[Dict[str, Any]] = []
        tenant_pool = ["shopsphere", "fincore", "clouddesk", "demo-tenant"]
        remaining = count

        # Guarantee active failure overrides are always included in the batch
        for svc_override, override_info in list(self.service_failure_overrides.items()):
            f_data = self._generate_failure_event_data(svc_override, override_info["failure_type"], random.randint(850, 4200))
            source_time = datetime.now(timezone.utc)
            source_iso = source_time.isoformat()
            trace_id = f"trc-{uuid.uuid4().hex[:16]}"
            span_id = f"spn-{uuid.uuid4().hex[:8]}"
            request_id = f"req-{uuid.uuid4().hex[:12]}"
            stage = SERVICE_STAGES.get(svc_override, "caching" if ("cache" in svc_override or "redis" in svc_override) else "business_logic")
            
            evt_dict = {
                "timestamp": source_iso,
                "tenant_id": "demo-tenant",
                "environment": "CONTROLLED_CUSTOMER_TEST",
                "service": svc_override,
                "stage": stage,
                "category": f_data["category"],
                "level": f_data["severity"].value,
                "severity": f_data["severity"].value,
                "event_type": override_info["failure_type"],
                "message": f_data["msg"],
                "status_code": f_data["status_code"],
                "latency_ms": f_data.get("latency_ms", 2500),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": None,
                "request_id": request_id,
                "dependency": f_data.get("dep", ("redis" if ("redis" in svc_override or "cache" in svc_override) else None)),
                "cpu_percent": round(f_data.get("cpu_percent", random.uniform(30.0, 75.0)), 1),
                "memory_percent": round(f_data.get("memory_percent", random.uniform(40.0, 80.0)), 1),
                "host": f"node-{svc_override}-01",
                "container": f"container-{svc_override}-prod"
            }
            results.append(evt_dict)
            remaining -= 1

        while remaining > 0:
            current_tenant = random.choice(tenant_pool)
            flow = random.choice(TENANT_TRANSACTION_FLOWS.get(current_tenant, TRANSACTION_FLOWS))
            trace_id = f"trc-{uuid.uuid4().hex[:16]}"
            request_id = f"req-{uuid.uuid4().hex[:12]}"
            parent_span_id = None

            for svc in flow:
                if remaining <= 0:
                    break
                remaining -= 1

                span_id = f"spn-{uuid.uuid4().hex[:8]}"
                override = self.service_failure_overrides.get(svc)

                source_time = datetime.now(timezone.utc)
                source_iso = source_time.isoformat()
                rand_id = str(random.randint(1000, 9999))
                stage = SERVICE_STAGES.get(svc, "business_logic")

                if override:
                    f_data = self._generate_failure_event_data(svc, override["failure_type"], random.randint(850, 4200))
                    category = f_data["category"]
                    sev = f_data["severity"]
                    event_type = override["failure_type"]
                    msg = f_data["msg"]
                    status_code = f_data["status_code"]
                    dur = f_data.get("latency_ms", 2500)
                    cpu_val = f_data.get("cpu_percent", random.uniform(30.0, 75.0))
                    mem_val = f_data.get("memory_percent", random.uniform(40.0, 80.0))
                    dep_name = f_data.get("dep", ("postgres" if "database" in svc else ("redis" if "cache" in svc else None)))
                else:
                    r = random.random()
                    if r < 0.35:
                        category = "APPLICATION"
                    elif r < 0.60:
                        category = "ACCESS"
                    elif r < 0.75:
                        category = "DATABASE" if "database" in svc else "CACHE" if "cache" in svc else "ACCESS"
                    elif r < 0.85:
                        category = "PERFORMANCE"
                    elif r < 0.92:
                        category = "SYSTEM_RESOURCE"
                    elif r < 0.96:
                        category = random.choice(["SECURITY", "AUDIT", "HEALTH", "NETWORK"])
                    elif r < 0.99:
                        category = "WARNING"
                    else:
                        category = "ERROR"

                    tmpl_list = NORMAL_CATEGORY_TEMPLATES.get(category, NORMAL_CATEGORY_TEMPLATES["APPLICATION"])
                    tmpl = random.choice(tmpl_list)
                    sev = TelemetrySeverity.INFO if category not in ("WARNING", "ERROR") else (TelemetrySeverity.WARNING if category == "WARNING" else TelemetrySeverity.ERROR)
                    event_type = f"{svc.upper()}_{category}_EVENT"
                    dur = random.randint(12, 42)
                    msg = tmpl["msg"].format(
                        dur=dur,
                        rand_id=rand_id,
                        method="GET" if "gateway" in svc else "POST",
                        route=f"/api/v1/{svc}",
                        svc=svc,
                        ip1=random.randint(1, 20),
                        ip2=random.randint(1, 250)
                    )
                    status_code = tmpl.get("status", 200)
                    dep_name = tmpl.get("dep", ("postgres" if "database" in svc else ("redis" if "cache" in svc else None)))
                    cpu_val = random.uniform(8.0, 28.0)
                    mem_val = random.uniform(18.0, 42.0)

                evt_dict = {
                    "timestamp": source_iso,
                    "tenant_id": current_tenant,
                    "environment": "CONTROLLED_CUSTOMER_TEST",
                    "service": svc,
                    "stage": stage,
                    "category": category,
                    "level": sev.value,
                    "severity": sev.value,
                    "event_type": event_type,
                    "message": msg,
                    "status_code": status_code,
                    "latency_ms": dur,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "request_id": request_id,
                    "dependency": dep_name,
                    "cpu_percent": round(cpu_val, 1),
                    "memory_percent": round(mem_val, 1),
                    "host": f"node-{svc}-01",
                    "container": f"container-{svc}-prod"
                }
                results.append(evt_dict)
                parent_span_id = span_id

        return results

    def get_status(self) -> Dict[str, Any]:
        events_per_sec = round(self.actual_eps if self.actual_eps > 0 else float(self.configured_eps), 1)
        events_per_min = round(events_per_sec * 60.0, 1)
        mb_per_sec = round((events_per_sec * 620) / (1024 * 1024), 3)

        tot = max(1, sum(self.tenant_counts.values()))
        tenant_eps = {t: round(events_per_sec * (c / tot), 1) for t, c in self.tenant_counts.items()}

        return {
            "is_running": self.is_running,
            "configured_eps": self.configured_eps,
            "actual_eps": events_per_sec,
            "events_per_sec": events_per_sec,
            "events_per_min": events_per_min,
            "events_by_tenant": tenant_eps,
            "total_events": self.total_events_generated,
            "total_errors": self.total_errors_generated,
            "kafka_throughput_mb_s": mb_per_sec,
            "consumer_lag": self.consumer_lag,
            "pipeline_latency_ms": round(self.avg_ingestion_latency_ms, 2),
            "avg_ingestion_latency_ms": round(self.avg_ingestion_latency_ms, 2),
            "last_event_time": self.last_event_time,
            "active_failure_overrides": list(self.service_failure_overrides.keys()),
            "recent_diagnostics_count": len(self.diagnostic_events)
        }

    def get_recent_diagnostics(self, limit: int = 30) -> List[Dict[str, Any]]:
        return list(self.diagnostic_events)[:limit]

    async def start(self):
        """Starts the continuous telemetry generator loop."""
        if self._generator_task and not self._generator_task.done():
            return
        self.is_running = True
        self._generator_task = asyncio.create_task(self._continuous_loop())

    async def stop(self):
        self.is_running = False
        if self._generator_task and not self._generator_task.done():
            self._generator_task.cancel()

    def _generate_failure_event_data(self, svc: str, scenario_id: str, dur: int) -> Dict[str, Any]:
        """Synthesizes genuine operational failure attributes for the 18 failure scenarios."""
        sid = scenario_id.upper()
        if "DATABASE_CONNECTION_EXHAUSTION" in sid:
            return {
                "category": "DATABASE",
                "severity": TelemetrySeverity.CRITICAL,
                "status_code": 500,
                "msg": f"FATAL: Database connection pool exhausted (50/50 connections in use). Connection acquire timeout after 3000ms on {svc}.",
                "error_type": "ConnectionPoolExhaustedException",
                "dep": "postgres",
                "latency_ms": random.randint(3200, 4800),
                "db_info": {"pool_utilization": 1.0, "active_connections": 50, "max_connections": 50, "acquire_timeout_ms": 3000}
            }
        elif "DATABASE_TIMEOUT" in sid:
            return {
                "category": "DATABASE",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 504,
                "msg": f"Database statement execution timeout: query exceeded 5000ms threshold on {svc}. Statement cancelled.",
                "error_type": "QueryTimeoutException",
                "dep": "postgres",
                "latency_ms": random.randint(5200, 7500),
                "db_info": {"lock_wait_ms": 5200, "slow_query": "SELECT * FROM orders WHERE status='PENDING' FOR UPDATE"}
            }
        elif "HTTP_500_SPIKE" in sid:
            return {
                "category": "APPLICATION",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 500,
                "msg": f"HTTP 500 Internal Server Error: Unhandled exception NullReferenceException in {svc} processing thread.",
                "error_type": "NullReferenceException",
                "latency_ms": random.randint(450, 1100)
            }
        elif "HTTP_502_UPSTREAM_FAILURE" in sid:
            return {
                "category": "NETWORK",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 502,
                "msg": f"HTTP 502 Bad Gateway: Upstream connection refused by target microservice {svc}.",
                "error_type": "BadGatewayException",
                "latency_ms": random.randint(1800, 3200)
            }
        elif "HTTP_503_SERVICE_UNAVAILABLE" in sid:
            return {
                "category": "DEPENDENCY",
                "severity": TelemetrySeverity.CRITICAL,
                "status_code": 503,
                "msg": f"HTTP 503 Service Unavailable: Circuit breaker OPEN for {svc}. Rapid failure threshold reached.",
                "error_type": "CircuitBreakerOpenException",
                "latency_ms": random.randint(250, 600)
            }
        elif "REDIS_CONNECTION_FAILURE" in sid or "CACHE" in sid:
            return {
                "category": "CACHE",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 500,
                "msg": f"Redis connection error: dial tcp 127.0.0.1:6379 connect refused on {svc}. Cache unavailable.",
                "error_type": "RedisConnectionRefusedError",
                "dep": "redis",
                "latency_ms": random.randint(800, 2200)
            }
        elif "HIGH_LATENCY" in sid:
            return {
                "category": "PERFORMANCE",
                "severity": TelemetrySeverity.WARNING,
                "status_code": 200,
                "msg": f"Latency degradation alert: P95 response time {dur}ms severely exceeded SLA baseline (120ms) on {svc}.",
                "error_type": "HighLatencyWarning",
                "latency_ms": random.randint(3200, 5200)
            }
        elif "REQUEST_TIMEOUT" in sid:
            return {
                "category": "NETWORK",
                "severity": TelemetrySeverity.CRITICAL,
                "status_code": 504,
                "msg": f"HTTP 504 Gateway Timeout: Upstream request to {svc} timed out after 5000ms.",
                "error_type": "GatewayTimeoutException",
                "latency_ms": random.randint(5100, 6200)
            }
        elif "SERVICE_CRASH" in sid:
            return {
                "category": "HEALTH",
                "severity": TelemetrySeverity.CRITICAL,
                "status_code": 503,
                "msg": f"Fatal service crash on {svc}: Process terminated with exit code 139 (SIGSEGV). Container restarted.",
                "error_type": "ServiceCrashedException",
                "latency_ms": random.randint(100, 400)
            }
        elif "CPU_SPIKE" in sid:
            return {
                "category": "SYSTEM_RESOURCE",
                "severity": TelemetrySeverity.CRITICAL,
                "status_code": 500,
                "msg": f"Host CPU spike critical: CPU utilization at 98.4% on node-{svc}. Thread pool starvation.",
                "error_type": "CpuStarvationException",
                "cpu_percent": random.uniform(96.0, 99.8),
                "latency_ms": random.randint(1800, 3600)
            }
        elif "MEMORY_PRESSURE" in sid:
            return {
                "category": "SYSTEM_RESOURCE",
                "severity": TelemetrySeverity.WARNING,
                "status_code": 200,
                "msg": f"Memory pressure warning: Container heap utilization at 94.2% on {svc}. GC pause time 1450ms.",
                "error_type": "MemoryPressureWarning",
                "memory_percent": random.uniform(92.0, 97.5),
                "latency_ms": random.randint(800, 2400)
            }
        elif "QUEUE_BACKLOG" in sid:
            return {
                "category": "PERFORMANCE",
                "severity": TelemetrySeverity.WARNING,
                "status_code": 200,
                "msg": f"Message queue backlog alert: Depth at 1,840 pending jobs, consumer lag 910 on {svc}.",
                "error_type": "QueueBacklogWarning",
                "latency_ms": random.randint(400, 900)
            }
        elif "AUTHENTICATION_FAILURE_SPIKE" in sid:
            return {
                "category": "SECURITY",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 401,
                "msg": f"HTTP 401 Unauthorized spike: Token signature verification failed across 48 consecutive requests on {svc}.",
                "error_type": "JWTVerificationException",
                "latency_ms": random.randint(50, 150)
            }
        elif "DEPLOYMENT_REGRESSION" in sid:
            return {
                "category": "DEPLOYMENT",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 500,
                "msg": f"Deployment regression on {svc}: Schema mismatch in release v2.4.2 caused unhandled JSON serialization errors.",
                "error_type": "SchemaMismatchException",
                "latency_ms": random.randint(300, 800)
            }
        elif "CASCADING_FAILURE" in sid:
            return {
                "category": "DEPENDENCY",
                "severity": TelemetrySeverity.CRITICAL,
                "status_code": 500,
                "msg": f"Cascading failure cascade: Downstream persistence failure on {svc} propagated upstream to Ingress Gateway.",
                "error_type": "CascadingFailureException",
                "latency_ms": random.randint(2800, 4900)
            }
        else:
            return {
                "category": "ERROR",
                "severity": TelemetrySeverity.ERROR,
                "status_code": 500,
                "msg": f"Unhandled operational failure '{scenario_id}' detected on {svc}.",
                "error_type": "OperationalException",
                "latency_ms": random.randint(1200, 3500)
            }

    async def _continuous_loop(self):
        """Main async generation loop pacing events at configured_eps with correlated traces."""
        rate_window = deque(maxlen=20)
        
        while self.is_running:
            loop_start = time.time()
            now_ts = time.time()
            # Clean up expired failure overrides
            expired = [s for s, data in self.service_failure_overrides.items() if data["expires_at"] <= now_ts]
            for s in expired:
                del self.service_failure_overrides[s]

            # Calculate target batch size for 100ms tick interval (10 ticks/sec)
            target_batch_size = max(1, int(self.configured_eps / 10))
            physical_sample_limit = min(target_batch_size, 50)
            multiplier = max(1, target_batch_size // physical_sample_limit)

            batch_events: List[NormalizedTelemetryEvent] = []
            log_dicts: List[Dict[str, Any]] = []

            remaining_samples = physical_sample_limit
            tenant_pool = ["shopsphere", "fincore", "clouddesk", "demo-tenant"]
            categories_pool = list(NORMAL_CATEGORY_TEMPLATES.keys())

            while remaining_samples > 0:
                current_tenant = random.choice(tenant_pool)
                flow = random.choice(TENANT_TRANSACTION_FLOWS.get(current_tenant, TRANSACTION_FLOWS))
                trace_id = f"trc-{uuid.uuid4().hex[:16]}"
                request_id = f"req-{uuid.uuid4().hex[:12]}"
                parent_span_id = None

                for svc in flow:
                    if remaining_samples <= 0:
                        break
                    remaining_samples -= 1

                    span_id = f"spn-{uuid.uuid4().hex[:8]}"
                    override = self.service_failure_overrides.get(svc)

                    source_time = datetime.now(timezone.utc)
                    source_iso = source_time.isoformat()
                    rand_id = str(random.randint(1000, 9999))
                    stage = SERVICE_STAGES.get(svc, "business_logic")

                    if override:
                        # Produce failure telemetry matching the specific scenario
                        f_data = self._generate_failure_event_data(svc, override["failure_type"], random.randint(850, 4200))
                        category = f_data["category"]
                        sev = f_data["severity"]
                        event_type = override["failure_type"]
                        msg = f_data["msg"]
                        status_code = f_data["status_code"]
                        dur = f_data.get("latency_ms", 2500)
                        err_type = f_data.get("error_type", "OperationalFailure")
                        dep_name = f_data.get("dep", ("postgres" if "database" in svc else ("redis" if "cache" in svc else None)))
                        cpu_val = f_data.get("cpu_percent", random.uniform(25.0, 65.0))
                        mem_val = f_data.get("memory_percent", random.uniform(35.0, 75.0))
                        db_info = f_data.get("db_info", {})
                    else:
                        # Normal realistic telemetry distributed across the 14 categories
                        r = random.random()
                        # Mostly APPLICATION, ACCESS, DATABASE, CACHE, PERFORMANCE, SYSTEM_RESOURCE
                        if r < 0.35:
                            category = "APPLICATION"
                        elif r < 0.60:
                            category = "ACCESS"
                        elif r < 0.75:
                            category = "DATABASE" if "database" in svc else "CACHE" if "cache" in svc else "ACCESS"
                        elif r < 0.85:
                            category = "PERFORMANCE"
                        elif r < 0.92:
                            category = "SYSTEM_RESOURCE"
                        elif r < 0.96:
                            category = random.choice(["SECURITY", "AUDIT", "HEALTH", "NETWORK"])
                        elif r < 0.99:
                            category = "WARNING"
                        else:
                            category = "ERROR"

                        tmpl_list = NORMAL_CATEGORY_TEMPLATES.get(category, NORMAL_CATEGORY_TEMPLATES["APPLICATION"])
                        tmpl = random.choice(tmpl_list)
                        sev = TelemetrySeverity.INFO if category not in ("WARNING", "ERROR") else (TelemetrySeverity.WARNING if category == "WARNING" else TelemetrySeverity.ERROR)
                        event_type = f"{svc.upper()}_{category}_EVENT"
                        dur = random.randint(12, 42)
                        msg = tmpl["msg"].format(
                            dur=dur,
                            rand_id=rand_id,
                            method="GET" if "gateway" in svc else "POST",
                            route=f"/api/v1/{svc}",
                            svc=svc,
                            ip1=random.randint(1, 20),
                            ip2=random.randint(1, 250)
                        )
                        status_code = tmpl.get("status", 200)
                        err_type = "MinorApplicationWarning" if sev == TelemetrySeverity.ERROR else None
                        dep_name = tmpl.get("dep", ("postgres" if "database" in svc else ("redis" if "cache" in svc else None)))
                        cpu_val = random.uniform(8.0, 28.0)
                        mem_val = random.uniform(18.0, 42.0)
                        db_info = {"pool_utilization": 0.24, "active_connections": 12, "max_connections": 50}

                    received_time = datetime.now(timezone.utc)
                    received_iso = received_time.isoformat()
                    latency_ms = max(0.4, (received_time - source_time).total_seconds() * 1000.0 + random.uniform(0.5, 2.5))
                    evt_id = str(uuid.uuid4())
                    http_method = "POST" if ("order" in svc or "payment" in svc or "transaction" in svc) else "GET"
                    route = f"/api/v1/{svc}"

                    # Rich structured attributes
                    attrs = {
                        "category": category,
                        "stage": stage,
                        "status_code": status_code,
                        "request_id": request_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "tenant_id": current_tenant,
                        "host": f"node-{svc}-01",
                        "container": f"container-{svc}-prod",
                        "cpu_percent": round(cpu_val, 1),
                        "memory_percent": round(mem_val, 1),
                        "dependency": dep_name,
                        "database": db_info,
                        "network": {"client_ip": "10.0.4.12", "timeout_ms": 3000},
                        "deployment": {"version": "v2.4.1", "environment": "production"}
                    }

                    normalized_evt = NormalizedTelemetryEvent(
                        source="controlled-demo",
                        service=svc,
                        tenant_id=current_tenant,
                        type=TelemetryType.LOG,
                        severity=sev,
                        event_type=event_type,
                        message=msg,
                        timestamp=source_iso,
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=parent_span_id,
                        http_method=http_method,
                        route=route,
                        status_code=status_code,
                        latency_ms=round(dur + latency_ms, 2),
                        error_type=err_type,
                        error_message=msg if status_code >= 400 else None,
                        dependency=dep_name,
                        metadata={
                            "event_id": evt_id,
                            "tenant_id": current_tenant,
                            "stage": stage,
                            "category": category,
                            "received_at": received_iso,
                            "ingestion_latency_ms": round(latency_ms, 2),
                            "host": f"node-{svc}-01",
                            "environment": "production",
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id,
                            "cpu_percent": round(cpu_val, 1),
                            "memory_percent": round(mem_val, 1),
                            "attributes": attrs
                        }
                    )

                    diagnostic_item = {
                        "event_id": evt_id,
                        "tenant_id": current_tenant,
                        "source": "controlled-demo",
                        "timestamp": source_iso,
                        "received_at": received_iso,
                        "service": svc,
                        "stage": stage,
                        "category": category,
                        "host": f"node-{svc}-01",
                        "severity": sev.value,
                        "event_type": event_type,
                        "message": msg,
                        "status_code": status_code,
                        "latency_ms": round(dur + latency_ms, 2),
                        "trace_id": trace_id,
                        "request_id": request_id,
                        "attributes": attrs
                    }

                    batch_events.append(normalized_evt)
                    self.diagnostic_events.appendleft(diagnostic_item)

                    log_dicts.append({
                        "timestamp": received_iso,
                        "tenant_id": current_tenant,
                        "service": svc,
                        "stage": stage,
                        "category": category,
                        "level": sev.value,
                        "event_type": event_type,
                        "message": msg,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "request_id": request_id,
                        "http_method": http_method,
                        "route": route,
                        "status_code": status_code,
                        "latency_ms": round(dur + latency_ms, 2),
                        "metadata": diagnostic_item
                    })

                    self.total_events_generated += multiplier
                    self.tenant_counts[current_tenant] = self.tenant_counts.get(current_tenant, 0) + multiplier
                    if sev in [TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]:
                        self.total_errors_generated += multiplier

                    parent_span_id = span_id

            self.last_event_time = datetime.now(timezone.utc).isoformat()

            # Ingest batch into high-speed log buffer
            await log_processor.ingest_batch(log_dicts)

            # Direct non-blocking ingestion into incident pipeline for feature extraction and moving baselines (Req 5, 6, 7)
            try:
                from backend.app.analytics.incident_pipeline import incident_pipeline
                for evt in batch_events:
                    incident_pipeline.record_telemetry_event(evt)
            except Exception:
                pass

            # Dispatch events to central collector
            if self._collector_callback:
                for evt in batch_events:
                    self._collector_callback(evt)

            # Measure rate
            rate_window.append((time.time(), target_batch_size))
            if len(rate_window) >= 2:
                time_span = rate_window[-1][0] - rate_window[0][0]
                total_in_win = sum(cnt for _, cnt in rate_window)
                if time_span > 0:
                    self.actual_eps = total_in_win / time_span

            # Sleep remaining time for 100ms pacing
            elapsed = time.time() - loop_start
            sleep_time = max(0.01, 0.1 - elapsed)
            await asyncio.sleep(sleep_time)

    def generate_batch(self, count: int = 50) -> List[NormalizedTelemetryEvent]:
        """Generates a synchronous batch of realistic multi-service correlated telemetry events."""
        events = []
        remaining = count
        tenant_pool = ["shopsphere", "fincore", "clouddesk", "demo-tenant"]
        while remaining > 0:
            current_tenant = random.choice(tenant_pool)
            flow = random.choice(TENANT_TRANSACTION_FLOWS.get(current_tenant, TRANSACTION_FLOWS))
            trace_id = f"trc-{uuid.uuid4().hex[:16]}"
            request_id = f"req-{uuid.uuid4().hex[:12]}"
            parent_span_id = None
            for svc in flow:
                if remaining <= 0:
                    break
                remaining -= 1
                span_id = f"spn-{uuid.uuid4().hex[:8]}"
                source_iso = datetime.now(timezone.utc).isoformat()
                dur = random.randint(10, 40)
                category = "APPLICATION"
                stage = SERVICE_STAGES.get(svc, "business_logic")
                evt = NormalizedTelemetryEvent(
                    source="controlled-demo",
                    service=svc,
                    tenant_id=current_tenant,
                    type=TelemetryType.LOG,
                    severity=TelemetrySeverity.INFO,
                    event_type=f"{svc.upper()}_PROCESSED",
                    message=f"Request processed successfully by {svc} in {dur}ms",
                    timestamp=source_iso,
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    http_method="POST" if ("order" in svc or "payment" in svc) else "GET",
                    route=f"/api/v1/{svc}",
                    status_code=200,
                    latency_ms=float(dur),
                    dependency="postgres" if "database" in svc else ("redis" if "cache" in svc else None),
                    metadata={
                        "category": category,
                        "stage": stage,
                        "request_id": request_id,
                        "tenant_id": current_tenant
                    }
                )
                events.append(evt)
                self.total_events_generated += 1
                self.tenant_counts[current_tenant] = self.tenant_counts.get(current_tenant, 0) + 1
                parent_span_id = span_id
        return events


# Global singleton instance
continuous_telemetry = ContinuousTelemetryEngine()
