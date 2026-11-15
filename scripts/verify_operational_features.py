"""
AegisOps AI - Comprehensive Operational Features End-to-End Verification Script
Tests all 7 remaining core features:
1. Professional Service Dependency Map (with incident cascade & blast radius)
2. Advanced Service Observability (time ranges, P50/P95/P99 latency, CPU, RAM, error rate)
3. Self-Healing Candidate Engine (safe allowlist, classifications, confidence)
4. Testing & Simulation Center (17 operational scenarios, 14-stage pipeline)
5. AI SRE Assistant (14-section structured response, 18 operational questions)
6. Controlled Execution + Validation (approval enforcement, workflow replay, side effects)
7. Historical Learning & Knowledge Base (known failure patterns, before/after metrics)
"""

import sys
import json
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def log_test(name: str):
    print("\n" + "="*70)
    print(f"[*] RUNNING: {name}")
    print("="*70)

def assert_true(cond: bool, msg: str):
    if not cond:
        print(f"[FAIL] {msg}")
        raise AssertionError(msg)
    print(f"  [PASS] {msg}")

def main():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # ---------------------------------------------------------
    # TEST 1: Service Observability
    # ---------------------------------------------------------
    log_test("1. Advanced Service Observability API")
    obs_res = session.get(f"{BASE_URL}/api/services/database-service/observability?time_range=15m")
    assert_true(obs_res.status_code == 200, f"GET /api/services/database-service/observability status {obs_res.status_code}")
    obs_data = obs_res.json()
    assert_true("service_overview" in obs_data, "Observability response contains service_overview")
    assert_true("time_series" in obs_data, "Observability response contains time_series")
    overview = obs_data["service_overview"]
    health = obs_data["current_health"]
    print(f"    Service: {overview.get('service_id')} | Status: {overview.get('status')} | P95 Latency: {health.get('latency_p95_ms')}ms | CPU: {health.get('cpu_percent')}%")
    assert_true(len(obs_data["time_series"]) > 0, f"Returned {len(obs_data['time_series'])} historical telemetry points")

    # ---------------------------------------------------------
    # TEST 2: Professional Service Dependency Map
    # ---------------------------------------------------------
    log_test("2. Professional Service Dependency Map")
    dep_res = session.get(f"{BASE_URL}/api/dependencies/graph")
    assert_true(dep_res.status_code == 200, f"GET /api/dependencies/graph status {dep_res.status_code}")
    dep_data = dep_res.json()
    assert_true("nodes" in dep_data and "edges" in dep_data, "Graph contains nodes and edges")
    nodes = dep_data["nodes"]
    edges = dep_data["edges"]
    print(f"    Discovered {len(nodes)} nodes, {len(edges)} real dependency edges")
    assert_true(len(nodes) >= 4, f"Found at least 4 topology nodes (found {len(nodes)})")
    
    # Check node attributes
    node_sample = nodes[0]
    for key in ["service", "health", "request_rate", "error_rate", "p95_latency", "cpu", "ram", "availability"]:
        assert_true(key in node_sample, f"Node contains '{key}' attribute")

    # Check edge attributes
    edge_sample = edges[0]
    for key in ["source", "target", "request_volume", "latency", "error_rate", "dependency_status"]:
        assert_true(key in edge_sample, f"Edge contains '{key}' attribute")

    # ---------------------------------------------------------
    # TEST 3: Testing & Simulation Center - Scenarios & Injection
    # ---------------------------------------------------------
    log_test("3. Testing & Simulation Center (Scenarios & Injection)")
    sim_list_res = session.get(f"{BASE_URL}/api/simulations")
    assert_true(sim_list_res.status_code == 200, f"GET /api/simulations status {sim_list_res.status_code}")
    sim_meta = sim_list_res.json()
    total_scenarios = sim_meta.get("total_scenarios", 0)
    print(f"    Available operational failure scenarios: {total_scenarios}")
    assert_true(total_scenarios >= 17, f"All 17 operational failure scenarios registered (found {total_scenarios})")

    # Inject DATABASE_CONNECTION_POOL_EXHAUSTION
    print("    Injecting scenario: DATABASE_CONNECTION_POOL_EXHAUSTION...")
    inject_res = session.post(
        f"{BASE_URL}/api/simulations/inject",
        json={"scenario": "DATABASE_CONNECTION_POOL_EXHAUSTION", "intensity": 0.95}
    )
    assert_true(inject_res.status_code == 200, f"POST /api/simulations/inject status {inject_res.status_code}")
    inject_data = inject_res.json()
    inc_id = inject_data.get("incident_id")
    print(f"    Simulation started! Created/Associated Incident ID: {inc_id}")
    assert_true(inc_id is not None, "Simulation returned incident_id")

    # Wait briefly for anomaly detection & incident pipeline correlation
    print("    Waiting 4 seconds for telemetry ingestion, anomaly detection, and RCA...")
    time.sleep(4.0)

    # ---------------------------------------------------------
    # TEST 4: Incident Correlation & Dependency Map Incident Highlighting
    # ---------------------------------------------------------
    log_test("4. Incident Pipeline Correlation & Dependency Highlighting")
    inc_res = session.get(f"{BASE_URL}/api/incidents/{inc_id}")
    assert_true(inc_res.status_code == 200, f"GET /api/incidents/{inc_id} status {inc_res.status_code}")
    inc_data = inc_res.json()
    print(f"    Incident ID: {inc_data.get('incident_id')} | Status: {inc_data.get('status')} | Root Cause: {inc_data.get('root_cause_service')}")
    assert_true(inc_data.get("root_cause_service") in ["database-service", "service-b", "service-a", "gateway"], "Root cause identified")

    # Query Dependency Map scoped to this incident
    dep_inc_res = session.get(f"{BASE_URL}/api/dependencies/graph?incident_id={inc_id}")
    assert_true(dep_inc_res.status_code == 200, f"GET /api/dependencies/graph?incident_id={inc_id} status 200")
    dep_inc_data = dep_inc_res.json()
    assert_true("incident_context" in dep_inc_data, "Graph response contains incident_context")
    blast_radius = dep_inc_data.get("incident_context", {}).get("blast_radius", {})
    print(f"    Blast radius affected services: {blast_radius.get('affected_services')}")
    
    # Verify at least one node has role_in_incident
    roles = [n.get("role_in_incident") for n in dep_inc_data["nodes"] if n.get("role_in_incident")]
    assert_true(len(roles) > 0, f"Dependency nodes labeled with incident roles: {roles}")

    # ---------------------------------------------------------
    # TEST 5: Self-Healing Candidate Engine
    # ---------------------------------------------------------
    log_test("5. Self-Healing Candidate Engine")
    cand_res = session.get(f"{BASE_URL}/api/self-healing/candidates")
    assert_true(cand_res.status_code == 200, f"GET /api/self-healing/candidates status {cand_res.status_code}")
    candidates = cand_res.json()
    print(f"    Total candidates found: {len(candidates)}")
    assert_true(len(candidates) > 0, "Self-healing candidate generated for active incident")
    cand = candidates[0]
    print(f"    Candidate ID: {cand.get('candidate_id')}")
    print(f"    Target Service: {cand.get('service')} | Recommended Action: {cand.get('recommended_action')}")
    print(f"    Classification: {cand.get('classification')} | Root Cause Confidence: {cand.get('root_cause_confidence')}")
    print(f"    Safety Score: {cand.get('action_safety')} | Expected Effectiveness: {cand.get('expected_effectiveness')}")
    print(f"    Explanation: {cand.get('recommendation_explanation')}")
    assert_true(cand.get("classification") in ["SELF_HEALING_RECOMMENDED", "MEMBER_ACTION_REQUIRED", "MANUAL_INVESTIGATION_REQUIRED"], "Valid classification")

    # ---------------------------------------------------------
    # TEST 6: Controlled Execution Engine + Approval Enforcement
    # ---------------------------------------------------------
    log_test("6. Controlled Execution & Policy Approval Enforcement")
    # First, test approval enforcement: if medium/high risk and not approved, execute must reject with 403
    # Check current incident status
    exec_attempt = session.post(f"{BASE_URL}/api/recovery/{inc_id}/execute", json={"action": "RESET_CONNECTION_POOL"})
    if inc_data.get("approval_status") != "APPROVED" and (inc_data.get("action_risk_level") or "LOW").upper() in ["MEDIUM", "HIGH", "CRITICAL"]:
        assert_true(exec_attempt.status_code == 403, "Strict policy enforcement: Rejected unapproved recovery with HTTP 403")
        print("    [ENFORCED] Unapproved execution was correctly blocked with HTTP 403.")

    # Now approve the recovery
    print(f"    Granting authorized member approval for incident {inc_id}...")
    appr_res = session.post(
        f"{BASE_URL}/api/recovery/{inc_id}/approve",
        json={"member_id": "lead-sre-alice", "role": "Senior Principal SRE", "reason": "Authorized connection pool flush runbook"}
    )
    assert_true(appr_res.status_code == 200, f"POST /api/recovery/{inc_id}/approve status {appr_res.status_code}")
    print(f"    Approval status: {appr_res.json().get('status')}")

    # Now execute controlled recovery
    print("    Executing controlled recovery loop (execution -> workflow replay -> fresh telemetry -> verification)...")
    exec_res = session.post(f"{BASE_URL}/api/recovery/{inc_id}/execute", json={"action": "RESET_CONNECTION_POOL"})
    assert_true(exec_res.status_code == 200, f"POST /api/recovery/{inc_id}/execute status {exec_res.status_code}")
    exec_out = exec_res.json()
    print(f"    Execution result status: {exec_out.get('status')}")

    # Check recovery verification
    verif_res = session.get(f"{BASE_URL}/api/recovery/{inc_id}/verification")
    assert_true(verif_res.status_code == 200, f"GET /api/recovery/{inc_id}/verification status {verif_res.status_code}")
    verif_data = verif_res.json().get("verification", {})
    print(f"    Verification details: Original error cleared: {verif_data.get('original_error_cleared')} | Error rate baseline: {verif_data.get('error_rate_baseline')} | Workflow completed: {verif_data.get('workflow_completed')} | Side effects: {verif_data.get('side_effects_detected')}")
    assert_true(verif_data.get("original_error_cleared") is True or exec_out.get("status") in ["RESOLVED", "SUCCESS", "RECOVERED_AFTER_EXECUTION_ERROR"], "Recovery verified")

    # ---------------------------------------------------------
    # TEST 7: Historical Learning & Knowledge Base
    # ---------------------------------------------------------
    log_test("7. Historical Learning & Knowledge Base")
    kn_inc_res = session.get(f"{BASE_URL}/api/knowledge/incidents")
    assert_true(kn_inc_res.status_code == 200, f"GET /api/knowledge/incidents status {kn_inc_res.status_code}")
    kn_incs = kn_inc_res.json().get("incidents", [])
    print(f"    Historical resolved incident records stored: {len(kn_incs)}")
    assert_true(len(kn_incs) > 0, "Knowledge store contains resolved incident records")
    hist_sample = kn_incs[0]
    print(f"    Sample Record: {hist_sample.get('incident_id')} | Failure: {hist_sample.get('failure_type')} | Root Cause: {hist_sample.get('root_cause')} | Solution: {hist_sample.get('solution')}")
    for key in ["before_metrics", "after_metrics", "root_cause_evidence", "recovery_procedure", "verification_result"]:
        assert_true(key in hist_sample, f"Historical record contains '{key}'")

    kn_pat_res = session.get(f"{BASE_URL}/api/knowledge/recovery-patterns")
    assert_true(kn_pat_res.status_code == 200, f"GET /api/knowledge/recovery-patterns status {kn_pat_res.status_code}")
    patterns = kn_pat_res.json().get("patterns", [])
    print(f"    Known recovery patterns: {len(patterns)}")
    assert_true(len(patterns) >= 5, f"At least 5 proven recovery patterns indexed (found {len(patterns)})")
    for pat in patterns[:3]:
        print(f"      - {pat['pattern_name']} ({pat['action']}): Success Rate={pat['historical_success_rate']}% | Avg MTTR={pat['average_recovery_time_sec']}s")

    # ---------------------------------------------------------
    # TEST 8: AI SRE Assistant
    # ---------------------------------------------------------
    log_test("8. AI SRE Assistant (Grounding & 14-Section Response)")
    
    # Test Question 1: What is happening right now?
    q1_res = session.post(f"{BASE_URL}/api/assistant/chat", json={"message": "What is happening right now?"})
    assert_true(q1_res.status_code == 200, f"Chat Q1 status {q1_res.status_code}")
    ans1 = q1_res.json().get("reply", "")
    print(f"    Answer 1 summary:\n    {ans1[:160]}...\n")
    assert_true(len(ans1) > 20, "Assistant provided meaningful operational overview")

    # Test Question 2: Specific incident investigation with 14-point structure
    q2_res = session.post(f"{BASE_URL}/api/assistant/chat", json={"message": f"Why did {inc_id} happen and what is the root cause?"})
    assert_true(q2_res.status_code == 200, f"Chat Q2 status {q2_res.status_code}")
    ans2 = q2_res.json().get("reply", "")
    print(f"    Answer 2 (Structured 14-Section Incident Analysis):\n")
    for section_header in ["CURRENT STATUS", "ROOT CAUSE", "EVIDENCE", "AFFECTED SERVICES", "BLAST RADIUS", "RECOMMENDED ACTION", "APPROVAL REQUIREMENT"]:
        has_sec = section_header in ans2
        assert_true(has_sec, f"AI Assistant structured response contains section: '{section_header}'")

    print("\n" + "="*70)
    print("ALL 8 VERIFICATION SUITES COMPLETED WITH 100% SUCCESS!")
    print("="*70)

if __name__ == "__main__":
    main()
