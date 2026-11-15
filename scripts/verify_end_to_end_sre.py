"""
AegisOps AI - Complete Intelligence Maturity Verification & Test Suite
Exercises:
1. AI Provider Configuration & Strict Credential Masking (Zero secrets exposed)
2. Incident-Specific Evidence Package Builder, 15 Questions & Evidence Lineage Graph
3. Transparent Recovery Decision Scoring & Multi-Factor Candidate Ranking
4. Isolated Sandbox Recovery Lifecycle & 8-Point Empirical Validation
5. Recovery Proof Report Generation (Structured technical proof & export)
6. Verified Recovery Memory: Creation, Persistence, Matching & Tenant Isolation
7. Negative Security & Correctness Tests (Failed recovery never creates pattern, cross-tenant isolation)
8. Operational SRE Assistant (Comparison queries, failure rationale, historical pattern queries, citations)
"""

import sys
import os
import asyncio
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure workspace root is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.app.api.ai_config import (
    get_ai_config_status,
    update_ai_config,
    UpdateAIConfigRequest,
    test_ai_connection
)
from backend.app.rca.evidence_package import IncidentEvidencePackageBuilder, IncidentRCAEngine
from backend.app.healing.sandbox_engine import (
    sandbox_recovery_engine,
    calculate_recovery_decision_scores,
    generate_recovery_proof,
    ALLOWLISTED_ACTIONS
)
from backend.app.knowledge.incident_memory import verified_recovery_store
from backend.app.ai.sre_chat_engine import sre_chat_engine


async def test_ai_config_security():
    print("\n[TEST 1] Testing AI Config Security, Masking & Connectivity...")
    # 1. Update config with a test secret
    await update_ai_config(UpdateAIConfigRequest(
        rca_ai_api_key="sk-test-super-secret-key-12345",
        rca_ai_provider="anthropic",
        rca_ai_model="claude-3-7-sonnet",
        max_recovery_attempts=4
    ))

    status = await get_ai_config_status()
    # Verify that the raw secret is NEVER in the public status
    status_str = json.dumps(status)
    assert "sk-test-super-secret-key-12345" not in status_str, "CRITICAL SECURITY FAULT: Raw secret exposed in status!"
    assert status["rca_ai"]["status"] == "CONNECTED", f"Expected CONNECTED, got {status['rca_ai']['status']}"
    assert status["max_recovery_attempts"] == 4, "Expected max_recovery_attempts=4"
    print("  [PASS] Raw API key is strictly masked and absent from public status.")
    print("  [PASS] Configured MAX_RECOVERY_ATTEMPTS = 4.")

    # 2. Test Connection endpoint without key vs with key
    test_res_configured = await test_ai_connection({"target": "rca_ai"})
    assert test_res_configured["status"] == "CONNECTED"
    print(f"  [PASS] Connection test for configured provider: {test_res_configured['message']}")

    # Clear key and verify NOT CONFIGURED
    await update_ai_config(UpdateAIConfigRequest(rca_ai_api_key=""))
    status_unconfigured = await get_ai_config_status()
    assert status_unconfigured["rca_ai"]["status"] == "NOT CONFIGURED"
    test_res_unconfigured = await test_ai_connection({"target": "rca_ai"})
    assert test_res_unconfigured["status"] == "FAILED"
    print("  [PASS] Unconfigured provider accurately reports NOT CONFIGURED (never false CONNECTED).")


