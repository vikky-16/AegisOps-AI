import asyncio
import time
import httpx

async def run_100_requests():
    print("=" * 60)
    print("GENERATING 100 REAL REQUESTS TO SHOPSPHERE")
    print("=" * 60)

    url_catalog = "http://127.0.0.1:8100/api/v1/catalog"
    url_order = "http://127.0.0.1:8100/api/v1/orders"

    order_payload = {
        "customer_id": "cust-batch-100",
        "items": [{"sku": "SKU-CABLE-10", "quantity": 1, "price": 29.99}],
        "total_amount": 29.99
    }

    start = time.time()
    success_count = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(100):
            req_id = f"batch-req-{i:03d}-{int(time.time()*1000)}"
            headers = {"X-Request-ID": req_id}
            if i % 2 == 0:
                resp = await client.get(url_catalog, headers=headers)
            else:
                resp = await client.post(url_order, json=order_payload, headers=headers)
            if resp.status_code in (200, 201):
                success_count += 1
            if (i + 1) % 25 == 0:
                print(f"  [+] Sent {i + 1}/100 requests (success: {success_count})")
            await asyncio.sleep(0.02)  # 20ms between requests

    elapsed = time.time() - start
    print(f"\nCompleted 100 requests in {elapsed:.2f}s ({success_count}/100 successful)")

    # Wait 1 second for background log flush loop to deliver logs
    await asyncio.sleep(1.0)

    # Query AegisOps stats
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get("http://127.0.0.1:8000/api/debug/telemetry")
        diag = r.json()
        sp = diag["companies"]["shopsphere"]
        print("\n" + "=" * 60)
        print("AEGISOPS REAL RUNTIME DIAGNOSTIC AFTER 100 REQUESTS:")
        print("=" * 60)
        print(f"  ShopSphere Status:    {sp['status'].upper()}")
        print(f"  Events Received:      {sp['events_received']}")
        print(f"  Last Event At:        {sp['last_event_at']}")

        r_src = await client.get("http://127.0.0.1:8000/api/v1/telemetry/sources?tenant_id=shopsphere")
        src_data = r_src.json()
        sp_src = src_data["sources"][0]
        print(f"  Events Per Second:    {sp_src.get('events_per_second')} eps")
        print(f"  Last Event Age:       {sp_src.get('last_event_age_seconds')}s ago")
        print(f"  Logs Received:        {sp_src.get('logs_received')}")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_100_requests())
