"""
CloudDesk Real-Time Traffic Generator
Continuously drives actual HTTP traffic through the CloudDesk API Gateway (Port 8300).
Simulates realistic SaaS and cloud platform traffic:
- 35% user authentication and developer profile lookups
- 35% compute instance provisioning (spans Gateway, Compute, Redis, Billing, DB, Notification)
- 15% compute instance status queries
- 15% project creation and project lookups
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
DEFAULT_GATEWAY_URL = "http://api-gateway:8300" if IN_DOCKER else "http://127.0.0.1:8300"
GATEWAY_URL = os.getenv("GATEWAY_URL", DEFAULT_GATEWAY_URL).rstrip("/")
TARGET_RPS = float(os.getenv("TRAFFIC_REQUESTS_PER_SECOND", "10"))

USERS = [f"developer_{i}@cloudtech.io" for i in range(15)]
PROJECTS = [f"prj-{500 + i}" for i in range(10)]
INSTANCE_TYPES = ["c5.large", "m5.xlarge", "t3.medium", "r5.2xlarge"]


class TrafficMetrics:
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.window_requests = 0
        self.window_errors = 0
        self.latencies: List[float] = []
        self.last_report = time.time()
        self.recent_instances: List[str] = []

    def record(self, latency_ms: float, success: bool, instance_id: str = None):
        self.total_requests += 1
        self.window_requests += 1
        self.latencies.append(latency_ms)
        if success:
            self.successful_requests += 1
            if instance_id:
                self.recent_instances.append(instance_id)
                if len(self.recent_instances) > 100:
                    self.recent_instances.pop(0)
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
            f"[CLOUDDESK TRAFFIC] {measured_rps} req/sec | Avg: {avg_lat}ms (p95: {p95_lat}ms) | "
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
    new_inst_id = None

    try:
        if op_type < 0.35:
            # User login
            email = random.choice(USERS)
            resp = await client.post(f"{GATEWAY_URL}/api/v1/users/login", json={"email": email, "password": "password123"})
            success = resp.status_code == 200
        elif op_type < 0.70:
            # Compute instance creation
            prj_id = random.choice(PROJECTS)
            inst_type = random.choice(INSTANCE_TYPES)
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/compute/instances",
                json={
                    "project_id": prj_id,
                    "name": f"worker-node-{random.randint(100, 999)}",
                    "instance_type": inst_type,
                    "cpu_cores": 4 if "large" in inst_type else 8,
                    "memory_gb": 16 if "large" in inst_type else 32
                }
            )
            success = resp.status_code in (200, 201)
            if success:
                new_inst_id = resp.json().get("instance_id")
        elif op_type < 0.85:
            # Compute instance status lookup
            if metrics.recent_instances:
                inst_id = random.choice(metrics.recent_instances)
                resp = await client.get(f"{GATEWAY_URL}/api/v1/compute/instances/{inst_id}/status")
                success = resp.status_code == 200
            else:
                resp = await client.get(f"{GATEWAY_URL}/health")
                success = resp.status_code == 200
        else:
            # Project lookup
            prj_id = random.choice(PROJECTS)
            resp = await client.get(f"{GATEWAY_URL}/api/v1/projects/{prj_id}")
            success = resp.status_code == 200

    except Exception:
        success = False

    dur_ms = round((time.time() - start) * 1000, 2)
    metrics.record(dur_ms, success, new_inst_id)


async def traffic_loop():
    print("=" * 70)
    print(f"  CLOUDDESK SAAS TRAFFIC GENERATOR -> {GATEWAY_URL}")
    print(f"  Target Rate: {TARGET_RPS} requests/sec")
    print("=" * 70, flush=True)

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(timeout=8.0, limits=limits, trust_env=False) as client:
        retries = 0
        while retries < 15:
            try:
                res = await client.get(f"{GATEWAY_URL}/health")
                if res.status_code == 200:
                    print(f"  [+] CloudDesk Gateway connected successfully ({GATEWAY_URL}). Starting traffic...", flush=True)
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
        print("\n[CLOUDDESK TRAFFIC] Stopped.")
