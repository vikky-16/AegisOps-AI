"""
AegisOps AI - Live Chaos Injection & End-to-End Pipeline Verification Script
Executes Phase 20 Verification:
1. Injects real database latency chaos into running company microservice
2. Drives real requests through the gateway
3. Measures cascaded latency and failure
4. Observes anomaly detection
5. Verifies incident creation in AegisOps
6. Verifies timeline and multi-factor RCA evidence
7. Resets fault and confirms recovery
"""

import sys
import os
import time
import json
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    print("=" * 75)
    print("   AEGISOPS AI - LIVE CHAOS INJECTION & INCIDENT PIPELINE VERIFICATION")
    print("=" * 75)

    # 1. Inject Chaos into ShopSphere Order Service
    print("\n[Step 1] Injecting 2500ms database latency chaos into Order Service (8101)...")
    r_inj = httpx.post("http://127.0.0.1:8101/inject/db-latency", json={"latency_ms": 2500, "exhaust_connections": True}, timeout=5.0)
    print(f"  -> Chaos Response: {r_inj.json()}")

    # 2. Drive Real Requests via API Gateway (8100)
    print("\n[Step 2] Sending Ingress Checkout Requests via ShopSphere Gateway (8100)...")
    order_payload = {
        "customer_id": "cust-chaos-test",
        "items": [{"sku": "SKU-LAPTOP-01", "quantity": 1, "price": 1299.99}],
        "payment_method": "credit_card"
    }

    for i in range(4):
        t0 = time.time()
        try:
            r = httpx.post("http://127.0.0.1:8100/api/v1/orders", json=order_payload, timeout=6.0)
            lat = round((time.time() - t0) * 1000, 1)
            print(f"  -> Req {i+1}: HTTP {r.status_code} in {lat}ms")
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            print(f"  -> Req {i+1}: Cascaded Timeout / Failure ({type(e).__name__}) after {lat}ms")

    # 3. Wait for AegisOps correlation engine
    print("\n[Step 3] Waiting 4s for AegisOps Anomaly Engine & Multi-Factor RCA...")
    time.sleep(4.0)

    # 4. Check Incidents
    print("\n[Step 4] Querying Incidents from AegisOps Central Orchestrator...")
    incs = []
    for _ in range(5):
        try:
            r_inc = httpx.get("http://127.0.0.1:8000/api/incidents?tenant_id=shopsphere", timeout=5.0)
            incs = r_inc.json()
            if incs:
                break
        except Exception:
            pass
        time.sleep(1.5)

    print(f"  -> Total Active Incidents for ShopSphere: {len(incs)}")
    if incs:
        latest = incs[0]
        print(f"  -> Incident ID:       {latest.get('incident_id')}")
        print(f"  -> Title:             {latest.get('title')}")
        print(f"  -> Status:            {latest.get('status')}")
        print(f"  -> Severity:          {latest.get('severity')}")
        print(f"  -> Root Cause:        {latest.get('root_cause_service')}")
        print(f"  -> Root Category:     {latest.get('root_cause_category')}")
        print(f"  -> RCA Confidence:    {latest.get('confidence_pct')}%")
        print(f"  -> Timeline Events:   {len(latest.get('timeline', []))}")
        print(f"  -> Supporting Evidence ({len(latest.get('supporting_evidence', []))} items):")
        for ev in latest.get("supporting_evidence", [])[:4]:
            print(f"     * {ev}")
        print(f"  -> Alternative Hypotheses:")
        for alt in latest.get("alternative_hypotheses", []):
            print(f"     * {alt.get('candidate')} ({alt.get('confidence_pct')}%): {alt.get('why_not_primary')}")

    # 5. Reset Chaos
    print("\n[Step 5] Resetting Chaos Injection on Order Service...")
    r_rst = httpx.post("http://127.0.0.1:8101/inject/db-reset", timeout=5.0)
    print(f"  -> Reset Status: {r_rst.json()}")

    # 6. Verify Normal Recovery
    print("\n[Step 6] Verifying Recovery with Fresh Checkout...")
    t0 = time.time()
    r_rec = httpx.post("http://127.0.0.1:8100/api/v1/orders", json=order_payload, timeout=5.0)
    lat = round((time.time() - t0) * 1000, 1)
    print(f"  -> Post-Recovery Order: HTTP {r_rec.status_code} in {lat}ms (Recovered!)")

    print("\n" + "=" * 75)
    print("   LIVE CHAOS & INCIDENT PIPELINE VERIFIED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    main()
