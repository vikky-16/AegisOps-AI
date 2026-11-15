"""
Rate of Change (Velocity) Anomaly Detector
Detects sharp spikes and sudden acceleration in metric gradients.
"""

from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult


class RateChangeDetector(BaseDetector):
    def __init__(self, spike_ratio_threshold: float = 3.0):
        super().__init__(name="rate_change")
        self.spike_ratio_threshold = spike_ratio_threshold

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        if not history or len(history) < 2:
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

        prev_val = history[-1]
        delta = current_value - prev_val
        
        # Check relative jump
        if prev_val > 0:
            ratio = (current_value / prev_val)
        else:
            ratio = current_value if current_value > 0 else 1.0

        if ratio >= (self.spike_ratio_threshold * 2.0) and current_value > 10.0:
            score = min(1.0, 0.82 + (ratio / 20.0))
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.92,
                severity="CRITICAL",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=prev_val,
                evidence=[f"Severe velocity surge on {service} ({metric_name}): {ratio:.1f}x spike from {prev_val:.1f} to {current_value:.1f}"]
            )
        elif ratio >= self.spike_ratio_threshold and current_value > 5.0:
            score = 0.55 + ((ratio - self.spike_ratio_threshold) / 10.0) * 0.25
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.86,
                severity="WARNING",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=prev_val,
                evidence=[f"Rapid rate-of-change on {service} ({metric_name}): {ratio:.1f}x increase from {prev_val:.1f} to {current_value:.1f}"]
            )

        return AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=0.90,
            severity="INFO",
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=prev_val
        )
