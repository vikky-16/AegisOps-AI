"""
AegisOps AI - Modular Anomaly Detection Engine
Combines statistical deviations (Z-score), multivariate anomaly detection (Isolation Forest),
temporal correlation ordering, and dependency-aware topological depth scoring.
Produces standardized EvidenceItem instances without storing meaningless raw telemetry.
"""

import time
import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from backend.app.ai.detectors.zscore_detector import ZScoreDetector
from backend.app.ai.detectors.isolation_forest_detector import IsolationForestDetector
from backend.app.rca.dynamic_graph import dynamic_graph
from backend.app.models.evidence import EvidenceItem


# Standard baseline operational values for microservices
DEFAULT_METRIC_BASELINES = {
    "error_rate": {"mean": 0.005, "std": 0.005, "unit": "ratio"},
    "latency_p95_ms": {"mean": 35.0, "std": 12.0, "unit": "ms"},
    "latency_p50_ms": {"mean": 15.0, "std": 5.0, "unit": "ms"},
    "cpu_percent": {"mean": 18.0, "std": 6.0, "unit": "%"},
    "memory_mb": {"mean": 140.0, "std": 20.0, "unit": "MB"},
    "active_connections": {"mean": 8.0, "std": 3.0, "unit": "connections"},
    "queue_depth": {"mean": 2.0, "std": 1.5, "unit": "messages"},
    "throughput_rps": {"mean": 120.0, "std": 15.0, "unit": "rps"}
}


