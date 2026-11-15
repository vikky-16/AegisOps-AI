"""
Customer Synthetic Traffic Generator
Generates realistic continuous and burst traffic across the customer microservices topology
via the Customer Gateway ingress endpoint (http://127.0.0.1:8001/work).
"""

import os
import sys
import time
import uuid
import asyncio
import argparse
from typing import Dict, Any, List, Optional
import httpx


class TrafficStats:
    def __init__(self):
        self.total_requests: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.timeout_count: int = 0
        self.latencies: List[float] = []
        self.last_status_code: Optional[int] = None
        self.last_error: Optional[str] = None
        self.start_time: float = time.time()

    def record_success(self, latency_ms: float, status_code: int):
        self.total_requests += 1
        self.success_count += 1
        self.last_status_code = status_code
        self.latencies.append(latency_ms)
        if len(self.latencies) > 200:
            self.latencies.pop(0)

    def record_error(self, status_code: int, error_msg: str, latency_ms: float = 0.0):
        self.total_requests += 1
        self.error_count += 1
        self.last_status_code = status_code
        self.last_error = error_msg
        if latency_ms > 0:
            self.latencies.append(latency_ms)
            if len(self.latencies) > 200:
                self.latencies.pop(0)

    def record_timeout(self, error_msg: str):
        self.total_requests += 1
        self.error_count += 1
        self.timeout_count += 1
        self.last_status_code = 504
        self.last_error = error_msg

    def summary(self) -> Dict[str, Any]:
        lats = self.latencies or [0.0]
        sorted_lats = sorted(lats)
        p50 = sorted_lats[int(len(sorted_lats) * 0.5)]
        p95 = sorted_lats[min(int(len(sorted_lats) * 0.95), len(sorted_lats) - 1)]
        elapsed = max(0.1, time.time() - self.start_time)
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "timeout_count": self.timeout_count,
            "rps": round(self.total_requests / elapsed, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "error_rate": round(self.error_count / max(1, self.total_requests), 4),
            "last_status_code": self.last_status_code,
            "last_error": self.last_error
        }


class CustomerTrafficGenerator:
    def __init__(self, target_url: str = "http://127.0.0.1:8001/work", rate_per_sec: float = 5.0):
        self.target_url = target_url
        self.rate_per_sec = rate_per_sec
        self.stats = TrafficStats()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def send_single_request(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        trace_id = uuid.uuid4().hex
        start_t = time.time()
        headers = {
            "X-Trace-ID": trace_id,
            "traceparent": f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"
        }
        try:
            resp = await client.get(self.target_url, headers=headers)
            elapsed_ms = (time.time() - start_t) * 1000.0
            if resp.status_code < 400:
                self.stats.record_success(elapsed_ms, resp.status_code)
                return {"success": True, "status": resp.status_code, "latency_ms": elapsed_ms, "trace_id": trace_id}
            else:
                self.stats.record_error(resp.status_code, resp.text[:100], elapsed_ms)
                return {"success": False, "status": resp.status_code, "latency_ms": elapsed_ms, "trace_id": trace_id}
        except httpx.TimeoutException as exc:
            self.stats.record_timeout(f"Timeout: {str(exc)}")
            return {"success": False, "status": 504, "error": "Timeout"}
        except Exception as exc:
            self.stats.record_error(500, str(exc))
            return {"success": False, "status": 500, "error": str(exc)}

    async def run_for_duration(self, duration_sec: float):
        """Runs traffic generator for a given duration in seconds."""
        self._running = True
        interval = 1.0 / max(0.1, self.rate_per_sec)
        end_time = time.time() + duration_sec
        async with httpx.AsyncClient(timeout=10.0) as client:
            while self._running and time.time() < end_time:
                req_start = time.time()
                await self.send_single_request(client)
                took = time.time() - req_start
                sleep_t = max(0.01, interval - took)
                await asyncio.sleep(sleep_t)
        self._running = False
        return self.stats.summary()

    def start_background(self):
        """Starts traffic generation in background task."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def _run_loop(self):
        interval = 1.0 / max(0.1, self.rate_per_sec)
        async with httpx.AsyncClient(timeout=10.0) as client:
            while self._running:
                req_start = time.time()
                await self.send_single_request(client)
                took = time.time() - req_start
                sleep_t = max(0.01, interval - took)
                await asyncio.sleep(sleep_t)

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()


async def main():
    parser = argparse.ArgumentParser(description="Customer Traffic Generator")
    parser.add_argument("--url", default="http://127.0.0.1:8001/work", help="Target URL")
    parser.add_argument("--rate", type=float, default=5.0, help="Requests per second")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration in seconds")
    args = parser.parse_args()

    gen = CustomerTrafficGenerator(args.url, args.rate)
    print(f"[*] Starting traffic generator: {args.rate} req/sec to {args.url} for {args.duration}s...")
    summary = await gen.run_for_duration(args.duration)
    print(f"[+] Traffic generation complete:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
