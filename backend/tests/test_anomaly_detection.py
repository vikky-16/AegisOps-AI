"""
Tests for Ensemble Anomaly Detection (Isolation Forest + Z-Score)
"""

import pytest
from backend.app.ai.anomaly_detector import EnsembleAnomalyDetector


def test_normal_telemetry_prediction():
    detector = EnsembleAnomalyDetector(contamination=0.05)
    
    # Normal metrics vector: [cpu=12%, mem=140MB, err_rate=0.0, lat_p95=18ms, req_count=30, active_conn=4]
    normal_features = [12.0, 140.0, 0.0, 18.0, 30.0, 4.0]
    is_anomaly, score, evidence = detector.predict(normal_features)
    
    assert not is_anomaly, f"Normal telemetry falsely marked anomalous (score={score})"
    assert score < 0.45, f"Normal score {score} should be < 0.45"


def test_high_error_rate_anomaly():
    detector = EnsembleAnomalyDetector(contamination=0.05)
    
    # Severe error spike: [cpu=30%, mem=180MB, err_rate=0.85 (85% errors!), lat_p95=450ms, req_count=50, active_conn=12]
    anomalous_features = [30.0, 180.0, 0.85, 450.0, 50.0, 12.0]
    is_anomaly, score, evidence = detector.predict(anomalous_features)
    
    assert is_anomaly, "High error rate should be detected as anomaly"
    assert score >= 0.50, f"Anomaly score {score} should be >= 0.50"
    assert any("error" in ev.lower() or "critical" in ev.lower() for ev in evidence)


def test_high_cpu_anomaly():
    detector = EnsembleAnomalyDetector(contamination=0.05)
    
    # CPU saturation: [cpu=98%, mem=220MB, err_rate=0.02, lat_p95=320ms, req_count=80, active_conn=25]
    cpu_spike_features = [98.0, 220.0, 0.02, 320.0, 80.0, 25.0]
    is_anomaly, score, evidence = detector.predict(cpu_spike_features)
    
    assert is_anomaly, "High CPU saturation should be detected as anomaly"
    assert score >= 0.50
    assert any("cpu" in ev.lower() for ev in evidence)
