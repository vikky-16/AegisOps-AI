"""
AegisOps AI - Production Telemetry Load Generator CLI
Generates fresh, real-time telemetry streams and delivers them through the public HTTP/OTLP
Ingestion Gateway (/api/v1/telemetry/batch) to measure real end-to-end platform throughput.
STRICTLY LABELED AS 'LOAD TEST' — NEVER USED AS REAL CUSTOMER TELEMETRY.
"""

import sys
import os
import time
import uuid
import random
import asyncio
import argparse
import statistics
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
import psutil

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DEFAULT_SERVICES = ["gateway-proxy", "order-api", "payment-service", "inventory-db", "auth-service", "cache-redis"]


def generate_event(
    tenant_id: str,
    services: List[str],
    include_logs: bool = True,
    include_metrics: bool = True,
    include_traces: bool = True
) -> Dict[str, Any]:
    """Generates a fresh, realistic telemetry payload with trace correlation."""
    svc = random.choice(services)
    now_iso = datetime.now(timezone.utc).isoformat()
    trace_id = f"trc-{uuid.uuid4().hex}"
    span_id = f"spn-{uuid.uuid4().hex[:16]}"

    # Determine event type
    available_types = []
    if include_logs:
        available_types.append("log")
    if include_metrics:
        available_types.append("metric")
    if include_traces:
        available_types.append("trace")
    if not available_types:
        available_types = ["log"]

    ev_type = random.choice(available_types)

    if ev_type == "metric":
        metric_name = random.choice(["http_requests_total", "latency_ms", "cpu_utilization", "active_connections"])
        val = random.uniform(10.0, 150.0) if metric_name != "cpu_utilization" else random.uniform(20.0, 85.0)
        return {
            "tenant_id": tenant_id,
            "source_mode": "LOAD_TEST",
            "event_type": "metric",
            "service_name": svc,
            "metric_name": metric_name,
            "metric_value": round(val, 2),
            "timestamp": now_iso,
            "trace_id": trace_id,
            "span_id": span_id,
            "severity": "INFO",
            "environment": "load-test-cluster",
            "attributes": {"load_generator": "telemetry_load_test.py", "service.name": svc}
        }
    elif ev_type == "trace":
        latency = round(random.uniform(5.0, 120.0), 2)
        status = 200 if random.random() > 0.05 else 500
        return {
            "tenant_id": tenant_id,
            "source_mode": "LOAD_TEST",
            "event_type": "trace",
            "service_name": svc,
            "trace_id": trace_id,
            "span_id": span_id,
            "latency": latency,
            "http_status": status,
            "http_method": "POST",
            "http_route": f"/api/v1/{svc}/process",
            "timestamp": now_iso,
            "severity": "INFO" if status == 200 else "ERROR",
            "environment": "load-test-cluster",
            "attributes": {"load_generator": "telemetry_load_test.py"}
        }
    else:
        # Log event
        sev = "INFO" if random.random() > 0.08 else "ERROR"
        return {
            "tenant_id": tenant_id,
            "source_mode": "LOAD_TEST",
            "event_type": "log",
            "service_name": svc,
            "severity": sev,
            "message": f"Processed inbound transaction request for account #{random.randint(10000, 99999)} on {svc}",
            "trace_id": trace_id,
            "span_id": span_id,
            "timestamp": now_iso,
            "environment": "load-test-cluster",
            "attributes": {"load_generator": "telemetry_load_test.py"}
        }


