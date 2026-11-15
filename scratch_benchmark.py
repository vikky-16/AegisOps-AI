import time
import requests
import json

BASE_URL = "http://localhost:8000"

endpoints = [
    ("GET", "/api/incidents"),
    ("GET", "/api/approvals"),
    ("GET", "/api/tenants"),
    ("GET", "/api/testing/status"),
    ("GET", "/api/testing/scenarios"),
    ("GET", "/api/testing/runs"),
    ("GET", "/api/testing/matrix"),
    ("GET", "/api/incidents/recovery/allowlisted-actions"),
    ("GET", "/api/sre-assistant/conversations"),
    ("GET", "/api/platform-health/status"),
    ("GET", "/api/ai-config/status"),
    ("GET", "/api/dependencies/topology"),
]

def benchmark():
    results = []
    print("=== BASELINE ENDPOINT LATENCY BENCHMARK ===")
    for method, path in endpoints:
        durations = []
        status_code = None
        for i in range(3):
            t0 = time.perf_counter()
            try:
                res = requests.get(f"{BASE_URL}{path}", headers={"X-Tenant-ID": "demo-tenant"}, timeout=10)
                dur = (time.perf_counter() - t0) * 1000
                durations.append(dur)
                status_code = res.status_code
            except Exception as e:
                durations.append(-1)
                status_code = str(e)
        
        valid_durs = [d for d in durations if d > 0]
        avg_dur = round(sum(valid_durs) / len(valid_durs), 2) if valid_durs else -1
        min_dur = round(min(valid_durs), 2) if valid_durs else -1
        results.append({
            "endpoint": path,
            "status": status_code,
            "avg_ms": avg_dur,
            "min_ms": min_dur,
            "runs": [round(d, 2) for d in durations]
        })
        print(f"{path:45} | Status: {status_code} | Avg: {avg_dur:7.2f} ms | Min: {min_dur:7.2f} ms")

    return results

if __name__ == "__main__":
    benchmark()
