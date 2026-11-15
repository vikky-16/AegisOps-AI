"""
AegisOps AI - Unified Multi-Company Real Traffic Generator
Drives actual HTTP traffic across all 3 company meshes concurrently:
1. ShopSphere (Gateway: http://127.0.0.1:8100)
2. FinCore (Gateway: http://127.0.0.1:8200)
3. CloudDesk (Gateway: http://127.0.0.1:8300)

Configurable rate (default 2-3 req/s per company) for smooth live telemetry
without CPU, SQLite WAL, or network buffer flooding.
"""

import sys
import os
import time
import asyncio
import httpx
from typing import List

# Ensure workspace root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

RATE_PER_COMPANY = float(os.getenv("TRAFFIC_REQUESTS_PER_SECOND", "2.5"))


async def drive_shopsphere(client: httpx.AsyncClient):
    import random
    from shopsphere.traffic.generator import send_operation, metrics
    print("[Traffic] ShopSphere traffic generator initialized (2.5 req/s)...", flush=True)
    interval = 1.0 / RATE_PER_COMPANY
    while True:
        try:
            await send_operation(client)
        except Exception:
            pass
        await asyncio.sleep(interval)


async def drive_fincore(client: httpx.AsyncClient):
    from fincore.traffic.generator import send_operation, metrics
    print("[Traffic] FinCore traffic generator initialized (2.5 req/s)...", flush=True)
    interval = 1.0 / RATE_PER_COMPANY
    while True:
        try:
            await send_operation(client)
        except Exception:
            pass
        await asyncio.sleep(interval)


async def drive_clouddesk(client: httpx.AsyncClient):
    from clouddesk.traffic.generator import send_operation, metrics
    print("[Traffic] CloudDesk traffic generator initialized (2.5 req/s)...", flush=True)
    interval = 1.0 / RATE_PER_COMPANY
    while True:
        try:
            await send_operation(client)
        except Exception:
            pass
        await asyncio.sleep(interval)


async def main():
    print("=" * 75)
    print("   AEGISOPS AI - MULTI-COMPANY CONTINUOUS REAL TRAFFIC GENERATOR")
    print(f"   Rate: {RATE_PER_COMPANY} requests/sec per company (~{RATE_PER_COMPANY * 3:.1f} RPS total)")
    print("   Targets: ShopSphere (8100), FinCore (8200), CloudDesk (8300)")
    print("=" * 75, flush=True)

    # Wait for gateways to be reachable
    gateways = [
        ("ShopSphere", "http://127.0.0.1:8100/health"),
        ("FinCore", "http://127.0.0.1:8200/health"),
        ("CloudDesk", "http://127.0.0.1:8300/health"),
    ]

    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
        for name, url in gateways:
            for _ in range(20):
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        print(f"  [+] {name:<12} Gateway is ONLINE", flush=True)
                        break
                except Exception:
                    await asyncio.sleep(0.5)
            else:
                print(f"  [-] {name:<12} Gateway not responding, will still attempt traffic...", flush=True)

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(limits=limits, timeout=6.0, trust_env=False) as client:
        tasks = [
            asyncio.create_task(drive_shopsphere(client)),
            asyncio.create_task(drive_fincore(client)),
            asyncio.create_task(drive_clouddesk(client)),
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Traffic] Traffic generation stopped.")
