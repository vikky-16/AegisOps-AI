"""
Base Anomaly Detector Interface
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple


class BaseAnomalyDetector(ABC):
    @abstractmethod
    def fit(self, X: List[List[float]]) -> None:
        """Fit or calibrate the model with normal telemetry observations."""
        pass

    @abstractmethod
    def predict(self, features: List[float]) -> Tuple[bool, float, List[str]]:
        """
        Returns:
            - is_anomaly: bool
            - anomaly_score: float (0.0 to 1.0)
            - top_contributing_features: list of string descriptions
        """
        pass
