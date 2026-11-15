"""
Tests for Risk Classification, Recommendation, and Self-Healing
"""

import pytest
from backend.app.healing.risk_engine import RiskEngine
from backend.app.healing.recommender import RecommendationEngine


def test_low_risk_action_allows_autonomous_execution():
    # CLEAR_CACHE on non-critical service is low risk and autonomous
    risk_res = RiskEngine.assess_risk("CLEAR_CACHE", "service-a", "LOW", confidence=0.95)
    assert risk_res["risk_level"] == "LOW"
    assert risk_res["approval_required"] is False


def test_destructive_or_high_impact_action_requires_approval():
    # ROLLBACK_CONFIG is high/critical risk
    risk_res = RiskEngine.assess_risk("ROLLBACK_CONFIG", "gateway", "CRITICAL", confidence=0.70)
    assert risk_res["approval_required"] is True
    assert risk_res["risk_level"] in ["HIGH", "CRITICAL"]


def test_recommendation_mapping():
    rec = RecommendationEngine.generate_recommendation("database-service", "CONNECTION_POOL_EXHAUSTION", "CRITICAL")
    assert rec["primary_action"] == "RESET_CONNECTION_POOL"
    assert rec["alternative_action"] == "RESTART_SERVICE"
    assert "restoring query throughput" in rec["expected_outcome"].lower()
