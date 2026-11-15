"""
ShopSphere Real-Time Traffic Generator
Continuously drives actual HTTP traffic through the API Gateway.
Simulates realistic e-commerce traffic:
- 60% inventory / catalog queries
- 25% checkout / order creation flows (spans all 5 services, DB, cache)
- 15% order status lookups
Configurable via TRAFFIC_REQUESTS_PER_SECOND environment variable.
Measures real throughput, latency, and error counts.
"""

import os
import sys
import time
import random
import asyncio
import httpx
from typing import List, Dict, Any

IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_GATEWAY_URL = "http://api-gateway:8100" if IN_DOCKER else "http://127.0.0.1:8100"
GATEWAY_URL = os.getenv("GATEWAY_URL", DEFAULT_GATEWAY_URL).rstrip("/")
TARGET_RPS = float(os.getenv("TRAFFIC_REQUESTS_PER_SECOND", "50"))

SKUS = [
    ("SKU-LAPTOP-01", 1299.99),
    ("SKU-PHONE-02", 899.99),
    ("SKU-HEADSET-03", 199.50),
    ("SKU-KEYBOARD-04", 129.00),
    ("SKU-MONITOR-05", 499.00),
    ("SKU-MOUSE-06", 69.99),
    ("SKU-SMARTWATCH-07", 249.99),
    ("SKU-CHARGER-08", 45.00),
    ("SKU-STAND-09", 39.99),
    ("SKU-CABLE-10", 29.99)
]

CUSTOMERS = [f"cust-{1000 + i}" for i in range(50)]


class TrafficMetrics:
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.window_requests = 0
        self.window_errors = 0
        self.latencies: List[float] = []
        self.last_report = time.time()
        self.recent_created_orders: List[str] = []

    def record(self, latency_ms: float, success: bool, order_id: str = None):
        self.total_requests += 1
        self.window_requests += 1
        self.latencies.append(latency_ms)
        if success:
            self.successful_requests += 1
            if order_id:
                self.recent_created_orders.append(order_id)
                if len(self.recent_created_orders) > 200:
                    self.recent_created_orders.pop(0)
        else:
            self.failed_requests += 1
            self.window_errors += 1

    def print_summary(self):
        now = time.time()
        elapsed = now - self.last_report
        if elapsed < 2.0:
            return

        measured_rps = round(self.window_requests / elapsed, 1)
        err_rate = round((self.window_errors / max(1, self.window_requests)) * 100, 1)
        avg_lat = round(sum(self.latencies) / max(1, len(self.latencies)), 1)
        p95_lat = round(sorted(self.latencies)[int(len(self.latencies) * 0.95)], 1) if self.latencies else 0.0

        print(
            f"[TRAFFIC GENERATOR] Throughput: {measured_rps} req/sec | Avg Latency: {avg_lat}ms (p95: {p95_lat}ms) | "
            f"Errors: {self.window_errors} ({err_rate}%) | Total Sent: {self.total_requests}",
            flush=True
        )

        self.window_requests = 0
        self.window_errors = 0
        self.latencies = []
        self.last_report = now


metrics = TrafficMetrics()


async def send_operation(client: httpx.AsyncClient):
    """Executes a single realistic operation through the API Gateway."""
    op_type = random.random()
    start = time.time()
    success = False
    order_id = None

    try:
        if op_type < 0.60:
            # 60%: Check inventory / catalog
            sku, _ = random.choice(SKUS)
            resp = await client.get(f"{GATEWAY_URL}/api/v1/inventory/{sku}", timeout=5.0)
            success = resp.status_code == 200
        elif op_type < 0.85:
            # 25%: Create order (full multi-service checkout pipeline)
            customer = random.choice(CUSTOMERS)
            selected_items = random.sample(SKUS, random.randint(1, 3))
            payload = {
                "customer_id": customer,
                "items": [
                    {"sku": s, "quantity": random.randint(1, 2), "price": p}
                    for s, p in selected_items
                ],
                "payment_method": "credit_card"
            }
            resp = await client.post(f"{GATEWAY_URL}/api/v1/orders", json=payload, timeout=8.0)
            success = resp.status_code == 201
            if success:
                data = resp.json()
                order_id = data.get("order_id")
        else:
            # 15%: Lookup existing order
            if metrics.recent_created_orders:
                target_order = random.choice(metrics.recent_created_orders)
                resp = await client.get(f"{GATEWAY_URL}/api/v1/orders/{target_order}", timeout=5.0)
                success = resp.status_code == 200
            else:
                resp = await client.get(f"{GATEWAY_URL}/api/v1/catalog", timeout=5.0)
                success = resp.status_code == 200
    except Exception:
        success = False

    latency_ms = round((time.time() - start) * 1000, 2)
    metrics.record(latency_ms, success, order_id)


async def traffic_worker(client: httpx.AsyncClient, rate_per_second: float):
    interval = 1.0 / max(1.0, rate_per_second)
    while True:
        asyncio.create_task(send_operation(client))
        await asyncio.sleep(interval)


async def main():
    print("=" * 70)
    print(f"   SHOPSPHERE REAL TRAFFIC GENERATOR")
    print(f"   Target Gateway: {GATEWAY_URL}")
    print(f"   Target Rate:    {TARGET_RPS} requests/second")
    print("=" * 70, flush=True)

    # Wait for gateway to become healthy
    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
        print("[TRAFFIC] Waiting for API Gateway to be reachable...", flush=True)
        for _ in range(30):
            try:
                r = await client.get(f"{GATEWAY_URL}/health")
                if r.status_code == 200:
                    print("[TRAFFIC] API Gateway is HEALTHY. Beginning continuous traffic...", flush=True)
                    break
            except Exception:
                await asyncio.sleep(1.0)
        else:
            print("[TRAFFIC] Warning: Gateway not yet ready. Proceeding anyway...", flush=True)

    # Scale concurrent worker loops to achieve desired RPS smoothly
    concurrency = min(20, max(2, int(TARGET_RPS / 25)))
    rate_per_worker = TARGET_RPS / concurrency

    limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
    async with httpx.AsyncClient(limits=limits, timeout=10.0, trust_env=False) as client:
        workers = [
            asyncio.create_task(traffic_worker(client, rate_per_worker))
            for _ in range(concurrency)
        ]
        
        while True:
            await asyncio.sleep(2.0)
            metrics.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
