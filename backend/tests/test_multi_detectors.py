"""
Unit and Integration Tests for Multi-Detector Engine and Baselines
Tests:
- Threshold Detector
- Z-Score Detector
- EWMA Detector
- Rate-of-Change Detector
- Consecutive Breach Detector
- Machine Learning (Isolation Forest) Detector
- MultiDetectorEngine ensemble scoring & Behavioral Anomaly Detection
"""

import pytest
from backend.app.ai.baselines import BaselineManager
from backend.app.ai.detectors.threshold_detector import ThresholdDetector
from backend.app.ai.detectors.zscore_detector import ZScoreDetector
from backend.app.ai.detectors.ewma_detector import EWMADetector
from backend.app.ai.detectors.rate_change_detector import RateChangeDetector
from backend.app.ai.detectors.consecutive_breach_detector import ConsecutiveBreachDetector
from backend.app.ai.detectors.ml_detector import MLDetector
from backend.app.ai.detectors.multi_detector_engine import MultiDetectorEngine
from backend.app.ai.model_manager import ModelManager


def test_threshold_detector():
    detector = ThresholdDetector(thresholds={
        "latency_p95_ms": {"warn": 500.0, "crit": 1200.0}
    })
    
    # Normal event
    res_normal = detector.evaluate(
        service="payment-service",
        metric_name="latency_p95_ms",
        current_value=250.0,
        history=[200.0, 220.0, 240.0]
    )
    assert res_normal.is_anomaly is False

    # Warning event
    res_warn = detector.evaluate(
        service="payment-service",
        metric_name="latency_p95_ms",
        current_value=600.0,
        history=[200.0, 220.0, 240.0]
    )
    assert res_warn.is_anomaly is True
    assert res_warn.severity == "WARNING"

    # Critical event
    res_crit = detector.evaluate(
        service="payment-service",
        metric_name="latency_p95_ms",
        current_value=1500.0,
        history=[200.0, 220.0, 240.0]
    )
    assert res_crit.is_anomaly is True
    assert res_crit.severity == "CRITICAL"
    assert "CRITICAL threshold breached" in res_crit.evidence[0]


def test_zscore_detector():
    baseline = {"mean": 100.0, "std": 15.0}
    detector = ZScoreDetector(warning_z=2.0, critical_z=3.5)
    
    # Normal
    res_normal = detector.evaluate(
        service="gateway",
        metric_name="latency_p95_ms",
        current_value=110.0,
        history=[95.0, 100.0, 105.0],
        baseline=baseline
    )
    assert res_normal.is_anomaly is False

    # Z-score critical spike (600ms vs mean=100, std=15 -> z > 30)
    res_spike = detector.evaluate(
        service="gateway",
        metric_name="latency_p95_ms",
        current_value=600.0,
        history=[95.0, 100.0, 105.0],
        baseline=baseline
    )
    assert res_spike.is_anomaly is True
    assert res_spike.severity == "CRITICAL"
    assert res_spike.confidence >= 0.90


def test_ewma_detector():
    detector = EWMADetector(alpha=0.3, deviation_factor=2.5)
    history = [30.0, 32.0, 31.0, 30.5, 31.5]
    
    # Normal reading
    res_normal = detector.evaluate(
        service="service-a",
        metric_name="cpu_percent",
        current_value=32.0,
        history=history
    )
    assert res_normal.is_anomaly is False

    # Sudden jump
    res_spike = detector.evaluate(
        service="service-a",
        metric_name="cpu_percent",
        current_value=95.0,
        history=history
    )
    assert res_spike.is_anomaly is True
    assert res_spike.severity in ("WARNING", "CRITICAL")
    assert "EWMA" in res_spike.evidence[0]


def test_rate_of_change_detector():
    detector = RateChangeDetector(spike_ratio_threshold=3.0)
    history = [20.0, 22.0, 25.0]
    
    # Normal change
    res_normal = detector.evaluate(
        service="database-service",
        metric_name="active_connections",
        current_value=28.0,
        history=history
    )
    assert res_normal.is_anomaly is False

    # Rapid spike (from 25 to 200 is 8x surge)
    res_spike = detector.evaluate(
        service="database-service",
        metric_name="active_connections",
        current_value=200.0,
        history=history
    )
    assert res_spike.is_anomaly is True
    assert res_spike.severity in ("WARNING", "CRITICAL")
    assert "velocity" in res_spike.evidence[0] or "rate-of-change" in res_spike.evidence[0]


def test_consecutive_breach_detector():
    baseline = {"p95": 85.0}
    detector = ConsecutiveBreachDetector(breach_window=3)
    
    # History with only 1 breach
    res_transient = detector.evaluate(
        service="auth-service",
        metric_name="memory_percent",
        current_value=90.0,
        history=[50.0, 60.0, 92.0],
        baseline=baseline
    )
    assert res_transient.is_anomaly is False

    # History with sustained breaches across window
    res_sustained = detector.evaluate(
        service="auth-service",
        metric_name="memory_percent",
        current_value=93.0,
        history=[88.0, 91.0, 89.0],
        baseline=baseline
    )
    assert res_sustained.is_anomaly is True
    assert res_sustained.severity == "HIGH"
    assert "Persistent breach" in res_sustained.evidence[0]


def test_ml_isolation_forest_detector():
    detector = MLDetector(contamination=0.05)
    
    # Normal metric value around baseline 15.0
    res_normal = detector.evaluate(
        service="service-b",
        metric_name="latency_p95_ms",
        current_value=16.0,
        history=[14.0, 15.0, 16.0]
    )
    assert res_normal.is_anomaly is False

    # Outlier value far from normal distribution
    res_outlier = detector.evaluate(
        service="service-b",
        metric_name="latency_p95_ms",
        current_value=1850.0,
        history=[14.0, 15.0, 16.0]
    )
    assert res_outlier.is_anomaly is True
    assert "Isolation Forest" in res_outlier.evidence[0]


def test_multi_detector_engine_and_model_manager_behavioral_anomaly():
    """
    Test Section 14: Behavioral Anomaly Detection.
    Verifies that a silent latency shift (e.g. 1850ms) with error_rate=0.0
    is flagged as a behavioral anomaly.
    """
    model_mgr = ModelManager()
    
    # Pre-feed 10 normal telemetry points
    for _ in range(10):
        model_mgr.evaluate_telemetry("service-b", {
            "cpu_percent": 25.0,
            "memory_mb": 120.0,
            "error_rate": 0.0,
            "latency_p95_ms": 65.0,
            "request_count": 100,
            "active_connections": 10
        })
    
    # Behavioral anomaly telemetry: latency degrades to 1850ms, but error_rate is 0.0
    is_anomaly, score, evidence = model_mgr.evaluate_telemetry("service-b", {
        "cpu_percent": 30.0,
        "memory_mb": 130.0,
        "error_rate": 0.0,
        "latency_p95_ms": 1850.0,
        "request_count": 100,
        "active_connections": 12
    })
    
    assert is_anomaly is True
    assert score >= 0.80
    assert any("latency" in ev.lower() or "behavioral" in ev.lower() for ev in evidence)
