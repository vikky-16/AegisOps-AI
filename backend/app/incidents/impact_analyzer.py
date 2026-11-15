"""
Business Impact & Blast Radius Analyzer
Evaluates direct impact, downstream cascade impact, affected requests, customer-facing status, and SLA risk.
"""

from typing import List, Dict, Any, Optional
from backend.app.rca.dynamic_graph import dynamic_graph

SERVICE_CRITICALITY = {
    "gateway": {"weight": 1.0, "criticality": "CRITICAL", "users_per_req": 15, "customer_facing": True},
    "service-a": {"weight": 0.85, "criticality": "HIGH", "users_per_req": 10, "customer_facing": False},
    "service-b": {"weight": 0.90, "criticality": "CRITICAL", "users_per_req": 12, "customer_facing": False},
    "database-service": {"weight": 1.0, "criticality": "CRITICAL", "users_per_req": 20, "customer_facing": False},
    "auth-service": {"weight": 0.95, "criticality": "CRITICAL", "users_per_req": 18, "customer_facing": True},
    "cache": {"weight": 0.60, "criticality": "MEDIUM", "users_per_req": 6, "customer_facing": False}
}


class BusinessImpactAnalyzer:
    @staticmethod
    def calculate_impact(
        primary_service: str,
        affected_services: List[str],
        error_rate: float = 0.85,
        request_count: int = 120
    ) -> Dict[str, Any]:
        """
        Calculates comprehensive Blast Radius and Business Impact metrics.
        """
        # Traversal of dynamic dependency graph
        blast_info = dynamic_graph.calculate_blast_radius(
            failing_service=primary_service,
            error_rate=error_rate,
            request_count=request_count,
            confirmed_affected=affected_services
        )

        all_svcs = list(set([primary_service] + affected_services + blast_info.get("confirmed_affected_services", [])))
        
        # Calculate users affected & total weight
        total_weight = 0.0
        max_criticality = "LOW"
        users_affected = 0
        customer_facing = False

        for svc in all_svcs:
            meta = SERVICE_CRITICALITY.get(svc, {"weight": 0.5, "criticality": "MEDIUM", "users_per_req": 5, "customer_facing": False})
            total_weight += meta["weight"]
            if meta.get("customer_facing", False):
                customer_facing = True

            if meta["criticality"] == "CRITICAL":
                max_criticality = "CRITICAL"
            elif meta["criticality"] == "HIGH" and max_criticality != "CRITICAL":
                max_criticality = "HIGH"

            users_affected += int(request_count * meta["users_per_req"] * max(0.2, error_rate))

        impact_score = blast_info.get("blast_radius_score", 85.0)

        # SLA Breach Risk
        if impact_score >= 80.0 or "gateway" in all_svcs or "database-service" in all_svcs:
            sla_risk = "CRITICAL"
        elif impact_score >= 50.0:
            sla_risk = "HIGH"
        elif impact_score >= 25.0:
            sla_risk = "MEDIUM"
        else:
            sla_risk = "LOW"

        return {
            "business_impact_score": impact_score,
            "blast_radius_score": impact_score,
            "estimated_users_affected": max(10, users_affected),
            "affected_requests": blast_info.get("failed_requests", request_count),
            "failed_requests": blast_info.get("failed_requests", request_count),
            "error_rate": blast_info.get("error_rate", error_rate),
            "latency_impact": blast_info.get("latency_impact", "Nominal"),
            "propagation_depth": blast_info.get("propagation_depth", 1),
            "sla_breach_risk": sla_risk,
            "max_service_criticality": max_criticality,
            "criticality": max_criticality,
            "customer_facing": customer_facing,
            "directly_affected": blast_info.get("directly_affected", [primary_service]),
            "confirmed_downstream": blast_info.get("confirmed_downstream", []),
            "confirmed_affected_services": blast_info.get("confirmed_affected_services", all_svcs),
            "potentially_affected": blast_info.get("potentially_affected", []),
            "summary": blast_info.get("summary", {}),
            "direct_impact": blast_info.get("direct_impact", [primary_service]),
            "downstream_impact": blast_info.get("downstream_impact", []),
            "affected_services": blast_info.get("confirmed_affected_services", all_svcs),
            "affected_services_count": len(blast_info.get("confirmed_affected_services", all_svcs)),
            "dependency_chain": blast_info.get("dependency_chain", [primary_service]),
            "impact_level": blast_info.get("impact_level", "CRITICAL")
        }