async def run_load_test(
    target_eps: int,
    duration_sec: int,
    tenant_id: str,
    services: List[str],
    endpoint: str,
    api_key: str,
    include_logs: bool,
    include_metrics: bool,
    include_traces: bool
):
    print("=================================================================", flush=True)
    print("       AEGISOPS AI — TELEMETRY LOAD & THROUGHPUT BENCHMARK       ", flush=True)
    print("=================================================================", flush=True)
    print(f" Target Throughput : {target_eps:,} Events/Sec", flush=True)
    print(f" Test Duration     : {duration_sec} seconds", flush=True)
    print(f" Target Tenant     : {tenant_id} (MODE: LOAD_TEST)", flush=True)
    print(f" Active Services   : {len(services)} services", flush=True)
    print(f" Public Ingest URL : {endpoint}", flush=True)
    print("=================================================================\n", flush=True)

    batch_size = max(10, min(250, target_eps // 10)) if target_eps > 50 else 1
    batches_per_sec = max(1, target_eps // batch_size)
    total_expected_events = target_eps * duration_sec

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Tenant-ID": tenant_id,
        "User-Agent": "AegisOps-LoadGenerator/2.0"
    }

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = httpx.Timeout(10.0, connect=5.0)

    latencies: List[float] = []
    successful_events = 0
    failed_events = 0
    total_bytes = 0

    process = psutil.Process(os.getpid())
    start_time = time.perf_counter()
    last_report = start_time

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        end_time = start_time + duration_sec
        
        while time.perf_counter() < end_time:
            sec_start = time.perf_counter()

            tasks = []
            for _ in range(batches_per_sec):
                batch = [
                    generate_event(tenant_id, services, include_logs, include_metrics, include_traces)
                    for _ in range(batch_size)
                ]
                payload_json = json.dumps(batch)
                total_bytes += len(payload_json.encode("utf-8"))

                async def send_batch(p_data=payload_json, b_size=batch_size):
                    nonlocal successful_events, failed_events
                    t0 = time.perf_counter()
                    try:
                        res = await client.post(endpoint, content=p_data, headers=headers)
                        latency_ms = (time.perf_counter() - t0) * 1000.0
                        latencies.append(latency_ms)
                        if res.status_code in [200, 202]:
                            successful_events += b_size
                        else:
                            failed_events += b_size
                    except Exception:
                        failed_events += b_size

                tasks.append(send_batch())

            await asyncio.gather(*tasks, return_exceptions=True)

            # Live cadence reporter every 2.0s
            now = time.perf_counter()
            if now - last_report >= 2.0:
                cur_duration = now - start_time
                cur_eps = successful_events / max(0.01, cur_duration)
                cur_mb_s = (total_bytes / (1024 * 1024)) / max(0.01, cur_duration)
                mem_mb = process.memory_info().rss / (1024 * 1024)
                print(f" [{int(cur_duration):02d}s/{duration_sec}s] Measured: {cur_eps:,.1f} EPS | {cur_mb_s:.2f} MB/s | Client RAM: {mem_mb:.1f} MB", flush=True)
                last_report = now

            elapsed_in_sec = time.perf_counter() - sec_start
            sleep_time = max(0.0, 1.0 - elapsed_in_sec)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    total_duration = time.perf_counter() - start_time
    actual_eps = successful_events / max(0.001, total_duration)
    actual_mb_s = (total_bytes / (1024 * 1024)) / max(0.001, total_duration)

    # Statistical percentiles
    def calc_percentiles(arr: List[float]) -> Dict[str, float]:
        if not arr:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
        sorted_arr = sorted(arr)
        n = len(sorted_arr)
        return {
            "p50": round(statistics.median(sorted_arr), 2),
            "p95": round(sorted_arr[int(n * 0.95)], 2),
            "p99": round(sorted_arr[int(n * 0.99)], 2),
            "max": round(max(sorted_arr), 2)
        }

    p = calc_percentiles(latencies)

    print("\n=================================================================", flush=True)
    print("                      LOAD TEST FINAL REPORT                     ", flush=True)
    print("=================================================================", flush=True)
    print(f" Target EPS Rate       : {target_eps:,} EPS", flush=True)
    print(f" Actual Measured EPS   : {actual_eps:,.1f} EPS", flush=True)
    print(f" Ingestion Bandwidth   : {actual_mb_s:.2f} MB/s", flush=True)
    print(f" Total Events Sent     : {successful_events + failed_events:,}", flush=True)
    print(f" Accepted Events (200) : {successful_events:,} ({(successful_events / max(1, successful_events + failed_events))*100:.1f}%)", flush=True)
    print(f" Rejected / Dropped    : {failed_events:,}", flush=True)
    print(f" Total Duration        : {total_duration:.2f} seconds", flush=True)
    print(f" Ingestion Latency p50 : {p['p50']} ms", flush=True)
    print(f" Ingestion Latency p95 : {p['p95']} ms", flush=True)
    print(f" Ingestion Latency p99 : {p['p99']} ms", flush=True)
    print(f" Max Batch Latency     : {p['max']} ms", flush=True)
    print("=================================================================\n", flush=True)


def main():
    import json
    parser = argparse.ArgumentParser(description="AegisOps AI High-Volume Telemetry Load Generator")
    parser.add_argument("--eps", type=int, default=500, help="Target Events Per Second (default: 500)")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds (default: 10)")
    parser.add_argument("--tenant", type=str, default="demo-tenant", help="Target tenant_id (default: demo-tenant)")
    parser.add_argument("--endpoint", type=str, default="http://127.0.0.1:8000/api/v1/telemetry/batch", help="API batch ingestion URL")
    parser.add_argument("--api-key", type=str, default="agt_live_demo_11112222333344445555", help="Tenant Ingestion API Key")
    parser.add_argument("--services", type=str, nargs="+", default=DEFAULT_SERVICES, help="List of services to simulate")
    parser.add_argument("--no-logs", action="store_true", help="Exclude log events")
    parser.add_argument("--no-metrics", action="store_true", help="Exclude metric events")
    parser.add_argument("--no-traces", action="store_true", help="Exclude trace events")

    args = parser.parse_args()

    asyncio.run(
        run_load_test(
            target_eps=args.eps,
            duration_sec=args.duration,
            tenant_id=args.tenant,
            services=args.services,
            endpoint=args.endpoint,
            api_key=args.api_key,
            include_logs=not args.no_logs,
            include_metrics=not args.no_metrics,
            include_traces=not args.no_traces
        )
    )


if __name__ == "__main__":
    main()
