"""
Exponentially Weighted Moving Average (EWMA) Anomaly Detector
Tracks exponential trend drift to detect rapid degradation and metric variance.
"""

from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult


class EWMADetector(BaseDetector):
    def __init__(self, alpha: float = 0.3, deviation_factor: float = 2.5):
        super().__init__(name="ewma")
        self.alpha = alpha
        self.deviation_factor = deviation_factor

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        if not history or len(history) < 3:
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

        # Compute EWMA over history
        ewma = history[0]
        for val in history[1:]:
            ewma = (self.alpha * val) + ((1 - self.alpha) * ewma)

        diff = abs(current_value - ewma)
        threshold = max(5.0, ewma * 0.40)

        if diff >= (threshold * self.deviation_factor):
            score = min(1.0, 0.80 + (diff / max(1.0, threshold * 4.0)) * 0.20)
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.91,
                severity="CRITICAL",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=round(ewma, 2),
                evidence=[f"EWMA trend surge on {service} ({metric_name}): Current = {current_value:.1f}, EWMA Target = {ewma:.1f} (+{diff:.1f})"]
            )
        elif diff >= threshold:
            score = 0.50 + ((diff - threshold) / max(1.0, threshold * (self.deviation_factor - 1))) * 0.30
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.84,
                severity="WARNING",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=round(ewma, 2),
                evidence=[f"EWMA drift detected on {service} ({metric_name}): Current = {current_value:.1f}, Expected EWMA = {ewma:.1f}"]
            )

        return AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=0.90,
            severity="INFO",
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=round(ewma, 2)
        )
