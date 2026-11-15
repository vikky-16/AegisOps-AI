import httpx
client = httpx.Client(timeout=10.0)
r = client.get('http://127.0.0.1:8000/api/incidents/INC-2026-1210A2').json()
print("Status:", r.get("status"))
print("Recovery Status:", r.get("recovery_status"))
print("Verification Status:", r.get("verification_status"))
print("Failure Reasons:", r.get("failure_reasons"))
for t in r.get("timeline", []):
    print("Timeline:", t.get("type"), "|", t.get("message"))
