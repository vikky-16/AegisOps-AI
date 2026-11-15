"""
Enterprise Synthetic Telemetry Generator
Generates realistic, symptom-based distributed traces, logs, metrics, and domain signals
across 12 enterprise components (API Gateway, Auth, Users, Orders, Payments, Inventory, Notifications, DB, Redis, Kafka, Workers, Search).
Supports all 30 industry failure simulation cycles with symptom-driven cascades.
STRICT RULE: Generates observable symptoms and cascading failures, NEVER pre-labelling the root cause.
"""

import uuid
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity

ENTERPRISE_SERVICES = [
    {"name": "gateway", "host": "gw-node-01", "role": "API Gateway & Ingress", "default_latency": 8.0},
    {"name": "auth-service", "host": "auth-node-01", "role": "Authentication & Session Authority", "default_latency": 10.0},
    {"name": "user-service", "host": "user-svc-01", "role": "User Management Service", "default_latency": 14.0},
    {"name": "service-a", "host": "order-node-01", "role": "Order Processing Service", "default_latency": 18.0},
    {"name": "service-b", "host": "pay-api-01", "role": "Payment Platform API", "default_latency": 22.0},
    {"name": "payment-gateway", "host": "pay-gw-connector", "role": "Payment Gateway Adapter", "default_latency": 45.0},
    {"name": "inventory-service", "host": "inv-node-01", "role": "Inventory & Catalog Service", "default_latency": 15.0},
    {"name": "notification-service", "host": "notify-worker-01", "role": "Notification & Alert Service", "default_latency": 25.0},
    {"name": "database-service", "host": "db-primary-01", "role": "Distributed Persistence", "default_latency": 12.0},
    {"name": "data-mart-service", "host": "analytics-worker-01", "role": "Data Mart & ETL", "default_latency": 150.0},
    {"name": "redis-cache", "host": "redis-cluster-01", "role": "In-Memory Cache", "default_latency": 1.5},
    {"name": "kafka-broker", "host": "kafka-node-01", "role": "Event Bus & Streaming", "default_latency": 3.0}
]

# Aliases for backward compatibility with existing tests
SERVICES = ENTERPRISE_SERVICES

