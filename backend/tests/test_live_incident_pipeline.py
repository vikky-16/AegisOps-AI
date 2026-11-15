"""
AegisOps AI - Phase 21 End-to-End Live Incident Pipeline Integration Test
Verifies the complete causal flow:
REAL EVENT -> ANOMALY -> INCIDENT -> RCA -> EVIDENCE -> VALIDATION CONNECTION
"""

import os
import sys
import time
import uuid
import pytest
import asyncio
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Set warm-up baseline duration to 0 for test execution speed
os.environ["BASELINE_WARMUP_SECONDS"] = "0"

from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent, TelemetrySeverityLevel
from backend.app.analytics.incident_pipeline import IncidentPipelineCoordinator
from backend.app.monitoring.collector import collector
from backend.app.analytics.feature_extractor import feature_extractor
from backend.app.analytics.anomaly_detector import anomaly_detector
from backend.app.analytics.rca_engine import rca_engine
from backend.app.core.database import init_db


@pytest.mark.asyncio
async def test_live_incident_pipeline():
    """
    End-to-End verification:
    1. Real Telemetry Event Ingestion
    2. Multi-Method Anomaly Detection (Z-score + EWMA + Isolation Forest + Error-Rate)
    3. Incident Correlation & Creation
    4. Algorithmic 7-Factor RCA & Structured Evidence Ranking
    """
    await init_db()
    coordinator = IncidentPipelineCoordinator()
    coordinator.baseline_warmup_seconds = 0.0

    tenant = "shopsphere"
    service = "order-service"
    trace_id = f"trace-{uuid.uuid4().hex[:16]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 1: Prime rolling baseline with 10 normal low-latency events (~25ms)
    for i in range(10):
        normal_event = UnifiedTelemetryEvent(
            event_id=f"EVT-NORM-{i}-{uuid.uuid4().hex[:6]}",
            tenant_id=tenant,
            company_id=tenant,
            service_name=service,
            timestamp=now_iso,
            event_type="trace",
            severity="INFO",
            latency=25.0 + (i % 5),
            http_status=200,
            trace_id=f"trace-baseline-{i}",
            message="GET /api/v1/orders HTTP 200 OK"
        )
        res = await coordinator.process_telemetry_event(normal_event, collector)
        assert res is None, "Baseline normal events must not trigger anomalies"

    # Step 2: Inject real degraded event with 2800ms database query latency and 500 error
    degraded_event = UnifiedTelemetryEvent(
        event_id=f"EVT-DEG-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant,
        company_id=tenant,
        service_name=service,
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type="log",
        severity="CRITICAL",
        latency=2800.0,
        http_status=500,
        trace_id=trace_id,
        message="Database query timed out after 2800ms: OperationalError: connection pool exhausted",
        attributes={
            "error_type": "DatabaseTimeout",
            "db_latency_ms": 2750.0,
            "dependency": "postgresql"
        }
    )

    # Step 3: Execute pipeline coordinator
    incident = await coordinator.process_telemetry_event(degraded_event, collector)

    # Step 4: Verify Incident Creation
    assert incident is not None, "Pipeline must create an incident on severe database latency surge!"
    assert incident["tenant_id"] == tenant
    assert service in incident["affected_services"]
    assert incident["severity"] in ("HIGH", "CRITICAL")
    assert incident["status"] in ("OPEN", "INVESTIGATING", "IDENTIFIED")

    # Step 5: Verify Incident Timeline
    timeline = incident.get("timeline", [])
    assert len(timeline) >= 1, "Incident must contain timeline events"
    assert timeline[0]["service"] == service

    # Step 6: Verify Algorithmic RCA
    rca = incident.get("rca", {})
    assert rca is not None, "Incident must contain RCA analysis"
    assert "root_cause_service" in rca
    assert "confidence_pct" in rca
    assert rca["confidence_pct"] >= 50, f"Confidence too low: {rca['confidence_pct']}%"
    assert "ranked_candidates" in rca
    assert len(rca["ranked_candidates"]) >= 1, "RCA must provide ranked candidate causes"

    # Step 7: Verify Evidence Structure
    evidence = rca.get("evidence", [])
    assert len(evidence) >= 1, "RCA must produce verifiable evidence items"

    print("\n" + "=" * 70)
    print("   TEST_LIVE_INCIDENT_PIPELINE PASSED END-TO-END!")
    print(f"   Incident ID:      {incident.get('incident_id')}")
    print(f"   Tenant:           {incident.get('tenant_id')}")
    print(f"   Severity:         {incident.get('severity')}")
    print(f"   Root Cause:       {rca.get('root_cause_service')}")
    print(f"   Confidence:       {rca.get('confidence_pct')}%")
    print(f"   Evidence Items:   {len(evidence)}")
    print(f"   Timeline Events:  {len(timeline)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_live_incident_pipeline())
