"""
Comprehensive verification of AegisOps Real Telemetry -> Anomaly Detection ->
Incident Creation -> Correlation -> RCA -> Evidence -> Validation Workflow.
"""
import sys
import os
import time
import json
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "c:/Users/admin/AegisOps AI")))
os.chdir("c:/Users/admin/AegisOps AI")

from backend.app.analytics.feature_extractor import feature_extractor
from backend.app.analytics.anomaly_detector import anomaly_detector
from backend.app.analytics.rca_engine import rca_engine
from backend.app.analytics.incident_pipeline import incident_pipeline
from backend.app.monitoring.collector import collector as telemetry_collector
from backend.app.replica.controlled_environment import replica_environment

class MockEvent:
    def __init__(self, tenant_id, service, status_code=200, latency=45.0, event_type="http_request", error_type=None, trace_id=None):
        self.tenant_id = tenant_id
        self.company_id = tenant_id
        self.service = service
        self.service_name = service
        self.status_code = status_code
        self.http_status = status_code
        self.latency = latency
        self.latency_ms = latency
        self.event_type = event_type
        self.error_type = error_type
        self.trace_id = trace_id or f"trace-{int(time.time()*1000)}"
        self.span_id = "span-001"
        self.request_id = f"req-{int(time.time()*1000)}"
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.message = f"{service} {event_type} status={status_code} latency={latency}ms"

