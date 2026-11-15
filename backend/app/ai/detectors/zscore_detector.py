"""
Z-Score Statistical Anomaly Detector
Computes statistical standard score deviation Z = (X - mu) / sigma against moving window history.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from backend.app.ai.detectors.base import BaseDetector, AnomalyResult


class ZScoreDetector(BaseDetector):
    def __init__(self, warning_z: float = 2.0, critical_z: float = 3.5):
        super().__init__(name="zscore")
        self.warning_z = warning_z
        self.critical_z = critical_z

    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        # Use baseline statistics if available, otherwise compute from history
        if baseline and "mean" in baseline and "std" in baseline:
            mean = baseline["mean"]
            std = baseline["std"] or 1.0
        elif len(history) >= 5:
            mean = float(np.mean(history))
            std = float(np.std(history)) or 1.0
        else:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.50,
                severity="INFO",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=current_value
            )

        z = (current_value - mean) / std

        if z >= self.critical_z:
            score = min(1.0, 0.85 + (z - self.critical_z) * 0.05)
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.94,
                severity="CRITICAL",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=round(mean, 2),
                evidence=[f"Critical statistical outlier on {service} ({metric_name}): Z-score = {z:.2f} >= {self.critical_z:.1f} (Mean: {mean:.1f}, Current: {current_value:.1f})"]
            )
        elif z >= self.warning_z:
            score = 0.50 + ((z - self.warning_z) / max(1.0, (self.critical_z - self.warning_z))) * 0.30
            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=round(score, 3),
                confidence=0.88,
                severity="WARNING",
                algorithm=self.name,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=round(mean, 2),
                evidence=[f"Statistical deviation on {service} ({metric_name}): Z-score = {z:.2f} >= {self.warning_z:.1f} (Mean: {mean:.1f}, Current: {current_value:.1f})"]
            )

        return AnomalyResult(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=0.90,
            severity="INFO",
            algorithm=self.name,
            metric_name=metric_name,
            current_value=current_value,
            expected_value=round(mean, 2)
        )
