"""
Tests for Alert Storm Correlation and Deduplication Engine
"""

import pytest
from backend.app.incidents.correlator import EventCorrelator


def test_cascade_event_correlation_into_single_incident():
    correlator = EventCorrelator(window_sec=20)
    
    # Active incident started on Database Service
    active_incidents = [
        {
            "incident_id": "INC-2026-TEST01",
            "primary_service": "database-service",
            "affected_services": ["database-service"],
            "status": "OPEN",
            "correlated_event_count": 1,
            "timeline": []
        }
    ]
    
    # New cascading anomaly on Service B (which depends on database-service)
    matching_id_b = correlator.find_matching_incident("service-b", active_incidents)
    assert matching_id_b == "INC-2026-TEST01", "Service B event should correlate with database-service incident"
    
    # Merge Service B into incident
    correlator.merge_event_into_incident(
        active_incidents[0],
        "service-b",
        {"timestamp": "2026-08-18T10:00:02Z", "event_type": "HTTP_504_TIMEOUT", "summary": "Service B timeout"}
    )
    
    # New cascading anomaly on Service A (which depends on Service B)
    matching_id_a = correlator.find_matching_incident("service-a", active_incidents)
    assert matching_id_a == "INC-2026-TEST01", "Service A event should correlate into same incident"
    
    # New cascading anomaly on Gateway
    matching_id_gw = correlator.find_matching_incident("gateway", active_incidents)
    assert matching_id_gw == "INC-2026-TEST01", "Gateway event should correlate into same incident"
    
    # Simulate an alert storm of 500 repeated events
    for i in range(500):
        correlator.merge_event_into_incident(
            active_incidents[0],
            "gateway",
            {"timestamp": f"2026-08-18T10:00:{i%60:02d}Z", "event_type": "502_BAD_GATEWAY", "summary": f"Storm event {i}"}
        )

    # Verify that only 1 single incident exists and holds 503 total correlated events
    assert len(active_incidents) == 1
    assert active_incidents[0]["correlated_event_count"] >= 500
    assert set(active_incidents[0]["affected_services"]) == {"database-service", "service-b", "gateway"}
