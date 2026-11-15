"""
Master 23-Step End-to-End Closed-Loop Verification Test
Tests the complete autonomous observability, AIOps, incident response, and self-healing lifecycle:

1. Normal telemetry baseline ingestion
2. Failure/anomaly injection (behavioral latency surge on database-service)
3. Universal normalization into UnifiedTelemetryEvent
4. Kafka / EventBus streaming dispatch
5. Multi-detector engine evaluation
6. Behavioral anomaly detection without explicit error logs
7. Event correlation across services (correlator window)
8. Fingerprint generation (FP-DATABASE_SERVICE-...)
9. Deduplicated Incident creation
10. Dynamic Topology graph construction
11. Multi-metric anomaly score aggregation
12. Ranked Root Cause Analysis (RCA) with confidence score & causal rationale
13. Blast radius & business impact estimation
14. Decision Engine policy evaluation (risk, freshness, cooldown)
15. Autonomous remediation decision & allowlist check
16. Action Lock acquisition
17. Execution of allowlisted recovery action (RESET_CONNECTION_POOL)
18. Cooldown timestamp recording
19. Transition to VERIFYING state with wait for fresh telemetry
20. Post-remediation multi-point verification probe
21. Verified healthy state -> Transition to RESOLVED
22. Persistent indexing into Incident Memory Store
23. AI Explanation generation with grounded causal factors and mitigation history
"""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.integrations.normalizer import universal_normalizer
from backend.app.kafka.event_bus import AegisEventBus
from backend.app.ai.baselines import baseline_manager
from backend.app.ai.detectors.multi_detector_engine import multi_detector_engine
from backend.app.ai.model_manager import model_manager
from backend.app.incidents.correlator import event_correlator
from backend.app.incidents.incident_manager import IncidentManager
from backend.app.rca.dynamic_graph import dynamic_graph
from backend.app.rca.engine import rca_engine
from backend.app.healing.decision_engine import decision_engine
from backend.app.healing.self_healing_engine import self_healing_engine
from backend.app.knowledge.incident_memory import incident_memory
from backend.app.ai.explanation_engine import explanation_engine


