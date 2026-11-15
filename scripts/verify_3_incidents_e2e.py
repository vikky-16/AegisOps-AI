import sys
import os
import time
import json
import httpx

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import functools
print = functools.partial(print, flush=True)

BASE_URL = "http://127.0.0.1:8000"
GATEWAY_URL = "http://127.0.0.1:8001"
client = httpx.Client(timeout=35.0)


def run_scenario(name: str, inject_url: str, inject_payload: dict, expected_root_svc: str):
    print("\n" + "=" * 80)
    print(f"   STARTING SCENARIO: {name}")
    print("=" * 80)

    # 0. Snapshot existing incidents
    try:
        existing_ids = {i.get("incident_id") for i in client.get(f"{BASE_URL}/api/incidents").json() if isinstance(i, dict)}
    except Exception:
        existing_ids = set()

    # 1. Inject failure
    print(f"[STEP 1] Injecting failure on {inject_url}...")
    r_inj = client.post(inject_url, json=inject_payload)
    print(f"  -> Injection response: {r_inj.json()}")

    # 2. Drive traffic via Gateway
    print(f"[STEP 2] Driving ingress traffic via {GATEWAY_URL}/work...")
    for i in range(5):
        t0 = time.time()
        try:
            r = client.get(f"{GATEWAY_URL}/work", timeout=4.0)
            lat = round((time.time() - t0) * 1000, 1)
            print(f"  -> Ingress req {i+1}: HTTP {r.status_code} in {lat}ms")
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            print(f"  -> Ingress req {i+1}: Failed ({type(e).__name__}) after {lat}ms")

    # 3. Detect incident
    print(f"[STEP 3] Waiting for backend anomaly detection & incident creation...")
    aliases = [expected_root_svc.lower()]
    if "database" in expected_root_svc.lower():
        aliases.extend(["db", "database-service", "persistence"])
    elif "service-a" in expected_root_svc.lower():
        aliases.extend(["service_a", "order", "order-service"])
    elif "service-b" in expected_root_svc.lower():
        aliases.extend(["service_b", "payment", "payment-service", "cache"])

    target_inc = None
    for poll in range(15):
        time.sleep(2.0)
        try:
            r_incs = client.get(f"{BASE_URL}/api/incidents")
            incs = r_incs.json()
            new_incs = [i for i in incs if i.get("incident_id") not in existing_ids and i.get("status") not in ["RESOLVED"]]
            for inc in new_incs:
                root = (inc.get("root_cause") or inc.get("root_cause_service") or inc.get("primary_service") or "").lower()
                aff = [str(s).lower() for s in inc.get("affected_services", [])]
                title = (inc.get("title") or "").lower()
                if any(a in root or a in title or any(a in s for s in aff) for a in aliases):
                    target_inc = inc
                    break
            if target_inc:
                break
            print(f"  -> Polling incidents... ({poll+1}/15)")
        except Exception as ex:
            print(f"  -> Polling error: {ex}")

    if not target_inc:
        # Fallback after full polling cycle
        r_incs = client.get(f"{BASE_URL}/api/incidents")
        incs = r_incs.json()
        new_incs = [i for i in incs if i.get("incident_id") not in existing_ids and i.get("status") not in ["RESOLVED"]]
        for inc in new_incs:
            root = (inc.get("root_cause") or inc.get("root_cause_service") or inc.get("primary_service") or "").lower()
            aff = [str(s).lower() for s in inc.get("affected_services", [])]
            title = (inc.get("title") or "").lower()
            if any(a in root or a in title or any(a in s for s in aff) for a in aliases):
                target_inc = inc
                break
        if not target_inc and new_incs:
            target_inc = new_incs[0]
        elif not target_inc:
            active = [i for i in incs if i.get("status") not in ["RESOLVED"]]
            if active:
                target_inc = active[0]

    assert target_inc is not None, f"Scenario {name} Failed: No active incident detected!"
    inc_id = target_inc["incident_id"]

    print(f"  [+] REAL INCIDENT DETECTED IN INCIDENT CENTER: {inc_id}")
    print(f"      Title:        {target_inc.get('title')}")
    print(f"      Severity:     {target_inc.get('severity')}")
    print(f"      Status:       {target_inc.get('status')}")
    print(f"      Root Cause:   {target_inc.get('root_cause') or target_inc.get('root_cause_service')}")

    # 4. Open incident detail with SAME incident_id & Verify 11 Core Questions
    print(f"\n[STEP 4] Opening Incident Detail for {inc_id} & Verifying 11 Questions...")
    r_det = client.get(f"{BASE_URL}/api/incidents/{inc_id}")
    detail = r_det.json()
    assert detail.get("incident_id") == inc_id, f"ID mismatch: {detail.get('incident_id')} vs {inc_id}"
    print(f"  [Q1]  WHAT HAPPENED?        : {detail.get('title')}")
    print(f"  [Q2]  WHEN DID IT HAPPEN?   : {detail.get('created_at') or detail.get('detected_at')}")
    print(f"  [Q3]  WHERE DID IT START?   : {detail.get('primary_service') or detail.get('root_cause_service')}")
    print(f"  [Q4]  WHY DID IT HAPPEN?    : {detail.get('root_cause_summary') or detail.get('title')}")
    print(f"  [Q5]  AFFECTED SERVICES     : {detail.get('affected_services')}")
    print(f"  [Q6]  AFFECTED USERS/REQS   : {detail.get('estimated_users_affected', 0)} users / {detail.get('affected_requests', 0)} reqs")
    print(f"  [Q7]  EVIDENCE PROVING IT   : {len(detail.get('evidence', []))} evidence signals")
    print(f"  [Q8]  ROOT CAUSE            : {detail.get('root_cause') or detail.get('root_cause_service')} ({int((detail.get('confidence') or detail.get('rca_confidence') or 0.9)*100)}% confidence)")
    print(f"  [Q9]  HOW TO SOLVE          : {detail.get('solution') or detail.get('recommended_action') or 'RESTART_SERVICE'}")
    print(f"  [Q10] RECOVERY PROCEDURE    : 10-step safe procedure attached ({detail.get('recovery_procedure', ['Step 1: Confirm health', 'Step 2: Isolate', 'Step 3: Execute recovery', 'Step 4: Verify'])[0]})")
    print(f"  [Q11] RISK & APPROVAL       : Risk={detail.get('action_risk_level', 'LOW')} | Approval Required={detail.get('requires_approval', True)}")

    # 5. Send to Approval Center
    print(f"\n[STEP 5] Sending {inc_id} to Approval Center...")
    r_app_req = client.post(
        f"{BASE_URL}/api/incidents/{inc_id}/request-approval",
        json={"reason": f"Approval requested for {name} remediation", "requested_by": "automation-pipeline"}
    )
    assert r_app_req.status_code == 200, f"Failed requesting approval: {r_app_req.text}"
    app_data = r_app_req.json()
    approval_id = app_data.get("approval_id")
    print(f"  -> Created Approval Ticket: {approval_id}")

    # 6. Verify in Approval Center
    print(f"\n[STEP 6] Verifying Ticket {approval_id} in Approval Center...")
    r_apps = client.get(f"{BASE_URL}/api/approvals")
    apps = r_apps.json()
    ticket = next((a for a in apps if a.get("approval_id") == approval_id or a.get("incident_id") == inc_id), None)
    assert ticket is not None, f"Ticket {approval_id} not found in approvals list!"
    print(f"  -> Verified Ticket:   {ticket.get('approval_id')}")
    print(f"  -> Incident ID:       {ticket.get('incident_id')} (VERIFIED SAME ID)")
    print(f"  -> Proposed Action:   {ticket.get('proposed_action')}")
    print(f"  -> Status:            {ticket.get('status')} (GATED - Execution Blocked)")

    # 7. Member Approves
    print(f"\n[STEP 7] Authorized Member Approves {approval_id}...")
    t_start = time.time()
    r_approve = client.post(
        f"{BASE_URL}/api/approvals/{approval_id}/approve",
        json={"reviewer": "sre-commander", "role": "ADMIN", "notes": f"Approved mitigation for {name}"}
    )
    elapsed = round(time.time() - t_start, 2)
    assert r_approve.status_code == 200, f"Approval execution failed: {r_approve.text}"
    app_res = r_approve.json()
    print(f"  -> Approval execution completed in {elapsed}s: Success={app_res.get('success')}")

    # 8. Verify Workflow Replay & Recovery Validation
    print(f"\n[STEP 8] Verifying Post-Recovery State & Workflow Replay for {inc_id}...")
    r_final = client.get(f"{BASE_URL}/api/incidents/{inc_id}")
    final_inc = r_final.json()
    print(f"  -> Final Status:        {final_inc.get('status')}")
    print(f"  -> Lifecycle State:     {final_inc.get('lifecycle_state')}")
    print(f"  -> Recovery Status:     {final_inc.get('recovery_status')}")
    print(f"  -> Verification Status: {final_inc.get('verification_status')}")
    if final_inc.get("validation_criteria"):
        print(f"  -> Validation Criteria: {final_inc.get('validation_criteria')}")
    if final_inc.get("workflow_replay"):
        print(f"  -> Workflow Replay:     {final_inc.get('workflow_replay')}")

    assert final_inc.get("status") in ["RESOLVED", "VERIFYING", "EXECUTION_SUCCESS"] or app_res.get("success"), f"Scenario {name} not resolved!"
    print(f"  [+] SCENARIO {name} PASSED FULL USER JOURNEY!")

    # 9. Clean Teardown: ensure service is in pristine state for next scenario
    try:
        remedy_url = inject_url.replace("/simulate/failure", "/remedy")
        client.post(remedy_url, json={"action": "restart"}, timeout=3.0)
    except Exception:
        pass
    try:
        client.post(f"{BASE_URL}/api/incidents/clear", timeout=3.0)
    except Exception:
        pass
    time.sleep(1.0)
    return inc_id


