import httpx

c = httpx.Client(timeout=5.0)
for p in [8001, 8002, 8003, 8004, 8005]:
    try:
        r = c.get(f"http://127.0.0.1:{p}/health")
        print(f"Port {p}: {r.status_code} -> {r.json().get('status')} ({r.json().get('service')})")
    except Exception as e:
        print(f"Port {p}: FAILED -> {e}")
