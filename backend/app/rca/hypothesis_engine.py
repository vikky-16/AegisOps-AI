"""
AegisOps AI - Explainable RCA Hypothesis Generation & Evidence Ranking Engine
Evaluates candidate root-cause hypotheses against empirical evidence items.
Computes calibrated confidence, extracts supporting and contradictory evidence,
ranks alternative hypotheses, and explains WHY the primary hypothesis was chosen.
"""

from typing import Dict, Any, List, Optional
from backend.app.rca.dynamic_graph import dynamic_graph


CANDIDATE_HYPOTHESIS_TEMPLATES = [
    {
        "id": "db_connection_pool_exhaustion",
        "title": "Database connection pool exhaustion",
        "category": "DATABASE",
        "target_service": "database-service",
        "component": "connection_pool",
        "matching_indicators": ["connection", "pool", "exhaustion", "max_connections", "active_connections"],
        "contradictory_indicators": ["active_connections=0", "no database query error"],
        "recommended_action": "RESET_CONNECTION_POOL"
    },
    {
        "id": "service_crash",
        "title": "Service process crash / unexpected termination",
        "category": "AVAILABILITY",
        "target_service": "service-b",
        "component": "process_runtime",
        "matching_indicators": ["crash", "sigsegv", "connection refused", "502", "unreachable", "process terminated"],
        "contradictory_indicators": ["service responding 200", "healthy status probe"],
        "recommended_action": "RESTART_SERVICE"
    },
    {
        "id": "high_api_latency",
        "title": "High API latency / bottleneck",
        "category": "PERFORMANCE",
        "target_service": "service-a",
        "component": "http_endpoint",
        "matching_indicators": ["latency", "slow", "timeout", "p95", "latency_p95_ms"],
        "contradictory_indicators": ["latency_p95_ms < 50", "instant response"],
        "recommended_action": "SCALE_WORKERS"
    },
    {
        "id": "memory_pressure",
        "title": "Memory pressure / heap saturation",
        "category": "RESOURCE",
        "target_service": "service-a",
        "component": "process_memory",
        "matching_indicators": ["memory", "heap", "oom", "memory_mb", "ram", "garbage collection"],
        "contradictory_indicators": ["memory_mb < 200", "low memory usage"],
        "recommended_action": "CLEAR_CACHE"
    },
    {
        "id": "cpu_saturation",
        "title": "CPU compute saturation / runaway thread",
        "category": "RESOURCE",
        "target_service": "gateway",
        "component": "compute_threads",
        "matching_indicators": ["cpu", "cpu_percent", "runaway", "load average", "core saturation"],
        "contradictory_indicators": ["cpu_percent < 25", "idle cpu"],
        "recommended_action": "SCALE_WORKERS"
    },
    {
        "id": "dependency_unavailable",
        "title": "Downstream dependency unavailable / network partition",
        "category": "DEPENDENCY",
        "target_service": "auth-service",
        "component": "downstream_client",
        "matching_indicators": ["dependency", "upstream", "circuit breaker", "auth", "504", "gateway timeout"],
        "contradictory_indicators": ["all dependencies healthy"],
        "recommended_action": "ENABLE_CIRCUIT_BREAKER_FALLBACK"
    },
    {
        "id": "queue_backlog",
        "title": "Message queue backlog / consumer starvation",
        "category": "ASYNC_PIPELINE",
        "target_service": "service-b",
        "component": "message_queue",
        "matching_indicators": ["queue", "backlog", "consumer lag", "kafka", "queue_depth", "unprocessed"],
        "contradictory_indicators": ["queue_depth=0", "consumer lag = 0"],
        "recommended_action": "SCALE_CONSUMER_WORKERS"
    },
    {
        "id": "configuration_error",
        "title": "Configuration error / invalid parameters",
        "category": "CONFIGURATION",
        "target_service": "database-service",
        "component": "configuration",
        "matching_indicators": ["config", "syntax", "environment variable", "bad credentials", "invalid flag"],
        "contradictory_indicators": ["config valid", "clean startup log"],
        "recommended_action": "ROLLBACK_CONFIG"
    },
    {
        "id": "network_latency",
        "title": "Network latency / packet loss",
        "category": "NETWORK",
        "target_service": "gateway",
        "component": "network_interface",
        "matching_indicators": ["packet loss", "retransmission", "ping spike", "socket timeout"],
        "contradictory_indicators": ["local latency < 5ms", "zero packet drops"],
        "recommended_action": "OPTIMIZE_ROUTE"
    },
    {
        "id": "application_thread_exhaustion",
        "title": "Application thread exhaustion",
        "category": "APPLICATION",
        "target_service": "service-a",
        "component": "thread_pool",
        "matching_indicators": ["thread pool full", "workers busy", "deadlock", "worker starved"],
        "contradictory_indicators": ["thread utilization < 20%"],
        "recommended_action": "SCALE_WORKERS"
    }
]