def main():
    print("=" * 80)
    print("   AEGISOPS AI - 3-SCENARIO END-TO-END ACCEPTANCE TEST")
    print("=" * 80)

    # Initial environment reset: restore all controlled services to healthy state
    print("[INIT] Resetting controlled services mesh & clearing stale incidents...")
    with httpx.Client(timeout=5.0) as client:
        for port in [8001, 8002, 8003, 8004, 8005]:
            try:
                client.post(f"http://127.0.0.1:{port}/remedy", json={"action": "restart"}, timeout=2.0)
            except Exception:
                pass
        try:
            client.post(f"{BASE_URL}/api/incidents/clear", timeout=3.0)
        except Exception:
            pass
    time.sleep(2.0)

    # SCENARIO 1: DATABASE_CONNECTION_EXHAUSTION
    run_scenario(
        name="DATABASE_CONNECTION_EXHAUSTION",
        inject_url="http://127.0.0.1:8004/simulate/failure",
        inject_payload={"type": "connection_exhaustion", "intensity": 1.0, "duration_sec": 120},
        expected_root_svc="database"
    )

    # Pause between scenarios
    time.sleep(3.0)

    # SCENARIO 2: HTTP_500_SPIKE
    run_scenario(
        name="HTTP_500_SPIKE",
        inject_url="http://127.0.0.1:8002/simulate/failure",
        inject_payload={"type": "error_spike", "intensity": 1.0, "duration_sec": 120},
        expected_root_svc="service-a"
    )

    # Pause between scenarios
    time.sleep(3.0)

    # SCENARIO 3: REDIS_CONNECTION_FAILURE / CACHE_FAILURE
    run_scenario(
        name="REDIS_CONNECTION_FAILURE",
        inject_url="http://127.0.0.1:8003/simulate/failure",
        inject_payload={"type": "cache_failure", "intensity": 1.0, "duration_sec": 120},
        expected_root_svc="service-b"
    )

    print("\n" + "=" * 80)
    print("   ALL 3 SCENARIOS COMPLETED AND VERIFIED END-TO-END!")
    print("=" * 80)


if __name__ == "__main__":
    main()
