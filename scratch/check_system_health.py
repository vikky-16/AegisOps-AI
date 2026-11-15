import socket
import json
import urllib.request
import urllib.error

PORTS_TO_CHECK = {
    "PostgreSQL": 5432,
    "Redis": 6379,
    "AegisOps Backend": 8000,
    "Frontend Vite": 5173,
    "ShopSphere Ingress (8100)": 8100,
    "ShopSphere Catalog (8101)": 8101,
    "ShopSphere Orders (8102)": 8102,
    "ShopSphere Inventory (8103)": 8103,
    "ShopSphere Database (8104)": 8104,
    "FinCore Gateway (8200)": 8200,
    "FinCore Transaction (8201)": 8201,
    "FinCore Accounts (8202)": 8202,
    "FinCore Fraud (8203)": 8203,
    "FinCore Payment (8204)": 8204,
    "FinCore Database (8205)": 8205,
    "CloudDesk Gateway (8300)": 8300,
    "CloudDesk Workspace (8301)": 8301,
    "CloudDesk Billing (8302)": 8302,
    "CloudDesk Auth (8303)": 8303,
    "CloudDesk Notification (8304)": 8304,
    "CloudDesk Database (8305)": 8305,
}

print("=== CHECKING PORT CONNECTIVITY ===")
for name, port in PORTS_TO_CHECK.items():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    result = s.connect_ex(('127.0.0.1', port))
    status = "OPEN (LISTENING)" if result == 0 else "CLOSED / DOWN"
    print(f"[{port}] {name}: {status}")
    s.close()

print("\n=== CHECKING BACKEND API ENDPOINTS ===")
ENDPOINTS = [
    "http://127.0.0.1:8000/api/health",
    "http://127.0.0.1:8000/api/platform/health",
    "http://127.0.0.1:8000/api/telemetry/sources?company=shopsphere",
    "http://127.0.0.1:8000/api/telemetry/sources?company=fincore",
    "http://127.0.0.1:8000/api/telemetry/sources?company=clouddesk",
    "http://127.0.0.1:8000/api/telemetry/live?tenant_id=shopsphere&limit=5",
]

for url in ENDPOINTS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AegisOps-Diagnostic"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = resp.read().decode('utf-8')
            try:
                js = json.loads(data)
                sample = json.dumps(js)[:150]
            except Exception:
                sample = data[:150]
            print(f"[OK 200] {url} -> {sample}...")
    except Exception as e:
        print(f"[FAILED] {url} -> {e}")
