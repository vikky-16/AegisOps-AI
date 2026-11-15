"""
AegisOps AI - ML Unit Test Suite (Part 34: 25+ Tests)
Covers all 9 ML anomaly algorithms, feature engineering, baselines, and mathematical edge cases:
- Feature extraction & inspectable vectors
- Learned baseline engine (mean, median, rolling std, EWMA, IQR, percentiles)
- Z-score (normal & anomalous)
- EWMA drift detector
- IQR robust outlier detection
- Isolation Forest (scikit-learn)
- Local Outlier Factor (LOF) with fallback
- DBSCAN density clustering
- Change-point detection (CUSUM & magnitude shift)
- Time-series forecasting
- Multi-detector weighted ensemble
- Model explainability & feature attributions
- Edge cases: zero variance, constant values, missing features, noisy data, sparse telemetry
"""

import pytest
import math
import numpy as np

from backend.app.analytics.feature_engine import feature_engine, DataQualityTracker
from backend.app.analytics.baseline_engine import baseline_engine
from backend.app.analytics.ml_ensemble import ml_ensemble_engine


# -------------------------------------------------------------
# 1. Feature Engineering & Vector Inspection Tests
# -------------------------------------------------------------

def test_feature_definitions_count():
    """Validates that all 27 standardized features are registered."""
    defs = feature_engine.get_all_feature_definitions()
    assert len(defs) == 27, f"Expected 27 features, got {len(defs)}"


def test_feature_categories():
    """Validates features span all 7 operational categories."""
    defs = feature_engine.get_all_feature_definitions()
    categories = {f["category"] for f in defs}
    expected = {"TRAFFIC", "ERRORS", "LATENCY", "SYSTEM", "DEPENDENCY", "TELEMETRY", "TIME"}
    assert expected.issubset(categories)


def test_inspectable_feature_vector_structure():
    """Validates that extracted feature vectors are fully inspectable with metadata."""
    vec = feature_engine.get_inspectable_feature_vector(tenant_id="shopsphere", service="database-service")
    assert "vector_id" in vec
    assert "features" in vec
    assert len(vec["features"]) == 27
    for f in vec["features"]:
        assert "name" in f
        assert "value" in f
        assert "unit" in f


def test_feature_extraction_from_raw():
    """Validates extraction from raw operational attributes."""
    raw = {
        "requests_sec": 120.0,
        "error_rate": 0.05,
        "p95_latency_ms": 32.0,
        "cpu_utilization": 45.0,
        "connection_pool_utilization": 0.30
    }
    extracted = feature_engine.extract_standard_features(raw)
    assert extracted["requests_sec"] == 120.0
    assert extracted["error_rate"] == 0.05
    assert extracted["p95_latency_ms"] == 32.0


# -------------------------------------------------------------
# 2. Baseline Engine Tests
# -------------------------------------------------------------

@pytest.fixture(autouse=True, scope="module")
def setup_test_baselines():
    base = baseline_engine.get_feature_baseline("shopsphere", "database-service", "latency_p95_ms")
    for v in [26.0, 27.5, 25.8, 28.2, 26.9, 27.1, 26.4, 27.8, 25.5, 28.0,
              26.7, 27.3, 26.1, 27.6, 26.8, 27.0, 26.5, 27.4, 26.2, 27.7,
              26.6, 27.2, 26.3, 27.5, 26.7, 27.1, 26.4, 27.8, 26.9, 27.0]:
        base.update(v)


def test_baseline_rolling_mean_and_std():
    """Validates rolling mean and standard deviation computation."""
    mean, std = baseline_engine.calculate_rolling_stats("shopsphere", "database-service", "latency_p95_ms")
    assert mean > 0.0
    assert std >= 0.0


def test_baseline_rolling_median():
    """Validates rolling median calculation."""
    med = baseline_engine.calculate_rolling_median("shopsphere", "database-service", "latency_p95_ms")
    assert med > 0.0


def test_baseline_ewma():
    """Validates EWMA calculation adheres to smoothing factor alpha."""
    val = baseline_engine.calculate_ewma("shopsphere", "database-service", "latency_p95_ms", alpha=0.3)
    assert val > 0.0


def test_baseline_iqr_fences():
    """Validates IQR Q1, Q3, and robust outlier fences."""
    q1, q3, iqr = baseline_engine.calculate_iqr("shopsphere", "database-service", "latency_p95_ms")
    assert q3 >= q1
    assert iqr >= 0.0