class HypothesisEngine:
    def __init__(self):
        self.graph = dynamic_graph

    def evaluate_hypotheses(
        self,
        evidence_items: List[Dict[str, Any]],
        affected_services: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates candidate hypotheses against evidence items and computes ranked hypotheses.
        Returns:
        - primary_hypothesis: { hypothesis, confidence, supporting_evidence, contradictory_evidence, target_service, action }
        - alternative_hypotheses: list of ranked alternatives
        - explanation_why: detailed text explanation of selection criteria
        - dependency_path: topological dependency chain
        - temporal_ordering: chronological order of signals
        """
        evidence_text_blobs = []
        for ev in evidence_items:
            blob = f"{ev.get('service', '')} {ev.get('component', '')} {ev.get('signal_type', '')} {ev.get('metric_or_log_value', '')} {ev.get('deviation', '')}".lower()
            evidence_text_blobs.append((ev, blob))

        evaluated: List[Dict[str, Any]] = []

        # Check each template
        for tpl in CANDIDATE_HYPOTHESIS_TEMPLATES:
            supporting: List[str] = []
            contradictory: List[str] = []
            raw_score = 10.0  # Base prior

            # Match supporting indicators
            for ev, blob in evidence_text_blobs:
                matched_support = False
                for ind in tpl["matching_indicators"]:
                    if ind in blob:
                        matched_support = True
                        break
                
                # Check service match
                svc_match = (ev.get("service") == tpl["target_service"])

                if matched_support:
                    if svc_match:
                        raw_score += 36.0
                        supporting.append(f"Direct match on {ev.get('service')}: {ev.get('metric_or_log_value')} ({ev.get('deviation')})")
                    else:
                        raw_score += 12.0
                        supporting.append(f"Correlated anomaly on {ev.get('service')}: {ev.get('metric_or_log_value')}")

                # Check contradictory indicators
                for c_ind in tpl["contradictory_indicators"]:
                    if c_ind in blob:
                        raw_score -= 25.0
                        contradictory.append(f"Contradictory signal on {ev.get('service')}: found '{c_ind}'")

            # Dependency topological depth boost
            topo_depth = self.graph.get_topological_depth(tpl["target_service"])
            raw_score += topo_depth * 4.0

            # If no supporting evidence was found, add a baseline contradictory note
            if not supporting:
                contradictory.append(f"No anomalous metrics or logs observed on target service '{tpl['target_service']}' for this condition")
                raw_score = max(5.0, raw_score - 15.0)

            # Calibrate confidence to percentage 0.05 to 0.96
            conf = min(0.96, max(0.08, raw_score / 100.0))

            evaluated.append({
                "id": tpl["id"],
                "hypothesis": tpl["title"],
                "category": tpl["category"],
                "target_service": tpl["target_service"],
                "component": tpl["component"],
                "recommended_action": tpl["recommended_action"],
                "confidence": round(conf, 2),
                "confidence_pct": int(round(conf * 100)),
                "supporting_evidence": supporting,
                "contradictory_evidence": contradictory,
                "topological_depth": topo_depth
            })

        # Sort descending by confidence
        evaluated.sort(key=lambda x: x["confidence"], reverse=True)

        primary = evaluated[0] if evaluated else {
            "hypothesis": "Unknown System Anomaly",
            "confidence": 0.50,
            "confidence_pct": 50,
            "supporting_evidence": [],
            "contradictory_evidence": [],
            "target_service": "database-service",
            "recommended_action": "RESTART_SERVICE"
        }

        alternatives = evaluated[1:5] if len(evaluated) > 1 else []

        # Construct dependency path from target service up to gateway
        chain = self.graph.get_dependency_chain(primary.get("target_service", "database-service"))
        dependency_path = list(reversed(chain)) if chain else ["gateway", "service-a", "service-b", primary.get("target_service", "database-service")]

        # Temporal ordering
        temporal_ordering = []
        for ev in sorted(evidence_items, key=lambda x: x.get("timestamp", 0.0)):
            temporal_ordering.append({
                "timestamp": ev.get("timestamp"),
                "service": ev.get("service"),
                "signal": ev.get("signal_type"),
                "value": ev.get("metric_or_log_value"),
                "deviation": ev.get("deviation")
            })

        # Explain WHY the primary hypothesis was selected over alternatives
        alt_str = ", ".join([f"{a['hypothesis']} ({a['confidence_pct']}%)" for a in alternatives[:2]])
        why_text = (
            f"The primary root-cause hypothesis '{primary['hypothesis']}' was selected with {primary['confidence_pct']}% confidence "
            f"because {len(primary['supporting_evidence'])} empirical evidence items directly substantiated failure in component '{primary.get('component')}' "
            f"on service '{primary.get('target_service')}', which sits at topological depth {primary.get('topological_depth')}. "
            f"Alternative hypotheses ({alt_str}) were assigned significantly lower confidence due to lack of primary telemetry signals or contradictory baseline data."
        )

        return {
            "primary_hypothesis": primary,
            "confidence": primary["confidence"],
            "supporting_evidence": primary["supporting_evidence"],
            "contradictory_evidence": primary["contradictory_evidence"],
            "alternative_hypotheses": alternatives,
            "affected_services": list({ev.get("service") for ev in evidence_items if ev.get("service")}),
            "dependency_path": dependency_path,
            "temporal_ordering": temporal_ordering,
            "why_selected": why_text
        }


hypothesis_engine = HypothesisEngine()