async def test_rca_evidence_and_lineage():
    print("\n[TEST 2] Testing Incident-Specific RCA, Evidence Lineage Graph & Claims...")
    test_incident = {
        "incident_id": "INC-20261008-001",
        "title": "Connection Starvation on Database Cluster",
        "severity": "CRITICAL",
        "status": "INVESTIGATING",
        "primary_service": "database-service",
        "affected_services": ["database-service", "service-b", "service-a", "gateway"],
        "root_cause_service": "database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "error_rate": 0.44,
        "latency_p95_ms": 860.0
    }

    # 1. Build evidence package
    pkg = await IncidentEvidencePackageBuilder.build(test_incident)
    assert pkg["incident_id"] == "INC-20261008-001", "Mismatch in incident_id"
    assert pkg["suspected_origin_service"] == "database-service", "Mismatch in origin service"
    assert len(pkg["recovery_options"]) >= 3, "Expected at least 3 allowlisted recovery options"
    print(f"  [PASS] Evidence Package assembled with {len(pkg['logs'])} logs, {len(pkg['metrics'])} metrics, {len(pkg['traces'])} traces.")

    # 2. Evaluate 15 deterministic questions
    det_eval = IncidentRCAEngine.evaluate_15_questions(pkg)
    answers = det_eval["answers"]
    assert answers["q2_where_failed"] == "database-service"
    assert "database-service" in answers["q4_first_deviated_service"]
    assert len(answers["q8_supporting_evidence"]) >= 3
    assert len(answers["q12_why_alternatives_rejected"]) >= 2
    assert det_eval["confidence_score"] >= 0.70
    print(f"  [PASS] Evaluated 15 RCA Questions. Confidence: {det_eval['confidence_score']} ({det_eval['confidence_tier']}).")

    # 3. Verify Evidence -> Root Cause Lineage Model
    lineage = det_eval["evidence_lineage"]
    steps = lineage["lineage_steps"]
    claims = lineage["claims"]
    assert len(steps) == 6, f"Expected 6 lineage steps, got {len(steps)}"
    step_types = [s["type"] for s in steps]
    assert step_types == ["LOG", "METRIC", "TRACE", "TEMPORAL", "DEPENDENCY", "ROOT_CAUSE"], f"Step types mismatch: {step_types}"
    assert len(claims) >= 1
    primary_claim = claims[0]
    assert len(primary_claim["supporting_evidence_ids"]) == 5
    assert primary_claim["decision"] == "ACCEPTED"
    print(f"  [PASS] 6-Step Evidence Lineage Pipeline constructed:")
    for s in steps:
        print(f"      [{s['type']}] {s['node_id']}: {s['title']} ({s['source']})")
    print(f"  [PASS] Primary Claim {primary_claim['claim_id']} verified with 5 supporting evidence nodes.")


async def test_recovery_decision_scoring():
    print("\n[TEST 3] Testing Multi-Signal Recovery Decision Scoring...")
    test_incident = {
        "incident_id": "INC-20261008-001",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "tenant_id": "demo-tenant"
    }

    matching_patterns = verified_recovery_store.find_matching_patterns(test_incident, tenant_id="demo-tenant")
    scores = calculate_recovery_decision_scores(test_incident, matching_patterns)

    assert len(scores) >= 3, "Expected at least 3 scored candidate actions"
    top_candidate = scores[0]
    assert top_candidate["action"] == "RESET_CONNECTION_POOL"
    assert top_candidate["decision"] == "RECOMMENDED"
    assert top_candidate["composite_score"] >= 88.0
    assert "explanation" in top_candidate and len(top_candidate["explanation"]) > 30

    print(f"  [PASS] Evaluated {len(scores)} candidate recovery actions:")
    for c in scores:
        print(f"      - {c['action']}: Composite={c['composite_score']} pts | Match={c['root_cause_match_pct']}% | Decision={c['decision']}")
        print(f"        Explanation: {c['explanation']}")


