"""
AegisOps AI - Detectors Package
"""

from backend.app.ai.detectors.base import BaseDetector, AnomalyResult
from backend.app.ai.detectors.threshold_detector import ThresholdDetector
from backend.app.ai.detectors.zscore_detector import ZScoreDetector
from backend.app.ai.detectors.ewma_detector import EWMADetector
from backend.app.ai.detectors.rate_change_detector import RateChangeDetector
from backend.app.ai.detectors.consecutive_breach_detector import ConsecutiveBreachDetector
from backend.app.ai.detectors.ml_detector import MLDetector
from backend.app.ai.detectors.isolation_forest_detector import IsolationForestDetector, isolation_forest_detector
from backend.app.ai.detectors.behavioral_detector import BehavioralDeviationDetector
from backend.app.ai.detectors.multi_detector_engine import multi_detector_engine, MultiDetectorEngine

__all__ = [
    "BaseDetector",
    "AnomalyResult",
    "ThresholdDetector",
    "ZScoreDetector",
    "EWMADetector",
    "RateChangeDetector",
    "ConsecutiveBreachDetector",
    "MLDetector",
    "IsolationForestDetector",
    "isolation_forest_detector",
    "BehavioralDeviationDetector",
    "multi_detector_engine",
    "MultiDetectorEngine"
]
