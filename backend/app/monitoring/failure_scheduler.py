"""
AegisOps AI - Failure Orchestrator & Scenario Scheduler
Manages controlled failure injection across 20 distinct failure classes with strict lifecycle tracking:
IDLE -> INJECTING -> ACTIVE -> DETECTED -> INVESTIGATING -> RCA -> REMEDIATING -> VERIFYING -> RESOLVED -> LEARNED.
Enforces non-overlapping failure discipline: never injects a new failure until the active incident is resolved and learned.
"""

import os
import time
import asyncio
import httpx
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.logger import realtime_logger
from backend.app.monitoring.continuous_telemetry import continuous_telemetry

# 12 Canonical Operational Failure Scenarios rotating across company microservices
# 18 Canonical Operational Failure Scenarios rotating across company microservices (Requirement 3)
CANONICAL_18_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "DATABASE_CONNECTION_EXHAUSTION",
        "name": "PostgreSQL Database Connection Pool Exhaustion",
        "scenario_type": "DATABASE_CONNECTION_EXHAUSTION",
        "category": "Database",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 4000.0, "exhaust_connections": True},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "db_timeout", "delay_sec": 2.5}],
        "expected_signal": "Connection pool saturation 20/20; pool acquisition timeouts; transaction aborts",
        "expected_root_cause": "order-service connection pool saturation",
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"active_connections_max": 5, "error_rate_max": 0.05}
    },
    {
        "id": "DATABASE_TIMEOUT",
        "name": "Database Query Timeout & Latency Degradation",
        "scenario_type": "DATABASE_TIMEOUT",
        "category": "Database",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 5500.0, "exhaust_connections": False},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "gateway_timeout", "delay_sec": 2.5}],
        "expected_signal": "Query latency exceeds SLA; Gateway 504 Gateway Timeout; order persistence failure",
        "expected_root_cause": "order-service slow query lock contention",
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"latency_p95_max_ms": 300, "health_ok": True}
    },
    {
        "id": "HTTP_500_SPIKE",
        "name": "HTTP 500 Internal Error Cascade",
        "scenario_type": "HTTP_500_SPIKE",
        "category": "Application",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 3000.0, "exhaust_connections": True},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "500_cascade", "delay_sec": 2.0}],
        "expected_signal": "Order checkout returns HTTP 500; statement error logged; gateway 5xx rate increases",
        "expected_root_cause": "order-service unhandled database exception",
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"error_rate_max": 0.05, "health_ok": True}
    },
    {
        "id": "HTTP_502_UPSTREAM_FAILURE",
        "name": "Ingress API Gateway 502 Bad Gateway",
        "scenario_type": "HTTP_502_UPSTREAM_FAILURE",
        "category": "Availability",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 6000.0, "exhaust_connections": False},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "502_storm", "delay_sec": 1.5}],
        "expected_signal": "Ingress gateway returns 502 Bad Gateway; upstream dependency failure logged with W3C trace",
        "expected_root_cause": "order-service upstream gateway connection drop",
        "remediation_candidates": ["RESTART_SERVICE", "SCALE_WORKERS"],
        "risk": "HIGH",
        "verification_criteria": {"error_rate_max": 0.02, "health_ok": True}
    },
    {
        "id": "HTTP_503_SERVICE_UNAVAILABLE",
        "name": "HTTP 503 Payment Gateway Dependency Outage",
        "scenario_type": "HTTP_503_SERVICE_UNAVAILABLE",
        "category": "Dependency",
        "company": "fincore",
        "target_service": "payment-service",
        "primary_port": 8203,
        "endpoint": "http://127.0.0.1:8203/inject/timeout",
        "payload": {"enabled": True, "delay_seconds": 6.5},
        "reset_endpoint": "http://127.0.0.1:8203/inject/reset",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "downstream": ["transaction-service", "api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8200, "failure_type": "503_outage", "delay_sec": 2.0}],
        "expected_signal": "Payment service unavailable (503/504); upstream transaction timeouts; elevated error rate",
        "expected_root_cause": "payment-service gateway outage",
        "remediation_candidates": ["RESTART_SERVICE", "RESET_CONNECTION_POOL"],
        "risk": "HIGH",
        "verification_criteria": {"timeout_rate_max": 0.05, "health_ok": True}
    },
    {
        "id": "REDIS_CONNECTION_FAILURE",
        "name": "Redis Outage & Cache Connection Failure",
        "scenario_type": "REDIS_CONNECTION_FAILURE",
        "category": "Infrastructure",
        "company": "clouddesk",
        "target_service": "compute-service",
        "primary_port": 8303,
        "endpoint": "http://127.0.0.1:8303/inject/redis-down",
        "payload": {},
        "reset_endpoint": "http://127.0.0.1:8303/inject/reset",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8300, "failure_type": "cache_degradation", "delay_sec": 2.0}],
        "expected_signal": "Connection refused to redis://127.0.0.1:6379; cache lookup failures; compute latency degradation",
        "expected_root_cause": "redis cache cluster socket connection dropped",
        "remediation_candidates": ["CLEAR_CACHE", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"health_ok": True}
    },
    {
        "id": "CACHE_FAILURE",
        "name": "Cache Cluster Eviction Storm & Partition",
        "scenario_type": "CACHE_FAILURE",
        "category": "Infrastructure",
        "company": "clouddesk",
        "target_service": "compute-service",
        "primary_port": 8303,
        "endpoint": "http://127.0.0.1:8303/inject/redis-down",
        "payload": {},
        "reset_endpoint": "http://127.0.0.1:8303/inject/reset",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8300, "failure_type": "cache_degradation", "delay_sec": 2.0}],
        "expected_signal": "Cache hit rate collapses to 0%; mass keys eviction; downstream database fallback storm",
        "expected_root_cause": "cache cluster partition",
        "remediation_candidates": ["CLEAR_CACHE"],
        "risk": "LOW",
        "verification_criteria": {"health_ok": True}
    },
    {
        "id": "HIGH_LATENCY",
        "name": "Fraud Detection Service Latency Surge",
        "scenario_type": "HIGH_LATENCY",
        "category": "Performance",
        "company": "fincore",
        "target_service": "fraud-detection-service",
        "primary_port": 8204,
        "endpoint": "http://127.0.0.1:8204/inject/latency",
        "payload": {"latency_ms": 2800.0},
        "reset_endpoint": "http://127.0.0.1:8204/inject/reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["transaction-service", "api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8200, "failure_type": "latency_surge", "delay_sec": 2.0}],
        "expected_signal": "p95/p99 latency jumps to 2800ms; transaction processing queue saturation",
        "expected_root_cause": "fraud-detection-service algorithmic compute bottleneck",
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"latency_p95_max_ms": 350, "health_ok": True}
    },
    {
        "id": "REQUEST_TIMEOUT",
        "name": "Upstream Dependency Request Timeout",
        "scenario_type": "REQUEST_TIMEOUT",
        "category": "Latency",
        "company": "fincore",
        "target_service": "payment-service",
        "primary_port": 8203,
        "endpoint": "http://127.0.0.1:8203/inject/timeout",
        "payload": {"enabled": True, "delay_seconds": 6.0},
        "reset_endpoint": "http://127.0.0.1:8203/inject/reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["transaction-service", "api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8200, "failure_type": "request_timeout", "delay_sec": 2.0}],
        "expected_signal": "Payment request exceeds client timeout SLA; 504 Gateway Timeout; socket timeout logs",
        "expected_root_cause": "payment-service upstream delay exceeding 5000ms SLA",
        "remediation_candidates": ["RESTART_SERVICE", "RESET_CONNECTION_POOL"],
        "risk": "HIGH",
        "verification_criteria": {"timeout_rate_max": 0.05, "health_ok": True}
    },
    {
        "id": "SERVICE_CRASH",
        "name": "Microservice Container Process Crash & Restart",
        "scenario_type": "SERVICE_CRASH",
        "category": "Availability",
        "company": "clouddesk",
        "target_service": "compute-service",
        "primary_port": 8303,
        "endpoint": "http://127.0.0.1:8303/inject/redis-down",
        "payload": {},
        "reset_endpoint": "http://127.0.0.1:8303/inject/reset",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8300, "failure_type": "service_down", "delay_sec": 1.5}],
        "expected_signal": "Health check fails; compute instances creation rejected; service degraded",
        "expected_root_cause": "compute-service worker process terminated unexpectedly",
        "remediation_candidates": ["RESTART_SERVICE"],
        "risk": "HIGH",
        "verification_criteria": {"health_ok": True}
    },
    {
        "id": "DEPENDENCY_FAILURE",
        "name": "Third-Party Banking Microservice Dependency Failure",
        "scenario_type": "DEPENDENCY_FAILURE",
        "category": "Dependency",
        "company": "fincore",
        "target_service": "payment-service",
        "primary_port": 8203,
        "endpoint": "http://127.0.0.1:8203/inject/timeout",
        "payload": {"enabled": True, "delay_seconds": 6.0},
        "reset_endpoint": "http://127.0.0.1:8203/inject/reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["transaction-service", "api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8200, "failure_type": "dep_failure", "delay_sec": 2.0}],
        "expected_signal": "Downstream banking provider connection reset; 503 Service Unavailable returned",
        "expected_root_cause": "payment-service third-party provider failure",
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"timeout_rate_max": 0.05, "health_ok": True}
    },
    {
        "id": "CPU_SPIKE",
        "name": "Order Engine Worker Core Saturation & CPU Burn",
        "scenario_type": "CPU_SPIKE",
        "category": "Resource",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 2800.0, "exhaust_connections": False},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "cpu_slowdown", "delay_sec": 2.0}],
        "expected_signal": "CPU utilization exceeds 90%; order queue processing backlog; thread pool contention",
        "expected_root_cause": "order-service CPU saturation burn",
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"cpu_percent_max": 65.0, "latency_p95_max_ms": 300}
    },
    {
        "id": "MEMORY_PRESSURE",
        "name": "Process Memory Buffer Leak & GC Stall",
        "scenario_type": "MEMORY_PRESSURE",
        "category": "Resource",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 2200.0, "exhaust_connections": False},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "mem_pressure", "delay_sec": 2.0}],
        "expected_signal": "Resident memory grows continuously; garbage collection stalls; response latency spikes",
        "expected_root_cause": "order-service memory pressure",
        "remediation_candidates": ["CLEAR_CACHE", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"latency_p95_max_ms": 350, "health_ok": True}
    },
    {
        "id": "QUEUE_BACKLOG",
        "name": "Message Queue Consumer Lag Surge & Backlog",
        "scenario_type": "QUEUE_BACKLOG",
        "category": "Throughput",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 3200.0, "exhaust_connections": False},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "queue_delay", "delay_sec": 2.0}],
        "expected_signal": "Async order event queue depth surges past 5,000; dispatch latency degrades",
        "expected_root_cause": "order-service event processing queue backlog",
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"health_ok": True}
    },
    {
        "id": "DEPLOYMENT_REGRESSION",
        "name": "Compute Worker Configuration Regression",
        "scenario_type": "DEPLOYMENT_REGRESSION",
        "category": "Configuration",
        "company": "clouddesk",
        "target_service": "compute-service",
        "primary_port": 8303,
        "endpoint": "http://127.0.0.1:8303/inject/latency",
        "payload": {"latency_ms": 3200.0},
        "reset_endpoint": "http://127.0.0.1:8303/inject/reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8300, "failure_type": "regression_slowdown", "delay_sec": 2.0}],
        "expected_signal": "Worker thread exhaustion; latency regression post-deployment; request queue backup",
        "expected_root_cause": "compute-service config parameter regression",
        "remediation_candidates": ["ROLLBACK_DEPLOYMENT", "ROLLBACK_CONFIG"],
        "risk": "LOW",
        "verification_criteria": {"latency_p95_max_ms": 300, "health_ok": True}
    },
    {
        "id": "AUTHENTICATION_FAILURE_SPIKE",
        "name": "Transaction Token Authentication Rejection Surge",
        "scenario_type": "AUTHENTICATION_FAILURE_SPIKE",
        "category": "Security",
        "company": "fincore",
        "target_service": "payment-service",
        "primary_port": 8203,
        "endpoint": "http://127.0.0.1:8203/inject/timeout",
        "payload": {"enabled": True, "delay_seconds": 5.5},
        "reset_endpoint": "http://127.0.0.1:8203/inject/reset",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "downstream": ["transaction-service"],
        "downstream_services": [{"service": "transaction-service", "port": 8202, "failure_type": "auth_drops", "delay_sec": 2.0}],
        "expected_signal": "Elevated transaction failure rate; authorization timeout; 401/403/504 errors",
        "expected_root_cause": "payment-service auth validation timeout",
        "remediation_candidates": ["ROLLBACK_CONFIG", "CLEAR_CACHE"],
        "risk": "LOW",
        "verification_criteria": {"error_rate_max": 0.05, "health_ok": True}
    },
    {
        "id": "NETWORK_TIMEOUT",
        "name": "TCP Network Ingress Socket Timeout",
        "scenario_type": "NETWORK_TIMEOUT",
        "category": "Network",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 5200.0, "exhaust_connections": False},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "net_timeout", "delay_sec": 2.0}],
        "expected_signal": "TCP socket connect timeout after 5000ms; reset by peer; ingress 504 errors",
        "expected_root_cause": "order-service network latency socket timeout",
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"timeout_rate_max": 0.05, "health_ok": True}
    },
    {
        "id": "CASCADING_FAILURE",
        "name": "Multi-Hop Cascading Dependency Failure",
        "scenario_type": "CASCADING_FAILURE",
        "category": "Cascading",
        "company": "shopsphere",
        "target_service": "order-service",
        "primary_port": 8101,
        "endpoint": "http://127.0.0.1:8101/inject/db-latency",
        "payload": {"latency_ms": 4500.0, "exhaust_connections": True},
        "reset_endpoint": "http://127.0.0.1:8101/inject/db-reset",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "downstream": ["api-gateway"],
        "downstream_services": [{"service": "api-gateway", "port": 8100, "failure_type": "cascading_500", "delay_sec": 2.0}],
        "expected_signal": "PostgreSQL exhaustion cascades to order-service timeouts, propagating to Gateway 503 errors",
        "expected_root_cause": "order-service database saturation cascade",
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "risk": "LOW",
        "verification_criteria": {"error_rate_max": 0.05, "health_ok": True}
    }
]