@pytest.mark.asyncio
async def test_master_23_step_closed_loop_pipeline():
    # -------------------------------------------------------------
    # STEP 1: Normal telemetry baseline ingestion
    # -------------------------------------------------------------
    for i in range(15):
        baseline_manager.record_sample("database-service", "latency_p95_ms", 35.0 + (i % 5))
        baseline_manager.record_sample("database-service", "error_rate", 0.0)
        baseline_manager.record_sample("database-service", "active_connections", 12.0)

    db_baseline = baseline_manager.get_baseline("database-service", "latency_p95_ms")
    assert db_baseline["sample_count"] >= 15
    assert db_baseline["mean"] < 50.0

    # -------------------------------------------------------------
    # STEP 2: Failure/anomaly injection (behavioral latency surge)
    # -------------------------------------------------------------
    raw_payload = {
        "service": "database-service",
        "type": "metric",
        "name": "latency_p95_ms",
        "value": 1950.0,
        "level": "INFO",  # Note: INFO level to test behavioral anomaly without ERROR logs
        "message": "Transaction completed with high latency; connection pool saturated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attributes": {
            "active_connections": 95,
            "max_pool_size": 100,
            "error_rate": 0.0
        }
    }

    # -------------------------------------------------------------
    # STEP 3: Universal normalization into UnifiedTelemetryEvent
    # -------------------------------------------------------------
    unified_event = universal_normalizer.normalize(raw_payload, source_type="json_rest")
    assert isinstance(unified_event, UnifiedTelemetryEvent)
    assert unified_event.service_name == "database-service"
    assert unified_event.metric_value == 1950.0
    assert unified_event.event_type == "metric"

    # -------------------------------------------------------------
    # STEP 4: Kafka / EventBus streaming dispatch
    # -------------------------------------------------------------
    event_bus = AegisEventBus()
    await event_bus.start()
    bus_emitted = await event_bus.emit(unified_event, topic="telemetry.metrics")
    assert bus_emitted is True
    await event_bus.stop()

    # -------------------------------------------------------------
    # STEP 5: Multi-detector engine evaluation
    # -------------------------------------------------------------
    detector_result = multi_detector_engine.evaluate_metric(
        service="database-service",
        metric_name="latency_p95_ms",
        current_value=1950.0,
        history=[35.0, 36.0, 37.0, 38.0],
        baseline=db_baseline
    )
    assert detector_result.is_anomaly is True
    assert detector_result.severity in ("CRITICAL", "HIGH", "WARNING")

    # -------------------------------------------------------------
    # STEP 6: Behavioral anomaly detection without explicit error logs
    # -------------------------------------------------------------
    is_anom, score, evidence = model_manager.evaluate_telemetry("database-service", {
        "cpu_percent": 35.0,
        "memory_mb": 256.0,
        "error_rate": 0.0,
        "latency_p95_ms": 1950.0,
        "request_count": 200,
        "active_connections": 95
    })
    assert is_anom is True
    assert score >= 0.85
    assert any("behavioral" in ev.lower() or "latency" in ev.lower() for ev in evidence)

    # -------------------------------------------------------------
    # STEP 7: Event correlation across services (correlator window)
    # -------------------------------------------------------------
    # Record events into event correlator
    event_correlator.add_event({
        "service_name": "database-service",
        "event_type": "CONNECTION_POOL_EXHAUSTION",
        "message": "Database connection pool saturated 50/50 connections",
        "timestamp": time.time()
    })
    event_correlator.add_event({
        "service_name": "service-b",
        "event_type": "TIMEOUT",
        "message": "Downstream database query timeout on /pay",
        "timestamp": time.time() + 1.0
    })

    are_corr = event_correlator.are_services_correlated("database-service", "service-b")
    assert are_corr is True

    # -------------------------------------------------------------
    # STEP 8: Fingerprint generation (FP-DATABASE_SERVICE-...)
    # -------------------------------------------------------------
    fingerprint = event_correlator.generate_fingerprint("database-service", "CONNECTION_POOL_EXHAUSTION")
    assert fingerprint.startswith("FP-")
    assert len(fingerprint) > 5

    # -------------------------------------------------------------
    # STEP 9: Deduplicated Incident creation
    # -------------------------------------------------------------
    events_list = [
        {"service_name": "database-service", "message": "Connection pool exhaustion 50/50", "event_type": "CONNECTION_POOL_EXHAUSTION", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"service_name": "service-b", "message": "Downstream timeout waiting for database pool", "event_type": "TIMEOUT", "timestamp": datetime.now(timezone.utc).isoformat()}
    ]
    incident = IncidentManager.create_incident_from_anomaly(
        service_name="database-service",
        anomaly_score=score,
        evidence=evidence,
        events=events_list,
        metrics_snapshot={
            "database-service": {"error_rate": 0.12, "latency_p95_ms": 1950.0, "request_count": 250},
            "service-b": {"error_rate": 0.45, "latency_p95_ms": 1500.0, "request_count": 250}
        }
    )
    incident["recommended_action"] = "RESET_CONNECTION_POOL"
    assert incident["incident_id"].startswith("INC-")
    assert incident["root_cause_service"] == "database-service"
    assert incident["status"] == "INVESTIGATING"

    # -------------------------------------------------------------
    # STEP 10: Dynamic Topology graph construction
    # -------------------------------------------------------------
    all_svcs = dynamic_graph.get_all_services()
    assert "database-service" in all_svcs
    dependents = dynamic_graph.get_dependents("database-service")
    assert len(dependents) >= 1

    # -------------------------------------------------------------
    # STEP 11 & 12: Ranked Root Cause Analysis (RCA) with confidence & rationale
    # -------------------------------------------------------------
    rca_analysis = rca_engine.analyze_incident(
        affected_services=["database-service", "service-b", "gateway"],
        events=events_list,
        current_metrics={
            "database-service": {"error_rate": 0.12, "latency_p95_ms": 1950.0},
            "service-b": {"error_rate": 0.45, "latency_p95_ms": 1500.0}
        }
    )
    assert rca_analysis["root_cause_service"] == "database-service"
    assert rca_analysis["confidence"] >= 0.80
    assert len(rca_analysis["ranked_candidates"]) >= 2
    assert rca_analysis["ranked_candidates"][0]["service"] == "database-service"
    assert rca_analysis["ranked_candidates"][0]["is_primary"] is True

    # -------------------------------------------------------------
    # STEP 13: Blast radius & business impact estimation
    # -------------------------------------------------------------
    blast_calc = dynamic_graph.calculate_blast_radius(
        failing_service="database-service",
        error_rate=0.45,
        request_count=250
    )
    assert blast_calc["blast_radius_score"] >= 40.0
    assert "service-b" in blast_calc["downstream_impact"] or "gateway" in blast_calc["downstream_impact"]

    # -------------------------------------------------------------
    # STEP 14: Decision Engine policy evaluation (risk, freshness, cooldown)
    # -------------------------------------------------------------
    decision = decision_engine.evaluate(incident, telemetry_fresh=True)
    assert decision["decision"] in ("AUTO_REMEDIATE", "REQUEST_APPROVAL")
    assert decision["risk_level"] == "LOW"

    # -------------------------------------------------------------
    # STEP 15: Autonomous remediation decision & allowlist check
    # -------------------------------------------------------------
    assert decision["action"] == "RESET_CONNECTION_POOL"

    # -------------------------------------------------------------
    # STEP 16: Action Lock acquisition
    # -------------------------------------------------------------
    lock_ok = self_healing_engine.acquire_lock("database-service", "RESET_CONNECTION_POOL")
    assert lock_ok is True
    self_healing_engine.release_lock("database-service")

    # -------------------------------------------------------------
    # STEP 17-21: Full recovery loop (Execution -> Fresh telemetry wait -> Multi-point probe -> RESOLVED)
    # -------------------------------------------------------------
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
        recovery_result = await self_healing_engine.execute_recovery_loop(
            incident=incident,
            action="RESET_CONNECTION_POOL",
            caller="Autonomous_Aegis_Agent",
            fresh_telemetry_wait_sec=0.1
        )

    # STEP 20 & 21 verification
    assert recovery_result["success"] is True
    assert incident["status"] == "RESOLVED"
    assert incident["verification_status"] == "VERIFIED"
    assert incident["resolved_at"] is not None

    # STEP 18 cooldown check
    assert decision_engine.last_action_per_service.get("database-service") is not None

    # -------------------------------------------------------------
    # STEP 22: Persistent indexing into Incident Memory Store
    # -------------------------------------------------------------
    memory_matches = incident_memory.find_similar_incidents(
        service="database-service",
        category="CONNECTION_POOL_EXHAUSTION"
    )
    assert len(memory_matches) >= 1
    assert memory_matches[0]["action_taken"] == "RESET_CONNECTION_POOL"
    assert memory_matches[0]["verification_status"] == "VERIFIED"

    # -------------------------------------------------------------
    # STEP 23: AI Explanation generation with grounded causal factors and mitigation history
    # -------------------------------------------------------------
    ai_explanation = explanation_engine.explain_incident(incident)
    assert ai_explanation["incident_id"] == incident["incident_id"]
    assert ai_explanation["root_cause_service"] == "database-service"
    assert len(ai_explanation["causal_factors"]) >= 1
    assert len(ai_explanation["mitigation_history"]) >= 1
    assert "remediation_summary" in ai_explanation
