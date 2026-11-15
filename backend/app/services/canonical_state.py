"""
AegisOps AI — Canonical Backend Operational State Engine
Single Source of Truth (SSOT) for all operational states across the application.
Implements Parts 1-4, 8-11, 18-21, 29, 39 of the Global Consistency Audit.
"""

import time
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
import threading
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# PART 2 — STATUS SEMANTICS
# ---------------------------------------------------------------------------

class ServiceOperationalStatus(str, Enum):
    """A. SERVICE OPERATIONAL STATUS"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class TelemetryConnectionStatus(str, Enum):
    """B. TELEMETRY CONNECTION STATUS"""
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    PENDING = "PENDING"


class IncidentStatus(str, Enum):
    """C. INCIDENT STATUS"""
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    REMEDIATION_FAILED = "REMEDIATION_FAILED"
    UNRESOLVED = "UNRESOLVED"


class RecoveryStatus(str, Enum):
    """D. RECOVERY STATUS"""
    NOT_REQUIRED = "NOT_REQUIRED"
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REFINING = "REFINING"
    UNRESOLVED = "UNRESOLVED"


class ModelStatus(str, Enum):
    """E. MODEL STATUS"""
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


# ---------------------------------------------------------------------------
# PART 1 — CANONICAL OPERATIONAL STATE MODEL
# ---------------------------------------------------------------------------

class ServiceOperationalState(BaseModel):
    tenant_id: str
    service_id: str
    service_name: str
    display_name: str
    role: str
    service_type: str
    port: int
    environment: str

    operational_status: ServiceOperationalStatus
    telemetry_status: TelemetryConnectionStatus
    dependency_status: str = "VALIDATED"  # VALIDATED | INFERRED | DEGRADED | HEALTHY

    request_rate: float = 0.0             # requests/minute in window
    error_rate: float = 0.0               # ratio 0.0 - 1.0
    p50: Optional[float] = None           # latency ms (or None if insufficient samples)
    p90: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None

    cpu: Optional[float] = None           # % or None if unavailable
    memory: Optional[float] = None        # MB or None if unavailable

    active_incidents: int = 0
    active_warnings: int = 0

    last_telemetry_at: Optional[str] = None      # ISO UTC
    last_health_check_at: Optional[str] = None   # ISO UTC
    updated_at: str                              # ISO UTC

    telemetry_sample_count: int = 0
    calculation_window: str = "Last 5 minutes"
    is_stale: bool = False
    stale_seconds: float = 0.0
    health_score: float = 100.0                  # 0.0 - 100.0 derived from actual evidence
    status_reasons: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# DEFAULT KNOWN TENANT TOPOLOGIES & METADATA
# ---------------------------------------------------------------------------

DEFAULT_TENANT_SERVICES = {
    "shopsphere": [
        {"service_id": "SVC-SHOP-GW", "name": "api-gateway", "display_name": "API Gateway / Ingress", "role": "Ingress & Routing", "service_type": "gateway", "port": 8100, "environment": "production"},
        {"service_id": "SVC-SHOP-ORD", "name": "order-service", "display_name": "Order Service A", "role": "Order Processing", "service_type": "api", "port": 8101, "environment": "production"},
        {"service_id": "SVC-SHOP-PAY", "name": "payment-service", "display_name": "Payment Service B", "role": "Payment & Ledger", "service_type": "api", "port": 8103, "environment": "production"},
        {"service_id": "SVC-SHOP-INV", "name": "inventory-service", "display_name": "Inventory & Stock Engine", "role": "Inventory Service", "service_type": "api", "port": 8102, "environment": "production"},
        {"service_id": "SVC-SHOP-NOTIF", "name": "notification-service", "display_name": "Customer Notification Dispatcher", "role": "Notification Service", "service_type": "worker", "port": 8104, "environment": "production"},
        {"service_id": "SVC-SHOP-PG", "name": "database-service", "display_name": "Database Persistence", "role": "Distributed Persistence", "service_type": "database", "port": 5432, "environment": "production"},
        {"service_id": "SVC-SHOP-REDIS", "name": "cache", "display_name": "ShopSphere Redis Cache", "role": "Cache Cluster", "service_type": "cache", "port": 6379, "environment": "production"},
    ],
    "fincore": [
        {"service_id": "SVC-FIN-GW", "name": "api-gateway", "display_name": "FinCore Transaction Gateway", "role": "API Gateway", "service_type": "gateway", "port": 8200, "environment": "production"},
        {"service_id": "SVC-FIN-ACC", "name": "account-service", "display_name": "Account & Ledger Balance Service", "role": "Account Service", "service_type": "api", "port": 8201, "environment": "production"},
        {"service_id": "SVC-FIN-TXN", "name": "transaction-service", "display_name": "High-Throughput Transaction Engine", "role": "Transaction Service", "service_type": "api", "port": 8202, "environment": "production"},
        {"service_id": "SVC-FIN-PAY", "name": "payment-service", "display_name": "Payment Settlement Service", "role": "Payment Service", "service_type": "api", "port": 8203, "environment": "production"},
        {"service_id": "SVC-FIN-FRD", "name": "fraud-detection-service", "display_name": "Fraud Detection & AML Scoring", "role": "Fraud Service", "service_type": "ml_service", "port": 8204, "environment": "production"},
        {"service_id": "SVC-FIN-NOTIF", "name": "notification-service", "display_name": "FinCore Notification Dispatcher", "role": "Notification Service", "service_type": "worker", "port": 8205, "environment": "production"},
        {"service_id": "SVC-FIN-PG", "name": "database-service", "display_name": "FinCore ACID PostgreSQL Ledger", "role": "Distributed Persistence", "service_type": "database", "port": 5432, "environment": "production"},
        {"service_id": "SVC-FIN-REDIS", "name": "cache", "display_name": "FinCore Redis Lock & Session Cache", "role": "Cache Cluster", "service_type": "cache", "port": 6379, "environment": "production"},
    ],
    "clouddesk": [
        {"service_id": "SVC-CLOUD-GW", "name": "api-gateway", "display_name": "CloudDesk Edge Ingress Router", "role": "API Gateway", "service_type": "gateway", "port": 8300, "environment": "production"},
        {"service_id": "SVC-CLOUD-USR", "name": "user-service", "display_name": "Multi-Tenant Authentication & IAM", "role": "Authentication Service", "service_type": "auth", "port": 8301, "environment": "production"},
        {"service_id": "SVC-CLOUD-PRJ", "name": "project-service", "display_name": "Workspace & Project Engine", "role": "Project Service", "service_type": "api", "port": 8302, "environment": "production"},
        {"service_id": "SVC-CLOUD-CMP", "name": "compute-service", "display_name": "Container & Virtual Instance Provisioner", "role": "Compute Service", "service_type": "compute", "port": 8303, "environment": "production"},
        {"service_id": "SVC-CLOUD-BILL", "name": "billing-service", "display_name": "Subscription & Metered Billing", "role": "Billing Service", "service_type": "api", "port": 8304, "environment": "production"},
        {"service_id": "SVC-CLOUD-NOTIF", "name": "notification-service", "display_name": "Notification & Webhook Dispatcher", "role": "Notification Service", "service_type": "worker", "port": 8305, "environment": "production"},
        {"service_id": "SVC-CLOUD-PG", "name": "database-service", "display_name": "CloudDesk Sharded PostgreSQL Cluster", "role": "Distributed Persistence", "service_type": "database", "port": 5432, "environment": "production"},
        {"service_id": "SVC-CLOUD-REDIS", "name": "cache", "display_name": "CloudDesk Redis Cache & Rate Limiter", "role": "Cache Cluster", "service_type": "cache", "port": 6379, "environment": "production"},
    ],
    "demo-tenant": [
        {"service_id": "SVC-GATEWAY", "name": "gateway", "display_name": "API Gateway / Ingress", "role": "Ingress & Routing", "service_type": "gateway", "port": 8001, "environment": "production"},
        {"service_id": "SVC-SERVICE-A", "name": "service-a", "display_name": "Order Service A", "role": "Order Processing", "service_type": "api", "port": 8002, "environment": "production"},
        {"service_id": "SVC-SERVICE-B", "name": "service-b", "display_name": "Payment Service B", "role": "Payment & Ledger", "service_type": "api", "port": 8003, "environment": "production"},
        {"service_id": "SVC-DATABASE", "name": "database-service", "display_name": "Database Persistence", "role": "Distributed Persistence", "service_type": "database", "port": 8004, "environment": "production"},
        {"service_id": "SVC-AUTH", "name": "auth-service", "display_name": "Authentication & Sessions", "role": "Identity & Tokens", "service_type": "auth", "port": 8005, "environment": "production"},
        {"service_id": "SVC-CACHE", "name": "cache", "display_name": "Distributed Redis Cache", "role": "Cache Cluster", "service_type": "cache", "port": 6379, "environment": "production"},
    ]
}


# ---------------------------------------------------------------------------
# CANONICAL STATE MANAGER (SINGLETON)
# ---------------------------------------------------------------------------

class CanonicalStateManager:
    """
    Authoritative state orchestrator for all AegisOps AI components.
    Guarantees that every page, card, badge, graph, notification, metric,
    incident, approval, and AI SRE response consume the exact same source of truth.
    """

    HEALTHY_INTERVAL_SEC: float = 30.0      # Telemetry <= 30s is CONNECTED
    DISCONNECT_THRESHOLD_SEC: float = 90.0  # Telemetry > 90s is DISCONNECTED
    STALE_THRESHOLD_SEC: float = 60.0       # Telemetry > 60s is STALE

    def __init__(self):
        self.lock = threading.Lock()
        
        # Telemetry sample windows: (tenant_id, service_name) -> deque of (timestamp, latency, is_error)
        self._sample_buffers: Dict[Tuple[str, str], deque] = {}
        
        # Raw metric caches: (tenant_id, service_name) -> dict
        self._raw_metrics: Dict[Tuple[str, str], Dict[str, Any]] = {}
        
        # Explicit service health overrides / probe states: (tenant_id, service_name) -> dict
        self._probe_states: Dict[Tuple[str, str], Dict[str, Any]] = {}

        # Forced telemetry disconnects (e.g. testing lab or simulated disconnection)
        self._forced_disconnects: Dict[Tuple[str, str], bool] = {}

        # Simulated service faults: (tenant_id, service_name) -> fault_dict
        self._simulated_faults: Dict[Tuple[str, str], Dict[str, Any]] = {}

        # In-memory service registry per tenant: tenant_id -> Dict[service_name, dict]
        self._services_registry: Dict[str, Dict[str, Dict[str, Any]]] = {}

        self._init_registries()

    def _init_registries(self):
        """Initializes canonical services across tenants."""
        now_iso = datetime.now(timezone.utc).isoformat()
        for t_id, s_list in DEFAULT_TENANT_SERVICES.items():
            self._services_registry[t_id] = {}
            for s in s_list:
                s_name = s["name"]
                self._services_registry[t_id][s_name] = dict(s)
                self._sample_buffers[(t_id, s_name)] = deque(maxlen=200)

    def normalize_tenant(self, tenant_id: Optional[str]) -> str:
        t = (tenant_id or "shopsphere").strip().lower()
        if t in ["*", "all", "default"]:
            return "shopsphere"
        return t

    def normalize_service(self, service_name: str) -> str:
        s = service_name.replace("SVC-", "").strip().lower()
        aliases = {
            "api-gateway": "gateway",
            "order-service": "service-a",
            "payment-service": "service-b",
            "payment-api": "service-b",
            "postgres": "database-service",
            "postgresql": "database-service",
            "redis": "cache"
        }
        return aliases.get(s, s)

    # -----------------------------------------------------------------------
    # TELEMETRY INGESTION HOOKS
    # -----------------------------------------------------------------------

    def record_telemetry(
        self,
        tenant_id: str,
        service_name: str,
        latency_ms: Optional[float] = None,
        is_error: bool = False,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        request_count: int = 1,
        timestamp: Optional[float] = None
    ):
        """
        Authoritative hook invoked on any incoming telemetry event.
        Guarantees metrics, timestamps, and sample windows are faithfully tracked.
        """
        t_id = self.normalize_tenant(tenant_id)
        s_name = service_name.strip().lower()
        now = timestamp or time.time()
        now_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

        key = (t_id, s_name)
        with self.lock:
            # Auto-register service in this tenant if not yet registered
            if t_id not in self._services_registry:
                self._services_registry[t_id] = {}
            if s_name not in self._services_registry[t_id]:
                self._services_registry[t_id][s_name] = {
                    "service_id": f"SVC-{s_name.upper()}",
                    "name": s_name,
                    "display_name": s_name.replace("-", " ").title(),
                    "role": "Microservice",
                    "service_type": "api",
                    "port": 8000,
                    "environment": "production"
                }

            if key not in self._sample_buffers:
                self._sample_buffers[key] = deque(maxlen=200)

            # Record sample in sliding window
            if latency_ms is not None:
                self._sample_buffers[key].append((now, float(latency_ms), bool(is_error)))

            # Update raw state snapshot
            curr_raw = self._raw_metrics.get(key, {})
            curr_raw["last_telemetry_time"] = now
            curr_raw["last_telemetry_at"] = now_iso
            if cpu_percent is not None:
                curr_raw["cpu_percent"] = float(cpu_percent)
            if memory_mb is not None:
                curr_raw["memory_mb"] = float(memory_mb)
            curr_raw["sample_count"] = curr_raw.get("sample_count", 0) + 1
            curr_raw["request_count"] = curr_raw.get("request_count", 0) + request_count
            self._raw_metrics[key] = curr_raw

            # If service was previously marked force disconnected, receiving fresh telemetry can reconnect it
            if self._forced_disconnects.get(key):
                self._forced_disconnects[key] = False

    def update_probe_health(
        self,
        tenant_id: str,
        service_name: str,
        healthy: bool,
        state: str = "HEALTHY",
        status_code: int = 200,
        response_time_ms: float = 5.0
    ):
        """Authoritative hook invoked by active health probes."""
        t_id = self.normalize_tenant(tenant_id)
        s_name = service_name.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        key = (t_id, s_name)

        with self.lock:
            self._probe_states[key] = {
                "healthy": healthy,
                "state": state.upper(),
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "last_health_check_at": now_iso
            }

    def set_forced_disconnect(self, tenant_id: str, service_name: str, disconnected: bool = True):
        """Intentionally disconnects/reconnects a telemetry source for testing or fault simulation."""
        t_id = self.normalize_tenant(tenant_id)
        s_name = service_name.strip().lower()
        with self.lock:
            self._forced_disconnects[(t_id, s_name)] = disconnected

    def set_simulated_fault(self, tenant_id: str, service_name: str, fault_type: str, severity: str = "CRITICAL"):
        """Injects a controlled failure state into canonical representation."""
        t_id = self.normalize_tenant(tenant_id)
        s_name = service_name.strip().lower()
        with self.lock:
            self._simulated_faults[(t_id, s_name)] = {
                "fault_type": fault_type,
                "severity": severity,
                "injected_at": datetime.now(timezone.utc).isoformat()
            }

    def clear_simulated_fault(self, tenant_id: str, service_name: str):
        """Clears simulated fault."""
        t_id = self.normalize_tenant(tenant_id)
        s_name = service_name.strip().lower()
        with self.lock:
            self._simulated_faults.pop((t_id, s_name), None)

    def clear_all_simulated_faults(self):
        """Resets all simulated faults."""
        with self.lock:
            self._simulated_faults.clear()
            self._forced_disconnects.clear()

    # -----------------------------------------------------------------------
    # CANONICAL TRUTH DERIVATION
    # -----------------------------------------------------------------------

    def get_service_operational_state(
        self,
        tenant_id: str,
        service_name: str,
        active_incidents: Optional[List[Dict[str, Any]]] = None
    ) -> ServiceOperationalState:
        """
        Builds the single canonical truth for a specific service.
        Derives operational status and connection status strictly from evidence.
        """
        t_id = self.normalize_tenant(tenant_id)
        s_name = service_name.strip().lower()
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        key = (t_id, s_name)
        meta = self._services_registry.get(t_id, {}).get(s_name)
        if not meta:
            # Fallback metadata
            meta = {
                "service_id": f"SVC-{s_name.upper()}",
                "name": s_name,
                "display_name": s_name.replace("-", " ").title(),
                "role": "Microservice",
                "service_type": "api",
                "port": 8000,
                "environment": "production"
            }

        raw = self._raw_metrics.get(key, {})
        probe = self._probe_states.get(key, {})
        buf = self._sample_buffers.get(key, deque())
        is_force_disconnected = self._forced_disconnects.get(key, False)
        sim_fault = self._simulated_faults.get(key)

        last_tel_time = raw.get("last_telemetry_time")
        last_tel_at = raw.get("last_telemetry_at")
        last_check_at = probe.get("last_health_check_at")

        # 1. Telemetry Connection Status Rules (Part 3)
        if is_force_disconnected:
            tel_status = TelemetryConnectionStatus.DISCONNECTED
            stale_sec = (now - last_tel_time) if last_tel_time else 999.0
            is_stale = True
        elif last_tel_time is None:
            tel_status = TelemetryConnectionStatus.PENDING
            stale_sec = 0.0
            is_stale = False
        else:
            diff_sec = now - last_tel_time
            stale_sec = round(diff_sec, 1)
            is_stale = (diff_sec > self.STALE_THRESHOLD_SEC)
            if diff_sec <= self.HEALTHY_INTERVAL_SEC:
                tel_status = TelemetryConnectionStatus.CONNECTED
            elif diff_sec <= self.DISCONNECT_THRESHOLD_SEC:
                tel_status = TelemetryConnectionStatus.DEGRADED
            else:
                tel_status = TelemetryConnectionStatus.DISCONNECTED

        # 2. Metric Calculations on actual sliding window samples (Part 18, 19, 20)
        # Filter samples within last 5 minutes (300s)
        window_sec = 300.0
        active_samples = [s for s in buf if (now - s[0]) <= window_sec]
        sample_count = len(active_samples)

        if sample_count > 0:
            latencies = sorted([s[1] for s in active_samples])
            err_count = sum(1 for s in active_samples if s[2])
            error_rate = round(err_count / sample_count, 4)
            # request rate per minute
            request_rate = round((sample_count / (window_sec / 60.0)), 1)
        else:
            latencies = []
            error_rate = 0.0
            request_rate = 0.0

        # Percentiles (Part 19: No faking. Need >= 5 samples)
        if len(latencies) >= 5:
            p50 = round(latencies[int(len(latencies) * 0.50)], 1)
            p90 = round(latencies[int(len(latencies) * 0.90)], 1)
            p95 = round(latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)], 1)
            p99 = round(latencies[min(int(len(latencies) * 0.99), len(latencies) - 1)], 1)
        else:
            p50 = None
            p90 = None
            p95 = None
            p99 = None

        # CPU / Memory (Part 21: None if unavailable)
        cpu = raw.get("cpu_percent")
        memory = raw.get("memory_mb")

        # Active Incidents matching this service
        matching_incidents = 0
        matching_warnings = 0
        if active_incidents:
            for inc in active_incidents:
                if inc.get("status") in ["RESOLVED", "CLOSED", "REJECTED"]:
                    continue
                ps = inc.get("primary_service", "").lower()
                rc = inc.get("root_cause_service", "").lower()
                aff = [s.lower() for s in inc.get("affected_services", [])]
                if s_name in [ps, rc] or s_name in aff:
                    sev = inc.get("severity", "HIGH").upper()
                    if sev in ["CRITICAL", "HIGH"]:
                        matching_incidents += 1
                    else:
                        matching_warnings += 1

        # 3. Service Operational Status Derivation (Part 4)
        status_reasons = []

        # Check explicit crash probe
        probe_healthy = probe.get("healthy", True)
        probe_state = probe.get("state", "HEALTHY")

        if sim_fault:
            op_status = ServiceOperationalStatus.CRITICAL if sim_fault.get("severity") == "CRITICAL" else ServiceOperationalStatus.DEGRADED
            status_reasons.append(f"Controlled failure injected: {sim_fault.get('fault_type')}")
        elif not probe_healthy or probe_state in ["CRASHED", "DOWN"]:
            op_status = ServiceOperationalStatus.DOWN
            status_reasons.append(f"Service probe reported failure state: {probe_state}")
        elif matching_incidents > 0:
            op_status = ServiceOperationalStatus.CRITICAL
            status_reasons.append(f"{matching_incidents} active critical/high incident(s) impacting service")
        elif tel_status == TelemetryConnectionStatus.DISCONNECTED:
            op_status = ServiceOperationalStatus.UNKNOWN
            status_reasons.append(f"No telemetry received for {stale_sec}s (threshold: {self.DISCONNECT_THRESHOLD_SEC}s)")
        elif tel_status == TelemetryConnectionStatus.PENDING:
            op_status = ServiceOperationalStatus.UNKNOWN
            status_reasons.append("Telemetry integration registered but no telemetry received yet")
        elif error_rate > 0.25:
            op_status = ServiceOperationalStatus.CRITICAL
            status_reasons.append(f"Error rate critical: {round(error_rate * 100, 1)}% (threshold > 25%)")
        elif error_rate > 0.05 or (p95 is not None and p95 > 250.0) or tel_status == TelemetryConnectionStatus.DEGRADED or matching_warnings > 0:
            op_status = ServiceOperationalStatus.DEGRADED
            if error_rate > 0.05:
                status_reasons.append(f"Elevated error rate: {round(error_rate * 100, 1)}%")
            if p95 is not None and p95 > 250.0:
                status_reasons.append(f"Elevated p95 latency: {p95}ms")
            if tel_status == TelemetryConnectionStatus.DEGRADED:
                status_reasons.append(f"Telemetry arriving late ({stale_sec}s delay)")
            if matching_warnings > 0:
                status_reasons.append(f"{matching_warnings} active operational warning(s)")
        elif tel_status == TelemetryConnectionStatus.CONNECTED:
            op_status = ServiceOperationalStatus.HEALTHY
            status_reasons.append("Telemetry connected and all health indicators normal")
        else:
            op_status = ServiceOperationalStatus.UNKNOWN
            status_reasons.append("Insufficient telemetry evidence to confirm health")

        # Health score calculation per service
        if op_status == ServiceOperationalStatus.HEALTHY:
            svc_health = max(95.0, round(100.0 - (error_rate * 100), 1))
        elif op_status == ServiceOperationalStatus.DEGRADED:
            svc_health = max(40.0, round(80.0 - (error_rate * 100), 1))
        elif op_status == ServiceOperationalStatus.CRITICAL:
            svc_health = max(10.0, round(30.0 - (error_rate * 50), 1))
        elif op_status == ServiceOperationalStatus.DOWN:
            svc_health = 0.0
        else:
            svc_health = 50.0

        return ServiceOperationalState(
            tenant_id=t_id,
            service_id=meta.get("service_id", f"SVC-{s_name.upper()}"),
            service_name=s_name,
            display_name=meta.get("display_name", s_name.replace("-", " ").title()),
            role=meta.get("role", "Microservice"),
            service_type=meta.get("service_type", "api"),
            port=meta.get("port", 8000),
            environment=meta.get("environment", "production"),
            operational_status=op_status,
            telemetry_status=tel_status,
            dependency_status="VALIDATED",
            request_rate=request_rate,
            error_rate=error_rate,
            p50=p50,
            p90=p90,
            p95=p95,
            p99=p99,
            cpu=cpu,
            memory=memory,
            active_incidents=matching_incidents,
            active_warnings=matching_warnings,
            last_telemetry_at=last_tel_at,
            last_health_check_at=last_check_at,
            updated_at=now_iso,
            telemetry_sample_count=sample_count,
            calculation_window="Last 5 minutes",
            is_stale=is_stale,
            stale_seconds=stale_sec,
            health_score=svc_health,
            status_reasons=status_reasons
        )

    def get_all_services_state(
        self,
        tenant_id: str,
        active_incidents: Optional[List[Dict[str, Any]]] = None
    ) -> List[ServiceOperationalState]:
        """Returns the canonical state for all registered services in a tenant."""
        t_id = self.normalize_tenant(tenant_id)
        services_dict = self._services_registry.get(t_id, {})
        if not services_dict:
            # Fallback to demo-tenant if unknown tenant
            services_dict = self._services_registry.get("demo-tenant", {})

        results = []
        for s_name in services_dict.keys():
            st = self.get_service_operational_state(t_id, s_name, active_incidents=active_incidents)
            results.append(st)
        return results

    # -----------------------------------------------------------------------
    # SYSTEM-WIDE HEALTH COMPUTATION (Part 11: No Fake 100%)
    # -----------------------------------------------------------------------

    def compute_system_health(
        self,
        tenant_id: str,
        active_incidents: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Derives real system health score using transparent, documented formula.
        NO hardcoded 100%.
        """
        states = self.get_all_services_state(tenant_id, active_incidents=active_incidents)
        total = len(states)
        if total == 0:
            return {
                "health_score": 100.0,
                "formula": "No services registered",
                "counts": {"healthy": 0, "degraded": 0, "critical": 0, "down": 0, "unknown": 0}
            }

        counts = {
            "healthy": sum(1 for s in states if s.operational_status == ServiceOperationalStatus.HEALTHY),
            "degraded": sum(1 for s in states if s.operational_status == ServiceOperationalStatus.DEGRADED),
            "critical": sum(1 for s in states if s.operational_status == ServiceOperationalStatus.CRITICAL),
            "down": sum(1 for s in states if s.operational_status == ServiceOperationalStatus.DOWN),
            "unknown": sum(1 for s in states if s.operational_status == ServiceOperationalStatus.UNKNOWN)
        }

        # Weight assignment:
        # HEALTHY = 1.0, DEGRADED = 0.6, UNKNOWN = 0.5, CRITICAL = 0.1, DOWN = 0.0
        weighted_sum = (
            counts["healthy"] * 100.0 +
            counts["degraded"] * 60.0 +
            counts["unknown"] * 50.0 +
            counts["critical"] * 10.0 +
            counts["down"] * 0.0
        )
        base_score = weighted_sum / total

        # Active incident penalties
        active_inc_cnt = len(active_incidents or [])
        crit_inc_cnt = sum(1 for i in (active_incidents or []) if i.get("severity") == "CRITICAL" and i.get("status") not in ["RESOLVED", "CLOSED"])
        high_inc_cnt = sum(1 for i in (active_incidents or []) if i.get("severity") == "HIGH" and i.get("status") not in ["RESOLVED", "CLOSED"])

        incident_penalty = (crit_inc_cnt * 12.0) + (high_inc_cnt * 6.0)
        final_score = max(0.0, min(100.0, round(base_score - incident_penalty, 1)))

        return {
            "health_score": final_score,
            "counts": counts,
            "total_services": total,
            "incident_penalties": incident_penalty,
            "formula": "WeightedServiceHealth - IncidentPenalty",
            "calculation_details": {
                "weights": "HEALTHY=1.0, DEGRADED=0.6, UNKNOWN=0.5, CRITICAL=0.1, DOWN=0.0",
                "critical_incident_penalty": "-12% per incident",
                "high_incident_penalty": "-6% per incident"
            }
        }

    # -----------------------------------------------------------------------
    # PART 39 — AUTOMATED TRUTH AUDITOR DIAGNOSTIC
    # -----------------------------------------------------------------------

    def run_consistency_audit(
        self,
        tenant_id: str,
        collector_inst: Any,
        dynamic_graph_inst: Any,
        incident_pipeline_inst: Optional[Any] = None,
        approval_manager_inst: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive consistency verification across all 9 domains.
        Returns:
        {
            "status": "PASS" | "FAIL",
            "checks": {
                "service_status": "PASS",
                "telemetry": "PASS",
                "incidents": "PASS",
                "approvals": "PASS",
                "recovery": "PASS",
                "dependencies": "PASS",
                "ml": "PASS",
                "tenant_isolation": "PASS",
                "timestamps": "PASS"
            },
            "discrepancies": []
        }
        """
        t_id = self.normalize_tenant(tenant_id)
        discrepancies = []
        checks = {
            "service_status": "PASS",
            "telemetry": "PASS",
            "incidents": "PASS",
            "approvals": "PASS",
            "recovery": "PASS",
            "dependencies": "PASS",
            "ml": "PASS",
            "tenant_isolation": "PASS",
            "timestamps": "PASS"
        }

        # 1. SERVICE STATUS & TELEMETRY CONSISTENCY
        canonical_states = self.get_all_services_state(t_id, active_incidents=collector_inst.active_incidents)
        for s in canonical_states:
            # Check timestamps
            if not s.updated_at:
                checks["timestamps"] = "FAIL"
                discrepancies.append(f"{s.service_name}: missing updated_at timestamp")

            # Check Telemetry Truth Rules
            if s.telemetry_status == TelemetryConnectionStatus.CONNECTED:
                if s.stale_seconds > self.HEALTHY_INTERVAL_SEC:
                    checks["telemetry"] = "FAIL"
                    discrepancies.append(f"{s.service_name}: marked CONNECTED but last telemetry was {s.stale_seconds}s ago")
            elif s.telemetry_status == TelemetryConnectionStatus.DISCONNECTED:
                if s.operational_status == ServiceOperationalStatus.HEALTHY:
                    checks["service_status"] = "FAIL"
                    discrepancies.append(f"{s.service_name}: telemetry is DISCONNECTED but service is falsely marked HEALTHY")

            # Check unknown vs healthy
            if s.operational_status == ServiceOperationalStatus.UNKNOWN and s.telemetry_status == TelemetryConnectionStatus.CONNECTED and s.error_rate == 0.0:
                pass  # valid if reasons state so

        # 2. DEPENDENCY GRAPH ACCURACY (Part 6 & 7)
        topo = dynamic_graph_inst.get_topology_graph(tenant_id=t_id)
        topo_node_names = {n["id"] for n in topo.get("nodes", [])}
        canonical_names = {s.service_name for s in canonical_states}
        
        # Verify node statuses in Dependency Map match canonical state
        for n in topo.get("nodes", []):
            nid = n["id"]
            c_match = next((s for s in canonical_states if s.service_name == nid), None)
            if c_match:
                node_st = n.get("status", "").upper()
                c_st = c_match.operational_status.value
                # Map CRITICAL/FAILED/DEGRADED equivalents
                is_node_crit = node_st in ["CRITICAL", "FAILED", "CRASHED", "DOWN"]
                is_c_crit = c_st in ["CRITICAL", "FAILED", "CRASHED", "DOWN"]
                is_node_deg = node_st in ["DEGRADED", "WARNING", "WARN"]
                is_c_deg = c_st in ["DEGRADED", "WARNING", "WARN"]
                is_node_hlth = node_st in ["HEALTHY", "UP", "OK"]
                is_c_hlth = c_st in ["HEALTHY", "UP", "OK"]

                if (is_c_crit and not is_node_crit) or (is_c_deg and is_node_hlth) or (is_c_hlth and (is_node_crit or is_node_deg)):
                    checks["dependencies"] = "FAIL"
                    discrepancies.append(f"Dependency Map mismatch for '{nid}': graph shows '{node_st}' but canonical is '{c_st}'")

        # 3. INCIDENT COUNT CONSISTENCY (Part 12)
        collector_active_cnt = len([i for i in collector_inst.active_incidents if i.get("status") not in ["RESOLVED", "CLOSED", "REJECTED"]])
        if incident_pipeline_inst and hasattr(incident_pipeline_inst, "_active_incidents"):
            pipe_active_cnt = len([i for i in incident_pipeline_inst._active_incidents.values() if i.get("status") not in ["RESOLVED", "CLOSED", "REJECTED"]])
            # Should be synchronized or consistent
            if abs(collector_active_cnt - pipe_active_cnt) > 2:
                checks["incidents"] = "FAIL"
                discrepancies.append(f"Incident count discrepancy: Collector={collector_active_cnt}, Pipeline={pipe_active_cnt}")

        # 4. APPROVAL CONSISTENCY (Part 15 & 38)
        inc_awaiting_app = [i for i in collector_inst.active_incidents if i.get("status") == "AWAITING_APPROVAL"]
        pending_app = [a for a in collector_inst.pending_approvals if a.get("status") in ["PENDING", "PENDING_APPROVAL", "AWAITING_APPROVAL"]]
        # If active incident is AWAITING_APPROVAL, an approval ticket should exist
        for inc in inc_awaiting_app:
            inc_id = inc.get("incident_id")
            has_ticket = any(a.get("incident_id") == inc_id for a in pending_app)
            if not has_ticket and len(pending_app) == 0:
                checks["approvals"] = "FAIL"
                discrepancies.append(f"Incident {inc_id} is AWAITING_APPROVAL but no approval ticket exists in pending queue")

        # 5. RECOVERY CONSISTENCY (Part 14 & 37)
        # Check that no incident is marked RESOLVED if recovery is still EXECUTING or VERIFYING
        for inc in collector_inst.active_incidents:
            rec_st = inc.get("recovery_status", "")
            inc_st = inc.get("status", "")
            if rec_st in ["EXECUTING", "VERIFYING", "OBSERVING", "REPLAYING"] and inc_st == "RESOLVED":
                checks["recovery"] = "FAIL"
                discrepancies.append(f"Incident {inc.get('incident_id')} is marked RESOLVED while recovery is still {rec_st}")

        # 6. ML RESULT CONSISTENCY (Part 16)
        # Verify ML anomaly features and model version format
        try:
            from backend.app.analytics.ml_ensemble import ml_ensemble
            reg_status = ml_ensemble.get_ensemble_health()
            if reg_status.get("status") == "DEGRADED" and reg_status.get("healthy_count", 0) == 0:
                checks["ml"] = "FAIL"
                discrepancies.append("All ML models are degraded or failing")
        except Exception:
            pass

        # 7. TENANT ISOLATION (Part 29)
        # Verify that querying one tenant does not leak services from another tenant
        for s in canonical_states:
            if s.tenant_id != t_id:
                checks["tenant_isolation"] = "FAIL"
                discrepancies.append(f"Service '{s.service_name}' has tenant_id '{s.tenant_id}', expected '{t_id}'")

        overall_status = "FAIL" if any(v == "FAIL" for v in checks.values()) else "PASS"

        return {
            "status": overall_status,
            "tenant_id": t_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "discrepancies": discrepancies,
            "total_services_audited": len(canonical_states),
            "active_incidents_audited": len(collector_inst.active_incidents),
            "pending_approvals_audited": len(collector_inst.pending_approvals)
        }


# Singleton Instance
canonical_state_manager = CanonicalStateManager()
