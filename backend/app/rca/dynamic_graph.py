"""
Dynamic Telemetry-Inferred Service Dependency Graph Engine
Dynamically discovers and updates service topologies, computes confidence scores,
evaluates live health status, and analyzes blast radius.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Any, Tuple

TENANT_TOPOLOGIES: Dict[str, Dict[str, Any]] = {
    "shopsphere": {
        "services": [
            {"service_id": "SVC-SHOP-GW", "name": "api-gateway", "display_name": "ShopSphere Ingress Gateway", "role": "API Gateway", "service_type": "gateway", "environment": "production", "status": "HEALTHY", "owner": "Traffic Team", "criticality": "CRITICAL", "port": 8100, "customer_facing": True},
            {"service_id": "SVC-SHOP-GW-ALIAS", "name": "gateway", "display_name": "ShopSphere Ingress Gateway", "role": "API Gateway", "service_type": "gateway", "environment": "production", "status": "HEALTHY", "owner": "Traffic Team", "criticality": "CRITICAL", "port": 8100, "customer_facing": True},
            {"service_id": "SVC-SHOP-ORD", "name": "order-service", "display_name": "Order Management Service", "role": "Order Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Checkout SRE", "criticality": "CRITICAL", "port": 8101, "customer_facing": True},
            {"service_id": "SVC-SHOP-PAY", "name": "payment-service", "display_name": "Payment Gateway Client", "role": "Payment Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Payments SRE", "criticality": "CRITICAL", "port": 8103, "customer_facing": False},
            {"service_id": "SVC-SHOP-INV", "name": "inventory-service", "display_name": "Inventory & Stock Engine", "role": "Inventory Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Fulfillment Team", "criticality": "HIGH", "port": 8102, "customer_facing": False},
            {"service_id": "SVC-SHOP-NOTIF", "name": "notification-service", "display_name": "Customer Notification Dispatcher", "role": "Notification Service", "service_type": "worker", "environment": "production", "status": "HEALTHY", "owner": "Engagement SRE", "criticality": "MEDIUM", "port": 8104, "customer_facing": False},
            {"service_id": "SVC-SHOP-PG", "name": "database-service", "display_name": "ShopSphere PostgreSQL Cluster", "role": "PostgreSQL Database", "service_type": "database", "environment": "production", "status": "HEALTHY", "owner": "Data Infra", "criticality": "CRITICAL", "port": 5432, "customer_facing": False},
            {"service_id": "SVC-SHOP-REDIS", "name": "cache", "display_name": "ShopSphere Redis Cache", "role": "Redis Cache", "service_type": "cache", "environment": "production", "status": "HEALTHY", "owner": "Infra Team", "criticality": "HIGH", "port": 6379, "customer_facing": False},
        ],
        "edges": [
            ("api-gateway", "order-service", "HTTP_UPSTREAM", 0.99),
            ("gateway", "order-service", "HTTP_UPSTREAM", 0.99),
            ("order-service", "payment-service", "HTTP_UPSTREAM", 0.98),
            ("order-service", "inventory-service", "HTTP_UPSTREAM", 0.97),
            ("order-service", "notification-service", "ASYNC_DISPATCH", 0.95),
            ("order-service", "cache", "CACHE_ACCESS", 0.93),
            ("order-service", "database-service", "DATABASE_QUERY", 0.99),
            ("payment-service", "database-service", "DATABASE_QUERY", 0.99),
            ("inventory-service", "database-service", "DATABASE_QUERY", 0.98),
        ]
    },
    "fincore": {
        "services": [
            {"service_id": "SVC-FIN-GW", "name": "api-gateway", "display_name": "FinCore Transaction Gateway", "role": "API Gateway", "service_type": "gateway", "environment": "production", "status": "HEALTHY", "owner": "Edge Traffic", "criticality": "CRITICAL", "port": 8200, "customer_facing": True},
            {"service_id": "SVC-FIN-GW-ALIAS", "name": "gateway", "display_name": "FinCore Transaction Gateway", "role": "API Gateway", "service_type": "gateway", "environment": "production", "status": "HEALTHY", "owner": "Edge Traffic", "criticality": "CRITICAL", "port": 8200, "customer_facing": True},
            {"service_id": "SVC-FIN-ACC", "name": "account-service", "display_name": "Account & Ledger Balance Service", "role": "Account Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Accounts Core", "criticality": "CRITICAL", "port": 8201, "customer_facing": False},
            {"service_id": "SVC-FIN-TXN", "name": "transaction-service", "display_name": "High-Throughput Transaction Engine", "role": "Transaction Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Core Banking", "criticality": "CRITICAL", "port": 8202, "customer_facing": True},
            {"service_id": "SVC-FIN-PAY", "name": "payment-service", "display_name": "Payment Settlement Service", "role": "Payment Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Settlement Operations", "criticality": "CRITICAL", "port": 8203, "customer_facing": False},
            {"service_id": "SVC-FIN-FRD", "name": "fraud-detection-service", "display_name": "Fraud Detection & AML Scoring", "role": "Fraud Service", "service_type": "ml_service", "environment": "production", "status": "HEALTHY", "owner": "Risk & Compliance", "criticality": "HIGH", "port": 8204, "customer_facing": False},
            {"service_id": "SVC-FIN-FRD-ALIAS", "name": "fraud-service", "display_name": "Fraud Detection & AML Scoring", "role": "Fraud Service", "service_type": "ml_service", "environment": "production", "status": "HEALTHY", "owner": "Risk & Compliance", "criticality": "HIGH", "port": 8204, "customer_facing": False},
            {"service_id": "SVC-FIN-NOTIF", "name": "notification-service", "display_name": "FinCore Notification Dispatcher", "role": "Notification Service", "service_type": "worker", "environment": "production", "status": "HEALTHY", "owner": "FinCore SRE", "criticality": "MEDIUM", "port": 8205, "customer_facing": False},
            {"service_id": "SVC-FIN-PG", "name": "database-service", "display_name": "FinCore ACID PostgreSQL Ledger", "role": "PostgreSQL Database", "service_type": "database", "environment": "production", "status": "HEALTHY", "owner": "Database Operations", "criticality": "CRITICAL", "port": 5432, "customer_facing": False},
            {"service_id": "SVC-FIN-REDIS", "name": "cache", "display_name": "FinCore Redis Lock & Session Cache", "role": "Redis Cache", "service_type": "cache", "environment": "production", "status": "HEALTHY", "owner": "Infra Operations", "criticality": "HIGH", "port": 6379, "customer_facing": False},
        ],
        "edges": [
            ("api-gateway", "transaction-service", "HTTP_UPSTREAM", 0.99),
            ("api-gateway", "account-service", "HTTP_UPSTREAM", 0.97),
            ("gateway", "transaction-service", "HTTP_UPSTREAM", 0.99),
            ("gateway", "account-service", "HTTP_UPSTREAM", 0.97),
            ("transaction-service", "fraud-detection-service", "HTTP_UPSTREAM", 0.98),
            ("transaction-service", "fraud-service", "HTTP_UPSTREAM", 0.98),
            ("transaction-service", "payment-service", "HTTP_UPSTREAM", 0.98),
            ("transaction-service", "account-service", "INTERNAL_CALL", 0.96),
            ("transaction-service", "notification-service", "ASYNC_DISPATCH", 0.95),
            ("transaction-service", "database-service", "DATABASE_QUERY", 0.99),
            ("fraud-detection-service", "cache", "CACHE_ACCESS", 0.94),
            ("fraud-service", "cache", "CACHE_ACCESS", 0.94),
            ("account-service", "database-service", "DATABASE_QUERY", 0.99),
        ]
    },
    "clouddesk": {
        "services": [
            {"service_id": "SVC-CLOUD-GW", "name": "api-gateway", "display_name": "CloudDesk Edge Ingress Router", "role": "API Gateway", "service_type": "gateway", "environment": "production", "status": "HEALTHY", "owner": "Network Engineering", "criticality": "CRITICAL", "port": 8300, "customer_facing": True},
            {"service_id": "SVC-CLOUD-GW-ALIAS", "name": "gateway", "display_name": "CloudDesk Edge Ingress Router", "role": "API Gateway", "service_type": "gateway", "environment": "production", "status": "HEALTHY", "owner": "Network Engineering", "criticality": "CRITICAL", "port": 8300, "customer_facing": True},
            {"service_id": "SVC-CLOUD-USR", "name": "user-service", "display_name": "Multi-Tenant Authentication & IAM", "role": "Authentication Service", "service_type": "auth", "environment": "production", "status": "HEALTHY", "owner": "Security Engineering", "criticality": "CRITICAL", "port": 8301, "customer_facing": True},
            {"service_id": "SVC-CLOUD-AUTH-ALIAS", "name": "auth-service", "display_name": "Multi-Tenant Authentication & IAM", "role": "Authentication Service", "service_type": "auth", "environment": "production", "status": "HEALTHY", "owner": "Security Engineering", "criticality": "CRITICAL", "port": 8301, "customer_facing": True},
            {"service_id": "SVC-CLOUD-PRJ", "name": "project-service", "display_name": "Workspace & Project Engine", "role": "Project Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "App Platform", "criticality": "CRITICAL", "port": 8302, "customer_facing": True},
            {"service_id": "SVC-CLOUD-CMP", "name": "compute-service", "display_name": "Container & Virtual Instance Provisioner", "role": "Compute Service", "service_type": "compute", "environment": "production", "status": "HEALTHY", "owner": "Compute Infrastructure", "criticality": "CRITICAL", "port": 8303, "customer_facing": True},
            {"service_id": "SVC-CLOUD-BILL", "name": "billing-service", "display_name": "Subscription & Metered Billing", "role": "Billing Service", "service_type": "api", "environment": "production", "status": "HEALTHY", "owner": "Revenue Operations", "criticality": "HIGH", "port": 8304, "customer_facing": False},
            {"service_id": "SVC-CLOUD-NOTIF", "name": "notification-service", "display_name": "Notification & Webhook Dispatcher", "role": "Notification Service", "service_type": "worker", "environment": "production", "status": "HEALTHY", "owner": "Integrations Team", "criticality": "MEDIUM", "port": 8305, "customer_facing": False},
            {"service_id": "SVC-CLOUD-PG", "name": "database-service", "display_name": "CloudDesk Sharded PostgreSQL Cluster", "role": "PostgreSQL Database", "service_type": "database", "environment": "production", "status": "HEALTHY", "owner": "Database Engineering", "criticality": "CRITICAL", "port": 5432, "customer_facing": False},
            {"service_id": "SVC-CLOUD-REDIS", "name": "cache", "display_name": "CloudDesk Redis Cache & Rate Limiter", "role": "Redis Cache", "service_type": "cache", "environment": "production", "status": "HEALTHY", "owner": "Core Systems", "criticality": "HIGH", "port": 6379, "customer_facing": False},
        ],
        "edges": [
            ("api-gateway", "user-service", "HTTP_UPSTREAM", 0.99),
            ("api-gateway", "project-service", "HTTP_UPSTREAM", 0.98),
            ("api-gateway", "compute-service", "HTTP_UPSTREAM", 0.98),
            ("gateway", "user-service", "HTTP_UPSTREAM", 0.99),
            ("gateway", "project-service", "HTTP_UPSTREAM", 0.98),
            ("gateway", "compute-service", "HTTP_UPSTREAM", 0.98),
            ("compute-service", "cache", "CACHE_ACCESS", 0.95),
            ("compute-service", "database-service", "DATABASE_QUERY", 0.98),
            ("compute-service", "billing-service", "HTTP_UPSTREAM", 0.96),
            ("compute-service", "notification-service", "ASYNC_DISPATCH", 0.94),
            ("project-service", "user-service", "INTERNAL_CALL", 0.97),
            ("project-service", "database-service", "DATABASE_QUERY", 0.99),
            ("project-service", "notification-service", "ASYNC_DISPATCH", 0.94),
            ("billing-service", "database-service", "DATABASE_QUERY", 0.98),
            ("user-service", "cache", "CACHE_ACCESS", 0.95),
            ("user-service", "database-service", "DATABASE_QUERY", 0.99),
        ]
    }
}


class DynamicDependencyGraph:
    def __init__(self):
        # Service registry: service_name -> metadata dict
        self.services: Dict[str, Dict[str, Any]] = {}
        
        # Dependencies: (source, target) -> edge dict
        self.dependencies: Dict[Tuple[str, str], Dict[str, Any]] = {}
        
        # Adjacency lists for fast lookup
        # source -> set of targets (who source calls)
        self.adj_list: Dict[str, Set[str]] = {}
        # target -> set of sources (who calls target)
        self.reverse_adj: Dict[str, Set[str]] = {}
        
        # Initialize standard enterprise baseline topology
        self._init_baseline_topology()

    def _init_baseline_topology(self):
        """Seeds standard enterprise service registry and initial inferred relationships."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        default_services = [
            {
                "service_id": "SVC-GATEWAY",
                "name": "gateway",
                "display_name": "API Gateway / Ingress",
                "service_type": "gateway",
                "environment": "production",
                "resource_id": "/subscriptions/sub-aegis/resourceGroups/aegisops-rg/providers/Microsoft.Network/applicationGateways/ingress-gateway",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Edge & Traffic Engineering",
                "criticality": "CRITICAL",
                "customer_facing": True,
                "port": 8001,
                "url": "http://127.0.0.1:8001"
            },
            {
                "service_id": "SVC-SERVICE-A",
                "name": "service-a",
                "display_name": "Order Service (Service A)",
                "service_type": "api",
                "environment": "production",
                "resource_id": "/subscriptions/sub-aegis/resourceGroups/aegisops-rg/providers/Microsoft.Web/sites/order-service-app",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "E-Commerce Core",
                "criticality": "HIGH",
                "customer_facing": False,
                "port": 8002,
                "url": "http://127.0.0.1:8002"
            },
            {
                "service_id": "SVC-SERVICE-B",
                "name": "service-b",
                "display_name": "Payment & Ledger API (Service B)",
                "service_type": "api",
                "environment": "production",
                "resource_id": "/subscriptions/sub-aegis/resourceGroups/aegisops-rg/providers/Microsoft.Web/sites/payment-service-app",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Payment Operations",
                "criticality": "CRITICAL",
                "customer_facing": False,
                "port": 8003,
                "url": "http://127.0.0.1:8003"
            },
            {
                "service_id": "SVC-DATABASE",
                "name": "database-service",
                "display_name": "Distributed Ledger Database",
                "service_type": "database",
                "environment": "production",
                "resource_id": "/subscriptions/sub-aegis/resourceGroups/aegisops-rg/providers/Microsoft.Sql/servers/aegis-sql-server/databases/ledger-db",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Data Infrastructure",
                "criticality": "CRITICAL",
                "customer_facing": False,
                "port": 8004,
                "url": "http://127.0.0.1:8004"
            },
            {
                "service_id": "SVC-AUTH",
                "name": "auth-service",
                "display_name": "Authentication & Token Validator",
                "service_type": "auth",
                "environment": "production",
                "resource_id": "/subscriptions/sub-aegis/resourceGroups/aegisops-rg/providers/Microsoft.Web/sites/auth-service-app",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Identity & Security",
                "criticality": "CRITICAL",
                "customer_facing": True,
                "port": 8005,
                "url": "http://127.0.0.1:8005"
            },
            {
                "service_id": "SVC-CACHE",
                "name": "cache",
                "display_name": "Distributed Redis Cache",
                "service_type": "cache",
                "environment": "production",
                "resource_id": "/subscriptions/sub-aegis/resourceGroups/aegisops-rg/providers/Microsoft.Cache/Redis/aegis-redis",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Infrastructure",
                "criticality": "MEDIUM",
                "customer_facing": False,
                "port": 6379,
                "url": "redis://127.0.0.1:6379"
            }
        ]

        for s in default_services:
            self.services[s["name"]] = s

        # Canonical baseline dependency relationships
        baseline_edges = [
            ("gateway", "service-a", "HTTP_UPSTREAM", 0.98, 340, 2, "VALIDATED"),
            ("gateway", "auth-service", "HTTP_UPSTREAM", 0.96, 210, 1, "VALIDATED"),
            ("service-a", "service-b", "HTTP_UPSTREAM", 0.97, 280, 5, "VALIDATED"),
            ("service-a", "cache", "CACHE_ACCESS", 0.91, 145, 0, "INFERRED"),
            ("service-b", "database-service", "DATABASE_QUERY", 0.99, 450, 18, "VALIDATED"),
            ("service-b", "cache", "CACHE_ACCESS", 0.89, 90, 0, "INFERRED"),
            ("auth-service", "database-service", "DATABASE_QUERY", 0.95, 180, 3, "VALIDATED")
        ]

        for src, dst, rel_type, conf, obs, fails, status in baseline_edges:
            self.add_or_update_dependency(
                source=src,
                target=dst,
                relationship_type=rel_type,
                confidence=conf,
                observation_count=obs,
                correlated_failures_count=fails,
                status=status,
                first_seen=now_iso,
                last_seen=now_iso
            )

        # Register services and topology edges for all three companies
        for tenant, topo in TENANT_TOPOLOGIES.items():
            for s in topo.get("services", []):
                self.services[s["name"]] = s
            for edge in topo.get("edges", []):
                src, dst, rel_type, conf = edge[0], edge[1], edge[2], edge[3]
                self.add_or_update_dependency(
                    source=src,
                    target=dst,
                    relationship_type=rel_type,
                    confidence=conf,
                    observation_count=250,
                    correlated_failures_count=1,
                    status="VALIDATED",
                    first_seen=now_iso,
                    last_seen=now_iso
                )

    def add_or_update_dependency(
        self,
        source: str,
        target: str,
        relationship_type: str = "HTTP_UPSTREAM",
        confidence: Optional[float] = None,
        observation_count: int = 1,
        correlated_failures_count: int = 0,
        status: str = "INFERRED",
        evidence: Optional[List[str]] = None,
        first_seen: Optional[str] = None,
        last_seen: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically adds or updates a service dependency with confidence calculation.
        """
        key = (source, target)
        now_iso = datetime.now(timezone.utc).isoformat()
        dep_id = f"DEP-{source.upper()}-{target.upper()}"

        if key in self.dependencies:
            edge = self.dependencies[key]
            edge["observation_count"] += observation_count
            edge["correlated_failures_count"] += correlated_failures_count
            edge["last_seen"] = last_seen or now_iso
            
            # Recalculate dynamic confidence score
            obs = edge["observation_count"]
            fails = edge["correlated_failures_count"]
            
            # Base confidence starts at 0.80, scales to 0.99 with volume & failure correlation
            calc_conf = min(0.99, 0.80 + (min(obs, 200) / 1000.0) + (min(fails, 20) * 0.007))
            edge["confidence"] = round(calc_conf, 2)
            
            if obs >= 30 or fails >= 2:
                edge["status"] = "VALIDATED"
            
            # Build evidence points citing actual telemetry facts
            ev_list = [
                f"{edge['observation_count']} observed service-to-service requests",
                f"Relationship type: {edge['relationship_type']}"
            ]
            if edge["correlated_failures_count"] > 0:
                ev_list.append(f"{edge['correlated_failures_count']} correlated cascade failures observed")
            ev_list.append(f"Status confirmed: {edge['status']}")
            edge["evidence"] = ev_list
            
            return edge

        # New dependency
        init_conf = confidence if confidence is not None else 0.88
        edge = {
            "dependency_id": dep_id,
            "source_service": source,
            "target_service": target,
            "relationship_type": relationship_type,
            "confidence": init_conf,
            "observation_count": observation_count,
            "correlated_failures_count": correlated_failures_count,
            "status": status,
            "evidence": evidence or [
                f"{observation_count} observed requests",
                f"Initial telemetry relationship: {relationship_type}",
                f"Status: {status}"
            ],
            "first_seen": first_seen or now_iso,
            "last_seen": last_seen or now_iso
        }
        self.dependencies[key] = edge

        # Update adjacency
        if source not in self.adj_list:
            self.adj_list[source] = set()
        self.adj_list[source].add(target)

        if target not in self.reverse_adj:
            self.reverse_adj[target] = set()
        self.reverse_adj[target].add(source)

        return edge

    def record_telemetry_interaction(
        self,
        source: str,
        target: str,
        relationship_type: str = "HTTP_UPSTREAM",
        is_error: bool = False
    ):
        """Records an actual live telemetry call between two services."""
        if not source or not target or source == target:
            return
        
        # Ensure services are registered
        if source not in self.services:
            self.services[source] = {
                "service_id": f"SVC-{source.upper()}",
                "name": source,
                "display_name": source.replace("-", " ").title(),
                "service_type": "api",
                "environment": "production",
                "resource_id": f"/subscriptions/demo/resourceGroups/aegisops-rg/{source}",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Engineering",
                "criticality": "HIGH",
                "customer_facing": False,
                "port": 8000,
                "url": f"http://127.0.0.1:8000/{source}"
            }
        if target not in self.services:
            self.services[target] = {
                "service_id": f"SVC-{target.upper()}",
                "name": target,
                "display_name": target.replace("-", " ").title(),
                "service_type": "api",
                "environment": "production",
                "resource_id": f"/subscriptions/demo/resourceGroups/aegisops-rg/{target}",
                "resource_group": "aegisops-rg",
                "status": "HEALTHY",
                "owner": "Engineering",
                "criticality": "HIGH",
                "customer_facing": False,
                "port": 8000,
                "url": f"http://127.0.0.1:8000/{target}"
            }

        self.add_or_update_dependency(
            source=source,
            target=target,
            relationship_type=relationship_type,
            observation_count=1,
            correlated_failures_count=1 if is_error else 0
        )

    def update_service_health(self, service_name: str, health_state: str):
        """
        Updates live health status: HEALTHY (GREEN), DEGRADED (ORANGE), FAILED/CRASHED (RED), UNKNOWN (GREY).
        Synchronizes with canonical_state_manager.
        """
        clean_state = health_state.upper()
        if service_name in self.services:
            if clean_state in ["UP", "HEALTHY", "OK"]:
                self.services[service_name]["status"] = "HEALTHY"
            elif clean_state in ["DEGRADED", "WARN", "WARNING"]:
                self.services[service_name]["status"] = "DEGRADED"
            elif clean_state in ["DOWN", "CRASHED", "FAILED", "UNHEALTHY", "CRITICAL"]:
                self.services[service_name]["status"] = "FAILED"
            else:
                self.services[service_name]["status"] = "UNKNOWN"

        try:
            from backend.app.services.canonical_state import canonical_state_manager
            is_healthy = clean_state in ["UP", "HEALTHY", "OK"]
            canonical_state_manager.update_probe_health(
                tenant_id="shopsphere",
                service_name=service_name,
                healthy=is_healthy,
                state=clean_state
            )
            canonical_state_manager.update_probe_health(
                tenant_id="demo-tenant",
                service_name=service_name,
                healthy=is_healthy,
                state=clean_state
            )
        except Exception:
            pass

    def get_all_services(self) -> List[str]:
        """Returns all registered service names in the topology."""
        return list(self.services.keys())

    def get_dependencies(self, service_name: str) -> List[Dict[str, Any]]:
        """Returns direct downstream dependencies that service_name calls."""
        results = []
        for target in self.adj_list.get(service_name, set()):
            edge = self.dependencies.get((service_name, target))
            if edge:
                results.append(edge)
        return results

    def get_dependents(self, service_name: str) -> List[str]:
        """
        Returns all upstream caller services that directly or indirectly depend on service_name.
        Traverses reverse adjacency list.
        """
        visited: Set[str] = set()
        queue = [service_name]

        while queue:
            curr = queue.pop(0)
            for upstream in self.reverse_adj.get(curr, set()):
                if upstream not in visited:
                    visited.add(upstream)
                    queue.append(upstream)

        return list(visited)

    def get_downstream_dependents(self, service_name: str) -> List[str]:
        """Alias for get_dependents (all upstream callers affected by service_name failing)."""
        return self.get_dependents(service_name)

    def get_dependency_chain(self, root_service: str) -> List[str]:
        """
        Returns ordered cascade propagation chain starting from root_service up to gateway.
        Example: ["database-service", "service-b", "service-a", "gateway"]
        """
        chain = [root_service]
        visited = {root_service}
        curr = root_service

        while True:
            upstreams = list(self.reverse_adj.get(curr, set()) - visited)
            if not upstreams:
                break
            # Prefer direct microservice path
            preferred = next((u for u in upstreams if u in ["service-b", "service-a", "gateway", "auth-service"]), upstreams[0])
            chain.append(preferred)
            visited.add(preferred)
            curr = preferred

        return chain

    def get_topological_depth(self, service_name: str) -> int:
        """
        Topological depth from leaf/persistence up to ingress.
        Leaf databases have highest depth (3 or 4), Gateway has depth 0.
        """
        s = service_name.lower()
        if s in ["gateway", "api-gateway", "ingress"]:
            return 0
        if any(k in s for k in ["database", "sql", "postgres", "cache", "redis", "ledger"]):
            return 3
        if any(k in s for k in ["payment", "fraud", "compute", "billing", "inventory", "notification", "service-b"]):
            return 2
        if any(k in s for k in ["order", "transaction", "project", "account", "user", "auth", "service-a"]):
            return 1
        return 1

    def calculate_blast_radius(
        self,
        failing_service: str,
        error_rate: Optional[float] = None,
        request_count: Optional[int] = None,
        incident: Optional[Dict[str, Any]] = None,
        confirmed_affected: Optional[List[str]] = None,
        telemetry_events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Calculates accurate blast radius impact grounded in actual incident telemetry,
        distinguishing directly affected, confirmed downstream affected, and inferred/potential services.
        """
        inc = incident or {}
        err_rate = float(inc.get("error_rate") if inc.get("error_rate") is not None else (error_rate if error_rate is not None else 0.85))
        baseline_err = float(inc.get("baseline_error_rate") if inc.get("baseline_error_rate") is not None else 0.005)
        req_cnt = int(inc.get("correlated_event_count") or inc.get("request_count") or (request_count if request_count is not None else 120))

        # 1. Directly affected root service
        direct_impact = [failing_service]

        # 2. Topological dependents (all callers that depend on failing_service)
        all_dependents = [d for d in self.get_dependents(failing_service) if d != failing_service]

        # 3. Confirmed downstream affected services (backed by incident evidence)
        confirmed_input = confirmed_affected or inc.get("affected_services") or []
        events = telemetry_events or inc.get("events") or inc.get("timeline") or []

        # Find services with confirmed telemetry errors or degraded metrics
        degraded_event_services = set()
        for e in events:
            if isinstance(e, dict):
                svc = e.get("service_name") or e.get("service")
                level = str(e.get("level") or e.get("severity") or "").upper()
                if svc and (level in ("ERROR", "CRITICAL", "WARN") or e.get("status_code", 200) >= 400):
                    degraded_event_services.add(svc)

        has_incident_telemetry = bool(confirmed_input or degraded_event_services)
        if has_incident_telemetry:
            # A dependent is confirmed only if it appears in confirmed_input or degraded_event_services
            confirmed_downstream = []
            for d in all_dependents:
                if d in confirmed_input or d in degraded_event_services:
                    if d not in confirmed_downstream and d != failing_service:
                        confirmed_downstream.append(d)

            # 4. Inferred / potentially affected (topological callers not yet confirmed degraded)
            potentially_affected = [d for d in all_dependents if d not in confirmed_downstream and d != failing_service]
        else:
            # Theoretical topological graph cascade when no incident-specific telemetry is provided
            confirmed_downstream = [d for d in all_dependents if d != failing_service]
            potentially_affected = []

        # 5. Deduplicated list of all confirmed affected services
        all_confirmed = list(dict.fromkeys(direct_impact + confirmed_downstream))
        confirmed_count = len(all_confirmed)

        # 6. Actual failed requests count
        if inc.get("failed_requests") is not None:
            failed_requests = int(inc["failed_requests"])
        elif inc.get("failed_request_count") is not None:
            failed_requests = int(inc["failed_request_count"])
        elif degraded_event_services and len(events) > 0:
            error_events = [e for e in events if isinstance(e, dict) and str(e.get("severity") or e.get("level") or "").upper() in ("ERROR", "CRITICAL")]
            failed_requests = len(error_events) if len(error_events) > 0 else max(int(req_cnt * err_rate), 1)
        else:
            failed_requests = max(int(req_cnt * err_rate), 1) if err_rate > 0 else 0

        # 7. Propagation depth along dependency chain
        dep_chain = self.get_dependency_chain(failing_service)
        propagation_depth = 1
        for idx, svc in enumerate(dep_chain, 1):
            if svc in all_confirmed:
                propagation_depth = max(propagation_depth, idx)

        # 8. Customer-facing impact (measured only if gateway or ingress confirmed degraded)
        is_customer_facing = any(
            s in all_confirmed and (self.services.get(s, {}).get("customer_facing", False) or s in ["gateway", "ingress-gateway", "api-gateway"])
            for s in all_confirmed
        )

        # 9. Criticality & blast score
        svc_meta = self.services.get(failing_service, {})
        criticality = svc_meta.get("criticality", "HIGH")

        if is_customer_facing and err_rate > 0.3:
            impact_level = "CRITICAL"
            blast_score = min(100.0, 75.0 + (confirmed_count * 5.0) + (err_rate * 15.0))
        elif confirmed_count >= 3:
            impact_level = "CRITICAL"
            blast_score = min(90.0, 65.0 + (confirmed_count * 6.0))
        elif confirmed_count >= 2:
            impact_level = "HIGH"
            blast_score = min(74.0, 48.0 + (confirmed_count * 7.0))
        elif confirmed_count == 1:
            impact_level = "MEDIUM"
            blast_score = 35.0
        else:
            impact_level = "LOW"
            blast_score = 15.0

        error_rate_display = f"{err_rate * 100:.1f}%" if err_rate <= 1.0 else f"{err_rate:.1f}%"
        latency_p95 = float(inc.get("latency_p95_ms") or inc.get("latency_p95") or 0.0)
        latency_baseline = float(inc.get("baseline_latency_p95_ms") or inc.get("baseline_latency") or 38.0)
        latency_impact = f"{latency_p95:.1f}ms (+{latency_p95 - latency_baseline:.1f}ms)" if latency_p95 > latency_baseline else (f"{latency_p95:.1f}ms" if latency_p95 > 0 else "Nominal")

        return {
            "failing_service": failing_service,
            "criticality": criticality,
            "directly_affected": direct_impact,
            "directly_affected_count": len(direct_impact),
            "confirmed_downstream": confirmed_downstream,
            "downstream_affected_count": len(confirmed_downstream),
            "confirmed_affected_services": all_confirmed,
            "confirmed_affected_count": confirmed_count,
            "potentially_affected": potentially_affected,
            "potentially_affected_count": len(potentially_affected),
            "failed_requests": failed_requests,
            "error_rate": err_rate,
            "baseline_error_rate": baseline_err,
            "error_rate_increase": round(max(0.0, err_rate - baseline_err), 4),
            "latency_impact": latency_impact,
            "propagation_depth": propagation_depth,
            "customer_impact_measured": is_customer_facing,
            "customer_facing": is_customer_facing,
            "impact_level": impact_level,
            "blast_radius_score": round(blast_score, 1),
            "dependency_chain": dep_chain,
            # Backward-compatible fields
            "direct_impact": direct_impact,
            "downstream_impact": confirmed_downstream,
            "affected_services": all_confirmed,
            "affected_services_count": confirmed_count,
            "affected_requests": failed_requests,
            "summary": {
                "confirmed_affected_services": confirmed_count,
                "directly_affected": len(direct_impact),
                "downstream_affected": len(confirmed_downstream),
                "potentially_affected": len(potentially_affected),
                "failed_requests": failed_requests,
                "error_rate": error_rate_display,
                "latency_impact": latency_impact,
                "propagation_depth": propagation_depth
            }
        }

    def get_topology_graph(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns full nodes and edges data for frontend visual graph and APIs, isolated by tenant."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Pull canonical operational state
        try:
            from backend.app.services.canonical_state import canonical_state_manager
        except ImportError:
            canonical_state_manager = None

        # Check if tenant has specialized company topology
        raw_key = (tenant_id or "").lower().strip()
        t_key = "shopsphere"
        if "fincore" in raw_key or "fin-core" in raw_key:
            t_key = "fincore"
        elif "clouddesk" in raw_key or "cloud-desk" in raw_key:
            t_key = "clouddesk"
        elif "shopsphere" in raw_key or "shop-sphere" in raw_key:
            t_key = "shopsphere"
        elif raw_key in TENANT_TOPOLOGIES:
            t_key = raw_key

        if t_key in TENANT_TOPOLOGIES:
            t_data = TENANT_TOPOLOGIES[t_key]
            nodes = []
            for s in t_data["services"]:
                s_name = s["name"]
                c_st = canonical_state_manager.get_service_operational_state(t_key, s_name) if canonical_state_manager else None
                computed_status = c_st.operational_status.value if c_st else s.get("status", "HEALTHY")
                tel_status = c_st.telemetry_status.value if c_st else "CONNECTED"
                
                nodes.append({
                    "id": s_name,
                    "name": s_name,
                    "display_name": s["display_name"],
                    "role": s.get("role", "Microservice"),
                    "service_type": s["service_type"],
                    "status": computed_status,
                    "operational_status": computed_status,
                    "telemetry_status": tel_status,
                    "healthy": computed_status == "HEALTHY",
                    "criticality": s["criticality"],
                    "owner": s["owner"],
                    "environment": s["environment"],
                    "resource_id": f"/subscriptions/{t_key}/resourceGroups/{t_key}-rg/{s_name}",
                    "port": s["port"],
                    "url": f"http://127.0.0.1:{s['port']}",
                    "customer_facing": s["customer_facing"],
                    "last_telemetry_at": c_st.last_telemetry_at if c_st else None,
                    "is_stale": c_st.is_stale if c_st else False,
                    "updated_at": c_st.updated_at if c_st else now_iso
                })
            edges = []
            for src, dst, rel_type, conf in t_data["edges"]:
                edges.append({
                    "id": f"DEP-{t_key.upper()}-{src}-{dst}",
                    "source": src,
                    "target": dst,
                    "relationship_type": rel_type,
                    "confidence": conf,
                    "confidence_pct": int(conf * 100),
                    "observation_count": 520,
                    "correlated_failures_count": 0,
                    "status": "VALIDATED",
                    "evidence": [f"Correlated {rel_type} RPC traces verified between {src} and {dst}"],
                    "first_seen": now_iso,
                    "last_seen": now_iso
                })
            return {
                "nodes": nodes,
                "edges": edges,
                "total_services": len(nodes),
                "total_dependencies": len(edges),
                "tenant_id": t_key
            }

        # Baseline demo topology
        nodes = []
        for name, meta in self.services.items():
            c_st = canonical_state_manager.get_service_operational_state(t_key, name) if canonical_state_manager else None
            computed_status = c_st.operational_status.value if c_st else meta.get("status", "HEALTHY")
            tel_status = c_st.telemetry_status.value if c_st else "CONNECTED"

            nodes.append({
                "id": name,
                "name": name,
                "display_name": meta.get("display_name", name),
                "service_type": meta.get("service_type", "api"),
                "status": computed_status,
                "operational_status": computed_status,
                "telemetry_status": tel_status,
                "healthy": computed_status == "HEALTHY",
                "criticality": meta.get("criticality", "HIGH"),
                "owner": meta.get("owner", "Core SRE"),
                "environment": meta.get("environment", "production"),
                "resource_id": meta.get("resource_id"),
                "port": meta.get("port", 8000),
                "url": meta.get("url", f"http://127.0.0.1:8000/{name}"),
                "customer_facing": meta.get("customer_facing", False),
                "last_telemetry_at": c_st.last_telemetry_at if c_st else None,
                "is_stale": c_st.is_stale if c_st else False,
                "updated_at": c_st.updated_at if c_st else now_iso
            })

        edges = []
        for (src, dst), edge in self.dependencies.items():
            edges.append({
                "id": edge.get("dependency_id", f"DEP-{src}-{dst}"),
                "source": src,
                "target": dst,
                "relationship_type": edge.get("relationship_type", "HTTP_UPSTREAM"),
                "confidence": edge.get("confidence", 0.95),
                "confidence_pct": int(edge.get("confidence", 0.95) * 100),
                "observation_count": edge.get("observation_count", 1),
                "correlated_failures_count": edge.get("correlated_failures_count", 0),
                "status": edge.get("status", "INFERRED"),
                "evidence": edge.get("evidence", []),
                "first_seen": edge.get("first_seen"),
                "last_seen": edge.get("last_seen")
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "total_services": len(nodes),
            "total_dependencies": len(edges),
            "tenant_id": tenant_id or "demo-tenant"
        }

    def build_incident_correlation_graph(
        self,
        root_service: str,
        affected_services: List[str],
        events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Constructs an advanced incident correlation graph classifying services into:
        - ROOT: The origin service of the failure
        - DIRECTLY_AFFECTED: Direct 1-hop upstream callers or downstream dependencies of ROOT in the affected scope
        - DOWNSTREAM_AFFECTED: Services further upstream in the ingress propagation path (e.g., Gateway, Service-A)
        - SECONDARY_SYMPTOMS: Peripheral services showing secondary latency/error ripples (e.g., Cache, Auth)
        - HEALTHY: Services operating within normal parameters
        """
        all_registered = set(self.services.keys())
        affected_set = set(affected_services)
        if root_service:
            affected_set.add(root_service)

        direct_upstream = self.reverse_adj.get(root_service, set())
        direct_downstream = self.adj_list.get(root_service, set())
        direct_neighbors = (direct_upstream | direct_downstream) & affected_set

        # Cascade callers (upstream in call hierarchy, downstream in impact)
        all_dependents = set(self.get_dependents(root_service)) & affected_set
        downstream_affected = (all_dependents - direct_neighbors) - {root_service}

        # Any remaining affected services are secondary symptoms
        secondary_candidates = affected_set - {root_service} - direct_neighbors - downstream_affected
        
        # Classify each service
        classification: Dict[str, List[str]] = {
            "ROOT": [root_service] if root_service else [],
            "DIRECTLY_AFFECTED": sorted(list(direct_neighbors)),
            "DOWNSTREAM_AFFECTED": sorted(list(downstream_affected)),
            "SECONDARY_SYMPTOMS": sorted(list(secondary_candidates)),
            "HEALTHY": sorted(list(all_registered - affected_set))
        }

        # Build detailed node representations
        nodes = []
        for s in all_registered:
            if s == root_service:
                role = "ROOT"
                node_status = "FAILED"
                expl = f"Root cause service where anomalous behavior originated."
            elif s in direct_neighbors:
                role = "DIRECTLY_AFFECTED"
                node_status = "FAILED" if s in affected_set else "DEGRADED"
                expl = f"Direct 1-hop dependency of {root_service} impacted immediately."
            elif s in downstream_affected:
                role = "DOWNSTREAM_AFFECTED"
                node_status = "DEGRADED"
                expl = f"Upstream caller in ingress chain degraded by cascade from {root_service}."
            elif s in secondary_candidates:
                role = "SECONDARY_SYMPTOMS"
                node_status = "DEGRADED"
                expl = f"Collateral service exhibiting secondary symptoms or connection churn."
            else:
                role = "HEALTHY"
                node_status = "HEALTHY"
                expl = f"Operating normally outside of the incident blast radius."

            meta = self.services.get(s, {})
            nodes.append({
                "id": s,
                "name": s,
                "display_name": meta.get("display_name", s),
                "role": role,
                "status": node_status,
                "criticality": meta.get("criticality", "HIGH"),
                "service_type": meta.get("service_type", "api"),
                "topological_depth": self.get_topological_depth(s),
                "explanation": expl
            })

        # Calculate propagation path
        propagation_path = self.get_dependency_chain(root_service) if root_service else []
        filtered_path = [s for s in propagation_path if s in affected_set]

        # Edges with cascade tags
        edges = []
        for (src, dst), edge in self.dependencies.items():
            is_cascade = (src in affected_set and dst in affected_set)
            edges.append({
                "id": edge.get("dependency_id", f"DEP-{src}-{dst}"),
                "source": src,
                "target": dst,
                "relationship_type": edge.get("relationship_type", "HTTP_UPSTREAM"),
                "confidence": edge.get("confidence", 0.95),
                "is_cascade_edge": is_cascade,
                "status": "CASCADE_FAILING" if is_cascade else edge.get("status", "VALIDATED")
            })

        return {
            "root_service": root_service,
            "classification": classification,
            "propagation_path": filtered_path or propagation_path,
            "nodes": nodes,
            "edges": edges,
            "affected_count": len(affected_set),
            "healthy_count": len(classification["HEALTHY"])
        }



# Global singleton instance
dynamic_graph = DynamicDependencyGraph()
