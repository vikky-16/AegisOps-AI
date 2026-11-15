"""
Tests for Dependency-Aware Root-Cause Analysis (RCA) Engine
"""

import pytest
from backend.app.rca.engine import RootCauseAnalysisEngine


def test_rca_identifies_deep_database_root_cause():
    rca = RootCauseAnalysisEngine()
    
    # Cascade scenario: Database failure occurred first at 10:14:02, followed by Service B and Gateway
    events = [
        {"timestamp": "2026-08-18T10:14:02Z", "service_name": "database-service", "event_type": "CONNECTION_POOL_EXHAUSTION"},
        {"timestamp": "2026-08-18T10:14:05Z", "service_name": "service-b", "event_type": "DATABASE_TIMEOUT"},
        {"timestamp": "2026-08-18T10:14:07Z", "service_name": "service-a", "event_type": "500_INTERNAL_ERROR"},
        {"timestamp": "2026-08-18T10:14:09Z", "service_name": "gateway", "event_type": "502_BAD_GATEWAY"},
    ]
    
    metrics = {
        "database-service": {"error_rate": 0.8, "cpu_percent": 45.0, "latency_p95_ms": 1200.0, "active_connections": 20},
        "service-b": {"error_rate": 0.7, "cpu_percent": 30.0, "latency_p95_ms": 2500.0, "active_connections": 10},
        "service-a": {"error_rate": 0.6, "cpu_percent": 25.0, "latency_p95_ms": 2800.0, "active_connections": 8},
        "gateway": {"error_rate": 0.6, "cpu_percent": 15.0, "latency_p95_ms": 3000.0, "active_connections": 5}
    }
    
    affected = ["gateway", "service-a", "service-b", "database-service"]
    
    result = rca.analyze_incident(affected, events, metrics)
    
    assert result["root_cause_service"] == "database-service", f"Expected database-service as root cause, got {result['root_cause_service']}"
    assert result["root_cause_category"] == "CONNECTION_POOL_EXHAUSTION"
    assert result["confidence"] >= 0.75
    assert len(result["evidence"]) >= 2
    assert any("database-service" in e for e in result["evidence"])
