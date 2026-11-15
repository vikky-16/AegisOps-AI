"""
Consecutive Breach Anomaly Detector
Filters transient single-sample blips and triggers high-confidence alarms on sustained breaches.
"""

from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult


class ConsecutiveBreachDetector(BaseDetector):
    def __init__(self, breach_window: int = 3):
        super().__init__(name="consecutive_breach")
        self.breach_window = breach_window

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        if not history or len(history) < self.breach_window:
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

        threshold = 50.0
        if baseline and "p95" in baseline:
            threshold = baseline["p95"]
        elif baseline and "mean" in baseline:
            threshold = baseline["mean"] * 1.5

        recent_window = history[-self.breach_window:] + [current_value]
        all_breached = all(val > threshold for val in recent_window)

        if all_breached:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=0.92,
                confidence=0.96,
                severity="HIGH",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=round(threshold, 2),
                evidence=[f"Persistent breach sustained across {len(recent_window)} consecutive telemetry cycles on {service} ({metric_name} > {threshold:.1f})"]
            )

        return AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=0.90,
            severity="INFO",
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=round(threshold, 2)
        )
