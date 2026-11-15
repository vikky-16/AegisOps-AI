"""
FinCore Unified Microservices Runner
Launches all 6 FinCore financial services concurrently on ports 8200-8205:
- API Gateway:              http://127.0.0.1:8200
- Account Service:          http://127.0.0.1:8201
- Transaction Service:      http://127.0.0.1:8202
- Payment Service:          http://127.0.0.1:8203
- Fraud Detection Service:  http://127.0.0.1:8204
- Notification Service:     http://127.0.0.1:8205
"""

import sys
import os
import asyncio
import uvicorn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SERVICES = [
    ("api-gateway", "fincore.services.gateway.app:app", 8200),
    ("account-service", "fincore.services.account_service.app:app", 8201),
    ("transaction-service", "fincore.services.transaction_service.app:app", 8202),
    ("payment-service", "fincore.services.payment_service.app:app", 8203),
    ("fraud-detection-service", "fincore.services.fraud_service.app:app", 8204),
    ("notification-service", "fincore.services.notification_service.app:app", 8205),
]


async def run_all():
    print("=" * 75)
    print("   FINCORE FINANCIAL MICROSERVICES MESH (PORTS 8200-8205)")
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
        print("\n[FINCORE] Shutting down all services.")