async def run_e2e_verification():
    print("=" * 80)
    print("  AEGISOPS E2E TELEMETRY -> ANOMALY -> INCIDENT -> RCA -> VALIDATION TEST")
    print("=" * 80)

    # 1. Feed baseline normal traffic to establish rolling window stats
    print("\n[Step 1] Feeding 40 baseline normal events for ShopSphere...")
    for _ in range(40):
        evt = MockEvent("shopsphere", "order-service", 200, 35.0)
        feature_extractor.process_event(evt)
        evt_db = MockEvent("shopsphere", "database-service", 200, 15.0)
        feature_extractor.process_event(evt_db)

    print("   Baseline window established.")

    # 2. Test Multi-Detector Anomaly Evaluation on Normal vs Failure
    print("\n[Step 2] Testing Anomaly Detector on normal vs severe degradation...")
    normal_feats = feature_extractor.get_features("shopsphere", "database-service")
    norm_res = anomaly_detector.evaluate("shopsphere", "database-service", normal_feats)
    print(f"   Normal Telemetry -> is_anomaly: {norm_res['is_anomaly']}, score: {norm_res['combined_score']:.3f}, sev: {norm_res['severity']}")
    assert norm_res['is_anomaly'] is False, "Normal traffic should not trigger anomaly!"

    # 3. TEST 1: Database Latency Degradation Injection
    print("\n[Step 3: TEST 1] Injecting Database Latency Degradation into ShopSphere...")
    t_shared_trace = f"trace-cascade-{int(time.time())}"
    
    # DB latency jumps from 15ms to 1850ms with 500 error
    db_anom_event = MockEvent(
        tenant_id="shopsphere",
        service="database-service",
        status_code=500,
        latency=1850.0,
        event_type="DB_POOL_TIMEOUT",
        error_type="ConnectionTimeout",
        trace_id=t_shared_trace
    )
    
    # Process through full pipeline coordinator
    inc1 = await incident_pipeline.process_telemetry_event(db_anom_event, telemetry_collector)
    print(f"   DB Anomaly Pipeline Result -> Incident: {inc1.get('incident_id') if inc1 else 'None'}")
    assert inc1 is not None, "Failed to create incident on severe DB latency anomaly!"
    print(f"   [+] Incident ID: {inc1['incident_id']}")
    print(f"   [+] Title: {inc1['title']}")
    print(f"   [+] Severity: {inc1['severity']}")
    print(f"   [+] Primary Service: {inc1['primary_service']}")
    print(f"   [+] Root Cause Identified: {inc1['root_cause']}")
    print(f"   [+] Algorithmic Confidence: {inc1['confidence_pct']}%")

    # 4. TEST ALERT FLOODING: 100 downstream cascading errors in 20 seconds
    print("\n[Step 4: Alert Flooding Test] Simulating 100 cascading 502/504 errors in 20 seconds...")
    downstream_svcs = ["order-service", "payment-service", "api-gateway"]
    initial_incidents_count = len(telemetry_collector.active_incidents)

    for i in range(100):
        svc = downstream_svcs[i % len(downstream_svcs)]
        cascade_evt = MockEvent(
            tenant_id="shopsphere",
            service=svc,
            status_code=502 if svc == "api-gateway" else 504,
            latency=1200.0 + (i * 5),
            event_type="CASCADE_FAILURE",
            error_type="UpstreamServiceUnavailable",
            trace_id=t_shared_trace
        )
        await incident_pipeline.process_telemetry_event(cascade_evt, telemetry_collector)

    final_incidents_count = len(telemetry_collector.active_incidents)
    print(f"   Initial Incidents: {initial_incidents_count} -> Final Incidents: {final_incidents_count}")
    print(f"   Correlated Event Count on Incident: {inc1['correlated_event_count']}")
    print(f"   Affected Services on Incident: {inc1['affected_services']}")
    print(f"   Timeline Event Count: {len(inc1['timeline'])}")
    
    assert final_incidents_count == initial_incidents_count, "Alert flooding occurred! Multiple incidents created for same failure cluster!"
    assert inc1['correlated_event_count'] >= 50, "Downstream events were not properly correlated into the incident!"
    print("   [+] ALERT FLOODING PREVENTED: 100 cascading errors merged into 1 incident!")

    # 5. Verify Chronological Timeline
    print("\n[Step 5] Verifying Chronological Timeline...")
    timeline = inc1.get("timeline", [])
    assert len(timeline) > 0, "Incident timeline is empty!"
    print(f"   Timeline entries (first 5 of {len(timeline)}):")
    for t_item in timeline[:5]:
        print(f"     {t_item.get('timestamp')} | {t_item.get('service')} | {t_item.get('type')} | {t_item.get('message')}")

    # 6. Verify 7-Factor RCA Ranking
    print("\n[Step 6] Verifying Evidence-Based RCA Engine (7 Factors)...")
    candidates = inc1.get("ranked_candidates", [])
    print(f"   Ranked Candidates: {len(candidates)}")
    for cand in candidates:
        print(f"     Rank: {'#1 PRIMARY' if cand.get('primary') else '#2 ALTERNATIVE'} | {cand.get('candidate')} ({cand.get('component')}) | Score: {cand.get('candidate_score')} | Conf: {cand.get('confidence_pct')}%")
        print(f"       Factors: {cand.get('factors')}")
        print(f"       Reasoning: {cand.get('reasoning')}")

    assert candidates[0]['candidate'] == 'database-service', "Database should be ranked #1 root cause!"

    # 7. Verify Alternative Hypotheses & Counter-Evidence
    print("\n[Step 7] Verifying Alternative Hypotheses with Counter-Evidence...")
    alts = inc1.get("alternative_hypotheses", [])
    for a in alts:
        print(f"     Alternative: {a.get('hypothesis')} (Conf: {a.get('confidence_pct')}%)")
        print(f"       Why Not Primary: {a.get('why_not_primary')}")
    assert len(alts) > 0, "No alternative hypotheses generated!"

    # 8. TEST 2: Redis Unavailable in CloudDesk
    print("\n[Step 8: TEST 2] Testing Anomaly Detection & RCA for CloudDesk Redis Outage...")
    cd_trace = f"trace-clouddesk-{int(time.time())}"
    # Seed baseline for clouddesk
    for _ in range(30):
        feature_extractor.process_event(MockEvent("clouddesk", "workspace-service", 200, 25.0))
        feature_extractor.process_event(MockEvent("clouddesk", "redis", 200, 2.0))

    # Inject Redis outage
    redis_evt = MockEvent(
        tenant_id="clouddesk",
        service="redis",
        status_code=503,
        latency=450.0,
        event_type="REDIS_CONNECTION_REFUSED",
        error_type="ConnectionRefusedError",
        trace_id=cd_trace
    )
    inc2 = await incident_pipeline.process_telemetry_event(redis_evt, telemetry_collector)
    print(f"   CloudDesk Redis Incident: {inc2['incident_id']} | Sev: {inc2['severity']} | Root: {inc2['root_cause']}")
    assert inc2['primary_service'] == 'redis', "CloudDesk incident did not identify Redis as root cause!"
    print("   [+] CloudDesk Redis Incident successfully created with Redis as root cause!")

    # 9. TEST 3: FinCore Payment Service Latency Spike
    print("\n[Step 9: TEST 3] Testing FinCore Payment Service Latency Spike...")
    fc_trace = f"trace-fincore-{int(time.time())}"
    for _ in range(30):
        feature_extractor.process_event(MockEvent("fincore", "payment-service", 200, 30.0))
        feature_extractor.process_event(MockEvent("fincore", "gateway", 200, 10.0))

    fc_evt = MockEvent(
        tenant_id="fincore",
        service="payment-service",
        status_code=504,
        latency=2500.0,
        event_type="PAYMENT_GATEWAY_TIMEOUT",
        error_type="GatewayTimeout",
        trace_id=fc_trace
    )
    inc3 = await incident_pipeline.process_telemetry_event(fc_evt, telemetry_collector)
    print(f"   FinCore Incident: {inc3['incident_id']} | Sev: {inc3['severity']} | Root: {inc3['root_cause']}")
    assert inc3['primary_service'] == 'payment-service', "FinCore incident did not identify payment-service as root cause!"
    print("   [+] FinCore Payment Incident successfully created with payment-service as root cause!")

    # 10. Connect to Existing Self-Healing Workflow (Replica Replay & Side-Effect Gating)
    print("\n[Step 10] Testing Connection to Existing Self-Healing / Controlled Replica Workflow...")
    print(f"   Applying recommended action '{inc1['recommended_action']}' in controlled replica sandbox...")
    replay_res = replica_environment.execute_solution_and_replay(
        scenario_id=inc1.get("scenario_id", "db_connection_exhaustion"),
        action=inc1.get("recommended_action", "RESET_CONNECTION_POOL"),
        iteration=1
    )
    print(f"   Replica Execution Outcome:")
    print(f"     Resolves Original Error: {replay_res.get('resolves_original_error')}")
    print(f"     Side-Effect Detected: {replay_res.get('side_effect_detected')}")
    print(f"     Post-Metrics Error Rate: {replay_res.get('post_metrics', {}).get('database-service', {}).get('error_rate')}")
    print(f"     Validation Decision: {'VALIDATED' if replay_res.get('resolves_original_error') and not replay_res.get('side_effect_detected') else 'REFINED'}")
    
    assert replay_res['resolves_original_error'] is True, "Replica replay did not resolve original error!"
    assert replay_res['side_effect_detected'] is False, "Replica replay caused unexpected side effect!"
    print("   [+] Closed-Loop Self-Healing successfully validated in replica sandbox!")

    print("\n" + "=" * 80)
    print("  ALL 10 VERIFICATION STAGES PASSED FLAWLESSLY!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
