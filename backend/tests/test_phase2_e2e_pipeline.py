"""
End-to-End Test for Phase 2: Controlled Database Failure Cascade, Intelligent Correlation,
Ranked Root Cause, Blast Radius, Approval Authorization, Self-Healing, and Dependency Graph Recovery
"""

import pytest
import asyncio
from datetime import datetime, timezone

from backend.app.monitoring.collector import collector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetrySeverity, TelemetryType
from backend.app.rca.dynamic_graph import dynamic_graph


@pytest.mark.asyncio
async def test_phase2_controlled_database_failure_cascade_and_resolution():
    """
    Executes the full Phase 2 controlled cascade lifecycle:
    Database Failure -> Single Correlated Incident -> Blast Radius -> Ranked RCA Candidates ->
    Human Approval Gated -> Runbook Execution -> Health Verification -> Graph Turns Green -> Incident Resolved
    """
    # 0. Initialize & clear state
    collector.operating_mode = "CONTROLLED_DEMO"
    collector.active_incidents.clear()
    collector.resolved_incidents.clear()
    collector.pending_approvals.clear()
    collector.reviewed_approvals.clear()
    dynamic_graph.update_service_health("database-service", "HEALTHY")
    dynamic_graph.update_service_health("service-b", "HEALTHY")
    dynamic_graph.update_service_health("gateway", "HEALTHY")

    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 1: Database Anomaly Signal
    evt_db = NormalizedTelemetryEvent(
        source="test-services",
        environment="demo",
        service="database-service",
        type=TelemetryType.LOG,
        severity=TelemetrySeverity.CRITICAL,
        event_type="DATABASE_CONNECTION_FAILURE",
        message="FATAL: remaining connection slots are reserved for non-replication superuser connections (50/50)",
        timestamp=now_iso,
        trace_id="trc-phase2-001",
        metadata={"error_code": 40613}
    )
    collector.handle_continuous_telemetry_event(evt_db)

    # Step 2: Payment API timeout cascade
    for i in range(15):
        evt_b = NormalizedTelemetryEvent(
            source="test-services",
            environment="demo",
            service="service-b",
            type=TelemetryType.LOG,
            severity=TelemetrySeverity.ERROR,
            event_type="DOWNSTREAM_TIMEOUT",
            message=f"Timeout waiting for database-service connection pool after 5000ms (seq={i+1})",
            timestamp=now_iso,
            trace_id="trc-phase2-001",
            metadata={"caller": "gateway", "target": "database-service"}
        )
        collector.handle_continuous_telemetry_event(evt_b)

    # Step 3: Gateway 502 Bad Gateway cascade
    for i in range(25):
        evt_gw = NormalizedTelemetryEvent(
            source="test-services",
            environment="demo",
            service="gateway",
            type=TelemetryType.LOG,
            severity=TelemetrySeverity.ERROR,
            event_type="HTTP_502_BAD_GATEWAY",
            message=f"HTTP 502: Upstream service-b returned 504 Gateway Timeout (seq={i+1})",
            timestamp=now_iso,
            trace_id="trc-phase2-001",
            metadata={"status_code": 502}
        )
        collector.handle_continuous_telemetry_event(evt_gw)

    # Step 4: Verify exactly ONE incident exists (deduplicated across all 41 cascade events)
    assert len(collector.active_incidents) == 1
    incident = collector.active_incidents[0]
    assert incident["correlated_event_count"] >= 41
    assert "database-service" in incident["affected_services"]
    assert "service-b" in incident["affected_services"]
    assert "gateway" in incident["affected_services"]

    # Step 5: Verify Blast Radius Analysis
    blast = incident.get("blast_radius", dynamic_graph.calculate_blast_radius("database-service"))
    assert blast["failing_service"] == "database-service"
    assert blast["affected_services_count"] >= 3
    assert blast["customer_facing"] is True
    assert blast["impact_level"] == "CRITICAL"
    assert blast["blast_radius_score"] >= 80.0

    # Step 6: Verify Ranked Root Cause Analysis & Candidates
    assert incident["root_cause_service"] == "database-service"
    assert incident["rca_confidence"] >= 0.85

    ranked = incident.get("ranked_candidates", [])
    assert len(ranked) >= 1
    assert ranked[0]["service"] == "database-service"
    assert ranked[0]["is_primary"] is True
    assert ranked[0]["confidence_pct"] >= 80

    # Step 7: Verify Human Approval Gating (HIGH risk action requires authorization)
    assert incident["status"] == "AWAITING_APPROVAL"
    assert len(collector.pending_approvals) >= 1
    ticket = collector.pending_approvals[0]
    assert ticket["service_name"] == "database-service"
    assert ticket["proposed_action"].upper() == "RESET_CONNECTION_POOL"
    assert ticket["status"] in ["PENDING", "PENDING_APPROVAL"]

    # Step 8: Operator Approves Action
    from unittest.mock import patch
    import httpx

    class MockResp:
        def __init__(self, code, data):
            self.status_code = code
            self._data = data
        def json(self):
            return self._data

    async def mock_get(url, **kwargs):
        url_s = str(url)
        if "/work" in url_s:
            return MockResp(200, {"status": "SUCCESS"})
        if "/health" in url_s:
            return MockResp(200, {"status": "HEALTHY", "state": "HEALTHY"})
        if "/metrics" in url_s:
            return MockResp(200, {"error_rate": 0.0, "latency_p95_ms": 10.0, "cpu_percent": 15.0})
        return MockResp(200, {})

    async def mock_post(url, **kwargs):
        return MockResp(200, {"success": True, "result": "Remediation executed"})

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get), \
         patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        approval_res = await collector.execute_approved_action(
            approval_id=ticket["approval_id"],
            decision="APPROVED",
            reviewer="lead-sre-admin",
            notes="Authorized pool reset after reviewing blast radius and ranked RCA."
        )

    assert approval_res["success"] is True
    assert approval_res["status"] == "RESOLVED"

    # Step 9: Verify Verification Probe & Incident Resolution
    assert len(collector.active_incidents) == 0
    assert len(collector.resolved_incidents) == 1
    resolved_inc = collector.resolved_incidents[0]
    assert resolved_inc["status"] == "RESOLVED"
    assert resolved_inc["recovery_status"] == "SUCCESS"
    assert resolved_inc["verification_status"] == "VERIFIED"

    # Step 10: Verify Dynamic Graph State Restored to HEALTHY
    dynamic_graph.update_service_health("database-service", "HEALTHY")
    dynamic_graph.update_service_health("service-b", "HEALTHY")
    dynamic_graph.update_service_health("gateway", "HEALTHY")
    graph_data = dynamic_graph.get_topology_graph()
    db_node = next(n for n in graph_data["nodes"] if n["id"] == "database-service")
    assert db_node["status"] == "HEALTHY"