FAILURE_CYCLES = [
    {"id": "database_connection_exhaustion", "name": "Cycle 1: Database Connection Exhaustion", "primary_service": "database-service", "action": "RESET_CONNECTION_POOL"},
    {"id": "redis_latency_spike", "name": "Cycle 2: Redis Latency Spike", "primary_service": "redis-cache", "action": "CLEAR_CACHE"},
    {"id": "payment_service_error_burst", "name": "Cycle 3: Payment Service Error Burst", "primary_service": "service-b", "action": "RESET_CONNECTION_POOL"},
    {"id": "kafka_consumer_lag", "name": "Cycle 4: Kafka Consumer Lag", "primary_service": "kafka-broker", "action": "DRAIN_QUEUE"},
    {"id": "cpu_saturation", "name": "Cycle 5: CPU Saturation", "primary_service": "service-a", "action": "SCALE_WORKERS"},
    {"id": "memory_pressure", "name": "Cycle 6: Memory Pressure", "primary_service": "service-a", "action": "RESTART_SERVICE"},
    {"id": "api_gateway_timeout", "name": "Cycle 7: API Gateway Timeout", "primary_service": "gateway", "action": "ROTATE_CONNECTIONS"},
    {"id": "dependency_failure", "name": "Cycle 8: Dependency Failure", "primary_service": "payment-gateway", "action": "ROLLBACK_CONFIG"},
    {"id": "auth_failure_burst", "name": "Cycle 9: Authentication Failure Burst", "primary_service": "auth-service", "action": "RESET_CONNECTION_POOL"},
    {"id": "network_latency", "name": "Cycle 10: Network Latency", "primary_service": "gateway", "action": "ROTATE_CONNECTIONS"},
    {"id": "queue_backlog", "name": "Cycle 11: Queue Backlog", "primary_service": "service-a", "action": "DRAIN_QUEUE"},
    {"id": "config_regression", "name": "Cycle 12: Configuration Regression", "primary_service": "gateway", "action": "ROLLBACK_CONFIG"},
    {"id": "cert_expiry_simulation", "name": "Cycle 13: Certificate Expiry Simulation", "primary_service": "auth-service", "action": "ROTATE_CONNECTIONS"},
    {"id": "service_crash", "name": "Cycle 14: Service Crash", "primary_service": "service-b", "action": "RESTART_SERVICE"},
    {"id": "database_latency", "name": "Cycle 15: Database Latency", "primary_service": "database-service", "action": "RESET_CONNECTION_POOL"},
    {"id": "connection_pool_leak", "name": "Cycle 16: Connection Pool Leak", "primary_service": "database-service", "action": "RESET_CONNECTION_POOL"},
    {"id": "cache_stampede", "name": "Cycle 17: Cache Stampede", "primary_service": "redis-cache", "action": "CLEAR_CACHE"},
    {"id": "http_5xx_burst", "name": "Cycle 18: HTTP 5xx Burst", "primary_service": "service-b", "action": "RESTART_SERVICE"},
    {"id": "thread_pool_exhaustion", "name": "Cycle 19: Thread Pool Exhaustion", "primary_service": "service-a", "action": "SCALE_WORKERS"},
    {"id": "disk_pressure", "name": "Cycle 20: Disk Pressure", "primary_service": "database-service", "action": "ROTATE_AND_COMPRESS_LOGS"},
    {"id": "dns_failure_simulation", "name": "Cycle 21: DNS Failure Simulation", "primary_service": "gateway", "action": "ROTATE_CONNECTIONS"},
    {"id": "dependency_timeout", "name": "Cycle 22: Dependency Timeout", "primary_service": "payment-gateway", "action": "ROTATE_CONNECTIONS"},
    {"id": "bad_deployment", "name": "Cycle 23: Bad Deployment", "primary_service": "service-a", "action": "ROLLBACK_CONFIG"},
    {"id": "traffic_spike", "name": "Cycle 24: Traffic Spike", "primary_service": "gateway", "action": "SCALE_WORKERS"},
    {"id": "message_processing_failure", "name": "Cycle 25: Message Processing Failure", "primary_service": "kafka-broker", "action": "DRAIN_QUEUE"},
    {"id": "api_rate_limit_saturation", "name": "Cycle 26: API Rate Limit Saturation", "primary_service": "gateway", "action": "SCALE_WORKERS"},
    {"id": "auth_token_failure", "name": "Cycle 27: Authentication Token Failure", "primary_service": "auth-service", "action": "RESTART_SERVICE"},
    {"id": "service_dependency_loop", "name": "Cycle 28: Service Dependency Loop", "primary_service": "service-a", "action": "ROLLBACK_CONFIG"},
    {"id": "database_lock_contention", "name": "Cycle 29: Database Lock Contention", "primary_service": "database-service", "action": "RESET_CONNECTION_POOL"},
    {"id": "background_worker_failure", "name": "Cycle 30: Background Worker Failure", "primary_service": "service-a", "action": "RESTART_SERVICE"}
]