# Aliases for backwards compatibility
CANONICAL_12_SCENARIOS = CANONICAL_18_SCENARIOS

# 10 Canonical Baseline Failure Scenarios (for backward compatibility with legacy test suites)
FAILURE_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "DATABASE_CONNECTION_FAILURE",
        "name": "Database Connection Pool Saturation",
        "category": "Database",
        "scenario_type": "DATABASE_CONNECTION_EXHAUSTION",
        "target_service": "database-service",
        "primary_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "connection_exhaustion",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "downstream": ["payment-api", "service-b", "gateway", "service-a"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "db_timeout", "delay_sec": 2.0},
            {"service": "gateway", "port": 8001, "failure_type": "error_spike", "delay_sec": 3.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "Active connections = 20/20, connection timeouts, elevated 500 error rate",
            "observable_via": ["connection_pool_utilization", "error_rate", "latency_p95"],
            "has_error_logs": True
        },
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"active_connections_max": 5, "error_rate_max": 0.05, "query_endpoint_200": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "PAYMENT_API_FAILURE",
        "name": "Payment Gateway Processing Outage",
        "category": "Dependency",
        "scenario_type": "PAYMENT_DEPENDENCY_FAILURE",
        "target_service": "payment-api",
        "primary_service": "payment-api",
        "primary_port": 8003,
        "failure_mode": "payment_dependency_failure",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "downstream": ["service-a", "gateway"],
        "downstream_services": [
            {"service": "service-a", "port": 8002, "failure_type": "error_spike", "delay_sec": 1.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 504 timeouts to third-party bank provider; latency spikes",
            "observable_via": ["timeout_rate", "dependency_latency"],
            "has_error_logs": True
        },
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"timeout_rate_max": 0.05, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "HTTP_500_SPIKE",
        "name": "Internal Server Error 500 Cascade",
        "category": "Application",
        "scenario_type": "DATABASE_QUERY_FAILURE",
        "target_service": "service-a",
        "primary_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "database_query_failure",
        "severity": "HIGH",
        "duration_sec": 40,
        "downstream": ["gateway"],
        "downstream_services": [
            {"service": "gateway", "port": 8001, "failure_type": "error_spike", "delay_sec": 1.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "Unhandled runtime exception loop triggering 500 responses",
            "observable_via": ["error_rate", "http_5xx_rate"],
            "has_error_logs": True
        },
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "HTTP_502_503_SPIKE",
        "name": "Bad Gateway & Service Unavailable Storm",
        "category": "Availability",
        "scenario_type": "GATEWAY_503_OUTAGE",
        "target_service": "gateway",
        "primary_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "gateway_503_storm",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "downstream": [],
        "downstream_services": [],
        "expected_telemetry_signature": {
            "primary_symptom": "Ingress reverse proxy returning 502/503 bad gateway",
            "observable_via": ["http_503_rate", "http_502_rate"],
            "has_error_logs": True
        },
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.01, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "REQUEST_TIMEOUT",
        "name": "Upstream Dependency Timeout",
        "category": "Latency",
        "scenario_type": "DEPENDENCY_TIMEOUT_BURST",
        "target_service": "service-b",
        "primary_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "upstream_timeout",
        "severity": "HIGH",
        "duration_sec": 40,
        "downstream": ["service-a"],
        "downstream_services": [
            {"service": "service-a", "port": 8002, "failure_type": "latency_spike", "delay_sec": 2.0}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "Calls to service-b exceeding 5000ms SLA timeout window",
            "observable_via": ["timeout_rate", "latency_p95"],
            "has_error_logs": True
        },
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"timeout_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "HIGH_LATENCY",
        "name": "Database Table Lock & P99 Latency Degradation",
        "category": "Performance",
        "scenario_type": "DATABASE_LATENCY_SPIKE",
        "target_service": "database-service",
        "primary_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "database_latency_spike",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["service-b", "service-a"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "latency_spike", "delay_sec": 2.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "p95/p99 query latency jumps to 2800ms; error rate initially normal",
            "observable_via": ["latency_p95", "latency_p99"],
            "has_error_logs": False
        },
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"latency_p95_max_ms": 300, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "SERVICE_UNAVAILABLE",
        "name": "Service Unavailable Outage",
        "category": "Availability",
        "scenario_type": "SERVICE_B_CRASH",
        "target_service": "payment-api",
        "primary_service": "payment-api",
        "primary_port": 8003,
        "failure_mode": "service_b_crash",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "downstream": ["gateway"],
        "downstream_services": [
            {"service": "gateway", "port": 8001, "failure_type": "error_spike", "delay_sec": 1.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "Payment API down, health check returning 503",
            "observable_via": ["service_health_state", "http_503_rate"],
            "has_error_logs": True
        },
        "remediation_candidates": ["RESTART_SERVICE"],
        "verification_criteria": {"health_status": "UP", "health_code": 200},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DEPENDENCY_FAILURE",
        "name": "Third-Party Microservice Dependency Failure",
        "category": "Dependency",
        "scenario_type": "PAYMENT_DEPENDENCY_FAILURE",
        "target_service": "service-b",
        "primary_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "payment_dependency_failure",
        "severity": "HIGH",
        "duration_sec": 45,
        "downstream": ["service-a", "gateway"],
        "downstream_services": [
            {"service": "service-a", "port": 8002, "failure_type": "error_spike", "delay_sec": 1.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "External provider socket disconnected with connection reset by peer",
            "observable_via": ["timeout_rate", "error_rate"],
            "has_error_logs": True
        },
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"timeout_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "RESOURCE_EXHAUSTION",
        "name": "CPU & Memory Resource Saturation",
        "category": "Resource",
        "scenario_type": "CPU_SATURATION_BURN",
        "target_service": "service-a",
        "primary_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "cpu_burn",
        "severity": "HIGH",
        "duration_sec": 40,
        "downstream": ["gateway"],
        "downstream_services": [
            {"service": "gateway", "port": 8001, "failure_type": "latency_spike", "delay_sec": 2.0}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "CPU utilization 98%, request processing queue backup",
            "observable_via": ["cpu_percent", "latency_p95"],
            "has_error_logs": False
        },
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "verification_criteria": {"cpu_percent_max": 65.0, "latency_p95_max_ms": 250},
        "rollback_strategy": "SCALE_WORKERS"
    },
    {
        "id": "CONTAINER_PROCESS_CRASH",
        "name": "Microservice Container Process Crash",
        "category": "Availability",
        "scenario_type": "SERVICE_A_CRASH",
        "target_service": "database-service",
        "primary_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "service_a_crash",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "downstream": ["service-b", "gateway"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "db_timeout", "delay_sec": 1.5}
        ],
        "expected_telemetry_signature": {
            "primary_symptom": "Process terminated, connection refused on port 8004",
            "observable_via": ["service_health_state", "http_503_rate"],
            "has_error_logs": True
        },
        "remediation_candidates": ["RESTART_SERVICE"],
        "verification_criteria": {"health_status": "UP", "health_code": 200},
        "rollback_strategy": "RESTART_SERVICE"
    }
]