class AnomalyDetectionEngine:
    """
    Modular Anomaly Detector & Evidence Synthesizer.
    Orchestrates Z-score, Isolation Forest, temporal sequence ordering, and dependency topology scoring.
    """
    def __init__(self):
        self.zscore_detector = ZScoreDetector(warning_z=2.0, critical_z=3.5)
        self.isolation_forest = IsolationForestDetector(contamination=0.08)
        self.graph = dynamic_graph
        self._custom_detectors: Dict[str, Any] = {}

    def register_detector(self, name: str, detector: Any):
        """Allows modular registration of additional ML/statistical models."""
        self._custom_detectors[name] = detector

    def compute_zscore_deviation(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        baseline: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculates Z-score deviation against specified or default baseline."""
        b_info = baseline or DEFAULT_METRIC_BASELINES.get(metric_name, {"mean": 10.0, "std": 2.0, "unit": ""})
        mean = float(b_info.get("mean", 10.0))
        std = max(0.001, float(b_info.get("std", 1.0)))

        z = (current_value - mean) / std
        pct_dev = ((current_value - mean) / max(0.001, abs(mean))) * 100.0

        is_anomaly = abs(z) >= self.zscore_detector.warning_z
        severity = "CRITICAL" if abs(z) >= self.zscore_detector.critical_z else ("WARNING" if is_anomaly else "INFO")

        return {
            "metric_name": metric_name,
            "current_value": round(current_value, 2),
            "baseline_mean": round(mean, 2),
            "baseline_std": round(std, 2),
            "z_score": round(z, 2),
            "percentage_deviation": f"{pct_dev:+.1f}%",
            "is_anomaly": is_anomaly,
            "severity": severity
        }

    def evaluate_telemetry_snapshot(
        self,
        incident_id: str,
        service_metrics: Dict[str, Dict[str, Any]],
        logs: Optional[List[Dict[str, Any]]] = None,
        iteration: int = 0,
        before_after_state: str = "BEFORE",
        tenant_id: str = "demo-tenant"
    ) -> Dict[str, Any]:
        """
        Analyzes a snapshot of multi-service telemetry and produces structured EvidenceItem instances.
        - Runs univariate Z-score deviations across standard metrics
        - Runs multivariate Isolation Forest across the feature space
        - Determines temporal ordering of first-seen anomalies
        - Evaluates dependency topological depth
        """
        now_ts = time.time()
        evidence_items: List[Dict[str, Any]] = []
        service_anomalies: Dict[str, List[Dict[str, Any]]] = {}
        temporal_events: List[Dict[str, Any]] = []

        # 1. Evaluate metrics with Z-score for each service
        for svc_name, metrics in service_metrics.items():
            service_anomalies[svc_name] = []
            topo_depth = self.graph.get_topological_depth(svc_name)

            # Check individual metrics
            for m_key in ["error_rate", "latency_p95_ms", "cpu_percent", "memory_mb", "active_connections", "queue_depth"]:
                if m_key in metrics:
                    val = float(metrics[m_key])
                    z_res = self.compute_zscore_deviation(svc_name, m_key, val)

                    if z_res["is_anomaly"]:
                        service_anomalies[svc_name].append(z_res)
                        component = self._map_metric_to_component(m_key)
                        
                        ev = {
                            "incident_id": incident_id,
                            "timestamp": now_ts,
                            "source": "statistical_detector_zscore",
                            "service": svc_name,
                            "component": component,
                            "signal_type": "METRIC",
                            "metric_or_log_value": f"{m_key}={val}",
                            "baseline": str(z_res["baseline_mean"]),
                            "deviation": f"{z_res['percentage_deviation']} (Z={z_res['z_score']})",
                            "correlation_info": {
                                "z_score": z_res["z_score"],
                                "topological_depth": topo_depth,
                                "metric": m_key
                            },
                            "execution_iteration": iteration,
                            "before_after_state": before_after_state,
                            "tenant_id": tenant_id
                        }
                        evidence_items.append(ev)
                        temporal_events.append({
                            "timestamp": now_ts,
                            "service": svc_name,
                            "signal": m_key,
                            "deviation": z_res["percentage_deviation"],
                            "z_score": z_res["z_score"],
                            "topological_depth": topo_depth
                        })

            # 2. Multivariate Isolation Forest evaluation
            try:
                if_result = self.isolation_forest.detect(metrics, service_name=svc_name)
                if if_result.get("is_anomaly"):
                    ev_if = {
                        "incident_id": incident_id,
                        "timestamp": now_ts,
                        "source": "isolation_forest_multivariate",
                        "service": svc_name,
                        "component": "service_runtime",
                        "signal_type": "ANOMALY",
                        "metric_or_log_value": f"AnomalyScore={if_result.get('anomaly_score', 0.85)}",
                        "baseline": "Contamination=0.08",
                        "deviation": f"Multivariate Outlier Score: {if_result.get('anomaly_score', 0.85)}",
                        "correlation_info": {
                            "model": "isolation_forest",
                            "top_deviating_features": if_result.get("top_deviating_features", []),
                            "topological_depth": topo_depth
                        },
                        "execution_iteration": iteration,
                        "before_after_state": before_after_state,
                        "tenant_id": tenant_id
                    }
                    evidence_items.append(ev_if)
            except Exception:
                pass

        # 3. Process error logs as qualitative evidence
        if logs:
            for l in logs:
                lvl = str(l.get("level", "INFO")).upper()
                msg = str(l.get("message", ""))
                svc = l.get("service") or l.get("service_name", "unknown")
                if lvl in ["ERROR", "CRITICAL", "FATAL"] or "exception" in msg.lower() or "error" in msg.lower():
                    topo_depth = self.graph.get_topological_depth(svc)
                    ev_log = {
                        "incident_id": incident_id,
                        "timestamp": float(l.get("timestamp", now_ts)),
                        "source": "log_intelligence_collector",
                        "service": svc,
                        "component": self._infer_log_component(msg),
                        "signal_type": "LOG",
                        "metric_or_log_value": msg[:200],
                        "baseline": "0 error events/min",
                        "deviation": f"Level={lvl}",
                        "correlation_info": {
                            "level": lvl,
                            "topological_depth": topo_depth
                        },
                        "execution_iteration": iteration,
                        "before_after_state": before_after_state,
                        "tenant_id": tenant_id
                    }
                    evidence_items.append(ev_log)
                    temporal_events.append({
                        "timestamp": float(l.get("timestamp", now_ts)),
                        "service": svc,
                        "signal": "ERROR_LOG",
                        "deviation": lvl,
                        "z_score": 3.0,
                        "topological_depth": topo_depth
                    })

        # 4. Temporal Ordering and Dependency-Aware Scoring
        # Sort chronologically by timestamp, break ties by deeper dependency first
        temporal_events.sort(key=lambda x: (x["timestamp"], -x.get("topological_depth", 0)))

        # Identify primary origin service based on earliest onset and deepest topological dependency
        origin_service = None
        if temporal_events:
            origin_service = temporal_events[0]["service"]

        return {
            "evidence_items": evidence_items,
            "temporal_ordering": temporal_events,
            "origin_service": origin_service,
            "total_anomalies_detected": len(evidence_items),
            "services_affected": list({e["service"] for e in evidence_items}),
            "analyzed_at": now_ts
        }

    def _map_metric_to_component(self, metric: str) -> str:
        if "connection" in metric:
            return "connection_pool"
        elif "latency" in metric:
            return "http_endpoint"
        elif "cpu" in metric:
            return "compute_threads"
        elif "memory" in metric:
            return "process_memory"
        elif "queue" in metric:
            return "message_queue"
        elif "error" in metric:
            return "application_handler"
        return "system"

    def _infer_log_component(self, msg: str) -> str:
        msg_lower = msg.lower()
        if "connection" in msg_lower or "pool" in msg_lower:
            return "connection_pool"
        elif "timeout" in msg_lower or "slow" in msg_lower:
            return "downstream_client"
        elif "memory" in msg_lower or "heap" in msg_lower or "oom" in msg_lower:
            return "process_memory"
        elif "config" in msg_lower or "setting" in msg_lower or "syntax" in msg_lower:
            return "configuration"
        elif "crash" in msg_lower or "sigsegv" in msg_lower or "killed" in msg_lower:
            return "process_runtime"
        elif "queue" in msg_lower or "backlog" in msg_lower:
            return "message_queue"
        return "application_logger"


anomaly_engine = AnomalyDetectionEngine()
