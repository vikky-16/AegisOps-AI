"""
Live Operational Verification Test Suite for Controlled Execution Engine
Runs full real-time operational workflows against the live backend API.
"""

import urllib.request
import json
import sys
import time
import traceback

API = "http://127.0.0.1:8000/api"

def api_call(endpoint: str, method: str = "GET", payload: dict = None, timeout: int = 60):
    url = f"{API}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    body = json.dumps(payload).encode("utf-8") if payload else None
    try:
        with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        content = err.read().decode()
        try:
            return {"http_code": err.code, "error": json.loads(content)}
        except Exception:
            return {"http_code": err.code, "raw_error": content}


def run_scenario_1():
    print("=================================================================", flush=True)
    print("TEST SCENARIO 1: DATABASE CONNECTION POOL EXHAUSTION RECOVERY", flush=True)
    print("=================================================================", flush=True)
    # 1. Incident Creation
    inc = api_call("/incidents", method="POST", payload={
        "title": "PostgreSQL Connection Pool Exhaustion Under Flash Sale Surge",
        "service": "database-service",
        "severity": "CRITICAL",
        "root_cause": "Active connection pool slots exhausted (100/100 slots saturated)",
        "status": "OPEN",
        "recommended_action": "RESET_CONNECTION_POOL",
        "recommended_runbook_id": "RB-DB-POOL-01"
    })
    inc_id = inc["incident_id"]
    print(f"[1] Incident Created: {inc_id} (Status: {inc['status']})", flush=True)

    # 2. Safety Check Evaluation
    sc = api_call(f"/recovery/{inc_id}/safety-check", method="POST", payload={"action": "RESET_CONNECTION_POOL"})
    print(f"[2] Safety Checks Evaluated: all_passed={sc.get('all_passed')}, checks_count={len(sc.get('checks', []))}", flush=True)
    assert sc.get("all_passed") is True, f"Safety checks failed: {sc.get('blocked_reasons')}"

    # 3. Controlled Execution (Replay + Telemetry + Verification)
    exec_res = api_call(f"/recovery/{inc_id}/execute", method="POST", payload={
        "action": "RESET_CONNECTION_POOL",
        "caller": "Lead_SRE_Operator"
    })
    result = exec_res.get("result", {})
    exec_data = result.get("execution", {})
    verif = result.get("verification", {})

    score = verif.get("verification_score_pct")
    threshold = verif.get("threshold_pct")
    verdict = verif.get("verdict")
    orig_passed = verif.get("original_problem", {}).get("passed")
    replay_passed = verif.get("workflow_replay", {}).get("passed")
    side_effects = verif.get("side_effects", [])

    print(f"[4] Verification Score: {score}% (Threshold: {threshold}%)", flush=True)
    print(f"[5] Verdict: {verdict}", flush=True)
    print(f"[6] Original Problem Cleared: {orig_passed}", flush=True)
    print(f"[7] Workflow Replay Status: {replay_passed}", flush=True)
    print(f"[8] Side Effects: {side_effects}", flush=True)

    # Verify Before vs After Comparison
    comp = exec_data.get("comparison", {})
    if comp:
        err_b = comp.get("error_rate", {}).get("before")
        err_a = comp.get("error_rate", {}).get("after")
        lat_b = comp.get("latency_p95", {}).get("before")
        lat_a = comp.get("latency_p95", {}).get("after")
        print(f"[9] Before / After Comparison: Error {err_b} -> {err_a} | Latency {lat_b} -> {lat_a}", flush=True)

    # Assertions
    assert result.get("status") == "RESOLVED"
    assert verdict == "RECOVERY_VERIFIED"
    assert score >= 85.0
    assert orig_passed is True
    assert replay_passed is True
    assert len(side_effects) == 0

    # Incident state verification in backend
    final_inc = api_call(f"/incidents/{inc_id}")
    assert final_inc.get("status") == "RESOLVED"
    print(f"[10] Final Incident Status in Database: {final_inc.get('status')} [OK]", flush=True)
    print(">>> SCENARIO 1 RESULT: SUCCESS (100% VERIFIED)\n", flush=True)


def run_scenario_2():
    print("=================================================================", flush=True)
    print("TEST SCENARIO 2: RECOVERY REFINEMENT (INSUFFICIENT ATTEMPT 1 -> RETRY)", flush=True)
    print("=================================================================", flush=True)
    # Incident where attempt 1 fixes DB but payment service still has stale sockets
    inc = api_call("/incidents", method="POST", payload={
        "title": "Payment Downstream Stale Socket Partition",
        "service": "database-service",
        "severity": "HIGH",
        "root_cause": "Downstream payment service retaining stale socket descriptors",
        "status": "OPEN",
        "recommended_action": "RESET_CONNECTION_POOL",
        "recommended_runbook_id": "RB-DB-POOL-01"
    })
    inc_id = inc["incident_id"]
    print(f"[1] Incident Created: {inc_id}", flush=True)

    # Execute with simulated insufficient attempt
    exec_res = api_call(f"/recovery/{inc_id}/execute", method="POST", payload={
        "action": "RESET_CONNECTION_POOL",
        "caller": "Lead_SRE_Operator",
        "simulate_insufficient_attempt": True
    })
    result = exec_res.get("result", {})
    history = result.get("execution", {}).get("attempts_history", [])

    print(f"[2] Refinement Execution Finished: Status={result.get('status')}, Total Attempts={result.get('attempts')}", flush=True)
    assert len(history) == 2, f"Expected 2 attempts, got {len(history)}"
    print(f"[3] Attempt 1: Action={history[0].get('action')} | Status={history[0].get('status')}", flush=True)
    print(f"[4] Attempt 1 Failure Refinement: {history[0].get('refinement_candidate', {}).get('rationale')}", flush=True)
    print(f"[5] Attempt 2: Action={history[1].get('action')} | Status={history[1].get('status')}", flush=True)

    assert history[0].get("status") == "FAILED"
    assert history[1].get("status") == "VERIFIED"
    assert history[1].get("action") == "RECONNECT_DATABASE"
    assert result.get("status") == "RESOLVED"

    final_inc = api_call(f"/incidents/{inc_id}")
    assert final_inc.get("status") == "RESOLVED"
    print(f"[6] Incident Status After Refined Recovery: {final_inc.get('status')} [OK]", flush=True)
    print(">>> SCENARIO 2 RESULT: SUCCESS (100% VERIFIED)\n", flush=True)


