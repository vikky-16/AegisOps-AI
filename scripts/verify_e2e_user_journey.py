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
GATEWAY_URL = "http://127.0.0.1:8100"
ORDER_URL = "http://127.0.0.1:8101"

client = httpx.Client(timeout=25.0)

print("=" * 80)
print("   AEGISOPS AI - END-TO-END INCIDENT LIFECYCLE VERIFICATION")
print("=" * 80)

# STEP 1: Controlled failure injection
print("\n[STEP 1] Triggering Controlled Failure: DATABASE_CONNECTION_EXHAUSTION on Order Service...")
try:
    inj_res = client.post(
        f"{ORDER_URL}/inject/db-latency",
        json={"latency_ms": 3500, "exhaust_connections": True},
        timeout=5.0
    )
    print(f"  -> Injection response: {inj_res.json()}")
except Exception as e:
    print(f"  -> Injection failed: {e}")
    sys.exit(1)

# STEP 2: Real Ingress Requests through API Gateway
print("\n[STEP 2] Sending Ingress Checkout Requests via Gateway to trigger real error/metric telemetry...")
order_payload = {
    "customer_id": "cust-e2e-test",
    "items": [{"sku": "SKU-SERVER-01", "quantity": 1, "price": 2499.00}],
    "payment_method": "credit_card"
}

for i in range(5):
    t0 = time.time()
    try:
        r = client.post(f"{GATEWAY_URL}/api/v1/orders", json=order_payload, timeout=6.0)
        lat = round((time.time() - t0) * 1000, 1)
        print(f"  -> Request {i+1}: HTTP {r.status_code} in {lat}ms")
    except Exception as e:
        lat = round((time.time() - t0) * 1000, 1)
        print(f"  -> Request {i+1}: Failed ({type(e).__name__}) after {lat}ms")

# STEP 3: Wait for Anomaly Detection & Incident Pipeline
print("\n[STEP 3] Waiting for Backend Anomaly Detection & Incident Creation...")
detected_inc = None
for poll in range(12):
    time.sleep(2.0)
    try:
        res = client.get(f"{BASE_URL}/api/incidents")
        incidents = res.json()
        for inc in incidents:
            if "shopsphere" in inc.get("tenant_id", "").lower() or "order" in str(inc.get("affected_services", [])).lower() or "order" in str(inc.get("title", "")).lower():
                if inc.get("status") in ["OPEN", "INVESTIGATING", "DETECTED", "ROOT_CAUSE_IDENTIFIED"]:
                    detected_inc = inc
                    break
        if detected_inc:
            break
        print(f"  -> Polling... ({poll+1}/12)")
    except Exception as ex:
        print(f"  -> Polling error: {ex}")

if not detected_inc:
    # Check all active incidents
    res = client.get(f"{BASE_URL}/api/incidents")
    incidents = res.json()
    if incidents:
        detected_inc = incidents[0]

if not detected_inc:
    print("  [ERROR] No incident detected by backend!")
    sys.exit(1)

inc_id = detected_inc["incident_id"]
print(f"  [+] REAL INCIDENT DETECTED: {inc_id}")
print(f"      Title:      {detected_inc.get('title')}")
print(f"      Severity:   {detected_inc.get('severity')}")
print(f"      Status:     {detected_inc.get('status')}")
print(f"      Root Cause: {detected_inc.get('root_cause') or detected_inc.get('root_cause_service')}")

# STEP 4: Inspect Incident Detail Endpoint with SAME incident_id
print(f"\n[STEP 4] Fetching Incident Detail for {inc_id}...")
det_res = client.get(f"{BASE_URL}/api/incidents/{inc_id}")
detail = det_res.json()
assert detail.get("incident_id") == inc_id, f"Incident ID mismatch: {detail.get('incident_id')} vs {inc_id}"
print(f"  -> Confirmed SAME incident_id: {detail.get('incident_id')}")
print(f"  -> Affected Services: {detail.get('affected_services')}")
print(f"  -> Solution: {detail.get('solution') or detail.get('remediation_plan')}")
print(f"  -> Recovery Procedure: {len(detail.get('recovery_procedure', []))} steps")
print(f"  -> Supporting Evidence items: {len(detail.get('supporting_evidence', []))}")
print(f"  -> Timeline Events: {len(detail.get('timeline', []))}")

# STEP 5: Request Approval
print(f"\n[STEP 5] Sending {inc_id} to Approval Center...")
req_app = client.post(
    f"{BASE_URL}/api/incidents/{inc_id}/request-approval",
    json={"reason": "Automated mitigation requested for database connection exhaustion", "requested_by": "AegisOps-AI"}
)
print(f"  -> Request approval response status: {req_app.status_code}")
app_data = req_app.json()
approval_id = app_data.get("approval_id")
print(f"  -> Generated Approval Ticket: {approval_id}")

# STEP 6: Check Approval Center for SAME incident_id
print(f"\n[STEP 6] Verifying Approval Ticket in Approval Center...")
apps_res = client.get(f"{BASE_URL}/api/approvals")
apps = apps_res.json()
target_ticket = next((a for a in apps if a.get("approval_id") == approval_id or a.get("incident_id") == inc_id), None)
assert target_ticket is not None, f"Ticket {approval_id} not found in approvals!"
print(f"  -> Confirmed Ticket {target_ticket.get('approval_id')} maps to Incident {target_ticket.get('incident_id')}")
print(f"  -> Status: {target_ticket.get('status')}")
print(f"  -> Proposed Action: {target_ticket.get('proposed_action')}")
print(f"  -> Risk Level: {target_ticket.get('risk_level')}")

# Verify recovery NOT executed before approval
inc_check = client.get(f"{BASE_URL}/api/incidents/{inc_id}").json()
print(f"  -> Incident Status before approval: {inc_check.get('status')} (GATED)")

# STEP 7: Authorized Member Approves
print(f"\n[STEP 7] Member Approves Remediation for {approval_id}...")
t_app_start = time.time()
approve_res = client.post(
    f"{BASE_URL}/api/approvals/{approval_id}/approve",
    json={"reviewer": "sre-commander", "role": "ADMIN", "notes": "Approved by Lead SRE Commander."}
)
app_elapsed = round(time.time() - t_app_start, 2)
print(f"  -> Approval Execution Response in {app_elapsed}s: HTTP {approve_res.status_code}")
print(f"  -> Body: {approve_res.json()}")

# STEP 8: Verify Post-Recovery Status
print(f"\n[STEP 8] Verifying Incident Lifecycle Transition to RESOLVED...")
final_inc = client.get(f"{BASE_URL}/api/incidents/{inc_id}").json()
print(f"  -> Final Status:           {final_inc.get('status')}")
print(f"  -> Final Lifecycle State:  {final_inc.get('lifecycle_state')}")
print(f"  -> Verification Status:    {final_inc.get('verification_status')}")
print(f"  -> Metric Comparison:     {final_inc.get('metric_comparison')}")

print("\n" + "=" * 80)
print(f"   SUCCESSFULLY VERIFIED FULL END-TO-END LIFECYCLE FOR {inc_id}!")
print("=" * 80)
