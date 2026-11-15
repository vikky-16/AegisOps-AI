"""
AegisOps AI - Base Anomaly Detector Interface
Standard interface for all statistical, time-series, rule-based, and ML detectors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AnomalyResult(BaseModel):
    is_anomaly: bool = False
    anomaly_score: float = 0.0  # Normalized 0.0 to 1.0
    confidence: float = 0.85
    severity: str = "INFO"  # INFO, WARNING, HIGH, CRITICAL
    algorithm: str = "base"
    metric_name: str = "general"
    current_value: float = 0.0
    expected_value: float = 0.0
    evidence: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseDetector(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        history: List[float],
        baseline: Optional[Dict[str, Any]] = None
    ) -> AnomalyResult:
        """Evaluates a telemetry metric against historical or baseline data."""
        pass
