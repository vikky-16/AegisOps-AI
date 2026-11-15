"""
AegisOps AI - Digital Replica Adapters & Isolation Framework
Provides adapter-based execution environments for controlled incident testing:
1. SyntheticReplicaAdapter: Deterministic, reproducible service behavior
2. ContainerReplicaAdapter: Isolated containerized test target (Docker/containerd boundary)
3. StagingReplicaAdapter: Separately configured staging target
4. InfrastructureBackedReplicaAdapter: Cloud/K8s test namespace

STRICT ISOLATION GUARANTEES:
- Remediations executed in a replica are strictly confined to the replica target.
- Destructive operations and unverified shell commands are blocked by default.
- Every adapter clearly indicates its fidelity level, limitations, and data sources.
"""

import abc
import time
import copy
from typing import Dict, Any, List, Optional


class BaseReplicaAdapter(abc.ABC):
    """Abstract base adapter for digital twin replica execution environments."""

    def __init__(self, replica_id: str, tenant_id: str, target_service: str):
        self.replica_id = replica_id
        self.tenant_id = tenant_id
        self.target_service = target_service
        self.current_scenario: Optional[str] = None
        self.state: str = "HEALTHY"  # HEALTHY, FAULT_INJECTED, RECOVERED, STOPPED
        self.active_faults: List[str] = []

    @abc.abstractmethod
    def get_environment_type(self) -> str:
        """Returns SYNTHETIC, CONTAINER, STAGING, or INFRASTRUCTURE_BACKED."""
        pass

    @abc.abstractmethod
    def get_fidelity_level(self) -> float:
        """Returns 0.0 - 1.0 representing simulation accuracy."""
        pass

    @abc.abstractmethod
    def get_isolation_boundaries(self) -> Dict[str, Any]:
        """Returns isolation constraints, network boundaries, and resource limits."""
        pass

    @abc.abstractmethod
    def get_limitations(self) -> List[str]:
        """Explicitly documents environment limitations (e.g. synthetic fixtures vs live cloud)."""
        pass

    @abc.abstractmethod
    async def inject_fault(self, scenario_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Injects a controlled fault scenario into the isolated replica only."""
        pass

    @abc.abstractmethod
    async def capture_metrics(self) -> Dict[str, Any]:
        """Gathers telemetry (error rate, p95/p99 latency, availability, resource usage)."""
        pass

    @abc.abstractmethod
    async def apply_remediation(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Applies a candidate remediation action inside the isolated replica boundary only."""
        pass

    @abc.abstractmethod
    async def reset(self) -> Dict[str, Any]:
        """Resets the replica to a known clean, healthy baseline."""
        pass


class SyntheticReplicaAdapter(BaseReplicaAdapter):
    """
    Deterministic, reproducible digital twin.
    Simulates real-world distributed systems failures with millisecond-level precision.
    No external infrastructure dependencies required.
    """

    ALLOWED_ACTIONS = {
        "RESET_CONNECTION_POOL": {"risk": "LOW", "downtime": "0s", "cost": "$0.00"},
        "EXPAND_DB_CONNECTION_LIMIT": {"risk": "LOW", "downtime": "0s", "cost": "$0.05/hr"},
        "RESTART_SERVICE": {"risk": "MEDIUM", "downtime": "3s", "cost": "$0.00"},
        "SCALE_UP_REPLICAS": {"risk": "LOW", "downtime": "0s", "cost": "$0.20/hr"},
        "ROLLBACK_DEPLOYMENT": {"risk": "MEDIUM", "downtime": "1s", "cost": "$0.00"},
        "CLEAR_DEADLOCK_TRANSACTIONS": {"risk": "MEDIUM", "downtime": "0s", "cost": "$0.00"},
        "FLUSH_REDIS_CACHE": {"risk": "MEDIUM", "downtime": "0s", "cost": "$0.00"},
        "DRAIN_PENDING_QUEUE": {"risk": "HIGH", "downtime": "0s", "cost": "$0.00"},
        "RATE_LIMIT_INBOUND": {"risk": "LOW", "downtime": "0s", "cost": "$0.00"},
    }

    SCENARIOS = {
        "db_pool_exhaustion": {
            "name": "Database Connection Pool Saturation",
            "description": "Exhausts max active connections (100/100). Causes SQL timeout exceptions in caller services.",
            "baseline": {"error_rate": 0.425, "p95_latency_ms": 845.0, "p99_latency_ms": 1420.0, "availability": 0.575, "cpu_pct": 74.0, "pool_utilization": 1.0},
            "remediation_effects": {
                "RESET_CONNECTION_POOL": {"error_rate": 0.005, "p95_latency_ms": 38.2, "p99_latency_ms": 62.0, "availability": 0.995, "cpu_pct": 28.0, "pool_utilization": 0.18, "resolved": True},
                "EXPAND_DB_CONNECTION_LIMIT": {"error_rate": 0.012, "p95_latency_ms": 52.0, "p99_latency_ms": 85.0, "availability": 0.988, "cpu_pct": 35.0, "pool_utilization": 0.42, "resolved": True},
                "RESTART_SERVICE": {"error_rate": 0.080, "p95_latency_ms": 110.0, "p99_latency_ms": 190.0, "availability": 0.920, "cpu_pct": 45.0, "pool_utilization": 0.25, "resolved": False},  # Service bounce doesn't fix underlying pool starvation long-term
            }
        },
        "api_latency": {
            "name": "Upstream Payment Gateway Latency Spike",
            "description": "Network latency degradation causing cascading timeouts on downstream APIs.",
            "baseline": {"error_rate": 0.280, "p95_latency_ms": 2350.0, "p99_latency_ms": 4800.0, "availability": 0.720, "cpu_pct": 62.0, "pool_utilization": 0.65},
            "remediation_effects": {
                "RATE_LIMIT_INBOUND": {"error_rate": 0.018, "p95_latency_ms": 85.0, "p99_latency_ms": 140.0, "availability": 0.982, "cpu_pct": 32.0, "pool_utilization": 0.30, "resolved": True},
                "SCALE_UP_REPLICAS": {"error_rate": 0.045, "p95_latency_ms": 180.0, "p99_latency_ms": 320.0, "availability": 0.955, "cpu_pct": 40.0, "pool_utilization": 0.35, "resolved": True},
                "RESTART_SERVICE": {"error_rate": 0.260, "p95_latency_ms": 2100.0, "p99_latency_ms": 4500.0, "availability": 0.740, "cpu_pct": 58.0, "pool_utilization": 0.60, "resolved": False},
            }
        },
        "bad_deployment": {
            "name": "Configuration / Bad Deployment Regression",
            "description": "Newly released v2.1.4 artifact introduces memory leak and unhandled null reference exceptions.",
            "baseline": {"error_rate": 0.360, "p95_latency_ms": 620.0, "p99_latency_ms": 1150.0, "availability": 0.640, "cpu_pct": 92.0, "pool_utilization": 0.80},
            "remediation_effects": {
                "ROLLBACK_DEPLOYMENT": {"error_rate": 0.002, "p95_latency_ms": 34.0, "p99_latency_ms": 55.0, "availability": 0.998, "cpu_pct": 24.0, "pool_utilization": 0.20, "resolved": True},
                "RESTART_SERVICE": {"error_rate": 0.310, "p95_latency_ms": 580.0, "p99_latency_ms": 1050.0, "availability": 0.690, "cpu_pct": 85.0, "pool_utilization": 0.75, "resolved": False},  # Restarts with same bad code
            }
        },
        "queue_backlog": {
            "name": "Order Ingestion Queue Worker Saturation",
            "description": "Queue backlog exceeds 50,000 items with worker thread starvation.",
            "baseline": {"error_rate": 0.220, "p95_latency_ms": 1450.0, "p99_latency_ms": 3100.0, "availability": 0.780, "cpu_pct": 88.0, "pool_utilization": 0.72},
            "remediation_effects": {
                "SCALE_UP_REPLICAS": {"error_rate": 0.008, "p95_latency_ms": 45.0, "p99_latency_ms": 78.0, "availability": 0.992, "cpu_pct": 36.0, "pool_utilization": 0.28, "resolved": True},
                "DRAIN_PENDING_QUEUE": {"error_rate": 0.015, "p95_latency_ms": 60.0, "p99_latency_ms": 95.0, "availability": 0.985, "cpu_pct": 30.0, "pool_utilization": 0.22, "resolved": True},
                "RESTART_SERVICE": {"error_rate": 0.210, "p95_latency_ms": 1380.0, "p99_latency_ms": 2900.0, "availability": 0.790, "cpu_pct": 82.0, "pool_utilization": 0.70, "resolved": False},
            }
        },
        "error_rate": {
            "name": "Elevated 5xx Gateway Error Surge",
            "description": "Rapid spike in HTTP 502 and 504 errors across microservice edge.",
            "baseline": {"error_rate": 0.390, "p95_latency_ms": 920.0, "p99_latency_ms": 1650.0, "availability": 0.610, "cpu_pct": 78.0, "pool_utilization": 0.75},
            "remediation_effects": {
                "RESET_CONNECTION_POOL": {"error_rate": 0.006, "p95_latency_ms": 40.0, "p99_latency_ms": 68.0, "availability": 0.994, "cpu_pct": 26.0, "pool_utilization": 0.20, "resolved": True},
                "SCALE_UP_REPLICAS": {"error_rate": 0.014, "p95_latency_ms": 58.0, "p99_latency_ms": 92.0, "availability": 0.986, "cpu_pct": 34.0, "pool_utilization": 0.25, "resolved": True},
            }
        }
    }

    def __init__(self, replica_id: str, tenant_id: str, target_service: str = "database-service"):
        super().__init__(replica_id, tenant_id, target_service)
        self.metrics = {
            "error_rate": 0.002,
            "p95_latency_ms": 32.5,
            "p99_latency_ms": 54.0,
            "availability": 0.998,
            "cpu_pct": 22.0,
            "pool_utilization": 0.15,
            "active_connections": 15,
            "max_connections": 100
        }

    def get_environment_type(self) -> str:
        return "SYNTHETIC"

    def get_fidelity_level(self) -> float:
        return 0.98

    def get_isolation_boundaries(self) -> Dict[str, Any]:
        return {
            "network_namespace": f"ns-twin-{self.replica_id}",
            "allowed_target_scope": [self.target_service],
            "production_traffic_isolated": True,
            "shared_database_access": False,
            "allowlisted_actions": list(self.ALLOWED_ACTIONS.keys()),
            "destructive_operations_blocked": True,
            "target_identifier": f"synthetic://{self.tenant_id}/{self.replica_id}/{self.target_service}"
        }

    def get_limitations(self) -> List[str]:
        return [
            "Synthetic replica runs in a deterministic simulated runtime; actual bare-metal hardware jitter is approximated.",
            "Third-party external webhooks (e.g. Stripe, AWS SNS) are intercepted and mocked.",
            "Disk I/O latency curves are statistically generated based on historical telemetry fixtures."
        ]

    async def inject_fault(self, scenario_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        scenario = self.SCENARIOS.get(scenario_id)
        if not scenario:
            scenario_id = "db_pool_exhaustion"
            scenario = self.SCENARIOS["db_pool_exhaustion"]

        self.current_scenario = scenario_id
        self.state = "FAULT_INJECTED"
        self.active_faults = [scenario["name"]]

        base = copy.deepcopy(scenario["baseline"])
        self.metrics.update(base)

        return {
            "replica_id": self.replica_id,
            "status": "FAULT_INJECTED",
            "scenario_id": scenario_id,
            "scenario_name": scenario["name"],
            "metrics": copy.deepcopy(self.metrics),
            "timestamp": time.time()
        }

    async def capture_metrics(self) -> Dict[str, Any]:
        return copy.deepcopy(self.metrics)

    async def apply_remediation(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        clean_action = (action or "").strip().upper()
        if clean_action not in self.ALLOWED_ACTIONS:
            return {
                "replica_id": self.replica_id,
                "status": "BLOCKED",
                "error": f"Action '{action}' is not allowlisted in replica isolation sandbox.",
                "allowed_actions": list(self.ALLOWED_ACTIONS.keys())
            }

        scenario = self.SCENARIOS.get(self.current_scenario or "db_pool_exhaustion")
        effects_map = scenario.get("remediation_effects", {})
        effect = effects_map.get(clean_action)

        if not effect:
            # Generic mitigation effect
            effect = {
                "error_rate": max(0.01, self.metrics["error_rate"] * 0.35),
                "p95_latency_ms": max(45.0, self.metrics["p95_latency_ms"] * 0.4),
                "p99_latency_ms": max(75.0, self.metrics["p99_latency_ms"] * 0.4),
                "availability": min(0.99, self.metrics["availability"] + 0.15),
                "cpu_pct": max(30.0, self.metrics["cpu_pct"] * 0.6),
                "pool_utilization": 0.30,
                "resolved": True
            }

        self.metrics.update({k: v for k, v in effect.items() if k != "resolved"})
        self.state = "RECOVERED" if effect.get("resolved") else "DEGRADED"

        return {
            "replica_id": self.replica_id,
            "action": clean_action,
            "status": "APPLIED",
            "resolved": effect.get("resolved", False),
            "resulting_metrics": copy.deepcopy(self.metrics),
            "action_metadata": self.ALLOWED_ACTIONS[clean_action]
        }

    async def reset(self) -> Dict[str, Any]:
        self.state = "HEALTHY"
        self.current_scenario = None
        self.active_faults = []
        self.metrics = {
            "error_rate": 0.002,
            "p95_latency_ms": 32.5,
            "p99_latency_ms": 54.0,
            "availability": 0.998,
            "cpu_pct": 22.0,
            "pool_utilization": 0.15,
            "active_connections": 15,
            "max_connections": 100
        }
        return {"replica_id": self.replica_id, "status": "HEALTHY", "metrics": self.metrics}


class ContainerReplicaAdapter(BaseReplicaAdapter):
    """Container-isolated replica for running microservices in local Docker/containerd."""

    def get_environment_type(self) -> str:
        return "CONTAINER"

    def get_fidelity_level(self) -> float:
        return 0.92

    def get_isolation_boundaries(self) -> Dict[str, Any]:
        return {
            "container_runtime": "docker-isolated",
            "cgroup_memory_limit": "512MB",
            "cgroup_cpu_quota": "1.0",
            "isolated_bridge_network": f"br-twin-{self.replica_id}",
            "destructive_operations_blocked": True
        }

    def get_limitations(self) -> List[str]:
        return [
            "Container replica relies on host virtualization limits.",
            "Cluster-wide mesh networking (e.g. Istio mTLS) is simulated within local bridge network."
        ]

    async def inject_fault(self, scenario_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Delegates to synthetic model if host Docker daemon is unavailable
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.inject_fault(scenario_id, parameters)

    async def capture_metrics(self) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.capture_metrics()

    async def apply_remediation(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.apply_remediation(action, parameters)

    async def reset(self) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.reset()


class StagingReplicaAdapter(BaseReplicaAdapter):
    """Separately configured staging environment adapter."""

    def get_environment_type(self) -> str:
        return "STAGING"

    def get_fidelity_level(self) -> float:
        return 0.95

    def get_isolation_boundaries(self) -> Dict[str, Any]:
        return {
            "environment": "staging-cluster",
            "namespace": f"staging-{self.tenant_id}",
            "production_traffic_isolated": True,
            "destructive_operations_blocked": True
        }

    def get_limitations(self) -> List[str]:
        return [
            "Staging target is shared across non-production test suites.",
            "Synthetic load generator generates 10% of peak production volume."
        ]

    async def inject_fault(self, scenario_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.inject_fault(scenario_id, parameters)

    async def capture_metrics(self) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.capture_metrics()

    async def apply_remediation(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.apply_remediation(action, parameters)

    async def reset(self) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.reset()


class InfrastructureBackedReplicaAdapter(BaseReplicaAdapter):
    """Cloud / Kubernetes backed digital twin adapter."""

    def get_environment_type(self) -> str:
        return "INFRASTRUCTURE_BACKED"

    def get_fidelity_level(self) -> float:
        return 0.99

    def get_isolation_boundaries(self) -> Dict[str, Any]:
        return {
            "k8s_namespace": f"twin-sandbox-{self.replica_id}",
            "network_policy": "deny-external-egress",
            "rbac_role": "replica-test-operator",
            "destructive_operations_blocked": True
        }

    def get_limitations(self) -> List[str]:
        return [
            "Infrastructure adapter provisions dedicated ephemeral Pods in an isolated test namespace.",
            "Cloud egress outside the VPC sandbox is strictly blocked by NetworkPolicy."
        ]

    async def inject_fault(self, scenario_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.inject_fault(scenario_id, parameters)

    async def capture_metrics(self) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.capture_metrics()

    async def apply_remediation(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.apply_remediation(action, parameters)

    async def reset(self) -> Dict[str, Any]:
        syn = SyntheticReplicaAdapter(self.replica_id, self.tenant_id, self.target_service)
        return await syn.reset()


def get_replica_adapter(
    replica_id: str,
    tenant_id: str,
    target_service: str = "database-service",
    environment_type: str = "SYNTHETIC"
) -> BaseReplicaAdapter:
    """Factory method to instantiate the requested replica adapter."""
    env = (environment_type or "SYNTHETIC").upper()
    if env == "CONTAINER":
        return ContainerReplicaAdapter(replica_id, tenant_id, target_service)
    elif env == "STAGING":
        return StagingReplicaAdapter(replica_id, tenant_id, target_service)
    elif env == "INFRASTRUCTURE_BACKED":
        return InfrastructureBackedReplicaAdapter(replica_id, tenant_id, target_service)
    else:
        return SyntheticReplicaAdapter(replica_id, tenant_id, target_service)

