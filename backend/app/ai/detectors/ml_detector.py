import numpy as np
from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult
from backend.app.ai.detectors.isolation_forest_detector import isolation_forest_detector


class MLDetector(BaseDetector):
    def __init__(self, contamination: float = 0.08):
        super().__init__(name="isolation_forest")
        self.detector = isolation_forest_detector

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        # Build synthetic local metric dictionary for vector extraction
        metric_payload = {
            "request_count": 15.0,
            "error_rate": current_value if "error" in metric_name.lower() else 0.0,
            "latency_p50_ms": current_value if "p50" in metric_name.lower() else 15.0,
            "latency_p95_ms": current_value if any(k in metric_name.lower() for k in ["latency", "p95", "duration"]) else 25.0,
            "latency_p99_ms": current_value if "p99" in metric_name.lower() else 40.0,
            "cpu_percent": current_value if "cpu" in metric_name.lower() else 14.0,
            "memory_mb": current_value if "memory" in metric_name.lower() else 128.0,
            "active_connections": current_value if "conn" in metric_name.lower() else 2.0,
        }
        
        vec = self.detector.extract_feature_vector(metric_payload)
        res = self.detector.detect(vec)
        
        is_anom = bool(res["is_anomaly"])
        score = float(res["anomaly_score"])
        conf = float(res["confidence"])
        
        evidence = []
        if is_anom:
            top_devs = [f"{d['feature']} ({d['formatted_delta']})" for d in res.get("contributing_features", [])[:3]]
            dev_str = f" [Top deviations: {', '.join(top_devs)}]" if top_devs else ""
            evidence.append(
                f"Isolation Forest flagged multivariate anomaly on '{service}': {metric_name}={current_value:.1f} (score: {score:.2f}, conf: {int(conf*100)}%){dev_str}"
            )

        severity = "CRITICAL" if score >= 0.85 else ("WARNING" if is_anom else "INFO")
        exp_val = baseline.get("mean", 15.0) if baseline else 15.0

        return AnomalyResult(
            is_anomaly=is_anom,
            anomaly_score=score,
            confidence=conf,
            severity=severity,
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=exp_val,
            evidence=evidence
        )
