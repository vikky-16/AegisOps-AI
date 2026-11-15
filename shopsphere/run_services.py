"""
ShopSphere Unified Microservices Runner
Launches all 5 ShopSphere microservices concurrently on ports 8100-8104:
- API Gateway:          http://127.0.0.1:8100
- Order Service:        http://127.0.0.1:8101
- Inventory Service:    http://127.0.0.1:8102
- Payment Service:      http://127.0.0.1:8103
- Notification Service: http://127.0.0.1:8104
"""

import sys
import os
import asyncio
import uvicorn

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SERVICES = [
    ("api-gateway", "shopsphere.services.gateway.app:app", 8100),
    ("order-service", "shopsphere.services.order_service.app:app", 8101),
    ("inventory-service", "shopsphere.services.inventory_service.app:app", 8102),
    ("payment-service", "shopsphere.services.payment_service.app:app", 8103),
    ("notification-service", "shopsphere.services.notification_service.app:app", 8104),
]


async def run_all():
    print("=" * 75)
    print("   SHOPSPHERE E-COMMERCE MICROSERVICES MESH (PORTS 8100-8104)")
    print("=" * 75)
    servers = []
    for name, target, port in SERVICES:
        print(f"  [+] Starting {name:<22} on http://127.0.0.1:{port}")
        cfg = uvicorn.Config(target, host="0.0.0.0", port=port, log_level="warning", access_log=False)
        servers.append(uvicorn.Server(cfg).serve())
    print("=" * 75, flush=True)
    await asyncio.gather(*servers)


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print("\n[SHOPSPHERE] Shutting down all services.")
