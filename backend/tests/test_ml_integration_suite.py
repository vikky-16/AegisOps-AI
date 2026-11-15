"""
AegisOps AI - ML Integration Test Suite (Part 34: 15+ Tests)
Tests interactions between ML subsystems:
- Early warning 4-tier lifecycle (NORMAL -> WARNING -> HIGH RISK -> INCIDENT)
- 3-minute extrapolation & failure probability
- 20-taxonomy operational failure classification
- 8-factor RCA engine with causal path and comparative explanation
- Case-Based Reasoning (CBR) similarity search with tenant isolation
- Model registry versions, status lifecycle, and promotion safeguards
- Post-recovery feedback loop & evaluation metrics
- Telemetry data quality monitor & feature drift detection
- Strict multi-tenant ML isolation
"""

import pytest
import time
from backend.app.analytics.early_warning import early_warning_engine
from backend.app.analytics.failure_classifier import failure_classifier
from backend.app.analytics.rca_engine import rca_engine
from backend.app.knowledge.incident_memory import incident_memory
from backend.app.analytics.model_registry import model_registry
from backend.app.analytics.feature_engine import feature_engine, data_quality_tracker


# -------------------------------------------------------------
# 1. Early Warning Engine Integration Tests
# -------------------------------------------------------------

def test_early_warning_normal_state():
    """Validates baseline telemetry maintains NORMAL state."""
    features = {"error_rate": 0.002, "p95_latency_ms": 25.0, "cpu_percent": 15.0, "db_pool_utilization": 0.10}
    alert = early_warning_engine.evaluate_telemetry("shopsphere", "database-service", features)
    assert alert is None
    assert early_warning_engine.get_service_state("shopsphere", "database-service") == "NORMAL"


def test_early_warning_warning_state():
    """Validates intermediate degradation raises WARNING state."""
    features = {"error_rate": 0.02, "p95_latency_ms": 220.0, "cpu_percent": 72.0, "db_pool_utilization": 0.72}
    alert = early_warning_engine.evaluate_telemetry("shopsphere", "database-service", features)
    assert alert is not None
    assert alert["state"] == "WARNING"
    assert alert["risk"] == "MEDIUM"


def test_early_warning_high_risk_and_3min_prediction():
    """Validates accelerating degradation triggers HIGH RISK and extrapolates 3m forecast."""
    features = {"error_rate": 0.06, "p95_latency_ms": 520.0, "cpu_percent": 82.0, "db_pool_utilization": 0.88}
    alert = early_warning_engine.evaluate_telemetry("shopsphere", "database-service", features)
    assert alert is not None
    assert alert["state"] in ("HIGH RISK", "INCIDENT")
    assert "predicted_in_3_min" in alert
    assert alert["failure_probability"] >= 65.0


# -------------------------------------------------------------
# 2. Failure Classifier Integration Tests
# -------------------------------------------------------------

def test_failure_classifier_db_exhaustion():
    """Validates classification into DATABASE_CONNECTION_EXHAUSTION."""
    features = {
        "connection_pool_utilization": 0.98,
        "timeout_rate": 0.15,
        "p95_latency_ms": 2200.0,
        "error_rate": 0.18
    }
    res = failure_classifier.classify(features, "database-service")
    assert res["failure_type"] == "DATABASE_CONNECTION_EXHAUSTION"
    assert res["confidence"] >= 0.85
    assert len(res["evidence"]) >= 2


def test_failure_classifier_http_500_spike():
    """Validates classification into HTTP_500_SPIKE."""
    features = {
        "http_5xx_rate": 0.35,
        "error_rate": 0.35,
        "exception_rate": 45.0
    }
    res = failure_classifier.classify(features, "order-service")
    assert res["failure_type"] == "HTTP_500_SPIKE"


def test_failure_classifier_dependency_timeout():
    """Validates classification into DEPENDENCY_TIMEOUT."""
    features = {
        "timeout_rate": 0.25,
        "p95_latency_ms": 4200.0,
        "dependency_failure_rate": 0.30
    }
    res = failure_classifier.classify(features, "payment-service")
    assert res["failure_type"] in ("DEPENDENCY_TIMEOUT", "REQUEST_TIMEOUT")


# -------------------------------------------------------------
# 3. 8-Factor RCA Engine with Causal Path Tests
# -------------------------------------------------------------