async def test_sandbox_recovery_and_proof():
    print("\n[TEST 4] Testing Isolated Sandbox Lifecycle, Empirical Validation & Proof Generation...")
    test_incident = {
        "incident_id": "INC-20261008-001",
        "root_cause_service": "database-service",
        "affected_services": ["database-service", "service-b", "gateway"],
        "tenant_id": "demo-tenant"
    }

    # 1. Initialize Sandbox
    sbx = await sandbox_recovery_engine.initialize_sandbox(test_incident, initial_action="RESET_CONNECTION_POOL")
    assert sbx["sandbox_id"].startswith("SBX-INC-20261008-001"), "Sandbox ID format invalid"
    print(f"  [PASS] Isolated Sandbox created: {sbx['sandbox_id']}")

    # 2. Capture Pre-Fix
    pre = await sandbox_recovery_engine.capture_prefix_telemetry(test_incident["incident_id"])
    assert pre["error_rate"] > 0.30
    assert pre["connection_pool_utilization"] == "100/100 (100%)"
    print(f"  [PASS] Pre-fix telemetry captured: Error Rate={pre['error_rate']}, Latency P95={pre['latency_p95_ms']}ms.")

    # 3. Reproduce Failure
    repro = await sandbox_recovery_engine.reproduce_failure(test_incident["incident_id"])
    assert repro["verified"] is True
    print(f"  [PASS] Failure reproduction verified: {repro['failure_condition']}")

    # 4. Execute Allowlisted Action
    exec_res = await sandbox_recovery_engine.execute_recovery_action(test_incident["incident_id"])
    assert exec_res["status"] == "EXECUTION_SUCCESS"
    print(f"  [PASS] Allowlisted action '{exec_res['action']}' executed successfully in sandbox.")

    # 5. Replay Failure Workload
    replay = await sandbox_recovery_engine.replay_failure_workload(test_incident["incident_id"])
    assert replay["successful_requests"] >= 95
    print(f"  [PASS] Failure workload replayed: {replay['successful_requests']}/{replay['total_requests']} requests succeeded.")

    # 6. Capture Post-Fix
    post = await sandbox_recovery_engine.capture_postfix_telemetry(test_incident["incident_id"])
    assert post["error_rate"] < 0.05
    diff = sbx["before_after_diff"]
    print(f"  [PASS] Post-fix captured. Error Rate improvement: {diff['error_rate']['improvement']}, Latency improvement: {diff['latency_p95_ms']['improvement']}.")

    # 7. 8-Point Empirical Validation
    val = await sandbox_recovery_engine.run_empirical_validation(test_incident["incident_id"])
    assert val["all_passed"] is True
    assert val["status"] == "RECOVERY_VERIFIED"
    assert len(val["criteria"]) == 8
    print(f"  [PASS] All 8 Empirical Validation Criteria PASSED (0 Collateral Regressions).")

    # 8. Recovery Proof Generation Check
    proof = sandbox_recovery_engine.get_recovery_proof(test_incident["incident_id"])
    assert proof is not None, "Recovery proof was not attached to sandbox!"
    assert all(c.get("status") == "PASS" for c in proof["validation_criteria"]) is True
    assert len(proof["validation_criteria"]) == 8
    assert "markdown_export" in proof and len(proof["markdown_export"]) > 200
    print(f"  [PASS] Recovery Proof '{proof['proof_id']}' generated with complete telemetry diff & export preview.")


async def test_verified_recovery_memory_and_tenant_isolation():
    print("\n[TEST 5] Testing Verified Recovery Memory, Pattern Creation & Tenant Isolation...")
    tenant_a = "tenant-alpha"
    tenant_b = "tenant-beta"

    # 1. Clean verify pattern for Tenant A
    pattern_a = verified_recovery_store.store_verified_pattern({
        "incident_id": "INC-ALPHA-001",
        "incident_type": "CONNECTION_POOL_EXHAUSTION",
        "failure_signature": "ConnectionPoolTimeoutException: 100/100 acquired",
        "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
        "root_cause_description": "Database pool exhaustion on database-service",
        "origin_service": "database-service",
        "affected_services": ["database-service", "service-b"],
        "recovery_action": "RESET_CONNECTION_POOL",
        "recovery_reason": "Drain hung connection handles",
        "attempts_required": 1,
        "pre_fix_metrics": {"error_rate": 0.42, "latency_p95_ms": 845.0},
        "post_fix_metrics": {"error_rate": 0.005, "latency_p95_ms": 38.0},
        "validation_results": {f"C{i}": "PASS" for i in range(1, 9)},
        "side_effect_results": [{"service": "service-b", "status": "CLEAN"}],
        "final_outcome": "RECOVERY_VERIFIED",
        "recovery_duration": 4.2,
        "sandbox_id": "SBX-ALPHA-01",
        "source_execution_id": "EXEC-ALPHA-01",
        "confidence": 0.96,
        "tenant_id": tenant_a
    })

    assert pattern_a is not None, "Failed to store verified pattern for Tenant A"
    assert pattern_a.startswith("VRP-"), "Pattern ID format invalid"
    print(f"  [PASS] Verified Pattern stored for Tenant A: {pattern_a}.")

    # 2. Negative Test: Failed recovery must NEVER create a pattern
    pattern_failed = verified_recovery_store.store_verified_pattern({
        "incident_id": "INC-FAILED-002",
        "final_outcome": "FAILED",
        "validation_results": {"C1": "FAIL"},
        "tenant_id": tenant_a
    })
    assert pattern_failed is None, "SECURITY FAULT: Stored non-verified recovery as verified pattern!"
    print("  [PASS] Rejected non-verified recovery (final_outcome != RECOVERY_VERIFIED).")

    # 3. Negative Test: Recovery with failing validation criteria must NEVER create a pattern
    pattern_crit_fail = verified_recovery_store.store_verified_pattern({
        "incident_id": "INC-FAILED-003",
        "final_outcome": "RECOVERY_VERIFIED",
        "validation_results": {"C1": "FAIL", "C2": "PASS"},
        "tenant_id": tenant_a
    })
    assert pattern_crit_fail is None, "SECURITY FAULT: Stored pattern with failing validation criteria!"
    print("  [PASS] Rejected recovery with failing criteria.")

    # 4. Tenant Isolation Test: Tenant B must NEVER see Tenant A's pattern
    matches_b = verified_recovery_store.find_matching_patterns({
        "incident_type": "CONNECTION_POOL_EXHAUSTION",
        "origin_service": "database-service",
        "failure_signature": "ConnectionPoolTimeoutException"
    }, tenant_id=tenant_b)

    for p in matches_b:
        assert p.get("tenant_id") == tenant_b, f"CROSS-TENANT LEAKAGE: Tenant B matched pattern belonging to {p.get('tenant_id')}!"
    print(f"  [PASS] Tenant isolation verified: Zero cross-tenant pattern leakage for Tenant B.")

    # 5. Matching Query for Tenant A
    matches_a = verified_recovery_store.find_matching_patterns({
        "incident_type": "CONNECTION_POOL_EXHAUSTION",
        "origin_service": "database-service",
        "failure_signature": "ConnectionPoolTimeoutException"
    }, tenant_id=tenant_a)
    assert len(matches_a) >= 1
    assert matches_a[0]["verified_recovery_action"] == "RESET_CONNECTION_POOL"
    assert matches_a[0]["similarity_pct"] >= 90.0
    print(f"  [PASS] Tenant A matched {matches_a[0]['pattern_id']} with {matches_a[0]['similarity_pct']}% similarity.")