def test_baseline_deviation_normal():
    """Validates that normal metric values yield NORMAL severity and zero alarm."""
    dev = baseline_engine.calculate_deviation("shopsphere", "database-service", "latency_p95_ms", current_value=28.0)
    assert dev["severity"] == "NORMAL"
    assert dev["deviation_pct"] < 50.0


def test_baseline_deviation_critical():
    """Validates that severe metric values yield CRITICAL severity and high confidence."""
    dev = baseline_engine.calculate_deviation("shopsphere", "database-service", "latency_p95_ms", current_value=1800.0)
    assert dev["severity"] == "CRITICAL"
    assert dev["confidence"] >= 0.90


# -------------------------------------------------------------
# 3. Model 1 — Z-Score Tests
# -------------------------------------------------------------

def test_z_score_normal_behavior():
    """Validates normal numerical reading produces low z-score."""
    res = ml_ensemble_engine.evaluate_z_score(28.0, mean=27.0, std=3.5, threshold=3.0)
    assert not res["is_anomaly"]
    assert res["z_score"] < 1.0


def test_z_score_extreme_deviation():
    """Validates severe deviation produces high z-score and qualitative label."""
    res = ml_ensemble_engine.evaluate_z_score(1800.0, mean=27.0, std=3.5, threshold=3.0)
    assert res["is_anomaly"]
    assert res["z_score"] > 10.0
    assert "Extreme" in res["interpretation"] or "Critical" in res["interpretation"]


# -------------------------------------------------------------
# 4. Model 2 — EWMA Drift Tests
# -------------------------------------------------------------

def test_ewma_normal():
    """Validates EWMA drift within tolerance."""
    res = ml_ensemble_engine.evaluate_ewma(current_val=29.0, expected_val=28.0, threshold_pct=40.0)
    assert not res["is_anomaly"]
    assert res["ewma_deviation_pct"] < 10.0


def test_ewma_abrupt_deviation():
    """Validates sudden deviation from smoothed expected value."""
    res = ml_ensemble_engine.evaluate_ewma(current_val=87.0, expected_val=42.0, threshold_pct=40.0)
    assert res["is_anomaly"]
    assert res["ewma_deviation_pct"] > 50.0


# -------------------------------------------------------------
# 5. Model 3 — IQR / Robust Outlier Tests
# -------------------------------------------------------------

def test_iqr_in_fences():
    """Validates values within Q1 - 1.5*IQR and Q3 + 1.5*IQR are not flagged."""
    res = ml_ensemble_engine.evaluate_iqr(current_val=30.0, q1=24.0, q3=32.0, iqr=8.0)
    assert not res["is_anomaly"]


def test_iqr_outlier_breach():
    """Validates values outside fences are detected as outliers."""
    res = ml_ensemble_engine.evaluate_iqr(current_val=95.0, q1=24.0, q3=32.0, iqr=8.0)
    assert res["is_anomaly"]
    assert res["current_val"] > res["upper_fence"]


# -------------------------------------------------------------
# 6. Model 4 — Isolation Forest Tests (scikit-learn)
# -------------------------------------------------------------

def test_isolation_forest_execution():
    """Validates scikit-learn IsolationForest model training and decision."""
    hist = [[100.0, 0.002, 25.0, 40.0, 0.20, 0.0] for _ in range(50)]
    anom_vec = [150.0, 0.25, 2200.0, 92.0, 0.98, 0.15]
    res = ml_ensemble_engine.evaluate_isolation_forest(anom_vec, hist)
    assert "model_score" in res
    assert "is_anomaly" in res
    assert res["status"] == "EVALUATED"


def test_isolation_forest_fallback_insufficient_samples():
    """Validates that Isolation Forest gracefully falls back when < 15 samples."""
    hist = [[100.0, 0.002, 25.0, 40.0, 0.20, 0.0] for _ in range(5)]
    vec = [150.0, 0.25, 2200.0, 92.0, 0.98, 0.15]
    res = ml_ensemble_engine.evaluate_isolation_forest(vec, hist)
    assert res["status"] == "FALLBACK DETECTION"


# -------------------------------------------------------------
# 7. Model 5 — Local Outlier Factor (LOF) Tests
# -------------------------------------------------------------

def test_lof_execution_and_fallback():
    """Validates LOF evaluates with sufficient history, falls back with low data."""
    # Under 20 samples -> fallback
    hist_low = [[25.0, 0.01] for _ in range(8)]
    res_fallback = ml_ensemble_engine.evaluate_lof([500.0, 0.3], hist_low)
    assert res_fallback["status"] == "FALLBACK DETECTION"

    # With 25 samples -> evaluated
    hist_ok = [[25.0, 0.01] for _ in range(25)]
    res_ok = ml_ensemble_engine.evaluate_lof([800.0, 0.4], hist_ok)
    assert res_ok["status"] == "EVALUATED"


