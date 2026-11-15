import asyncio
import json
import time
import httpx
import websockets

async def verify_multi_company():
    print("=" * 70)
    print("VERIFYING MULTI-COMPANY TELEMETRY PIPELINE & TENANT ISOLATION")
    print("=" * 70)

    # 1. Send distinct requests to each of the 3 companies
    companies = [
        {
            "id": "shopsphere",
            "url": "http://127.0.0.1:8100/api/v1/orders",
            "method": "POST",
            "payload": {"customer_id": "cust-sp-1", "items": [{"sku": "SKU-CABLE-10", "quantity": 1, "price": 29.99}], "total_amount": 29.99}
        },
        {
            "id": "fincore",
            "url": "http://127.0.0.1:8200/api/v1/transactions",
            "method": "POST",
            "payload": {"account_id": "acc-1001", "amount": 150.00, "transaction_type": "DEPOSIT", "currency": "USD"}
        },
        {
            "id": "clouddesk",
            "url": "http://127.0.0.1:8300/api/v1/users/login",
            "method": "POST",
            "payload": {"username": "admin@clouddesk.io", "password": "password123"}
        }
    ]

    async with httpx.AsyncClient(timeout=10.0) as client:
        for c in companies:
            req_id = f"trace-{c['id']}-{int(time.time()*1000)}"
            headers = {"X-Request-ID": req_id}
            print(f"\n[+] Sending real traffic to {c['id']} ({c['url']})...")
            resp = await client.post(c["url"], json=c["payload"], headers=headers)
            print(f"    Response: HTTP {resp.status_code}")

    # Wait for logs to flush into AegisOps
    await asyncio.sleep(1.0)

    # 2. Check /api/debug/telemetry
    async with httpx.AsyncClient(timeout=5.0) as client:
        diag = (await client.get("http://127.0.0.1:8000/api/debug/telemetry")).json()
        print("\n" + "=" * 70)
        print("REAL STATUS OF ALL 3 COMPANIES IN /api/debug/telemetry:")
        print("=" * 70)
        for comp_id in ["shopsphere", "fincore", "clouddesk"]:
            comp_info = diag["companies"][comp_id]
            print(f"  [{comp_id.upper()}]:")
            print(f"    Status:          {comp_info['status'].upper()}")
            print(f"    Events Received: {comp_info['events_received']}")
            print(f"    Last Event At:   {comp_info['last_event_at']}")

    # 3. Check Tenant Isolation in TelemetryStore queries
    print("\n" + "=" * 70)
    print("VERIFYING TENANT ISOLATION IN REST API (/api/v1/telemetry/live-events):")
    print("=" * 70)
    async with httpx.AsyncClient(timeout=5.0) as client:
        for comp_id in ["shopsphere", "fincore", "clouddesk"]:
            res = (await client.get(f"http://127.0.0.1:8000/api/v1/telemetry/live-events?tenant_id={comp_id}&limit=20")).json()
            events = res.get("events", [])
            other_tenants = [e["tenant_id"] for e in events if e.get("tenant_id") != comp_id]
            print(f"  [{comp_id}]: {len(events)} events returned, foreign events detected: {len(other_tenants)}")
            assert len(other_tenants) == 0, f"Tenant isolation breach! Found events: {other_tenants}"

    # 4. Check Tenant Isolation over WebSocket
    print("\n" + "=" * 70)
    print("VERIFYING TENANT ISOLATION OVER WEBSOCKET:")
    print("=" * 70)
    async with websockets.connect("ws://127.0.0.1:8000/ws/telemetry") as ws:
        # Subscribe strictly to fincore
        await ws.send(json.dumps({"action": "subscribe", "tenant_id": "fincore"}))
        sub_resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
        print(f"  [+] Connected & Subscribed to FinCore stream: {sub_resp}")

        # Send an event to shopsphere
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post("http://127.0.0.1:8100/api/v1/catalog", headers={"X-Request-ID": f"leak-test-sp-{int(time.time())}"})
            # Send an event to fincore
            await client.post("http://127.0.0.1:8200/api/v1/transactions", json={"account_id": "acc-1002", "amount": 25.0, "transaction_type": "TRANSFER", "currency": "USD"}, headers={"X-Request-ID": f"fincore-target-{int(time.time())}"})

        # Receive packets over WebSocket
        received_tenants = set()
        start = time.time()
        while time.time() - start < 3.0:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                tid = data.get("tenant_id")
                if tid:
                    received_tenants.add(tid)
                    print(f"  [+] WS received event: tenant_id={tid}, service={data.get('service')}, req_id={data.get('request_id')}")
            except asyncio.TimeoutError:
                break

        print(f"  Tenants observed on FinCore subscription: {received_tenants}")
        assert "shopsphere" not in received_tenants, "Leak! ShopSphere event received on FinCore socket!"
        print("  [+] Strict WebSocket Tenant Isolation Confirmed!")

    print("\n" + "=" * 70)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(verify_multi_company())
