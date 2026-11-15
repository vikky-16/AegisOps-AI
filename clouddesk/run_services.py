"""
CloudDesk Unified Microservices Runner
Launches all 6 CloudDesk cloud/SaaS services concurrently on ports 8300-8305:
- API Gateway:          http://127.0.0.1:8300
- User Service:          http://127.0.0.1:8301
- Project Service:       http://127.0.0.1:8302
- Compute Service:       http://127.0.0.1:8303
- Billing Service:       http://127.0.0.1:8304
- Notification Service:  http://127.0.0.1:8305
"""

import sys
import os
import asyncio
import uvicorn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SERVICES = [
    ("api-gateway", "clouddesk.services.gateway.app:app", 8300),
    ("user-service", "clouddesk.services.user_service.app:app", 8301),
    ("project-service", "clouddesk.services.project_service.app:app", 8302),
    ("compute-service", "clouddesk.services.compute_service.app:app", 8303),
    ("billing-service", "clouddesk.services.billing_service.app:app", 8304),
    ("notification-service", "clouddesk.services.notification_service.app:app", 8305),
]


async def run_all():
    print("=" * 75)
    print("   CLOUDDESK SAAS / CLOUD MICROSERVICES MESH (PORTS 8300-8305)")
    print("=" * 75)
    servers = []
    for name, target, port in SERVICES:
        print(f"  [+] Starting {name:<26} on http://127.0.0.1:{port}")
        cfg = uvicorn.Config(target, host="0.0.0.0", port=port, log_level="warning", access_log=False)
        servers.append(uvicorn.Server(cfg).serve())
    print("=" * 75, flush=True)
    await asyncio.gather(*servers)


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print("\n[CLOUDDESK] Shutting down all services.")