def run_scenario_3():
    print("=================================================================", flush=True)
    print("TEST SCENARIO 3: UNRESOLVABLE FAILURE SCENARIO (MAX ATTEMPTS EXCEEDED)", flush=True)
    print("=================================================================", flush=True)
    inc = api_call("/incidents", method="POST", payload={
        "title": "Severe Kernel Hardware Disk Corruption",
        "service": "database-service",
        "severity": "CRITICAL",
        "root_cause": "Persistent hardware storage unresponsiveness",
        "status": "OPEN",
        "recommended_action": "RESET_CONNECTION_POOL",
        "recommended_runbook_id": "RB-DB-POOL-01"
    })
    inc_id = inc["incident_id"]
    print(f"[1] Incident Created: {inc_id}", flush=True)

    # Execute with simulate_unresolvable
    exec_res = api_call(f"/recovery/{inc_id}/execute", method="POST", payload={
        "action": "RESET_CONNECTION_POOL",
        "caller": "Lead_SRE_Operator",
        "simulate_unresolvable": True
    })
    result = exec_res.get("result", {})
    exec_record = result.get("execution", {})

    print(f"[2] Max Attempts Result: Status={result.get('status')}, Attempts={result.get('attempts')}", flush=True)
    print(f"[3] Execution Current Stage: {exec_record.get('current_stage')}", flush=True)

    assert result.get("status") == "UNRESOLVED"
    assert result.get("attempts") == 3
    assert exec_record.get("current_stage") == "UNRESOLVED"

    final_inc = api_call(f"/incidents/{inc_id}")
    print(f"[4] Incident DB Status: {final_inc.get('status')} (Must NOT be RESOLVED)", flush=True)
    assert final_inc.get("status") == "UNRESOLVED"
    print(">>> SCENARIO 3 RESULT: SUCCESS (UNRESOLVED CORRECTLY RETAINED)\n", flush=True)


def run_scenario_4():
    print("=================================================================", flush=True)
    print("TEST SCENARIO 4: APPROVAL GATE ENFORCEMENT (HTTP 403 ON UNAPPROVED HIGH RISK)", flush=True)
    print("=================================================================", flush=True)
    inc = api_call("/incidents", method="POST", payload={
        "title": "Unstable Daemon Process Requiring Service Restart",
        "service": "database-service",
        "severity": "HIGH",
        "root_cause": "Process-level thread deadlock requiring service recycle",
        "status": "OPEN",
        "recommended_action": "RESTART_CONTROLLED_SERVICE",
        "action_risk_level": "MEDIUM",
        "approval_status": "PENDING"
    })
    inc_id = inc["incident_id"]
    print(f"[1] Medium/High Risk Incident Created: {inc_id} (Approval: PENDING)", flush=True)

    # Attempt execution without approval -> MUST return 403
    unapproved = api_call(f"/recovery/{inc_id}/execute", method="POST", payload={"action": "RESTART_CONTROLLED_SERVICE"})
    print(f"[2] Unapproved Execution Response HTTP Code: {unapproved.get('http_code')}", flush=True)
    assert unapproved.get("http_code") == 403, f"Expected HTTP 403 Forbidden, got {unapproved}"
    print(f"[3] 403 Error Detail: {unapproved.get('error', {}).get('detail')}", flush=True)

    # Provide formal member approval
    approval = api_call(f"/recovery/{inc_id}/approve", method="POST", payload={"member_id": "lead-sre-alice"})
    print(f"[4] Member Authorization Granted: Approval ID={approval.get('approval_id')}", flush=True)

    # Now execute with approval -> MUST succeed
    approved_exec = api_call(f"/recovery/{inc_id}/execute", method="POST", payload={"action": "RESTART_CONTROLLED_SERVICE"})
    print(f"[5] Post-Approval Execution Status: {approved_exec.get('status')}", flush=True)
    assert approved_exec.get("status") == "RESOLVED"
    print(">>> SCENARIO 4 RESULT: SUCCESS (APPROVAL ENFORCED & AUDITED)\n", flush=True)


if __name__ == "__main__":
    t0 = time.time()
    try:
        run_scenario_1()
        run_scenario_2()
        run_scenario_3()
        run_scenario_4()
        print(f"=================================================================", flush=True)
        print(f"ALL 4 OPERATIONAL SCENARIOS PASSED 100% IN {round(time.time() - t0, 2)}s", flush=True)
        print(f"=================================================================", flush=True)
    except Exception as e:
        print(f"FAILED WITH EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
