"""
Static Threshold Anomaly Detector
Evaluates metrics against pre-configured warning and critical limits.
"""

from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult

DEFAULT_THRESHOLDS = {
    "cpu_percent": {"warn": 75.0, "crit": 90.0},
    "memory_mb": {"warn": 300.0, "crit": 500.0},
    "error_rate": {"warn": 0.05, "crit": 0.20},
    "latency_p95_ms": {"warn": 500.0, "crit": 1200.0},
    "active_connections": {"warn": 35.0, "crit": 70.0}
}


class ThresholdDetector(BaseDetector):
    def __init__(self, thresholds: Optional[Dict[str, Dict[str, float]]] = None):
        super().__init__(name="threshold")
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        thresh = self.thresholds.get(metric_name)
        if not thresh:
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

        crit_val = thresh.get("crit", 9999.0)
        warn_val = thresh.get("warn", 999.0)

        if current_value >= crit_val:
            score = min(1.0, 0.85 + (current_value - crit_val) / max(1.0, crit_val) * 0.15)
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.95,
                severity="CRITICAL",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=warn_val,
                evidence=[f"CRITICAL threshold breached: {metric_name} = {current_value:.1f} >= {crit_val:.1f}"]
            )
        elif current_value >= warn_val:
            score = 0.50 + ((current_value - warn_val) / max(1.0, (crit_val - warn_val))) * 0.30
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.85,
                severity="WARNING",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=warn_val,
                evidence=[f"WARNING threshold breached: {metric_name} = {current_value:.1f} >= {warn_val:.1f}"]
            )

        return AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=0.90,
            severity="INFO",
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=warn_val
        )
