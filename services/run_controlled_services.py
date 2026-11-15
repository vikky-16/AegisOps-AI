"""
Controlled Company Microservices Mesh (Ports 8001-8005)
Launches:
- Gateway (8001)
- Service A (8002)
- Service B (8003)
- Database Service (8004)
- Auth Service (8005)
"""

import sys
import os
import asyncio
import uvicorn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SERVICES = [
    ("database-service", "services.database_service.app:app", 8004),
    ("service-b", "services.service_b.app:app", 8003),
    ("service-a", "services.service_a.app:app", 8002),
    ("gateway", "services.gateway.app:app", 8001),
    ("auth-service", "services.auth_service.app:app", 8005),
]


async def run_all():
    print("=" * 75)
    print("   CONTROLLED COMPANY MICROSERVICES MESH (PORTS 8001-8005)")
    print("=" * 75)
    servers = []
    for name, target, port in SERVICES:
        print(f"  [+] Starting {name:<20} on http://127.0.0.1:{port}")
        cfg = uvicorn.Config(target, host="0.0.0.0", port=port, log_level="warning", access_log=False)
        servers.append(uvicorn.Server(cfg).serve())
    print("=" * 75, flush=True)
    await asyncio.gather(*servers)


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print("\n[CONTROLLED SERVICES] Shutting down.")
