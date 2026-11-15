"""
AegisOps AI - Behavioral Anomaly Detector
Detects subtle operational & distribution shifts (e.g. latency creep, degradation without 5xx errors)
specifically addressing failures that do not emit ERROR logs.
"""

from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult


class BehavioralDeviationDetector(BaseDetector):
    def __init__(self, latency_shift_factor: float = 2.2):
        super().__init__(name="behavioral_deviation")
        self.latency_shift_factor = latency_shift_factor

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        if not baseline:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.5,
                severity="INFO",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=current_value
            )

        base_mean = float(baseline.get("mean", 15.0))
        base_p95 = float(baseline.get("p95", 25.0))
        
        # Check for behavioral latency distribution shift
        is_latency_metric = any(k in metric_name.lower() for k in ["latency", "duration", "time"])
        is_anomaly = False
        anomaly_score = 0.0
        evidence = []
        
        if is_latency_metric and base_p95 > 0:
            ratio = current_value / base_p95
            if ratio >= self.latency_shift_factor:
                is_anomaly = True
                anomaly_score = min(0.95, 0.60 + (ratio * 0.08))
                evidence.append(
                    f"Behavioral shift detected on '{service}': {metric_name} ({current_value:.1f}ms) "
                    f"exceeds learned p95 baseline ({base_p95:.1f}ms) by {ratio:.1f}x without explicit ERROR logs."
                )

        confidence = round(min(0.96, 0.70 + (anomaly_score * 0.25)), 2)

        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=round(anomaly_score, 3),
            confidence=confidence,
            severity="WARNING" if is_anomaly else "INFO",
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=base_p95,
            evidence=evidence
        )
