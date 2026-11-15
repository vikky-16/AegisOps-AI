"""
AegisOps AI - Multi-Tenant Realistic Incident & Telemetry Generator
Generates business-aligned, deterministic operational failure scenarios for:
1. FinCore: Financial transactions, ledger lock contention, payment latency, fraud timeouts.
2. ShopSphere: E-commerce checkout spikes, inventory sync lag, flash sale queues, catalog latency.
3. CloudDesk: SaaS workspace auth failures, document sync memory leaks, background indexing backlog.

SECURITY & AUDIT RULES:
- Every generated scenario is explicitly tagged with is_synthetic=True and telemetry_source_mode='SYNTHETIC_SCENARIO'.
- Never presented as live production outages without explicit labelling.
- Completely idempotent: never generates duplicate incidents on restart.
- Generates at most 1 approval ticket per incident requiring approval.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.incident import Incident as IncidentModel
from backend.app.models.approval import ApprovalTicket
from backend.app.monitoring.collector import collector


TENANT_SCENARIOS = {
    "fincore": [
        {
            "incident_id": "INC-FINCORE-PAY-101",
            "title": "Payment Gateway API Latency Spike & Transaction Degradation",
            "severity": "CRITICAL",
            "status": "OPEN",
            "primary_service": "fincore-payment-gateway",
            "root_cause_service": "fincore-payment-gateway",
            "root_cause_category": "API_LATENCY_SPIKE",
            "root_cause": "TLS handshake renegotiation timeout to upstream card processor (Mastercard/Visa network) causing connection queue buildup.",
            "description": "High-security financial transactions exceeding 2,500ms P95 latency threshold. SLA breach risk.",
            "affected_services": ["fincore-payment-gateway", "fincore-checkout-api", "fincore-ledger"],
            "requires_approval": True,
            "proposed_action": "ROUTE_PAYMENT_TRAFFIC_SECONDARY",
            "risk_level": "LOW",
            "metrics": {
                "error_rate": 0.082,
                "p95_latency_ms": 2680.0,
                "p99_latency_ms": 4850.0,
                "throughput_rps": 450.0,
                "cpu_utilization": 0.68
            }
        },
        {
            "incident_id": "INC-FINCORE-DB-102",
            "title": "Database Connection Pool Saturation on Core Banking Ledger",
            "severity": "CRITICAL",
            "status": "OPEN",
            "primary_service": "fincore-ledger-db",
            "root_cause_service": "fincore-ledger-db",
            "root_cause_category": "CONNECTION_POOL_EXHAUSTION",
            "root_cause": "Unindexed transaction reconciliation batch query exhausted max pool connections (200/200).",
            "description": "Core banking ledger unable to lease idle database sockets. Transaction commits failing with timeout.",
            "affected_services": ["fincore-ledger-db", "fincore-ledger", "fincore-payment-gateway"],
            "requires_approval": True,
            "proposed_action": "RESET_CONNECTION_POOL",
            "risk_level": "LOW",
            "metrics": {
                "error_rate": 0.385,
                "p95_latency_ms": 1450.0,
                "p99_latency_ms": 2890.0,
                "throughput_rps": 120.0,
                "cpu_utilization": 0.88
            }
        }
    ],
    "shopsphere": [
        {
            "incident_id": "INC-SHOP-CHK-201",
            "title": "Checkout Service 503 HTTP Service Unavailable Surge",
            "severity": "CRITICAL",
            "status": "OPEN",
            "primary_service": "shopsphere-checkout",
            "root_cause_service": "shopsphere-checkout",
            "root_cause_category": "HTTP_503_SURGE",
            "root_cause": "Downstream inventory reservation lock contention during seasonal flash sale promotion.",
            "description": "Customers experiencing shopping cart drop-offs with HTTP 503 error rate reaching 14.5%.",
            "affected_services": ["shopsphere-checkout", "shopsphere-cart", "shopsphere-frontend"],
            "requires_approval": True,
            "proposed_action": "SCALE_UP_REPLICAS",
            "risk_level": "LOW",
            "metrics": {
                "error_rate": 0.145,
                "p95_latency_ms": 890.0,
                "p99_latency_ms": 1720.0,
                "throughput_rps": 2400.0,
                "cpu_utilization": 0.94
            }
        },
        {
            "incident_id": "INC-SHOP-QUEUE-202",
            "title": "Order Processing Queue Worker Thread Starvation",
            "severity": "HIGH",
            "status": "OPEN",
            "primary_service": "shopsphere-order-worker",
            "root_cause_service": "shopsphere-order-worker",
            "root_cause_category": "QUEUE_BACKLOG",
            "root_cause": "Async event worker queue reached 65,000 backlogged events due to slow PDF receipt generation.",
            "description": "Order notification emails and fulfillment dispatch delayed past acceptable SLA.",
            "affected_services": ["shopsphere-order-worker", "shopsphere-email-service"],
            "requires_approval": True,
            "proposed_action": "DRAIN_PENDING_QUEUE",
            "risk_level": "MEDIUM",
            "metrics": {
                "error_rate": 0.042,
                "p95_latency_ms": 1250.0,
                "p99_latency_ms": 3100.0,
                "throughput_rps": 850.0,
                "cpu_utilization": 0.79
            }
        }
    ],
    "clouddesk": [
        {
            "incident_id": "INC-CLOUD-AUTH-301",
            "title": "Tenant Token Verification Failure & Collaborative Workspace Degradation",
            "severity": "CRITICAL",
            "status": "OPEN",
            "primary_service": "clouddesk-auth",
            "root_cause_service": "clouddesk-auth",
            "root_cause_category": "AUTH_FAILURE",
            "root_cause": "JWT signing key rotation cache miss causing intermittent 401 Unauthorized across multi-tenant workspaces.",
            "description": "Collaborative document editing sessions dropping connections with authentication invalidation.",
            "affected_services": ["clouddesk-auth", "clouddesk-doc-sync", "clouddesk-web-client"],
            "requires_approval": True,
            "proposed_action": "FLUSH_REDIS_CACHE",
            "risk_level": "LOW",
            "metrics": {
                "error_rate": 0.185,
                "p95_latency_ms": 420.0,
                "p99_latency_ms": 860.0,
                "throughput_rps": 1800.0,
                "cpu_utilization": 0.55
            }
        },
        {
            "incident_id": "INC-CLOUD-SYNC-302",
            "title": "Document Sync Worker Socket Leak & Memory Pressure",
            "severity": "HIGH",
            "status": "OPEN",
            "primary_service": "clouddesk-doc-sync",
            "root_cause_service": "clouddesk-doc-sync",
            "root_cause_category": "MEMORY_LEAK",
            "root_cause": "WebSocket connection pool failing to clean up dead sessions from inactive browser tabs.",
            "description": "Worker memory steadily climbing to 91% threshold with periodic OOM kills.",
            "affected_services": ["clouddesk-doc-sync"],
            "requires_approval": True,
            "proposed_action": "RESTART_SERVICE",
            "risk_level": "MEDIUM",
            "metrics": {
                "error_rate": 0.052,
                "p95_latency_ms": 610.0,
                "p99_latency_ms": 1150.0,
                "throughput_rps": 920.0,
                "cpu_utilization": 0.82
            }
        }
    ]
}


class TenantIncidentGenerator:
    """Populates realistic operational scenarios for company tenants in an auditable, idempotent manner."""

    @classmethod
    async def seed_tenant_scenarios(cls, tenant_id: str) -> Dict[str, Any]:
        t_id = (tenant_id or "demo-tenant").lower()
        scenarios = TENANT_SCENARIOS.get(t_id, [])
        if not scenarios:
            return {"status": "NOOP", "message": f"No scenario definitions for tenant '{tenant_id}'.", "created_count": 0}

        created_incidents = []
        existing_incidents = []
        created_approvals = []
        now_dt = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            for s in scenarios:
                inc_id = s["incident_id"]

                # 1. Check if incident already exists in DB
                stmt = select(IncidentModel).where(IncidentModel.incident_id == inc_id)
                res = await session.execute(stmt)
                existing_inc = res.scalar_one_or_none()

                if not existing_inc:
                    inc_record = IncidentModel(
                        incident_id=inc_id,
                        tenant_id=t_id,
                        title=s["title"],
                        description=s["description"],
                        severity=s["severity"],
                        status=s["status"],
                        primary_service=s["primary_service"],
                        root_cause_service=s["root_cause_service"],
                        root_cause=s["root_cause"],
                        root_cause_category=s["root_cause_category"],
                        affected_services_json=json.dumps(s["affected_services"]),
                        is_synthetic=True,
                        telemetry_source_mode="SYNTHETIC_SCENARIO",
                        created_at=now_dt,
                        updated_at=now_dt
                    )
                    session.add(inc_record)
                    created_incidents.append(inc_id)

                    # Also add to collector in-memory active incidents
                    collector_inc = {
                        "incident_id": inc_id,
                        "tenant_id": t_id,
                        "title": s["title"],
                        "description": s["description"],
                        "severity": s["severity"],
                        "status": s["status"],
                        "primary_service": s["primary_service"],
                        "root_cause_service": s["root_cause_service"],
                        "root_cause": s["root_cause"],
                        "root_cause_category": s["root_cause_category"],
                        "affected_services": s["affected_services"],
                        "is_synthetic": True,
                        "telemetry_source_mode": "SYNTHETIC_SCENARIO",
                        "metrics": s.get("metrics", {}),
                        "created_at": now_dt.isoformat()
                    }
                    if not any(i.get("incident_id") == inc_id for i in collector.active_incidents):
                        collector.active_incidents.insert(0, collector_inc)
                else:
                    existing_incidents.append(inc_id)

                # 2. Check if approval ticket required and not already present
                if s.get("requires_approval"):
                    app_stmt = select(ApprovalTicket).where(
                        ApprovalTicket.incident_id == inc_id,
                        ApprovalTicket.status == "PENDING"
                    )
                    app_res = await session.execute(app_stmt)
                    existing_app = app_res.scalar_one_or_none()

                    if not existing_app:
                        app_id = f"APP-{inc_id[-8:]}-v1"
                        new_ticket = ApprovalTicket(
                            approval_id=app_id,
                            incident_id=inc_id,
                            tenant_id=t_id,
                            service_name=s["root_cause_service"],
                            proposed_action=s["proposed_action"],
                            status="PENDING",
                            risk_level=s["risk_level"],
                            reason=f"Requires human authorization to execute {s['proposed_action']} on {s['root_cause_service']}.",
                            expected_outcome=f"Resolves {s['root_cause_category']} on {s['root_cause_service']} in {t_id}.",
                            details_json=json.dumps(s.get("metrics", {})),
                            created_at=now_dt
                        )
                        session.add(new_ticket)
                        created_approvals.append(app_id)

            await session.commit()

        return {
            "status": "SUCCESS",
            "tenant_id": t_id,
            "created_incidents": created_incidents,
            "existing_incidents": existing_incidents,
            "created_approvals": created_approvals,
            "message": f"Generated {len(created_incidents)} incidents and {len(created_approvals)} approvals for {t_id} ({len(existing_incidents)} already existed)."
        }
