import httpx
import json

client = httpx.Client(timeout=45.0)

app_id = "APP-6-4A675E"
inc_id = "INC-2026-4A675E"

print(f"--- APPROVING {app_id} ---")
r_approve = client.post(f"http://127.0.0.1:8000/api/approvals/{app_id}/approve", json={
    "reviewer": "sre-commander",
    "role": "ADMIN",
    "notes": "Approved for automated mitigation."
})
print("Approve status code:", r_approve.status_code)
print("Response:", r_approve.json())

# Check incident status
r_inc = client.get(f"http://127.0.0.1:8000/api/incidents/{inc_id}")
print(f"\n--- INCIDENT {inc_id} STATUS ---")
inc_data = r_inc.json()
print("Status:", inc_data.get("status"))
print("Lifecycle State:", inc_data.get("lifecycle_state"))
print("Validation Status:", inc_data.get("validation_status"))
print("Metric Diff:", inc_data.get("metric_diff"))
