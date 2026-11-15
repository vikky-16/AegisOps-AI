"""
FinCore Real-Time Traffic Generator
Continuously drives actual HTTP traffic through the FinCore API Gateway (Port 8200).
Simulates realistic financial traffic:
- 40% account balance and details lookups
- 30% fund transfers / transaction creation (spans Gateway, Account, Transaction, Payment, Fraud, DB, Cache)
- 15% transaction limit validations
- 15% account transaction history lookups
Configurable via TRAFFIC_REQUESTS_PER_SECOND environment variable.
Measures real requests/sec, latencies, and error counts.
"""

import os
import sys
import time
import random
import asyncio
import httpx
from typing import List, Dict, Any

IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_GATEWAY_URL = "http://api-gateway:8200" if IN_DOCKER else "http://127.0.0.1:8200"
GATEWAY_URL = os.getenv("GATEWAY_URL", DEFAULT_GATEWAY_URL).rstrip("/")
TARGET_RPS = float(os.getenv("TRAFFIC_REQUESTS_PER_SECOND", "10"))

ACCOUNTS = [f"acc-{1000 + i}" for i in range(25)]


class TrafficMetrics:
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.window_requests = 0
        self.window_errors = 0
        self.latencies: List[float] = []
        self.last_report = time.time()

    def record(self, latency_ms: float, success: bool):
        self.total_requests += 1
        self.window_requests += 1
        self.latencies.append(latency_ms)
        if success:
            self.successful_requests += 1
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
            f"[FINCORE TRAFFIC] {measured_rps} req/sec | Avg: {avg_lat}ms (p95: {p95_lat}ms) | "
            f"Errors: {self.window_errors} ({err_rate}%) | Total Sent: {self.total_requests}",
            flush=True
        )

        self.window_requests = 0
        self.window_errors = 0
        self.latencies = []
        self.last_report = now


metrics = TrafficMetrics()


async def send_operation(client: httpx.AsyncClient):
    op_type = random.random()
    start = time.time()
    success = False

    try:
        if op_type < 0.40:
            # Account lookup
            acc_id = random.choice(ACCOUNTS)
            resp = await client.get(f"{GATEWAY_URL}/api/v1/accounts/{acc_id}")
            success = resp.status_code == 200
        elif op_type < 0.70:
            # Transaction creation
            from_acc = random.choice(ACCOUNTS)
            to_acc = random.choice([a for a in ACCOUNTS if a != from_acc])
            amount = round(random.uniform(25.0, 750.0), 2)
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/transactions",
                json={"from_account": from_acc, "to_account": to_acc, "amount": amount, "currency": "USD"}
            )
            success = resp.status_code in (200, 201)
        elif op_type < 0.85:
            # Transaction validation
            from_acc = random.choice(ACCOUNTS)
            to_acc = random.choice([a for a in ACCOUNTS if a != from_acc])
            amount = round(random.uniform(50.0, 5000.0), 2)
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/transactions/validate",
                json={"from_account": from_acc, "to_account": to_acc, "amount": amount}
            )
            success = resp.status_code == 200
        else:
            # History lookup
            acc_id = random.choice(ACCOUNTS)
            resp = await client.get(f"{GATEWAY_URL}/api/v1/transactions/history/{acc_id}")
            success = resp.status_code == 200

    except Exception:
        success = False

    dur_ms = round((time.time() - start) * 1000, 2)
    metrics.record(dur_ms, success)


async def traffic_loop():
    print("=" * 70)
    print(f"  FINCORE FINANCIAL TRAFFIC GENERATOR -> {GATEWAY_URL}")
    print(f"  Target Rate: {TARGET_RPS} requests/sec")
    print("=" * 70, flush=True)

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(timeout=8.0, limits=limits, trust_env=False) as client:
        # Verify gateway connectivity
        retries = 0
        while retries < 15:
            try:
                res = await client.get(f"{GATEWAY_URL}/health")
                if res.status_code == 200:
                    print(f"  [+] FinCore Gateway connected successfully ({GATEWAY_URL}). Starting traffic...", flush=True)
                    break
            except Exception:
                pass
            retries += 1
            await asyncio.sleep(1.0)

        interval = 1.0 / TARGET_RPS if TARGET_RPS > 0 else 0.1
        while True:
            t0 = time.time()
            asyncio.create_task(send_operation(client))
            metrics.print_summary()
            elapsed = time.time() - t0
            sleep_time = max(0.001, interval - elapsed)
            await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        asyncio.run(traffic_loop())
    except KeyboardInterrupt:
        print("\n[FINCORE TRAFFIC] Stopped.")