# 20 Distinct Failure Scenarios across Database, Performance, Availability, Resource, Network, Dependency, Behavioral
ALL_FAILURE_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "DATABASE_CONNECTION_EXHAUSTION",
        "name": "Database Connection Pool Saturated",
        "scenario_type": "DATABASE_CONNECTION_EXHAUSTION",
        "category": "Database",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "connection_exhaustion",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Active connections = 20/20, connection timeouts, elevated 500 error rate",
            "observable_via": ["connection_pool_utilization", "error_rate", "latency_p95"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-b", "service-a", "gateway"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "db_timeout", "delay_sec": 2.0},
            {"service": "gateway", "port": 8001, "failure_type": "error_spike", "delay_sec": 3.5}
        ],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"active_connections_max": 5, "error_rate_max": 0.05, "query_endpoint_200": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DATABASE_LATENCY_SPIKE",
        "name": "Database Table Lock & Latency Surge",
        "scenario_type": "DATABASE_LATENCY_SPIKE",
        "category": "Performance",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "database_latency_spike",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "p95/p99 query latency jumps to 2800ms; error rate initially normal",
            "observable_via": ["latency_p95", "latency_p99", "trace_duration"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-b", "service-a"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "latency_spike", "delay_sec": 2.5}
        ],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"latency_p95_max_ms": 300, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DATABASE_QUERY_FAILURE",
        "name": "Database Deadlock & Statement Abort Storm",
        "scenario_type": "DATABASE_QUERY_FAILURE",
        "category": "Database",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "database_query_failure",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "SQL 500 error spikes on ledger commits; transaction deadlocks",
            "observable_via": ["error_rate", "http_5xx_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-b"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.02, "query_200": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "SERVICE_A_CRASH",
        "name": "Order Service A Process Crash",
        "scenario_type": "SERVICE_A_CRASH",
        "category": "Availability",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "service_a_crash",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 503 Service Unavailable, health endpoint down",
            "observable_via": ["service_health_state", "http_503_rate", "availability"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [
            {"service": "gateway", "port": 8001, "failure_type": "high_http_503_rate", "delay_sec": 1.5}
        ],
        "remediation_candidates": ["RESTART_SERVICE"],
        "verification_criteria": {"health_status": "UP", "health_code": 200},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "SERVICE_B_CRASH",
        "name": "Payment Service B Crash",
        "scenario_type": "SERVICE_B_CRASH",
        "category": "Availability",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "service_b_crash",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 503, Payment API down, Order fulfillment cascading failure",
            "observable_via": ["service_health_state", "http_503_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-a", "gateway"],
        "downstream_services": [
            {"service": "service-a", "port": 8002, "failure_type": "error_spike", "delay_sec": 1.5}
        ],
        "remediation_candidates": ["RESTART_SERVICE"],
        "verification_criteria": {"health_status": "UP", "health_code": 200},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "PAYMENT_DEPENDENCY_FAILURE",
        "name": "External Payment Gateway Provider Outage",
        "scenario_type": "PAYMENT_DEPENDENCY_FAILURE",
        "category": "Dependency",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "payment_dependency_failure",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 504 timeouts to third-party bank provider; latency spikes",
            "observable_via": ["timeout_rate", "dependency_latency"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["RESTART_SERVICE", "ROLLBACK_CONFIG"],
        "verification_criteria": {"timeout_rate_max": 0.05, "p95_max_ms": 400},
        "rollback_strategy": "ROLLBACK_CONFIG"
    },
    {
        "id": "HIGH_HTTP_5XX_RATE",
        "name": "Order Service Unhandled Exception Storm",
        "scenario_type": "HIGH_HTTP_5XX_RATE",
        "category": "Application",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "high_http_5xx_rate",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 500 error rate exceeds 65%; unhandled NullReference",
            "observable_via": ["http_5xx_rate", "error_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.05, "http_status": 200},
        "rollback_strategy": "ROLLBACK_CONFIG"
    },
    {
        "id": "HIGH_HTTP_503_RATE",
        "name": "API Gateway Ingress Saturation",
        "scenario_type": "HIGH_HTTP_503_RATE",
        "category": "Availability",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "high_http_503_rate",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 503 Service Unavailable on 75% ingress traffic",
            "observable_via": ["http_503_rate", "error_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["RESTART_SERVICE", "SCALE_WORKERS"],
        "verification_criteria": {"http_503_rate_max": 0.0, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DEPENDENCY_TIMEOUT",
        "name": "Service A to Service B Timeout",
        "scenario_type": "DEPENDENCY_TIMEOUT",
        "category": "Dependency",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "dependency_timeout",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Inter-service RPC calls take >3500ms; Gateway 504 timeouts",
            "observable_via": ["dependency_latency", "timeout_rate", "trace_duration"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [
            {"service": "gateway", "port": 8001, "failure_type": "dependency_timeout", "delay_sec": 2.0}
        ],
        "remediation_candidates": ["CLEAR_CACHE", "RESTART_SERVICE"],
        "verification_criteria": {"latency_p95_max_ms": 500, "timeout_rate_max": 0.02},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "NETWORK_LATENCY_SPIKE",
        "name": "Cross-AZ Service Mesh Network Jitter",
        "scenario_type": "NETWORK_LATENCY_SPIKE",
        "category": "Network",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "network_latency_spike",
        "severity": "MEDIUM",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "P95 latency elevated to 3100ms; 0 error logs; HTTP 200 response",
            "observable_via": ["latency_p95", "latency_p50", "trace_duration"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["CLEAR_CACHE", "SCALE_WORKERS"],
        "verification_criteria": {"latency_p95_max_ms": 350},
        "rollback_strategy": "CLEAR_CACHE"
    },
    {
        "id": "CPU_SPIKE",
        "name": "Payment Service Cryptographic CPU Burn",
        "scenario_type": "CPU_SPIKE",
        "category": "Resource",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "cpu_spike",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "CPU utilization reaches 92-98%; request processing throttled",
            "observable_via": ["cpu_percent", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "verification_criteria": {"cpu_percent_max": 40.0, "latency_p95_max_ms": 250},
        "rollback_strategy": "SCALE_WORKERS"
    },
    {
        "id": "MEMORY_PRESSURE",
        "name": "Payment Heap Memory Pressure & Leak",
        "scenario_type": "MEMORY_PRESSURE",
        "category": "Resource",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "memory_pressure",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Memory allocated reaches 850MB; Major GC pauses; latency creeps upward",
            "observable_via": ["memory_mb", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["CLEAR_CACHE", "RESTART_SERVICE"],
        "verification_criteria": {"memory_mb_max": 200.0, "latency_p95_max_ms": 200},
        "rollback_strategy": "CLEAR_CACHE"
    },
    {
        "id": "THREAD_POOL_EXHAUSTION",
        "name": "Order Service Thread Pool Depletion",
        "scenario_type": "THREAD_POOL_EXHAUSTION",
        "category": "Resource",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "thread_pool_exhaustion",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Worker threads at max capacity (18/20); queue build-up; 40% drops",
            "observable_via": ["active_connections", "error_rate", "latency_p95"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "verification_criteria": {"active_connections_max": 8, "error_rate_max": 0.05},
        "rollback_strategy": "SCALE_WORKERS"
    },
    {
        "id": "CONNECTION_POOL_EXHAUSTION",
        "name": "Gateway Client Ingress Pool Exhaustion",
        "scenario_type": "CONNECTION_POOL_EXHAUSTION",
        "category": "Network",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "connection_pool_exhaustion",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Active ingress connections saturated at limit (20/20); new calls rejected",
            "observable_via": ["active_connections", "error_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"active_connections_max": 6, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "CACHE_FAILURE",
        "name": "Cache Cluster Eviction Storm & Cold Misses",
        "scenario_type": "CACHE_FAILURE",
        "category": "Infrastructure",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "cache_failure",
        "severity": "MEDIUM",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Cache miss rate 100%; backend fallback latency quadrupled; 25% errors",
            "observable_via": ["latency_p95", "error_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["database-service"],
        "downstream_services": [],
        "remediation_candidates": ["CLEAR_CACHE", "ROLLBACK_CONFIG"],
        "verification_criteria": {"error_rate_max": 0.05, "latency_p95_max_ms": 300},
        "rollback_strategy": "CLEAR_CACHE"
    },
    {
        "id": "SLOW_RESPONSE_BEHAVIOR",
        "name": "Database Query Degradation & Slow Log Warning",
        "scenario_type": "SLOW_RESPONSE_BEHAVIOR",
        "category": "Behavioral",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "slow_response_behavior",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Query latency consistently 2500ms; HTTP 200 status; zero 5xx errors",
            "observable_via": ["latency_p50", "latency_p95", "trace_duration"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-b"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "CLEAR_CACHE"],
        "verification_criteria": {"latency_p95_max_ms": 250},
        "rollback_strategy": "RESET_CONNECTION_POOL"
    },
    {
        "id": "TRAFFIC_SPIKE",
        "name": "Flash Sale Ingress Traffic Spike",
        "scenario_type": "TRAFFIC_SPIKE",
        "category": "Performance",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "traffic_spike",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Request rate increases 5x; latency shifts up; saturation warning",
            "observable_via": ["request_count", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-a", "service-b"],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS"],
        "verification_criteria": {"latency_p95_max_ms": 350, "health_ok": True},
        "rollback_strategy": "SCALE_WORKERS"
    },
    {
        "id": "ERROR_RATE_SPIKE",
        "name": "Payment Authorization Failure Rate Surge",
        "scenario_type": "ERROR_RATE_SPIKE",
        "category": "Application",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "error_rate_spike",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Error rate spikes to 55%; 500 internal errors",
            "observable_via": ["error_rate", "http_5xx_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.05},
        "rollback_strategy": "ROLLBACK_CONFIG"
    },
    {
        "id": "CASCADING_SERVICE_DEGRADATION",
        "name": "Multi-Tier Cascading Service Degradation",
        "scenario_type": "CASCADING_SERVICE_DEGRADATION",
        "category": "Infrastructure",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "cascading_service_degradation",
        "severity": "CRITICAL",
        "duration_sec": 50,
        "expected_telemetry_signature": {
            "primary_symptom": "Database locks propagate to Service B timeouts, Service A retries, Gateway 502",
            "observable_via": ["latency_p95", "error_rate", "trace_duration", "http_5xx_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-b", "service-a", "gateway"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "error_spike", "delay_sec": 2.0},
            {"service": "service-a", "port": 8002, "failure_type": "dependency_timeout", "delay_sec": 3.0},
            {"service": "gateway", "port": 8001, "failure_type": "high_http_503_rate", "delay_sec": 4.5}
        ],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.05, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "BEHAVIORAL_ANOMALY_WITHOUT_ERROR_LOGS",
        "name": "Silent Behavioral Latency Degradation (Zero Error Logs)",
        "scenario_type": "BEHAVIORAL_ANOMALY_WITHOUT_ERROR_LOGS",
        "category": "Behavioral",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "behavioral_anomaly_without_error_logs",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "P95 latency shifts from 15ms to 360ms; status is 200 OK; 0 ERROR logs emitted",
            "observable_via": ["latency_p95", "latency_p50", "trace_duration"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-b"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "CLEAR_CACHE"],
        "verification_criteria": {"latency_p95_max_ms": 120, "health_ok": True},
        "rollback_strategy": "RESET_CONNECTION_POOL"
    },
    {
        "id": "DATABASE_DEADLOCK",
        "name": "Database Deadlock & Lock Cycle",
        "scenario_type": "DATABASE_DEADLOCK",
        "category": "Database",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "database_deadlock",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Mutual lock wait graph cycle detected, transaction rollbacks spike",
            "observable_via": ["error_rate", "latency_p99"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-b"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DATABASE_LOCK_CONTENTION",
        "name": "Database Table Lock Contention",
        "scenario_type": "DATABASE_LOCK_CONTENTION",
        "category": "Database",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "lock_contention",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Exclusive row-level write locks block concurrent readers, P95 jumps to 3200ms",
            "observable_via": ["latency_p95", "active_connections"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-b", "service-a"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"latency_p95_max_ms": 250, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "SERVICE_RESTART_LOOP",
        "name": "Service CrashLoopBackOff Anomaly",
        "scenario_type": "SERVICE_RESTART_LOOP",
        "category": "Application",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "restart_loop",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Repeated SIGKILL / container bootstrap loop, flapping availability",
            "observable_via": ["service_health_state", "http_503_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [{"service": "gateway", "port": 8001, "failure_type": "high_http_503_rate", "delay_sec": 2.0}],
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESTART_SERVICE"],
        "verification_criteria": {"health_status": "UP", "health_code": 200},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "THREAD_POOL_EXHAUSTION",
        "name": "Application Worker Thread Pool Starvation",
        "scenario_type": "THREAD_POOL_EXHAUSTION",
        "category": "Application",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "threadpool_starvation",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Active threads = 100/100, task queue rejects incoming requests with 503",
            "observable_via": ["queue_depth", "latency_p95", "error_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "REQUEST_QUEUE_SATURATION",
        "name": "Ingress Request Queue Backlog Saturation",
        "scenario_type": "REQUEST_QUEUE_SATURATION",
        "category": "Application",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "queue_saturation",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Queue depth reaches 5,000 backlog items, socket buffers overflow",
            "observable_via": ["queue_depth", "latency_p95"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS", "RESTART_SERVICE"],
        "verification_criteria": {"latency_p95_max_ms": 150, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "PACKET_LOSS",
        "name": "Network Packet Loss & TCP Retransmit Storm",
        "scenario_type": "PACKET_LOSS",
        "category": "Network",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "packet_loss",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "15% synthetic packet drop rate, TCP retransmissions surge",
            "observable_via": ["packet_loss_rate", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-a", "service-b"],
        "downstream_services": [],
        "remediation_candidates": ["RESTART_SERVICE", "RESET_CONNECTION_POOL"],
        "verification_criteria": {"latency_p95_max_ms": 100, "health_ok": True},
        "rollback_strategy": "RESET_CONNECTION_POOL"
    },
    {
        "id": "DNS_FAILURE",
        "name": "Authoritative DNS Resolution Outage",
        "scenario_type": "DNS_FAILURE",
        "category": "Network",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "dns_failure",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "getaddrinfo failed (Name or service not known), upstream unresolved",
            "observable_via": ["error_rate", "http_5xx_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["CLEAR_CACHE", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.01, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "CACHE_MISS_SPIKE",
        "name": "Cache Key Invalidation & Miss Storm",
        "scenario_type": "CACHE_MISS_SPIKE",
        "category": "Cache",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "cache_miss_spike",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Cache hit ratio drops from 95% to 8%, database query load spikes 10x",
            "observable_via": ["cache_hit_ratio", "active_connections", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-b"],
        "downstream_services": [],
        "remediation_candidates": ["CLEAR_CACHE", "RESET_CONNECTION_POOL"],
        "verification_criteria": {"latency_p95_max_ms": 200, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DATABASE_TO_SERVICE_CASCADE",
        "name": "Database Saturation to Gateway Cascade",
        "scenario_type": "DATABASE_TO_SERVICE_CASCADE",
        "category": "Cascade",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "database_to_service_cascade",
        "severity": "CRITICAL",
        "duration_sec": 50,
        "expected_telemetry_signature": {
            "primary_symptom": "Database pool exhaustion cascades up: Service B timeouts -> Service A retry storm -> Gateway 502",
            "observable_via": ["latency_p95", "error_rate", "trace_duration", "http_502_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-b", "service-a", "gateway"],
        "downstream_services": [
            {"service": "service-b", "port": 8003, "failure_type": "db_timeout", "delay_sec": 1.5},
            {"service": "service-a", "port": 8002, "failure_type": "error_spike", "delay_sec": 2.5},
            {"service": "gateway", "port": 8001, "failure_type": "high_http_503_rate", "delay_sec": 3.5}
        ],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.05, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "UNKNOWN_BEHAVIORAL_ANOMALY",
        "name": "Novel Behavioral Anomaly (Uncategorized Pattern)",
        "scenario_type": "UNKNOWN_BEHAVIORAL_ANOMALY",
        "category": "Novel",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "unknown_behavioral_anomaly",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Unprecedented latency skew without error logs; cosine similarity < 0.80 to historical store",
            "observable_via": ["latency_p95", "latency_p50", "trace_duration"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"latency_p95_max_ms": 120, "health_ok": True},
        "rollback_strategy": "RESET_CONNECTION_POOL"
    },
    {
        "id": "AUTH_DEPENDENCY_FAILURE",
        "name": "Auth JWT Authority Handshake Failure",
        "scenario_type": "AUTH_DEPENDENCY_FAILURE",
        "category": "Dependency",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "auth_failure",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Stale token validation cache causing 401 Unauthorized bursts",
            "observable_via": ["error_rate", "http_401_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["CLEAR_CACHE", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.01, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "DEPENDENCY_TIMEOUT_BURST",
        "name": "Upstream Dependency Timeout Cascade",
        "scenario_type": "DEPENDENCY_TIMEOUT_BURST",
        "category": "Dependency",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "upstream_timeout",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "External vendor SLA timeout window (5000ms) breached on batch settlements",
            "observable_via": ["timeout_rate", "latency_p95"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [{"service": "service-a", "port": 8002, "failure_type": "latency_spike", "delay_sec": 2.0}],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"timeout_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "BRUTE_FORCE_AUTH_BURST",
        "name": "Distributed Auth Probe & Credential Stuffing",
        "scenario_type": "BRUTE_FORCE_AUTH_BURST",
        "category": "Security",
        "target_service": "auth-service",
        "primary_port": 8005,
        "failure_mode": "auth_probe_storm",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "HTTP 401/403 surge > 500 req/min, token signing thread lock",
            "observable_via": ["http_401_rate", "http_403_rate", "request_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [{"service": "gateway", "port": 8001, "failure_type": "high_http_401_rate", "delay_sec": 1.0}],
        "remediation_candidates": ["ENABLE_CIRCUIT_BREAKER", "RESTART_SERVICE"],
        "verification_criteria": {"http_401_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "TOKEN_EXPIRATION_STORM",
        "name": "Mass JWT Token Expiration & Re-Auth Wave",
        "scenario_type": "TOKEN_EXPIRATION_STORM",
        "category": "Security",
        "target_service": "auth-service",
        "primary_port": 8005,
        "failure_mode": "token_storm",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Simultaneous token refresh storm causing 10x traffic spike on /auth/refresh",
            "observable_via": ["request_rate", "latency_p95", "cpu_percent"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS", "CLEAR_CACHE"],
        "verification_criteria": {"cpu_max": 50.0, "latency_p95_max_ms": 200},
        "rollback_strategy": "SCALE_WORKERS"
    },
    {
        "id": "UNAUTHORIZED_PROBE_SCAN",
        "name": "Vulnerability Scanner Traversal & 403 Flood",
        "scenario_type": "UNAUTHORIZED_PROBE_SCAN",
        "category": "Security",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "endpoint_scan",
        "severity": "MEDIUM",
        "duration_sec": 35,
        "expected_telemetry_signature": {
            "primary_symptom": "Anomalous traversal of non-existent endpoints /admin/*, /config/*",
            "observable_via": ["http_404_rate", "http_403_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["ENABLE_CIRCUIT_BREAKER", "ROLLBACK_CONFIG"],
        "verification_criteria": {"http_403_rate_max": 0.01, "health_ok": True},
        "rollback_strategy": "ENABLE_CIRCUIT_BREAKER"
    },
    {
        "id": "KAFKA_CONSUMER_LAG_SURGE",
        "name": "Streaming Consumer Lag & Partition Backpressure",
        "scenario_type": "KAFKA_CONSUMER_LAG_SURGE",
        "category": "Message Queue",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "consumer_lag_spike",
        "severity": "HIGH",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Kafka offset lag climbs past 50,000 messages; message processing latency > 8000ms",
            "observable_via": ["consumer_lag", "processing_latency_ms"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["SCALE_WORKERS", "DRAIN_QUEUE"],
        "verification_criteria": {"consumer_lag_max": 100, "health_ok": True},
        "rollback_strategy": "SCALE_WORKERS"
    },
    {
        "id": "DEAD_LETTER_QUEUE_FLOOD",
        "name": "Dead Letter Queue Message Reject Flood",
        "scenario_type": "DEAD_LETTER_QUEUE_FLOOD",
        "category": "Message Queue",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "dlq_poison_pill",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Poison pill payloads triggering JSON deserialization failure loop into DLQ",
            "observable_via": ["error_rate", "dlq_message_count"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["DRAIN_QUEUE", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "DRAIN_QUEUE"
    },
    {
        "id": "MESSAGE_PROCESSING_TIMEOUT",
        "name": "Async Worker Thread Deadlock on Queue Drain",
        "scenario_type": "MESSAGE_PROCESSING_TIMEOUT",
        "category": "Message Queue",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "worker_starvation",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "All 8 event loop workers hung awaiting blocking RPC call; queue stops advancing",
            "observable_via": ["active_workers", "latency_p95"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-a"],
        "downstream_services": [],
        "remediation_candidates": ["RESTART_SERVICE", "SCALE_WORKERS"],
        "verification_criteria": {"latency_p95_max_ms": 150, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "BAD_DEPLOYMENT_CONFIG",
        "name": "Corrupted Environment Variable & Config Regression",
        "scenario_type": "BAD_DEPLOYMENT_CONFIG",
        "category": "Configuration",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "misconfiguration",
        "severity": "CRITICAL",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Mismatched DB connection string port (8009 vs 8004); immediate connection refuels",
            "observable_via": ["error_rate", "http_500_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [{"service": "gateway", "port": 8001, "failure_type": "high_http_500_rate", "delay_sec": 1.0}],
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.01, "health_ok": True},
        "rollback_strategy": "ROLLBACK_CONFIG"
    },
    {
        "id": "CORRUPTED_FEATURE_FLAG",
        "name": "Faulty Feature Flag Infinite Loop Activation",
        "scenario_type": "CORRUPTED_FEATURE_FLAG",
        "category": "Configuration",
        "target_service": "service-a",
        "primary_port": 8002,
        "failure_mode": "feature_flag_bug",
        "severity": "HIGH",
        "duration_sec": 40,
        "expected_telemetry_signature": {
            "primary_symptom": "Dark launch toggle 'new_checkout_flow' enters recursion loop on inventory check",
            "observable_via": ["cpu_percent", "latency_p95"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["gateway"],
        "downstream_services": [],
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESTART_SERVICE"],
        "verification_criteria": {"cpu_max": 40.0, "latency_p95_max_ms": 120},
        "rollback_strategy": "ROLLBACK_CONFIG"
    },
    {
        "id": "SCHEMA_VERSION_MISMATCH",
        "name": "Database Schema Migration Drift & Column Not Found",
        "scenario_type": "SCHEMA_VERSION_MISMATCH",
        "category": "Configuration",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "schema_drift",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Missing column 'billing_zip' causing 100% ORM query execution aborts",
            "observable_via": ["error_rate", "http_500_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": ["service-b", "service-a"],
        "downstream_services": [{"service": "service-b", "port": 8003, "failure_type": "db_timeout", "delay_sec": 2.0}],
        "remediation_candidates": ["ROLLBACK_CONFIG", "RESET_CONNECTION_POOL"],
        "verification_criteria": {"error_rate_max": 0.01, "health_ok": True},
        "rollback_strategy": "ROLLBACK_CONFIG"
    },
    {
        "id": "DATABASE_REPLICATION_LAG",
        "name": "Database Read Replica Sync Delay & Stale Reads",
        "scenario_type": "DATABASE_REPLICATION_LAG",
        "category": "Database",
        "target_service": "database-service",
        "primary_port": 8004,
        "failure_mode": "replication_lag",
        "severity": "MEDIUM",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "WAL replay replication lag jumps from 10ms to 45,000ms; consistency violations",
            "observable_via": ["replication_lag_ms", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-b"],
        "downstream_services": [],
        "remediation_candidates": ["RESET_CONNECTION_POOL", "RESTART_SERVICE"],
        "verification_criteria": {"replication_lag_max_ms": 100, "health_ok": True},
        "rollback_strategy": "RESET_CONNECTION_POOL"
    },
    {
        "id": "TCP_CONNECTION_RESET_STORM",
        "name": "Kernel Socket Table Saturation & RST Storm",
        "scenario_type": "TCP_CONNECTION_RESET_STORM",
        "category": "Network",
        "target_service": "gateway",
        "primary_port": 8001,
        "failure_mode": "socket_table_exhaustion",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "TIME_WAIT socket surge past 65,535; ECONNRESET across ingress endpoints",
            "observable_via": ["error_rate", "socket_count", "http_502_rate"],
            "has_error_logs": True
        },
        "expected_affected_dependencies": [],
        "downstream_services": [],
        "remediation_candidates": ["ROTATE_CONNECTIONS", "RESTART_SERVICE"],
        "verification_criteria": {"error_rate_max": 0.02, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    },
    {
        "id": "NOVEL_ZERO_DAY_ANOMALY",
        "name": "Novel Multi-Signal Polymorphic Drift",
        "scenario_type": "NOVEL_ZERO_DAY_ANOMALY",
        "category": "Novel",
        "target_service": "service-b",
        "primary_port": 8003,
        "failure_mode": "novel_composite_drift",
        "severity": "CRITICAL",
        "duration_sec": 45,
        "expected_telemetry_signature": {
            "primary_symptom": "Uncorrelated tripartite oscillation across memory, garbage collection, and IO wait. Similarity to memory store: 0.18",
            "observable_via": ["anomaly_score", "memory_mb", "latency_p95"],
            "has_error_logs": False
        },
        "expected_affected_dependencies": ["service-a", "gateway"],
        "downstream_services": [],
        "remediation_candidates": ["RESTART_SERVICE", "RESET_CONNECTION_POOL"],
        "verification_criteria": {"latency_p95_max_ms": 100, "health_ok": True},
        "rollback_strategy": "RESTART_SERVICE"
    }
]


class FailureSchedulerEngine:
    """
    Intelligent Failure Orchestration Engine.
    Controls periodic, non-overlapping failure injection with full lifecycle management:
    NORMAL -> FAILURE_INJECTED -> FAILURE_DETECTED -> INCIDENT_CREATED -> RCA -> RECOVERY -> VERIFICATION -> RESOLVED -> COOLDOWN -> NEXT_FAILURE.
    Enforces non-overlapping failure discipline: never injects a new failure until the active incident is verified resolved and cooled down.
    """
    def __init__(self):
        self.is_enabled: bool = True
        self.is_auto_mode: bool = True
        self.interval_seconds: int = int(os.getenv("FAILURE_INTERVAL_SECONDS", "180"))  # Default 180s (3 minutes)
        self.cooldown_seconds: int = int(os.getenv("FAILURE_COOLDOWN_SECONDS", "15"))  # 15s cooldown post-resolution
        self.cooldown_until: float = 0.0
        
        # Lifecycle state: NORMAL, FAILURE_INJECTED, FAILURE_DETECTED, INCIDENT_CREATED, RCA, RECOVERY, VERIFICATION, RESOLVED, COOLDOWN
        self.current_lifecycle_state: str = "NORMAL"
        self.active_incident_id: Optional[str] = None
        self.active_scenario: Optional[Dict[str, Any]] = None
        self.current_failure_id: Optional[str] = None
        
        self.last_failure_time: Optional[float] = None
        self.next_failure_time: Optional[float] = None
        self.total_failures_injected: int = 0
        self.scenario_index: int = 0
        self.selected_scenario_id: Optional[str] = None  # None for auto-rotate
        
        # Scenario catalogs: 12 Canonical Rotating Operational Failures
        self.scenarios = CANONICAL_12_SCENARIOS
        self.legacy_scenarios = FAILURE_SCENARIOS
        self.all_scenarios = ALL_FAILURE_SCENARIOS
        
        # Execution history
        self.execution_history: List[Dict[str, Any]] = []
        self._scheduler_task: Optional[asyncio.Task] = None

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return self.scenarios

    def can_inject_next(self) -> bool:
        """
        Critical Rule: Do NOT inject another failure while the previous failure is still unresolved or recovering.
        Only allow injection when state is NORMAL, IDLE, RESOLVED, or LEARNED and any active cooldown has expired.
        """
        if self.current_lifecycle_state in ["RESOLVED", "LEARNED"]:
            return True
        return self.current_lifecycle_state in ["NORMAL", "IDLE"] and time.time() >= self.cooldown_until

    def transition_lifecycle(self, new_state: str, metadata: Optional[Dict[str, Any]] = None):
        """Advances the scenario lifecycle state machine."""
        prev_state = self.current_lifecycle_state
        self.current_lifecycle_state = new_state
        
        if metadata and "incident_id" in metadata:
            self.active_incident_id = metadata["incident_id"]

        realtime_logger.info(
            f"[Failure Lifecycle] Transition: {prev_state} -> {new_state}",
            scenario=self.active_scenario["id"] if self.active_scenario else None,
            incident_id=self.active_incident_id
        )

        if new_state in ["RESOLVED", "LEARNED"]:
            # Mark current scenario run resolved in SQLite
            if self.execution_history:
                self.execution_history[0]["resolved_at"] = datetime.now(timezone.utc).isoformat()
                self.execution_history[0]["lifecycle_state"] = "RESOLVED"
            
            # Reset schedule timer for next run after recovery and cooldown
            if self.is_enabled and self.is_auto_mode:
                self.next_failure_time = time.time() + self.interval_seconds

    def get_status(self) -> Dict[str, Any]:
        time_to_next = 0
        now = time.time()
        if self.next_failure_time and self.is_enabled and self.can_inject_next():
            time_to_next = max(0, int(self.next_failure_time - now))

        next_scenario = self.scenarios[(self.scenario_index) % len(self.scenarios)]

        return {
            "is_enabled": self.is_enabled,
            "is_auto_mode": self.is_auto_mode,
            "interval_seconds": self.interval_seconds,
            "default_interval_sec": 180,
            "time_to_next_failure_sec": time_to_next,
            "lifecycle_state": self.current_lifecycle_state,
            "can_inject_next": self.can_inject_next(),
            "cooldown_remaining_sec": max(0, int(self.cooldown_until - now)) if self.current_lifecycle_state == "COOLDOWN" else 0,
            "active_incident_id": self.active_incident_id,
            "total_failures_injected": self.total_failures_injected,
            "current_scenario": self.active_scenario["name"] if self.active_scenario else "NORMAL_OPERATION",
            "current_scenario_id": self.active_scenario["id"] if self.active_scenario else None,
            "current_scenario_details": self.active_scenario,
            "next_scenario_id": next_scenario["id"],
            "next_scenario_name": next_scenario["name"],
            "selected_scenario_id": self.selected_scenario_id or "AUTO_ROTATE",
            "execution_mode": "CONTROLLED_CUSTOMER_TEST",
            "environment": "CONTROLLED_CUSTOMER_TEST",
            "available_scenarios": self.scenarios,
            "all_scenarios": self.scenarios,
            "total_available_scenarios": len(self.scenarios),
            "recent_runs": self.execution_history[:10]
        }

    def set_config(
        self,
        enabled: Optional[bool] = None,
        auto_mode: Optional[bool] = None,
        interval_seconds: Optional[int] = None,
        scenario_id: Optional[str] = None
    ):
        if enabled is not None:
            self.is_enabled = enabled
            if self.is_enabled and self.can_inject_next():
                self.next_failure_time = time.time() + self.interval_seconds
            else:
                self.next_failure_time = None

        if auto_mode is not None:
            self.is_auto_mode = auto_mode

        if interval_seconds is not None:
            self.interval_seconds = max(15, min(900, interval_seconds))
            if self.is_enabled and self.can_inject_next():
                self.next_failure_time = time.time() + self.interval_seconds

        if scenario_id is not None:
            if scenario_id in ["AUTO", "AUTO_ROTATE", "ALL", ""]:
                self.selected_scenario_id = None
            else:
                self.selected_scenario_id = scenario_id

    async def trigger_manual_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """Immediately executes a specific failure scenario if no unresolved failure is running."""
        scenario = next((s for s in self.scenarios if s["id"] == scenario_id), None)
        if not scenario:
            scenario = next((s for s in self.legacy_scenarios if s["id"] == scenario_id), None)
        if not scenario:
            scenario = self.scenarios[0]

        target_svc = scenario.get("target_service") or scenario.get("primary_service", "order-service")
        downstream = scenario.get("downstream", [d["service"] if isinstance(d, dict) else d for d in scenario.get("downstream_services", [])])

        if not self.can_inject_next():
            return {
                "success": False,
                "error": f"Cannot inject new failure while previous incident ({self.active_incident_id or 'active'}) is in state '{self.current_lifecycle_state}'. Wait for RESOLVED/NORMAL."
            }

        asyncio.create_task(self._execute_failure_cascade(scenario))
        return {
            "success": True,
            "scenario": scenario["name"],
            "scenario_id": scenario["id"],
            "target_service": target_svc,
            "primary_service": target_svc,
            "downstream": downstream,
            "lifecycle_state": "FAILURE_INJECTED"
        }

    async def trigger_next_scenario(self) -> Dict[str, Any]:
        """Manually triggers the next failure scenario in sequence (respects non-overlapping rule)."""
        if not self.can_inject_next():
            return {
                "success": False,
                "error": f"Cannot inject new failure while previous incident ({self.active_incident_id or 'active'}) is in state '{self.current_lifecycle_state}'. Wait for RESOLVED/NORMAL."
            }
        scenario = self.scenarios[self.scenario_index % len(self.scenarios)]
        self.scenario_index += 1
        asyncio.create_task(self._execute_failure_cascade(scenario))
        return {
            "success": True,
            "scenario": scenario["name"],
            "scenario_id": scenario["id"],
            "target_service": scenario["target_service"],
            "primary_service": scenario["target_service"],
            "downstream": [d["service"] if isinstance(d, dict) else d for d in scenario.get("downstream_services", [])],
            "lifecycle_state": "FAILURE_INJECTED"
        }

    async def skip_current_scenario(self) -> Dict[str, Any]:
        """Force cancels or clears the active scenario and resets state to NORMAL."""
        prev = self.active_scenario
        self.active_scenario = None
        self.current_lifecycle_state = "NORMAL"
        self.active_incident_id = None
        self.cooldown_until = 0.0
        self.next_failure_time = time.time() + self.interval_seconds
        
        # Reset live services concurrently
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as c:
                await asyncio.gather(
                    c.post("http://127.0.0.1:8101/inject/db-reset"),
                    c.post("http://127.0.0.1:8203/inject/reset"),
                    c.post("http://127.0.0.1:8204/inject/reset"),
                    c.post("http://127.0.0.1:8303/inject/reset"),
                    return_exceptions=True
                )
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Cleared active scenario '{prev.get('name') if prev else 'None'}'. State reset to NORMAL."
        }

    def reset(self):
        """Resets engine state to NORMAL baseline."""
        self.active_scenario = None
        self.current_lifecycle_state = "NORMAL"
        self.active_incident_id = None
        self.current_failure_id = None
        self.cooldown_until = 0.0

    async def start(self):
        if self._scheduler_task and not self._scheduler_task.done():
            return
        self.next_failure_time = time.time() + self.interval_seconds
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()

    async def _scheduler_loop(self):
        """Periodically triggers next failure scenario every ~3 minutes (180s) when idle."""
        while True:
            await asyncio.sleep(1.0)
            now = time.time()
            
            # Cooldown expiration check
            if self.current_lifecycle_state == "COOLDOWN":
                if now >= self.cooldown_until:
                    self.current_lifecycle_state = "NORMAL"
                    self.active_scenario = None
                    self.active_incident_id = None
                    realtime_logger.info("[Failure Lifecycle] Cooldown period completed. Mesh state restored to NORMAL.")
                continue

            if not self.is_enabled or not self.is_auto_mode:
                continue

            if self.next_failure_time and now >= self.next_failure_time:
                # Check lifecycle blocking: do not inject if unresolved!
                if not self.can_inject_next():
                    continue

                if self.selected_scenario_id:
                    scenario = next((s for s in self.scenarios if s["id"] == self.selected_scenario_id), None)
                    if not scenario:
                        scenario = next((s for s in self.legacy_scenarios if s["id"] == self.selected_scenario_id), self.scenarios[0])
                else:
                    scenario = self.scenarios[self.scenario_index % len(self.scenarios)]
                    self.scenario_index += 1
                
                await self._execute_failure_cascade(scenario)

    async def _execute_failure_cascade(self, scenario: Dict[str, Any]):
        """
        Executes real controlled failure injection:
        1. Calls actual microservice chaos injection endpoint using httpx with trust_env=False
        2. Sets metadata with environment='CONTROLLED_CUSTOMER_TEST'
        3. Advances state to FAILURE_INJECTED
        4. Broadcasts to WebSocket
        5. Persists execution record to DB
        """
        self.active_scenario = scenario
        self.current_failure_id = f"FAIL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        self.last_failure_time = time.time()
        self.total_failures_injected += 1
        self.current_lifecycle_state = "FAILURE_INJECTED"
        
        target = scenario["target_service"]
        company = scenario.get("company", "shopsphere")
        endpoint = scenario.get("endpoint")
        payload = scenario.get("payload", {})
        duration = scenario.get("duration_sec", 45)
        severity = scenario.get("severity", "HIGH")
        expected_signal = scenario.get("expected_signal", "")
        
        realtime_logger.warn(
            f"[Failure Orchestrator] Injected controlled scenario #{self.total_failures_injected}: {scenario['name']} on {target} ({company})",
            scenario_id=scenario["id"],
            target=target,
            company=company,
            severity=severity,
            environment="CONTROLLED_CUSTOMER_TEST"
        )

        scenario_record = {
            "failure_id": self.current_failure_id,
            "scenario": scenario["id"],
            "scenario_type": scenario["id"],
            "target_service": target,
            "company": company,
            "severity": severity,
            "duration_sec": duration,
            "expected_signal": expected_signal,
            "lifecycle_state": "FAILURE_INJECTED",
            "associated_incident_id": None,
            "environment": "CONTROLLED_CUSTOMER_TEST",
            "execution_mode": "CONTROLLED_CUSTOMER_TEST",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None
        }
        self.execution_history.insert(0, scenario_record)
        asyncio.create_task(self._persist_scenario_record(scenario_record))

        # 1. Primary service failure injection via real HTTP chaos call
        if endpoint:
            try:
                async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
                    await client.post(endpoint, json=payload)
            except Exception as e:
                realtime_logger.error(f"Failed to inject chaos into {endpoint}: {e}")
        else:
            # Fallback based on target service
            try:
                async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
                    if "order" in target:
                        await client.post("http://127.0.0.1:8101/inject/db-latency", json={"latency_ms": 3000.0, "exhaust_connections": True})
                    elif "payment" in target:
                        await client.post("http://127.0.0.1:8203/inject/timeout", json={"enabled": True, "delay_seconds": 6.0})
                    elif "fraud" in target:
                        await client.post("http://127.0.0.1:8204/inject/latency", json={"latency_ms": 2500.0})
                    elif "compute" in target or "redis" in scenario["id"].lower():
                        await client.post("http://127.0.0.1:8303/inject/redis-down")
            except Exception as e:
                realtime_logger.error(f"Fallback chaos injection failed: {e}")

        # 2. Update continuous telemetry synthetic state
        continuous_telemetry.set_service_failure(
            service=target,
            failure_type=scenario["id"],
            severity=severity,
            duration_sec=float(duration)
        )

        # 3. Broadcast real-time failure notification to UI
        try:
            from backend.app.api.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "FAILURE_INJECTED",
                "failure": scenario_record,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception:
            pass

    async def _persist_scenario_record(self, record_dict: Dict[str, Any]):
        """Persists scenario record to SQLite failure_scenarios_history table."""
        try:
            from backend.app.core.database import AsyncSessionLocal
            from backend.app.models.historical import FailureScenarioRecord
            async with AsyncSessionLocal() as session:
                rec = FailureScenarioRecord(
                    failure_id=record_dict["failure_id"],
                    scenario_type=record_dict["scenario_type"],
                    target_service=record_dict["target_service"],
                    severity=record_dict["severity"],
                    duration_sec=record_dict["duration_sec"],
                    lifecycle_state=record_dict["lifecycle_state"],
                    associated_incident_id=record_dict.get("associated_incident_id"),
                    execution_mode=record_dict.get("execution_mode", "CONTROLLED_CUSTOMER_TEST"),
                    started_at=record_dict["started_at"],
                    resolved_at=record_dict.get("resolved_at")
                )
                session.add(rec)
                await session.commit()
        except Exception as exc:
            realtime_logger.error(f"Failed to persist failure scenario record: {exc}")


# Global singleton failure scheduler
failure_scheduler = FailureSchedulerEngine()