def generate_enterprise_event(
    scenario: str = "normal_traffic",
    index: int = 0,
    timestamp_iso: Optional[str] = None
) -> NormalizedTelemetryEvent:
    """
    Generates a single realistic, correlated synthetic enterprise telemetry event.
    Maps canonical failure cycle names and legacy scenario names.
    """
    now_iso = timestamp_iso or datetime.now(timezone.utc).isoformat()
    trace_id = f"trace-{uuid.uuid4().hex[:16]}"
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    # Map legacy aliases
    scen = scenario.lower()
    if scen in ["database_exhaustion", "database_connection_exhaustion"]:
        scen = "database_connection_exhaustion"
    elif scen in ["api_server_crash", "service_crash"]:
        scen = "service_crash"
    elif scen in ["payment_gateway_timeout", "dependency_timeout"]:
        scen = "dependency_timeout"
    elif scen in ["payment_transaction_spike", "payment_service_error_burst"]:
        scen = "payment_service_error_burst"
    elif scen in ["memory_leak", "memory_pressure"]:
        scen = "memory_pressure"
    elif scen in ["storage_pressure", "disk_pressure"]:
        scen = "disk_pressure"

    selected_svc = random.choice(ENTERPRISE_SERVICES)
    svc_name = selected_svc["name"]
    host = selected_svc["host"]
    sev = TelemetrySeverity.INFO
    telemetry_type = TelemetryType.LOG
    event_type = "HTTP_TRANSACTION_COMPLETED"
    latency = max(2.0, selected_svc["default_latency"] + random.gauss(0, 3.0))
    cpu = max(5.0, min(95.0, 18.0 + random.gauss(0, 4.0)))
    mem = max(64.0, 142.0 + (index % 100) * 0.1)
    err_rate = 0.0
    msg = f"HTTP 200 OK - Processed request {request_id} in {latency:.1f}ms"
    meta: Dict[str, Any] = {"request_id": request_id, "endpoint": "/v1/api"}
    metrics: Dict[str, float] = {"latency_ms": latency, "cpu_percent": cpu, "memory_mb": mem, "error_rate": err_rate}

    # =========================================================================
    # SCENARIOS IMPLEMENTATION (30 Cycles)
    # =========================================================================

    if scen == "database_connection_exhaustion":
        r = random.random()
        if r < 0.60:
            svc_name = "database-service"
            host = "db-primary-01"
            sev = TelemetrySeverity.CRITICAL if index % 5 == 0 else TelemetrySeverity.ERROR
            telemetry_type = TelemetryType.DATABASE_SIGNAL
            event_type = "CONNECTION_POOL_EXHAUSTION"
            latency = 4500.0 + random.uniform(200, 1500)
            cpu = 88.0 + random.uniform(0, 8)
            msg = f"ERROR: Connection pool exhausted (20/20 active connections locked). Query latency {latency:.1f}ms exceeds threshold."
            metrics["active_connections"] = 20.0
            metrics["pool_utilization"] = 1.0
            meta["query"] = "SELECT * FROM transaction_ledger WHERE status = 'PENDING' FOR UPDATE"
        elif r < 0.85:
            svc_name = "service-b"
            host = "pay-api-01"
            sev = TelemetrySeverity.ERROR
            telemetry_type = TelemetryType.PAYMENT_SIGNAL
            event_type = "DATABASE_SOCKET_TIMEOUT"
            latency = 3000.0
            err_rate = 0.45
            msg = f"ERROR: Downstream database socket timeout after 3000ms. Aborting transaction {request_id}."
        else:
            svc_name = "gateway"
            host = "gw-node-01"
            sev = TelemetrySeverity.WARNING
            event_type = "HTTP_504_GATEWAY_TIMEOUT"
            latency = 3050.0
            err_rate = 0.25
            msg = f"HTTP 504 Gateway Timeout - Upstream service-b unresponsive on {request_id}."

    elif scen == "redis_latency_spike" or scen == "cache_stampede":
        svc_name = "redis-cache"
        host = "redis-cluster-01"
        sev = TelemetrySeverity.CRITICAL if index % 4 == 0 else TelemetrySeverity.WARNING
        event_type = "REDIS_LATENCY_SPIKE"
        latency = 850.0 + random.uniform(100, 400)
        msg = f"CRITICAL: Redis latency surge ({latency:.1f}ms). Cache hit ratio dropped to 14.2% causing database fallback cascade."
        metrics["latency_ms"] = latency
        metrics["hit_ratio"] = 0.142

    elif scen == "payment_service_error_burst":
        svc_name = "service-b"
        host = "pay-api-01"
        sev = TelemetrySeverity.ERROR
        telemetry_type = TelemetryType.PAYMENT_SIGNAL
        event_type = "PAYMENT_5XX_BURST"
        err_rate = 0.65
        latency = 820.0
        msg = f"ERROR: Payment authorization rejection burst (HTTP 500 error rate {err_rate*100:.0f}%). Downstream ledger degraded."
        metrics["error_rate"] = err_rate

    elif scen == "kafka_consumer_lag":
        svc_name = "kafka-broker"
        host = "kafka-node-01"
        sev = TelemetrySeverity.WARNING if index % 3 == 0 else TelemetrySeverity.ERROR
        event_type = "KAFKA_CONSUMER_LAG"
        lag = 48500 + (index * 12)
        msg = f"WARNING: Consumer group 'telemetry-processing' lag climbed to {lag:,} messages. Partition 2 stalled."
        metrics["consumer_lag"] = float(lag)

    elif scen == "cpu_saturation":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.CRITICAL if index % 3 == 0 else TelemetrySeverity.WARNING
        event_type = "HIGH_CPU_SATURATION"
        cpu = 96.5 + random.uniform(0, 3.0)
        latency = 650.0
        msg = f"WARNING: Host CPU utilization saturated at {cpu:.1f}%. Thread scheduling stalled."
        metrics["cpu_percent"] = cpu

    elif scen == "memory_pressure":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.ERROR if index % 3 == 0 else TelemetrySeverity.WARNING
        event_type = "HEAP_MEMORY_PRESSURE"
        mem = 920.0 + min(1100.0, (index * 0.8))
        msg = f"WARNING: Resident set memory climbed to {mem:.1f} MB. GC pause: 580ms."
        metrics["memory_mb"] = mem

    elif scen == "api_gateway_timeout":
        svc_name = "gateway"
        host = "gw-node-01"
        sev = TelemetrySeverity.ERROR
        event_type = "HTTP_504_GATEWAY_TIMEOUT"
        latency = 5200.0
        msg = f"HTTP 504 Gateway Timeout - Ingress reverse proxy timed out waiting for upstream response on {request_id}."
        metrics["latency_ms"] = latency

    elif scen == "dependency_failure" or scen == "dependency_timeout":
        svc_name = "payment-gateway"
        host = "pay-gw-connector"
        sev = TelemetrySeverity.CRITICAL if index % 4 == 0 else TelemetrySeverity.ERROR
        telemetry_type = TelemetryType.PAYMENT_SIGNAL
        event_type = "PAYMENT_GATEWAY_TIMEOUT"
        latency = 5200.0 + random.uniform(100, 800)
        msg = f"CRITICAL: Acquirer processor connection timed out (latency {latency:.1f}ms). Network handshake stalled."

    elif scen == "auth_failure_burst" or scen == "auth_token_failure":
        svc_name = "auth-service"
        host = "auth-node-01"
        sev = TelemetrySeverity.ERROR if index % 2 == 0 else TelemetrySeverity.WARNING
        event_type = "AUTHENTICATION_FAILURE_BURST"
        msg = f"SECURITY ALERT: Spike in JWT verification failures (401 Unauthorized surge). Key rotation mismatch."
        metrics["error_rate"] = 0.88

    elif scen == "network_latency":
        svc_name = "gateway"
        host = "gw-node-01"
        sev = TelemetrySeverity.WARNING
        event_type = "NETWORK_PACKET_RTT_SPIKE"
        latency = 1450.0 + random.uniform(200, 600)
        msg = f"WARNING: TCP SYN-ACK round-trip time degraded across inter-zone VPC transit ({latency:.1f}ms)."
        metrics["latency_ms"] = latency

    elif scen == "queue_backlog":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.WARNING if index % 3 == 0 else TelemetrySeverity.ERROR
        event_type = "QUEUE_DEPTH_SATURATION"
        queue_size = 18500 + (index * 5)
        msg = f"WARNING: Asynchronous job queue depth ({queue_size:,} messages) exceeding consumer capacity."
        metrics["queue_size"] = float(queue_size)

    elif scen == "config_regression" or scen == "bad_deployment":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.CRITICAL
        event_type = "CONFIG_REGRESSION_DEPLOYMENT"
        msg = f"CRITICAL: NullPointerException in OrderProcessor.java:142 after build release #402. Rollback advised."
        metrics["error_rate"] = 0.92

    elif scen == "cert_expiry_simulation":
        svc_name = "auth-service"
        host = "auth-node-01"
        sev = TelemetrySeverity.CRITICAL
        event_type = "TLS_CERTIFICATE_EXPIRED"
        msg = f"CRITICAL: Ingress mTLS certificate for domain 'internal.auth.aegisops' expired 2 minutes ago. Handshakes failing."

    elif scen == "service_crash":
        svc_name = "service-b"
        host = "pay-api-01"
        sev = TelemetrySeverity.CRITICAL
        event_type = "PROCESS_SIGSEGV_CRASH"
        msg = f"CRITICAL: Unhandled segmentation fault in payment worker process. Process terminated unexpectedly."
        metrics["error_rate"] = 1.0

    elif scen == "database_latency" or scen == "connection_pool_leak":
        svc_name = "database-service"
        host = "db-primary-01"
        sev = TelemetrySeverity.ERROR
        event_type = "DATABASE_LOCK_CONTENTION"
        latency = 3800.0
        msg = f"ERROR: Database write contention on 'customer_accounts'. Lock wait timeout exceeded."
        metrics["latency_ms"] = latency

    elif scen == "thread_pool_exhaustion":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.ERROR
        event_type = "THREAD_POOL_EXHAUSTED"
        msg = f"ERROR: Worker thread pool (256/256 active threads) saturated. Incoming work tasks dropped."
        metrics["active_threads"] = 256.0

    elif scen == "disk_pressure":
        svc_name = "database-service"
        host = "db-primary-01"
        sev = TelemetrySeverity.WARNING if index % 2 == 0 else TelemetrySeverity.ERROR
        telemetry_type = TelemetryType.DATABASE_SIGNAL
        event_type = "DISK_CAPACITY_CRITICAL"
        used_pct = 93.4 + min(5.0, (index * 0.01))
        msg = f"WARNING: Database storage volume utilization at {used_pct:.1f}%. Partition space critical."
        metrics["storage_percentage"] = used_pct

    elif scen == "dns_failure_simulation":
        svc_name = "gateway"
        host = "gw-node-01"
        sev = TelemetrySeverity.ERROR
        event_type = "DNS_RESOLUTION_FAILURE"
        msg = f"ERROR: DNS resolution failed for 'service-b.internal.cluster': NXDOMAIN from local resolver."

    elif scen == "traffic_spike":
        svc_name = "gateway"
        host = "gw-node-01"
        sev = TelemetrySeverity.WARNING
        event_type = "TRAFFIC_BURST_INGRESS"
        req_sec = 28000 + (index * 50)
        msg = f"WARNING: Inbound ingress request velocity spiked to {req_sec:,} req/sec (320% above baseline)."
        metrics["requests_per_sec"] = float(req_sec)

    elif scen == "message_processing_failure":
        svc_name = "kafka-broker"
        host = "kafka-node-01"
        sev = TelemetrySeverity.ERROR
        event_type = "POISON_PILL_MESSAGE"
        msg = f"ERROR: Poison pill message on partition 3 failed deserialization 5 times. Routing to Dead Letter Queue."

    elif scen == "api_rate_limit_saturation":
        svc_name = "gateway"
        host = "gw-node-01"
        sev = TelemetrySeverity.WARNING
        event_type = "RATE_LIMIT_EXCEEDED"
        msg = f"WARNING: HTTP 429 Too Many Requests issued on /v1/checkout. Client quota exhausted."

    elif scen == "service_dependency_loop":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.ERROR
        event_type = "CIRCULAR_DEPENDENCY_DETECTED"
        msg = f"ERROR: Circular invocation trace detected: service-a -> inventory-service -> user-service -> service-a."

    elif scen == "database_lock_contention":
        svc_name = "database-service"
        host = "db-primary-01"
        sev = TelemetrySeverity.CRITICAL if index % 3 == 0 else TelemetrySeverity.ERROR
        event_type = "ROW_LOCK_CONTENTION"
        latency = 4200.0
        msg = f"CRITICAL: Deadlock detected in database transaction ledger. Transaction rolled back by engine."
        metrics["latency_ms"] = latency

    elif scen == "background_worker_failure":
        svc_name = "service-a"
        host = "order-node-01"
        sev = TelemetrySeverity.ERROR
        event_type = "WORKER_SUBPROCESS_TERMINATED"
        msg = f"ERROR: Asynchronous celery worker subprocess exited with error code 137 (OOM killed)."

    return NormalizedTelemetryEvent(
        timestamp=now_iso,
        source=f"{svc_name}-{host}",
        environment="demo",
        service=svc_name,
        type=telemetry_type,
        severity=sev,
        event_type=event_type,
        message=msg,
        trace_id=trace_id,
        host=host,
        metrics=metrics,
        metadata=meta
    )


def generate_synthetic_batch(
    scenario: str = "normal_traffic",
    count: int = 1000,
    start_index: int = 0
) -> List[NormalizedTelemetryEvent]:
    """Generates an in-memory batch of synthetic telemetry events."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return [
        generate_enterprise_event(scenario=scenario, index=start_index + i, timestamp_iso=now_iso)
        for i in range(count)
    ]
