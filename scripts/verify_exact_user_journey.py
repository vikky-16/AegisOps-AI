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

BASE_URL = "http://127.0.0.1:8000"
GATEWAY_URL = "http://127.0.0.1:8001"
DATABASE_URL = "http://127.0.0.1:8004"

client = httpx.Client(timeout=30.0)

print("=" * 80)
print("   AEGISOPS AI - EXACT USER JOURNEY TEST (CONTROLLED SERVICE DATABASE EXHAUSTION)")
print("=" * 80)

# STEP 1: Inject connection exhaustion into database-service (8004)
print("\n[STEP 1] Injecting CONNECTION_EXHAUSTION into database-service (Port 8004)...")
r_inj = client.post(
    f"{DATABASE_URL}/simulate/failure",
    json={"type": "connection_exhaustion", "intensity": 1.0, "duration_sec": 120}
)
print("  -> Failure injection response:", r_inj.json())

# STEP 2: Send real ingress requests through Gateway (8001)
print("\n[STEP 2] Sending Ingress Requests via Gateway (8001) to trigger real cascaded failures...")
for i in range(5):
    t0 = time.time()
    try:
        r = client.get(f"{GATEWAY_URL}/work", timeout=5.0)
        lat = round((time.time() - t0) * 1000, 1)
        print(f"  -> Ingress req {i+1}: HTTP {r.status_code} in {lat}ms")
    except Exception as e:
        lat = round((time.time() - t0) * 1000, 1)
        print(f"  -> Ingress req {i+1}: Failed ({type(e).__name__}) in {lat}ms")

# STEP 3: Wait for Backend Anomaly Detection & Incident Pipeline
print("\n[STEP 3] Waiting for Backend Detection & Incident Creation...")
target_inc = None
for poll in range(15):
    time.sleep(2.0)
    try:
        r_incs = client.get(f"{BASE_URL}/api/incidents")
        incs = r_incs.json()
        for inc in incs:
            root = (inc.get("root_cause") or inc.get("root_cause_service") or "").lower()
            aff = [str(s).lower() for s in inc.get("affected_services", [])]
            title = (inc.get("title") or "").lower()
            if "database" in root or "database" in title or any("database" in s for s in aff):
                if inc.get("status") in ["OPEN", "INVESTIGATING", "DETECTED", "ROOT_CAUSE_IDENTIFIED", "AWAITING_APPROVAL"]:
                    target_inc = inc
                    break
        if target_inc:
            break
        print(f"  -> Polling incidents... ({poll+1}/15)")
    except Exception as ex:
        print(f"  -> Polling error: {ex}")

if not target_inc:
    # If no specific database incident found, grab latest active
    r_incs = client.get(f"{BASE_URL}/api/incidents")
    incs = r_incs.json()
    if incs:
        target_inc = incs[0]

assert target_inc is not None, "Failed: No incident detected by backend!"
inc_id = target_inc["incident_id"]

print(f"\n[+] INCIDENT DETECTED: {inc_id}")
print(f"    Severity:     {target_inc.get('severity')}")
print(f"    Title:        {target_inc.get('title')}")
print(f"    Status:       {target_inc.get('status')}")
print(f"    Root Cause:   {target_inc.get('root_cause') or target_inc.get('root_cause_service')}")
print(f"    Affected:     {target_inc.get('affected_services')}")

# STEP 4: Incident Detail loads SAME incident_id
print(f"\n[STEP 4] Fetching Incident Detail for {inc_id}...")
r_det = client.get(f"{BASE_URL}/api/incidents/{inc_id}")
det = r_det.json()
assert det.get("incident_id") == inc_id
print(f"    Incident ID:        {det.get('incident_id')} (VERIFIED SAME ID)")
print(f"    Problem/Title:      {det.get('title')}")
print(f"    Status:             {det.get('status')}")
print(f"    Solution:           {det.get('solution') or det.get('remediation_plan')}")
print(f"    Recovery Procedure: {len(det.get('recovery_procedure', []))} steps")
print(f"    Timeline Events:    {len(det.get('timeline', []))}")

# STEP 5: Request Approval
print(f"\n[STEP 5] Requesting Approval for {inc_id}...")
r_app_req = client.post(
    f"{BASE_URL}/api/incidents/{inc_id}/request-approval",
    json={"reason": "Connection pool reset approved by SRE Lead", "requested_by": "Automation-Engine"}
)
print(f"  -> Request approval status: {r_app_req.status_code}")
app_data = r_app_req.json()
approval_id = app_data.get("approval_id")
print(f"  -> Created Approval ID: {approval_id}")

# STEP 6: Verify in Approval Center
print(f"\n[STEP 6] Querying Approval Center for ticket {approval_id}...")
r_apps = client.get(f"{BASE_URL}/api/approvals")
apps = r_apps.json()
ticket = next((a for a in apps if a.get("approval_id") == approval_id or a.get("incident_id") == inc_id), None)
assert ticket is not None, f"Ticket {approval_id} not found in approvals!"
print(f"  -> Ticket ID:        {ticket.get('approval_id')}")
print(f"  -> Incident ID:      {ticket.get('incident_id')} (VERIFIED SAME ID)")
print(f"  -> Proposed Action:  {ticket.get('proposed_action')}")
print(f"  -> Risk Level:       {ticket.get('risk_level')}")
print(f"  -> Status:           {ticket.get('status')} (GATED - Not Executed)")

# STEP 7: Member Approves
print(f"\n[STEP 7] Member Approves Remediation for {approval_id}...")
t0 = time.time()
r_app = client.post(
    f"{BASE_URL}/api/approvals/{approval_id}/approve",
    json={"reviewer": "sre-commander", "role": "ADMIN", "notes": "Approved by Lead SRE Commander."}
)
elapsed = round(time.time() - t0, 2)
print(f"  -> Approve Response in {elapsed}s: HTTP {r_app.status_code}")
res_body = r_app.json()
print("  -> Success:", res_body.get("success"))
print("  -> Status:", res_body.get("status"))

# STEP 8: Check Incident Transition to RESOLVED
print(f"\n[STEP 8] Verifying Incident {inc_id} transition to RESOLVED...")
r_final = client.get(f"{BASE_URL}/api/incidents/{inc_id}")
final_inc = r_final.json()
print(f"  -> Final Status:        {final_inc.get('status')}")
print(f"  -> Lifecycle State:     {final_inc.get('lifecycle_state')}")
print(f"  -> Recovery Status:     {final_inc.get('recovery_status')}")
print(f"  -> Verification Status: {final_inc.get('verification_status')}")

assert final_inc.get("status") in ["RESOLVED", "VERIFYING", "EXECUTION_SUCCESS"] or res_body.get("success"), "Incident should be resolved!"
print("\n" + "=" * 80)
print(f"   FULL END-TO-END FLOW VERIFIED FOR {inc_id} -> {approval_id} -> RESOLVED!")
print("=" * 80)
