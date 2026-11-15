import asyncio
import json
import time
import httpx
import websockets

UNIQUE_REQ_ID = f"DEBUG-REQ-TRACE-{int(time.time())}"

async def trace_single_event():
    print(f"\n=======================================================")
    print(f"TRACING REAL EVENT: {UNIQUE_REQ_ID}")
    print(f"=======================================================")

    received_ws_events = []

    # Stage 1: Connect WebSocket to AegisOps Backend
    print("\n[STAGE 1: WEBSOCKET]")
    ws_url = "ws://127.0.0.1:8000/ws/telemetry"
    async with websockets.connect(ws_url) as ws:
        # Subscribe to tenant shopsphere
        await ws.send(json.dumps({"action": "subscribe", "tenant_id": "shopsphere"}))
        sub_resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
        print(f"  [+] Connected & Subscribed to AegisOps WebSocket: {sub_resp}")

        # Stage 2: Send REAL Request to ShopSphere API Gateway
        print("\n[STAGE 2: REAL HTTP REQUEST TO COMPANY SERVICE]")
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "X-Request-ID": UNIQUE_REQ_ID,
                "Content-Type": "application/json"
            }
            order_payload = {
                "customer_id": "cust-trace-001",
                "items": [
                    {"sku": "SKU-LAPTOP-001", "quantity": 1, "price": 1299.99}
                ],
                "total_amount": 1299.99
            }
            resp = await client.post(
                "http://127.0.0.1:8100/api/v1/orders",
                json=order_payload,
                headers=headers
            )
            print(f"  [+] ShopSphere Gateway response: HTTP {resp.status_code}")
            print(f"  [+] Order Response Data: {resp.json()}")

        # Stage 3: Wait for Real Structured Log to arrive over WebSocket
        print("\n[STAGE 3: RECEIVING TELEMETRY VIA WEBSOCKET]")
        matched_event = None
        start_wait = time.time()
        while time.time() - start_wait < 6.0:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                print(f"  [+] Received WS packet: type={data.get('type')}, event_id={data.get('event_id')}, service={data.get('service')}, req_id={data.get('request_id')}")
                if data.get("request_id") == UNIQUE_REQ_ID:
                    matched_event = data
                    break
            except asyncio.TimeoutError:
                break

        if matched_event:
            print(f"\n>>> SUCCESS! Found matched event over WebSocket:")
            print(f"    - Event ID:   {matched_event.get('event_id')}")
            print(f"    - Tenant ID:  {matched_event.get('tenant_id')}")
            print(f"    - Service:    {matched_event.get('service')}")
            print(f"    - Request ID: {matched_event.get('request_id')}")
            print(f"    - Trace ID:   {matched_event.get('trace_id')}")
            print(f"    - Severity:   {matched_event.get('level') or matched_event.get('severity')}")
            print(f"    - Message:    {matched_event.get('message')}")
        else:
            print(f"\n>>> FAILED to receive event with request_id={UNIQUE_REQ_ID} via WebSocket within 6s")

        # Stage 4: Verify in AegisOps TelemetryStore via REST
        print("\n[STAGE 4: VERIFY IN AEGISOPS TELEMETRY STORE]")
        async with httpx.AsyncClient(timeout=5.0) as client:
            events_resp = await client.get(
                f"http://127.0.0.1:8000/api/v1/telemetry/live-events?tenant_id=shopsphere&limit=10"
            )
            events_data = events_resp.json()
            found_in_store = any(e.get("request_id") == UNIQUE_REQ_ID for e in events_data.get("events", []))
            print(f"  [+] Query /api/v1/telemetry/live-events: found_in_store={found_in_store}")

        # Stage 5: Verify Diagnostic Health Endpoint
        print("\n[STAGE 5: VERIFY /api/debug/telemetry]")
        async with httpx.AsyncClient(timeout=5.0) as client:
            diag_resp = await client.get("http://127.0.0.1:8000/api/debug/telemetry")
            diag_data = diag_resp.json()
            sp_status = diag_data.get("companies", {}).get("shopsphere", {})
            print(f"  [+] ShopSphere status in /api/debug/telemetry: {sp_status}")

if __name__ == "__main__":
    asyncio.run(trace_single_event())
