import httpx
import json

client = httpx.Client(timeout=30.0)

# 1. Fetch incident detail
inc_id = "INC-2026-4A675E"
r = client.get(f"http://127.0.0.1:8000/api/incidents/{inc_id}")
print(f"--- INCIDENT DETAIL FOR {inc_id} ---")
print("Status code:", r.status_code)
inc_data = r.json()
print("ID:", inc_data.get("incident_id"))
print("Title:", inc_data.get("title"))
print("Severity:", inc_data.get("severity"))
print("Status:", inc_data.get("status"))
print("Lifecycle State:", inc_data.get("lifecycle_state"))
print("Root Cause:", inc_data.get("root_cause"))
print("Confidence:", inc_data.get("confidence"))
print("Affected Services:", inc_data.get("affected_services"))
print("Remediation Plan:", inc_data.get("remediation_plan"))
print("Solution:", inc_data.get("solution"))
print("Recovery Procedure:", len(inc_data.get("recovery_procedure", [])), "steps")

# 2. Request Approval
print(f"\n--- REQUESTING APPROVAL FOR {inc_id} ---")
r_app_req = client.post(f"http://127.0.0.1:8000/api/incidents/{inc_id}/request-approval", json={
    "reason": "Requesting SRE lead approval for connection pool reset",
    "requested_by": "automation-pipeline"
})
print("Request approval status:", r_app_req.status_code)
print(r_app_req.json())

# 3. Check approvals list
r_apps = client.get("http://127.0.0.1:8000/api/approvals")
apps = r_apps.json()
target_ticket = None
for app in apps:
    if app.get("incident_id") == inc_id or inc_id in str(app.get("approval_id")):
        target_ticket = app
        break

print(f"\nTarget Ticket found: {target_ticket}")
