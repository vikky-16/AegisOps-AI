"""
Tests for Storage Intelligence & Predictive Growth
"""

import pytest
from backend.app.ai.predictor import TrendPredictor
from backend.app.storage.manager import storage_manager


def test_storage_growth_prediction():
    snapshots = [
        {"timestamp": "2026-08-18T00:00:00Z", "used_gb": 80.0},
        {"timestamp": "2026-08-18T01:00:00Z", "used_gb": 81.8},
        {"timestamp": "2026-08-18T02:00:00Z", "used_gb": 83.6},
    ]
    
    pred = TrendPredictor.predict_storage_exhaustion(snapshots, total_capacity_gb=100.0, critical_threshold_pct=95.0)
    
    assert pred["used_percentage"] > 80.0
    assert pred["growth_rate_gb_per_hour"] > 1.0
    assert pred["predicted_critical_hours"] < 15.0
    assert pred["status"] in ["WARNING", "CRITICAL"]


def test_storage_optimization_execution():
    res = storage_manager.execute_storage_optimization()
    assert res["success"] is True
    assert res["reclaimed_gb"] > 0
    assert res["new_used_percentage"] < 80.0
