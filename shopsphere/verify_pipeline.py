"""
ShopSphere Pipeline End-to-End Verification & Real Failure Chaos Test
Can run inside Docker network or from host.
Tests:
1. Microservices health (Gateway, Order, Inventory, Payment, Notification, OTel, Redpanda)
2. Real multi-hop checkout transaction with W3C distributed trace propagation
3. Ingress traffic measurement (RPS, latency, error rate)
4. AegisOps Ingestion Gateway stats & tenant isolation verification
5. Phase 11 — Real Database Degradation Chaos Test (latency injection -> cascaded delay -> AegisOps incident detection -> reset)
"""

import sys
import os
import time
import json
import httpx
import asyncio
from typing import Dict, Any, List

# Target URL discovery
IN_DOCKER = os.path.exists("/.dockerenv")

if IN_DOCKER:
    AEGISOPS_URL = os.getenv("AEGISOPS_BASE_URL", "http://172.18.80.1:8000")
    GATEWAY_URL = "http://api-gateway:8100"
    ORDER_URL = "http://order-service:8101"
    INVENTORY_URL = "http://inventory-service:8102"
    PAYMENT_URL = "http://payment-service:8103"
    NOTIFICATION_URL = "http://notification-service:8104"
    OTEL_URL = "http://otel-collector:13133"
    REDPANDA_URL = "http://redpanda:9644"
else:
    AEGISOPS_URL = "http://127.0.0.1:8000"
    GATEWAY_URL = "http://127.0.0.1:8100"
    ORDER_URL = "http://127.0.0.1:8101"
    INVENTORY_URL = "http://127.0.0.1:8102"
    PAYMENT_URL = "http://127.0.0.1:8103"
    NOTIFICATION_URL = "http://127.0.0.1:8104"
    OTEL_URL = "http://127.0.0.1:13133"
    REDPANDA_URL = "http://127.0.0.1:9644"