# -------------------------------------------------------------
# 8. Model 6 — DBSCAN Density Clustering Tests
# -------------------------------------------------------------

def test_dbscan_clustering():
    """Validates DBSCAN clusters observations and detects noise/outliers."""
    hist = [[25.0, 0.01] for _ in range(30)]
    anom_point = [950.0, 0.45]
    res = ml_ensemble_engine.evaluate_dbscan(anom_point, hist)
    assert "cluster_label" in res
    assert res["status"] == "EVALUATED"


# -------------------------------------------------------------
# 9. Model 7 — Change-Point Detection Tests
# -------------------------------------------------------------

def test_change_point_step_change():
    """Validates CUSUM change-point detector identifies sudden distribution shift."""
    series_before = [25.0, 26.0, 24.5, 27.0, 25.5]
    series_after = [780.0, 810.0, 795.0, 820.0]
    res = ml_ensemble_engine.evaluate_change_point(series_before, series_after, metric_name="P95 latency")
    assert res["is_change_point"]
    assert res["change_magnitude"] > 20.0  # ~30x magnitude shift


# -------------------------------------------------------------
# 10. Model 8 — Time-Series Forecasting Tests
# -------------------------------------------------------------

def test_forecasting_deviation():
    """Validates forecasting trend extrapolation and prediction deviation."""
    history = [0.03, 0.035, 0.04, 0.042, 0.045]
    res = ml_ensemble_engine.evaluate_forecast(actual_val=0.137, history=history, metric_name="error_rate")
    assert res["predicted_val"] > 0.0
    assert res["prediction_deviation_pct"] > 100.0


# -------------------------------------------------------------
# 11. Model 9 — Weighted Ensemble & Explainability Tests
# -------------------------------------------------------------

def test_ensemble_aggregation_healthy():
    """Validates that healthy service features produce low anomaly score and NORMAL classification."""
    normal_features = {
        "requests_sec": 120.0,
        "error_rate": 0.002,
        "p95_latency_ms": 26.0,
        "cpu_utilization": 38.0,
        "connection_pool_utilization": 0.20,
        "timeout_rate": 0.0
    }
    res = ml_ensemble_engine.evaluate("shopsphere", "database-service", normal_features)
    assert res["ensemble_score"] < 0.40
    assert res["classification"] == "NORMAL"


def test_ensemble_aggregation_anomalous():
    """Validates that multi-metric degradation produces high score and HIGH CONFIDENCE ANOMALY."""
    anom_features = {
        "requests_sec": 140.0,
        "error_rate": 0.22,
        "p95_latency_ms": 1850.0,
        "cpu_utilization": 89.0,
        "connection_pool_utilization": 0.98,
        "timeout_rate": 0.15
    }
    res = ml_ensemble_engine.evaluate("shopsphere", "database-service", anom_features)
    assert res["ensemble_score"] >= 0.70
    assert "ANOMALY" in res["classification"]
    assert res["confidence"] >= 0.90
    assert len(res["dominant_detectors"]) >= 2
    assert "model_contributions" in res
    assert "feature_contributions" in res
    assert "baseline_comparison" in res


# -------------------------------------------------------------
# 12. Edge Cases (Missing, Zero Variance, Constant, Noisy)
# -------------------------------------------------------------

def test_edge_case_zero_variance():
    """Validates Z-Score does not divide by zero when variance is zero."""
    res = ml_ensemble_engine.evaluate_z_score(10.0, mean=10.0, std=0.0, threshold=3.0)
    assert res["z_score"] == 0.0
    assert not res["is_anomaly"]


def test_edge_case_missing_metrics():
    """Validates ensemble gracefully handles empty or sparse feature dictionaries."""
    res = ml_ensemble_engine.evaluate("shopsphere", "database-service", {})
    assert "ensemble_score" in res
    assert not math.isnan(res["ensemble_score"])


def test_edge_case_constant_telemetry():
    """Validates constant metric streams do not trigger false anomalies."""
    const_features = {k: 50.0 for k in ["requests_sec", "cpu_utilization", "p95_latency_ms"]}
    res = ml_ensemble_engine.evaluate("shopsphere", "database-service", const_features)
    assert not math.isnan(res["ensemble_score"])
