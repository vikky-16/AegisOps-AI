"""
Tests for Advanced Multi-Factor Event Correlation, Incident Deduplication, Error Signature Normalization, and Ranked RCA
"""

import pytest
from datetime import datetime, timezone, timedelta
from backend.app.incidents.signature_normalizer import signature_normalizer, ErrorSignatureNormalizer
from backend.app.incidents.correlator import EventCorrelator
from backend.app.rca.engine import RootCauseAnalysisEngine
from backend.app.incidents.incident_manager import IncidentManager


def test_error_signature_normalization():
    """Verify raw error messages normalize into deterministic canonical signatures."""
    normalizer = ErrorSignatureNormalizer()

    # Database connection exhaustion pattern
    raw_db_msg = "FATAL: remaining connection slots are reserved for non-replication superuser connections (50/50)"
    norm_db = normalizer.normalize(raw_db_msg, "database-service")
    assert norm_db["signature_id"] == "SIG-DB-CONN-001"
    assert norm_db["category"] == "DATABASE_CONNECTION_POOL"
    assert norm_db["severity"] == "CRITICAL"
    assert norm_db["is_cascade_compatible"] is True

    # Upstream HTTP 502/504 gateway pattern
    raw_gw_msg = "HTTP 502 Bad Gateway: Upstream server payment-service timed out after 30000ms"
    norm_gw = normalizer.normalize(raw_gw_msg, "gateway")
    assert norm_gw["signature_id"] == "SIG-GW-502-001"
    assert norm_gw["category"] == "GATEWAY_UPSTREAM_502"
    assert norm_gw["severity"] == "HIGH"


def test_multi_factor_correlation_scoring():
    """Verify deterministic scoring across temporal window, dependency graph, and error signatures."""
    correlator = EventCorrelator(window_seconds=60)

    now = datetime.now(timezone.utc)
    ev_db = {
        "service": "database-service",
        "service_name": "database-service",
        "timestamp": now.isoformat(),
        "event_type": "DATABASE_CONNECTION_EXHAUSTION",
        "message": "connection pool exhausted 50/50",
        "trace_id": "trace-xyz-100"
    }

    ev_b = {
        "service": "service-b",
        "service_name": "service-b",
        "timestamp": (now + timedelta(seconds=2)).isoformat(),
        "event_type": "DOWNSTREAM_TIMEOUT",
        "message": "Database query timeout after 5000ms",
        "trace_id": "trace-xyz-100"
    }

    score, breakdown = correlator.calculate_correlation_score(ev_db, ev_b)
    assert score >= 0.85
    assert breakdown["temporal_factor"] >= 0.20
    assert breakdown["dependency_factor"] >= 0.25
    assert breakdown["trace_factor"] == 0.20


def test_thousand_cascade_events_deduplicated_into_one_incident():
    """
    Requirement 16:
    When a database fails and triggers cascading errors across Payment API and Gateway (1,000 events),
    all 1,000 events MUST be correlated into ONE SINGLE INCIDENT without spamming duplicate incidents.
    """
    correlator = EventCorrelator(window_seconds=60)
    now = datetime.now(timezone.utc)

    # 1. Initial Root Incident Created
    incident = IncidentManager.create_incident_from_anomaly(
        service_name="database-service",
        anomaly_score=0.96,
        evidence=["DB Connection pool exhausted (50/50)"],
        events=[{
            "timestamp": now.isoformat(),
            "service_name": "database-service",
            "event_type": "CONNECTION_POOL_EXHAUSTION",
            "message": "FATAL: connection pool limit reached"
        }]
    )
    active_incidents = [incident]

    # 2. Simulate 1,000 cascade events from database, service-b, service-a, and gateway
    cascade_services = ["database-service", "service-b", "service-a", "gateway"]
    for i in range(1000):
        svc = cascade_services[i % len(cascade_services)]
        evt_dict = {
            "timestamp": (now + timedelta(milliseconds=i * 50)).isoformat(),
            "service_name": svc,
            "event_type": "HTTP_500" if svc != "database-service" else "CONNECTION_ERROR",
            "message": f"Cascading degradation event #{i+1} on {svc}"
        }

        # Correlator checks if event matches existing incident
        matched = correlator.find_matching_incident(
            service_name=svc,
            active_incidents=active_incidents,
            event_dict=evt_dict
        )

        assert matched is not None, f"Event #{i} on {svc} should match existing incident cluster!"
        assert matched == incident["incident_id"]
        
        # Merge event into existing incident
        correlator.merge_event_into_incident(
            incident=active_incidents[0],
            new_service=svc,
            event_entry=evt_dict,
            event_count=1
        )

    # Assert exactly ONE incident exists with all 1,000 correlated events
    assert len(active_incidents) == 1
    assert active_incidents[0]["correlated_event_count"] == 1001
    assert "database-service" in active_incidents[0]["affected_services"]
    assert "service-b" in active_incidents[0]["affected_services"]
    assert "service-a" in active_incidents[0]["affected_services"]
    assert "gateway" in active_incidents[0]["affected_services"]
    assert active_incidents[0]["root_cause_service"] == "database-service"