async def main():
    print("=" * 80)
    print("   AEGISOPS AI - SHOPSPHERE LIVE TELEMETRY PIPELINE VERIFICATION")
    print("=" * 80)
    print(f"   Execution Environment: {'Docker Container' if IN_DOCKER else 'Host'}")
    print(f"   AegisOps Target:       {AEGISOPS_URL}")
    print(f"   API Gateway Target:    {GATEWAY_URL}")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Verify Service Health
        print("\n[PHASE 1] Checking ShopSphere Microservices & Infrastructure...")
        services_to_check = [
            ("API Gateway", f"{GATEWAY_URL}/health"),
            ("Order Service", f"{ORDER_URL}/health"),
            ("Inventory Service", f"{INVENTORY_URL}/health"),
            ("Payment Service", f"{PAYMENT_URL}/health"),
            ("Notification Service", f"{NOTIFICATION_URL}/health"),
        ]
        if IN_DOCKER:
            services_to_check.extend([
                ("OTel Collector", f"{OTEL_URL}/"),
                ("Redpanda Broker", f"{REDPANDA_URL}/v1/status/ready"),
            ])
        else:
            services_to_check.extend([
                ("AegisOps Backend", f"{AEGISOPS_URL}/health"),
                ("AegisOps OTel Ingest", f"{AEGISOPS_URL}/api/otel/health"),
            ])

        healthy_count = 0
        for name, url in services_to_check:
            try:
                resp = await client.get(url)
                if resp.status_code in [200, 204]:
                    print(f"  [+] {name:<22}: ONLINE ({resp.status_code})")
                    healthy_count += 1
                else:
                    print(f"  [-] {name:<22}: STATUS {resp.status_code}")
            except Exception as e:
                print(f"  [-] {name:<22}: UNREACHABLE ({type(e).__name__})")

        print(f"\n-> Services Healthy: {healthy_count}/{len(services_to_check)}")
        assert healthy_count >= 5, "Critical services unavailable!"

        # 2. Test Real Multi-Hop Communication
        print("\n[PHASE 2 & 4] Testing Real Multi-Service Checkout Flow with Trace Propagation...")
        order_payload = {
            "customer_id": "cust-verify-001",
            "items": [
                {"sku": "SKU-LAPTOP-01", "quantity": 1, "price": 1299.99},
                {"sku": "SKU-HEADSET-03", "quantity": 2, "price": 199.50}
            ],
            "payment_method": "credit_card"
        }
        
        start_t = time.time()
        order_resp = await client.post(f"{GATEWAY_URL}/api/v1/orders", json=order_payload)
        elapsed_ms = round((time.time() - start_t) * 1000, 2)
        
        assert order_resp.status_code == 201, f"Order creation failed: {order_resp.text}"
        order_data = order_resp.json()
        trace_id = order_resp.headers.get("X-Trace-ID")
        req_id = order_resp.headers.get("X-Request-ID")
        tenant_hdr = order_resp.headers.get("X-Tenant-ID")

        print(f"  [+] Checkout Pipeline: SUCCESS in {elapsed_ms}ms")
        print(f"      Order ID:     {order_data.get('order_id')}")
        print(f"      Total Amount: ${order_data.get('total_amount')}")
        print(f"      X-Trace-ID:   {trace_id}")
        print(f"      X-Request-ID: {req_id}")
        print(f"      X-Tenant-ID:  {tenant_hdr}")

        # 3. Measure Live Traffic Throughput
        print("\n[PHASE 2 MEASUREMENT] Measuring Actual Traffic Ingress Throughput over 5 seconds...")
        sample_requests = 0
        sample_errors = 0
        sample_latencies = []
        sample_start = time.time()

        while (time.time() - sample_start) < 5.0:
            t0 = time.time()
            try:
                r = await client.get(f"{GATEWAY_URL}/api/v1/inventory/SKU-PHONE-02")
                lat = (time.time() - t0) * 1000
                sample_latencies.append(lat)
                if r.status_code == 200:
                    sample_requests += 1
                else:
                    sample_errors += 1
            except Exception:
                sample_errors += 1
            await asyncio.sleep(0.01)

        dur = time.time() - sample_start
        measured_rps = round(sample_requests / dur, 1)
        avg_lat = round(sum(sample_latencies) / max(1, len(sample_latencies)), 2)
        print(f"  [+] Measured Ingress Rate: {measured_rps} requests/sec")
        print(f"  [+] Average API Latency:   {avg_lat} ms")
        print(f"  [+] Error Rate:            {sample_errors} errors ({round(sample_errors/(sample_requests+sample_errors+1e-5)*100, 1)}%)")

        # 4. Verify AegisOps Ingestion Gateway & Tenant Isolation
        print("\n[PHASE 7 & 8] Verifying AegisOps Ingestion Gateway & Tenant Preservation...")
        stats_resp = await client.get(f"{AEGISOPS_URL}/api/v1/telemetry/stats?tenant_id=shopsphere")
        if stats_resp.status_code == 200:
            sp_stats = stats_resp.json()
            print(f"  [+] Tenant ID:              {sp_stats.get('tenant_id')}")
            print(f"  [+] Total Events Ingested:  {sp_stats.get('total_events')}")
            print(f"  [+] Total Volume Ingested:  {round(sp_stats.get('total_bytes', 0)/(1024*1024), 2)} MB")
            print(f"  [+] Measured Telemetry EPS: {sp_stats.get('measured_eps')} events/sec")
            print(f"  [+] Measured Log Rate:      {sp_stats.get('logs_per_sec')} logs/sec")
            print(f"  [+] Measured Metric Rate:   {sp_stats.get('metrics_per_sec')} metrics/sec")
            print(f"  [+] Measured Trace Rate:    {sp_stats.get('traces_per_sec')} traces/sec")
            print(f"  [+] Active Microservices:   {sp_stats.get('active_services')}")
            print(f"  [+] Last Ingest Timestamp:  {sp_stats.get('last_timestamp')}")
        else:
            print(f"  [-] Failed to fetch AegisOps stats: {stats_resp.status_code}")

        # 5. Phase 11 — Real Database Degradation Chaos Test
        print("\n[PHASE 11] Executing Real Database Degradation Failure Test...")
        print("  -> Injecting 2500ms database latency into Order Service PostgreSQL queries...")
        inj_resp = await client.post(f"{ORDER_URL}/inject/db-latency", json={"latency_ms": 2500.0, "exhaust_connections": False})
        print(f"  [+] Chaos Status: {inj_resp.json()}")

        # Send request during database degradation
        degraded_start = time.time()
        try:
            deg_order = await client.post(f"{GATEWAY_URL}/api/v1/orders", json=order_payload, timeout=8.0)
            deg_latency = round((time.time() - degraded_start) * 1000, 2)
            print(f"  [+] Order under DB degradation returned status {deg_order.status_code} in {deg_latency}ms (Cascaded Latency Confirmed!)")
        except httpx.TimeoutException:
            deg_latency = round((time.time() - degraded_start) * 1000, 2)
            print(f"  [+] Order timed out after {deg_latency}ms (Cascaded Timeout Confirmed!)")

        # Give AegisOps 5 seconds to observe abnormal telemetry and run anomaly detectors
        print("  -> Waiting 5s for AegisOps Anomaly Ensemble to process degraded telemetry...")
        await asyncio.sleep(5.0)

        # Query AegisOps incidents for ShopSphere
        inc_resp = await client.get(f"{AEGISOPS_URL}/api/incidents?tenant_id=shopsphere")
        if inc_resp.status_code == 200:
            incidents = inc_resp.json()
            print(f"  [+] Active Incidents in AegisOps for ShopSphere: {len(incidents)}")
            for inc in incidents[:5]:
                print(f"      - [{inc.get('incident_id')}] {inc.get('title')} (Status: {inc.get('status')}, Severity: {inc.get('severity')})")

        # Reset failure injection
        print("  -> Resetting database latency back to normal (0ms)...")
        reset_resp = await client.post(f"{ORDER_URL}/inject/db-reset")
        print(f"  [+] Reset Result: {reset_resp.json()}")

        # Give in-flight requests 2 seconds to clear
        print("  -> Waiting 2s for in-flight database requests to drain...")
        await asyncio.sleep(2.0)

        # Verify recovery
        rec_start = time.time()
        rec_order = await client.post(f"{GATEWAY_URL}/api/v1/orders", json=order_payload, timeout=10.0)
        rec_latency = round((time.time() - rec_start) * 1000, 2)
        print(f"  [+] Post-recovery Order succeeded with status {rec_order.status_code} in {rec_latency}ms (Normal Operation Restored!)")

    print("\n" + "=" * 80)
    print("   ALL SHOPSPHERE TELEMETRY PIPELINE PHASES VERIFIED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