async def test_operational_sre_assistant():
    print("\n[TEST 6] Testing Operational SRE Assistant Upgrades...")
    conv_id = f"CONV-OPS-TEST-{int(os.getpid())}"
    inc_id = "INC-20261008-001"

    test_queries = [
        ("Why did recovery attempt 1 fail?", "failure rationale & criteria citations"),
        ("Compare attempt 1 and attempt 2.", "side-by-side attempt comparison table"),
        ("Has this happened before?", "historical verified pattern query"),
        ("Why was this recovery selected?", "decision scoring rationale"),
        ("What evidence proves recovery worked?", "empirical validation proof"),
        ("Show me the validation proof.", "structured proof report citations"),
        ("Was there a side effect?", "collateral checks downstream")
    ]

    for q, desc in test_queries:
        res = await sre_chat_engine.chat(
            message=q,
            conversation_id=conv_id,
            incident_id=inc_id
        )
        assert len(res["answer"]) > 20, f"Answer too short for query: {q}"
        assert res["conversation_id"] == conv_id
        assert res["mode"] in ("DETERMINISTIC MODE", "AI + TELEMETRY MODE")
        print(f"\n  [Q: {desc}] {q}")
        print(f"  [Mode]: {res['mode']}")
        print(f"  [A]: {res['answer'][:180]}...")
        if res.get("sources"):
            print(f"       Sources: {res['sources']}")
        if res.get("evidence_items"):
            print(f"       Evidence Items: {res['evidence_items']}")

    history = sre_chat_engine.get_conversation_history(conv_id)
    assert len(history) == len(test_queries) * 2, "Conversation history turn count mismatch"
    print(f"\n  [PASS] Conversational memory maintained across all {len(test_queries)} operational turns.")


async def main():
    print("=" * 80)
    print("   AEGISOPS AI — INTELLIGENCE MATURITY UPGRADE TEST SUITE")
    print("=" * 80)

    try:
        await test_ai_config_security()
        await test_rca_evidence_and_lineage()
        await test_recovery_decision_scoring()
        await test_sandbox_recovery_and_proof()
        await test_verified_recovery_memory_and_tenant_isolation()
        await test_operational_sre_assistant()

        print("\n" + "=" * 80)
        print("   ALL 6 MATURITY TEST SUITES PASSED END-TO-END WITH ZERO ERRORS!")
        print("=" * 80 + "\n")
    except Exception as e:
        print(f"\n[FAIL] Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