def test_unrelated_events_create_separate_incidents():
    """Verify unrelated events outside the dependency topology and time window do not merge."""
    correlator = EventCorrelator(window_seconds=60)
    now = datetime.now(timezone.utc)

    inc1 = IncidentManager.create_incident_from_anomaly(
        service_name="service-a",
        anomaly_score=0.88,
        evidence=["Order processing failure"],
        events=[{"timestamp": now.isoformat(), "service_name": "service-a", "event_type": "ORDER_ERROR", "message": "Order validation failed"}]
    )
    active_incidents = [inc1]

    # Event on an unrelated external resource outside the window
    unrelated_event = {
        "timestamp": (now + timedelta(hours=3)).isoformat(),
        "service_name": "isolated-backup-worker",
        "event_type": "BACKUP_DISK_FULL",
        "message": "Local backup disk /mnt/backup full"
    }

    matched = correlator.find_matching_incident(
        service_name="isolated-backup-worker",
        active_incidents=active_incidents,
        event_dict=unrelated_event
    )

    assert matched is None


def test_ranked_root_cause_candidates_and_causal_ordering():
    """Verify root cause ranking calculates confidence and preserves earliest onset order."""
    engine = RootCauseAnalysisEngine()
    
    t0 = datetime(2026, 8, 22, 14, 30, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=2)
    t2 = t0 + timedelta(seconds=4)

    events = [
        {"timestamp": t0.isoformat(), "service_name": "database-service", "event_type": "CONNECTION_POOL_EXHAUSTION", "message": "50/50 pool exhausted"},
        {"timestamp": t1.isoformat(), "service_name": "service-b", "event_type": "TIMEOUT_504", "message": "Payment gateway timeout on DB write"},
        {"timestamp": t2.isoformat(), "service_name": "gateway", "event_type": "HTTP_502", "message": "Bad gateway upstream"}
    ]

    res = engine.analyze_incident(
        affected_services=["gateway", "service-b", "database-service"],
        events=events,
        current_metrics={}
    )

    assert res["root_cause_service"] == "database-service"
    assert res["confidence"] >= 0.85

    ranked = res["ranked_candidates"]
    assert len(ranked) == 3
    assert ranked[0]["service"] == "database-service"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["is_primary"] is True
    assert ranked[0]["confidence_pct"] >= 80

    # Ensure secondary services are ranked lower
    assert ranked[1]["confidence_pct"] < ranked[0]["confidence_pct"]
    assert ranked[2]["confidence_pct"] < ranked[1]["confidence_pct"]


def test_explainable_correlation_rationale():
    """Verify human-readable bullet points explaining correlation grouping."""
    correlator = EventCorrelator()
    incident = {
        "incident_id": "INC-TEST-01",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "service-b", "service-a", "gateway"],
        "correlated_event_count": 842,
        "timeline": [
            {"service": "database-service", "timestamp": "2026-08-22T14:31:01Z", "message": "DB lock timeout"},
            {"service": "service-b", "timestamp": "2026-08-22T14:31:03Z", "message": "Payment timeout"},
            {"service": "gateway", "timestamp": "2026-08-22T14:31:05Z", "message": "502 Bad Gateway"}
        ]
    }

    explanation = correlator.generate_correlation_explanation(incident)
    assert explanation["confidence_pct"] >= 85
    assert explanation["total_correlated_events"] == 842
    assert len(explanation["reasons"]) >= 4
    assert any("842 telemetry events" in r for r in explanation["reasons"])
    assert any("topological dependency chain" in r for r in explanation["reasons"])
    assert any("Earliest failure onset" in r for r in explanation["reasons"])