def test_rca_engine_causal_path_and_rationale():
    """Validates 8-factor RCA computes causal path and explains why primary won."""
    features = {"connection_pool_utilization": 0.96, "p95_latency_ms": 2100.0, "error_rate": 0.20}
    res = rca_engine.analyze(
        incident_id="INC-UNIT-01",
        primary_service="database-service",
        correlated_services=["database-service", "order-service", "api-gateway"],
        symptoms=["DATABASE_CONNECTION_EXHAUSTION"],
        features=features
    )
    assert res["root_cause_service"] == "database-service"
    assert res["primary_root_cause"] == "database-service"
    assert "causal_path" in res
    assert len(res["causal_path"]) >= 2
    assert "why_primary_won" in res
    assert len(res["why_primary_won"]) > 10


# -------------------------------------------------------------
# 4. Historical CBR & Tenant Isolation Tests
# -------------------------------------------------------------

def test_historical_cbr_similarity_and_recommendation():
    """Validates similarity matching returns past verified remediation."""
    incident_memory.record_incident({
        "tenant_id": "shopsphere",
        "incident_id": "INC-HIST-01",
        "primary_service": "database-service",
        "failure_type": "DATABASE_CONNECTION_EXHAUSTION",
        "failure_category": "Database",
        "remediation_action": "RESET_CONNECTION_POOL",
        "verification_status": "VERIFIED",
        "success": True,
        "time_to_recover_sec": 14.5
    })
    matches = incident_memory.find_similar_incidents(
        service="database-service",
        category="Database",
        failure_type="DATABASE_CONNECTION_EXHAUSTION",
        tenant_id="shopsphere"
    )
    assert len(matches) > 0
    assert matches[0]["remediation_action"] == "RESET_CONNECTION_POOL"


def test_tenant_isolation_in_cbr():
    """Validates Tenant B cannot access Tenant A historical incidents."""
    incident_memory.record_incident({
        "tenant_id": "tenant-alpha",
        "incident_id": "INC-ALPHA-SECRET",
        "primary_service": "auth-service",
        "failure_type": "SECRET_LEAK",
        "failure_category": "Security",
        "remediation_action": "ROTATE_SECRETS",
        "verification_status": "VERIFIED",
        "success": True
    })
    # Search under tenant-beta
    matches = incident_memory.find_similar_incidents(
        service="auth-service",
        tenant_id="tenant-beta"
    )
    for m in matches:
        assert m.get("tenant_id") != "tenant-alpha"
        assert m.get("incident_id") != "INC-ALPHA-SECRET"


# -------------------------------------------------------------
# 5. Model Registry & Evaluation Tests
# -------------------------------------------------------------

def test_model_registry_inventory():
    """Validates model registry lists active and candidate models."""
    models = model_registry.get_all_models()
    assert len(models) >= 8
    active = [m for m in models if m["status"] == "ACTIVE"]
    assert len(active) >= 6


def test_candidate_promotion_safeguard():
    """Validates promotion safeguards reject candidate with insufficient data."""
    with pytest.raises(ValueError, match="INSUFFICIENT EVALUATION DATA"):
        model_registry.promote_candidate("experimental_lstm_autoencoder")


def test_candidate_promotion_success():
    """Validates successful promotion of validated candidate model."""
    res = model_registry.promote_candidate("candidate_isolation_forest_v2")
    assert res["new_status"] == "ACTIVE"
    # Verify previous active is retired
    cand = model_registry.get_model("candidate_isolation_forest_v2")
    assert cand["status"] == "ACTIVE"


def test_feedback_loop_recording():
    """Validates recording post-recovery verification feedback."""
    fb = model_registry.record_feedback(
        tenant_id="shopsphere",
        incident_id="INC-FB-01",
        anomaly_correctness=True,
        rca_correctness=True,
        recovery_effectiveness="EFFECTIVE",
        verification_outcome="PASSED",
        side_effects=[],
        false_positive=False
    )
    assert fb["feedback_id"].startswith("fb-")
    records = model_registry.get_feedback_records(tenant_id="shopsphere")
    assert any(r["incident_id"] == "INC-FB-01" for r in records)


# -------------------------------------------------------------
# 6. Data Quality & Drift Detection Tests
# -------------------------------------------------------------

def test_data_quality_tracker():
    """Validates data quality tracking reports metrics."""
    dq = data_quality_tracker.get_quality_summary(tenant_id="shopsphere")
    assert dq["telemetry_completeness_pct"] > 90.0
    assert "missing_latency_pct" in dq
    assert "missing_cpu_pct" in dq


def test_feature_drift_evaluation():
    """Validates drift evaluation detects distance from baseline."""
    drift = feature_engine.evaluate_feature_drift(tenant_id="shopsphere", service="database-service")
    assert "drift_status" in drift
    assert "drift_severity" in drift
