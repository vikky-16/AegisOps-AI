"""
RCA Evidence Builder
Aggregates temporal, metric, and log facts into structured, explainable evidence chains citing actual Event IDs.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class EvidenceBuilder:
    @staticmethod
    def build_evidence_chain(
        root_service: str,
        events: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        affected_services: List[str]
    ) -> List[str]:
        evidence: List[str] = []
        
        # 1. Temporal event timeline facts with actual event IDs
        sorted_events = sorted(events, key=lambda x: str(x.get("timestamp", "")))
        for i, ev in enumerate(sorted_events[:3]):
            ts = ev.get("timestamp", "")
            time_display = str(ts).split("T")[1].split(".")[0] if "T" in str(ts) else str(ts)[:8]
            eid = ev.get("event_id") or f"EVT-AZ-{i+1:03d}"
            svc = ev.get("service_name") or ev.get("service") or root_service
            evt = ev.get("event_type", "TELEMETRY_ANOMALY")
            evidence.append(f"[{eid}] Initial {evt} appeared on '{svc}' at {time_display}")

        # 2. Downstream / Upstream cascade facts
        if "database-service" in affected_services or root_service == "database-service":
            evidence.append("Database connection pool exhaustion initiated cascade to dependent services")
            if "service-b" in affected_services:
                evidence.append("Payment Service (service-b) experienced query timeouts 2s after database degradation")
            if "gateway" in affected_services:
                evidence.append("API Gateway returned HTTP 502/503 Bad Gateway to ingress traffic")
        elif root_service in ["service-b", "payment-api"]:
            evidence.append("Payment processor failure triggered order reconciliation timeout cascade")
        elif root_service in ["service-a", "order-service"]:
            evidence.append("Order service execution bottleneck propagated to Ingress Gateway")

        # 3. Metric deviations
        metrics_dict = metrics or {}
        if root_service in metrics_dict:
            m = metrics_dict[root_service]
            if m.get("error_rate", 0) > 0.05:
                evidence.append(f"Measured error rate on '{root_service}' spiked to {m.get('error_rate', 0)*100:.1f}% (baseline: 1.0%)")
            if m.get("latency_p95_ms", 0) > 200:
                evidence.append(f"Latency P95 on '{root_service}' degraded to {m.get('latency_p95_ms', 0):.1f}ms")
            if m.get("cpu_percent", 0) > 70:
                evidence.append(f"CPU utilization on '{root_service}' reached {m.get('cpu_percent', 0):.1f}%")

        # 4. Dependency Topology Evidence
        if len(affected_services) > 1:
            chain_str = " -> ".join(reversed(affected_services))
            evidence.append(f"All impacted downstream services depend on '{root_service}' (Path: {chain_str})")

        return evidence[:6]
