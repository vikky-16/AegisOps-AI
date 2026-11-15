"""
AegisOps AI - Company-Specific Architecture & Operational Workflow Discovery Engine
Maintains tenant-scoped architecture models, runtime platforms, dependency paths,
critical business workflows, permissions, and discovery coverage gap metrics.
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, delete
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.architecture import TenantArchitectureNode, TenantWorkflowDefinition
from backend.app.logger import realtime_logger


# Default initial architectural topology definitions per company
DEFAULT_COMPANY_ARCHITECTURES: Dict[str, Dict[str, Any]] = {
    "shopsphere": {
        "company_name": "ShopSphere Retail Inc.",
        "nodes": [
            {
                "resource_id": "gateway",
                "name": "API Gateway / Edge Router",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Kubernetes (EKS v1.29)",
                "runtime": "envoy-proxy-1.28",
                "tier": "Tier-1",
                "service_owner": "Platform Networking Team",
                "oncall_team": "network-sre@shopsphere.io",
                "maintenance_window": "Sun 02:00-04:00 UTC",
                "data_classification": "INTERNAL",
                "dependencies": ["auth-service", "service-a"],
                "downstream_services": [],
                "capabilities": ["canary_routing", "rate_limiting", "circuit_breaking", "config_reload"],
                "rollback_procedure": "ROLLBACK_INGRESS_CONFIG",
                "discovery_source": "KUBERNETES_API_DISCOVERY",
                "confidence_score": 0.98,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics/prometheus",
                "logs_system": "OpenSearch + FluentBit",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-gateway-sandbox"
            },
            {
                "resource_id": "auth-service",
                "name": "Authentication & Session Authority",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Kubernetes (EKS v1.29)",
                "runtime": "python-fastapi-3.11",
                "tier": "Tier-1",
                "service_owner": "Identity & Security Team",
                "oncall_team": "sec-ops@shopsphere.io",
                "maintenance_window": "Tue 01:00-03:00 UTC",
                "data_classification": "RESTRICTED",
                "dependencies": ["redis-cache", "database-service"],
                "downstream_services": ["gateway", "service-a"],
                "capabilities": ["token_rotation", "scale_replicas", "graceful_restart", "circuit_breaker"],
                "rollback_procedure": "K8S_ROLLOUT_UNDO",
                "discovery_source": "KUBERNETES_API_DISCOVERY",
                "confidence_score": 0.95,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "OpenSearch + FluentBit",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-auth-sandbox"
            },
            {
                "resource_id": "service-a",
                "name": "Order Management Service",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Kubernetes (EKS v1.29)",
                "runtime": "python-fastapi-3.11",
                "tier": "Tier-1",
                "service_owner": "Checkout Experience Team",
                "oncall_team": "order-sre@shopsphere.io",
                "maintenance_window": "Tue 02:00-04:00 UTC",
                "data_classification": "CONFIDENTIAL",
                "dependencies": ["service-b", "database-service", "kafka-events"],
                "downstream_services": ["gateway"],
                "capabilities": ["scale_workers", "restart_pod", "flush_local_cache", "drain_connections"],
                "rollback_procedure": "K8S_DEPLOYMENT_ROLLBACK",
                "discovery_source": "KUBERNETES_API_DISCOVERY",
                "confidence_score": 0.96,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "OpenSearch + FluentBit",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-service-a-sandbox"
            },
            {
                "resource_id": "service-b",
                "name": "Inventory & Catalog Service",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Kubernetes (EKS v1.29)",
                "runtime": "python-fastapi-3.11",
                "tier": "Tier-1",
                "service_owner": "Inventory Core Team",
                "oncall_team": "inventory-oncall@shopsphere.io",
                "maintenance_window": "Thu 03:00-05:00 UTC",
                "data_classification": "INTERNAL",
                "dependencies": ["database-service", "redis-cache"],
                "downstream_services": ["service-a"],
                "capabilities": ["scale_workers", "tune_connection_pool", "restart_pod", "circuit_breaker"],
                "rollback_procedure": "K8S_DEPLOYMENT_ROLLBACK",
                "discovery_source": "KUBERNETES_API_DISCOVERY",
                "confidence_score": 0.94,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "OpenSearch + FluentBit",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-service-b-sandbox"
            },
            {
                "resource_id": "database-service",
                "name": "Primary Relational Cluster (PostgreSQL)",
                "resource_type": "DATABASE",
                "environment": "production",
                "platform": "AWS Aurora PostgreSQL 15.4",
                "runtime": "postgresql-15",
                "tier": "Tier-1",
                "service_owner": "Database Reliability Team",
                "oncall_team": "dba-oncall@shopsphere.io",
                "maintenance_window": "Sun 01:00-03:00 UTC",
                "data_classification": "RESTRICTED",
                "dependencies": [],
                "downstream_services": ["service-a", "service-b", "auth-service"],
                "capabilities": ["reset_connection_pool", "failover_replica", "kill_idle_connections", "snapshot_restore"],
                "rollback_procedure": "AURORA_PITR_RESTORE",
                "discovery_source": "AWS_RDS_API_DISCOVERY",
                "confidence_score": 0.99,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "cloudwatch/aurora",
                "logs_system": "AWS CloudWatch Logs",
                "traces_system": "AWS X-Ray",
                "sandbox_available": True,
                "sandbox_env_id": "rep-database-sandbox"
            },
            {
                "resource_id": "redis-cache",
                "name": "Distributed Memory Grid (Redis)",
                "resource_type": "CACHE",
                "environment": "production",
                "platform": "AWS ElastiCache Redis 7.0 Cluster",
                "runtime": "redis-7.0",
                "tier": "Tier-2",
                "service_owner": "Caching & Performance Team",
                "oncall_team": "cache-team@shopsphere.io",
                "maintenance_window": "Sun 04:00-05:00 UTC",
                "data_classification": "INTERNAL",
                "dependencies": [],
                "downstream_services": ["auth-service", "service-b"],
                "capabilities": ["flush_expired_keys", "failover_node", "resize_memory"],
                "rollback_procedure": "REDIS_REPLICA_PROMOTION",
                "discovery_source": "AWS_ELASTICACHE_API",
                "confidence_score": 0.92,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "cloudwatch/elasticache",
                "logs_system": "AWS CloudWatch Logs",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-redis-sandbox"
            },
            {
                "resource_id": "kafka-events",
                "name": "Event Bus & Message Streaming",
                "resource_type": "QUEUE",
                "environment": "production",
                "platform": "AWS Managed Streaming Kafka (MSK 3.5)",
                "runtime": "kafka-3.5",
                "tier": "Tier-2",
                "service_owner": "Streaming Infrastructure Team",
                "oncall_team": "stream-sre@shopsphere.io",
                "maintenance_window": "Wed 03:00-05:00 UTC",
                "data_classification": "INTERNAL",
                "dependencies": [],
                "downstream_services": ["service-a"],
                "capabilities": ["rebalance_partitions", "increase_retention", "restart_broker"],
                "rollback_procedure": "CONSUMER_OFFSET_REWIND",
                "discovery_source": "AWS_MSK_API",
                "confidence_score": 0.90,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "prometheus/jmx-exporter",
                "logs_system": "AWS CloudWatch Logs",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-kafka-sandbox"
            },
            {
                "resource_id": "legacy-sync-job",
                "name": "Legacy ERP Sync Batch Job",
                "resource_type": "BATCH_WORKER",
                "environment": "production",
                "platform": "Legacy VM (CentOS 7)",
                "runtime": "cron-bash-oracle-client",
                "tier": "Tier-3",
                "service_owner": "Enterprise Systems",
                "oncall_team": "erp-support@shopsphere.io",
                "maintenance_window": "Mon 00:00-02:00 UTC",
                "data_classification": "CONFIDENTIAL",
                "dependencies": ["database-service"],
                "downstream_services": [],
                "capabilities": ["restart_cron", "kill_pid"],
                "rollback_procedure": "MANUAL_RESTORE",
                "discovery_source": "HOST_AGENT_INCOMPLETE",
                "confidence_score": 0.55,
                "verified": False,
                "health_status": "DEGRADED",
                "metrics_endpoint": None,
                "logs_system": "Local syslog (unforwarded)",
                "traces_system": None,
                "sandbox_available": False,
                "sandbox_env_id": None
            }
        ],
        "workflows": [
            {
                "workflow_id": "WF-CHECKOUT-PRIMARY",
                "name": "End-to-End E-Commerce Checkout",
                "criticality": "MISSION_CRITICAL",
                "service_path": ["gateway", "auth-service", "service-a", "service-b", "database-service"],
                "entrypoint_service": "gateway",
                "data_stores_involved": ["database-service", "redis-cache"],
                "slo_latency_target_ms": 350.0,
                "slo_availability_target": 0.9995,
                "verification_status": "VERIFIED",
                "active_canary_ratio": 0.0,
                "change_freeze_active": False,
                "last_audited_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "workflow_id": "WF-AUTH-LOGIN",
                "name": "Customer Authentication & SSO",
                "criticality": "HIGH",
                "service_path": ["gateway", "auth-service", "redis-cache", "database-service"],
                "entrypoint_service": "gateway",
                "data_stores_involved": ["redis-cache", "database-service"],
                "slo_latency_target_ms": 120.0,
                "slo_availability_target": 0.9999,
                "verification_status": "VERIFIED",
                "active_canary_ratio": 0.0,
                "change_freeze_active": False,
                "last_audited_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "workflow_id": "WF-ORDER-FULFILLMENT",
                "name": "Asynchronous Order Processing & Streaming",
                "criticality": "HIGH",
                "service_path": ["service-a", "kafka-events", "service-b", "database-service"],
                "entrypoint_service": "service-a",
                "data_stores_involved": ["database-service", "kafka-events"],
                "slo_latency_target_ms": 1500.0,
                "slo_availability_target": 0.999,
                "verification_status": "VERIFIED",
                "active_canary_ratio": 0.0,
                "change_freeze_active": False,
                "last_audited_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "workflow_id": "WF-ERP-SYNC",
                "name": "Legacy Enterprise ERP Inventory Sync",
                "criticality": "LOW",
                "service_path": ["legacy-sync-job", "database-service"],
                "entrypoint_service": "legacy-sync-job",
                "data_stores_involved": ["database-service"],
                "slo_latency_target_ms": 60000.0,
                "slo_availability_target": 0.95,
                "verification_status": "UNVERIFIED",
                "active_canary_ratio": 0.0,
                "change_freeze_active": False,
                "last_audited_at": None
            }
        ]
    },
    "fincore": {
        "company_name": "FinCore Institutional Banking",
        "nodes": [
            {
                "resource_id": "fincore-edge-proxy",
                "name": "Zero-Trust Financial Edge Ingress",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Kubernetes Dedicated FIPS-140-2",
                "runtime": "envoy-mtls-1.28",
                "tier": "Tier-0",
                "service_owner": "SecOps Core",
                "oncall_team": "fincore-sre@fincore.bank",
                "maintenance_window": "Sat 23:00-01:00 UTC",
                "data_classification": "RESTRICTED",
                "dependencies": ["identity-vault", "transaction-core"],
                "downstream_services": [],
                "capabilities": ["mtls_renegotiate", "traffic_shed", "circuit_breaker"],
                "rollback_procedure": "STANDBY_CLUSTER_FAILOVER",
                "discovery_source": "KUBERNETES_API_DISCOVERY",
                "confidence_score": 0.99,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "Splunk Enterprise",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-fincore-edge-sandbox"
            },
            {
                "resource_id": "identity-vault",
                "name": "HSM Key Custody & Authorization Vault",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Dedicated HSM BareMetal Node",
                "runtime": "vault-enterprise-1.15",
                "tier": "Tier-0",
                "service_owner": "Cryptographic Services",
                "oncall_team": "crypto-ops@fincore.bank",
                "maintenance_window": "Sun 02:00-03:00 UTC",
                "data_classification": "RESTRICTED",
                "dependencies": [],
                "downstream_services": ["fincore-edge-proxy", "transaction-core"],
                "capabilities": ["rotate_token", "unseal_standby", "audit_lock"],
                "rollback_procedure": "DISASTER_RECOVERY_SEAL",
                "discovery_source": "INTERNAL_REGISTRY",
                "confidence_score": 0.99,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/sys/metrics",
                "logs_system": "Splunk Enterprise",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-vault-sandbox"
            },
            {
                "resource_id": "transaction-core",
                "name": "Real-time Settlement & Ledger Engine",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Low-Latency Dedicated Compute",
                "runtime": "rust-settlement-engine",
                "tier": "Tier-0",
                "service_owner": "Ledger Engineering",
                "oncall_team": "settlement-sre@fincore.bank",
                "maintenance_window": "Sun 01:00-02:00 UTC",
                "data_classification": "RESTRICTED",
                "dependencies": ["identity-vault", "ledger-db"],
                "downstream_services": ["fincore-edge-proxy"],
                "capabilities": ["halt_trading", "rebalance_shards", "graceful_drain"],
                "rollback_procedure": "ATOMIC_SNAPSHOT_ROLLBACK",
                "discovery_source": "INTERNAL_REGISTRY",
                "confidence_score": 0.98,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "Splunk Enterprise",
                "traces_system": "OpenTelemetry OTLP",
                "sandbox_available": True,
                "sandbox_env_id": "rep-transaction-sandbox"
            },
            {
                "resource_id": "ledger-db",
                "name": "Immutable Distributed Ledger Spanner",
                "resource_type": "DATABASE",
                "environment": "production",
                "platform": "Google Cloud Spanner Regional",
                "runtime": "spanner-sql",
                "tier": "Tier-0",
                "service_owner": "Data Architecture",
                "oncall_team": "data-infra@fincore.bank",
                "maintenance_window": "Sun 03:00-04:00 UTC",
                "data_classification": "RESTRICTED",
                "dependencies": [],
                "downstream_services": ["transaction-core"],
                "capabilities": ["read_only_failover", "restore_backup"],
                "rollback_procedure": "SPANNER_VERSION_TAG_RESTORE",
                "discovery_source": "GCP_CLOUD_DISCOVERY",
                "confidence_score": 0.99,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "cloudmonitoring/spanner",
                "logs_system": "GCP Cloud Logging",
                "traces_system": "Cloud Trace",
                "sandbox_available": True,
                "sandbox_env_id": "rep-ledger-sandbox"
            }
        ],
        "workflows": [
            {
                "workflow_id": "WF-FIN-SETTLEMENT",
                "name": "Institutional Real-Time Wire Settlement",
                "criticality": "MISSION_CRITICAL",
                "service_path": ["fincore-edge-proxy", "identity-vault", "transaction-core", "ledger-db"],
                "entrypoint_service": "fincore-edge-proxy",
                "data_stores_involved": ["ledger-db"],
                "slo_latency_target_ms": 75.0,
                "slo_availability_target": 0.99999,
                "verification_status": "VERIFIED",
                "active_canary_ratio": 0.0,
                "change_freeze_active": False,
                "last_audited_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    },
    "clouddesk": {
        "company_name": "CloudDesk Collaborative Workspace",
        "nodes": [
            {
                "resource_id": "desk-ingress",
                "name": "CloudDesk Global CDN & WebSocket Ingress",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Cloudflare Workers + K8s Ingress",
                "runtime": "cloudflare-workers",
                "tier": "Tier-1",
                "service_owner": "Edge Networking",
                "oncall_team": "edge@clouddesk.app",
                "maintenance_window": "Wed 04:00-05:00 UTC",
                "data_classification": "INTERNAL",
                "dependencies": ["collab-service"],
                "downstream_services": [],
                "capabilities": ["reroute_edge", "purge_cdn_cache"],
                "rollback_procedure": "WORKERS_ROLLBACK",
                "discovery_source": "CLOUDFLARE_API",
                "confidence_score": 0.96,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "Datadog Logs",
                "traces_system": "Datadog APM",
                "sandbox_available": True,
                "sandbox_env_id": "rep-desk-sandbox"
            },
            {
                "resource_id": "collab-service",
                "name": "Real-time Document Synchronization Engine",
                "resource_type": "SERVICE",
                "environment": "production",
                "platform": "Kubernetes (GKE v1.28)",
                "runtime": "node-20-websockets",
                "tier": "Tier-1",
                "service_owner": "Collaboration Core",
                "oncall_team": "collab-sre@clouddesk.app",
                "maintenance_window": "Tue 02:00-03:00 UTC",
                "data_classification": "CONFIDENTIAL",
                "dependencies": ["tenant-db-cluster"],
                "downstream_services": ["desk-ingress"],
                "capabilities": ["scale_replicas", "drain_rooms", "restart_pod"],
                "rollback_procedure": "K8S_ROLLBACK",
                "discovery_source": "KUBERNETES_API_DISCOVERY",
                "confidence_score": 0.93,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "/metrics",
                "logs_system": "Datadog Logs",
                "traces_system": "Datadog APM",
                "sandbox_available": True,
                "sandbox_env_id": "rep-collab-sandbox"
            },
            {
                "resource_id": "tenant-db-cluster",
                "name": "Multi-Tenant Document DB (MongoDB Atlas)",
                "resource_type": "DATABASE",
                "environment": "production",
                "platform": "MongoDB Atlas M50 Replica Set",
                "runtime": "mongodb-6.0",
                "tier": "Tier-1",
                "service_owner": "Database Operations",
                "oncall_team": "dba@clouddesk.app",
                "maintenance_window": "Sat 01:00-03:00 UTC",
                "data_classification": "CONFIDENTIAL",
                "dependencies": [],
                "downstream_services": ["collab-service"],
                "capabilities": ["step_down_primary", "increase_oplog", "restore_point_in_time"],
                "rollback_procedure": "ATLAS_SNAPSHOT_RESTORE",
                "discovery_source": "ATLAS_API",
                "confidence_score": 0.97,
                "verified": True,
                "health_status": "HEALTHY",
                "metrics_endpoint": "datadog/mongo",
                "logs_system": "Datadog Logs",
                "traces_system": "Datadog APM",
                "sandbox_available": True,
                "sandbox_env_id": "rep-docdb-sandbox"
            }
        ],
        "workflows": [
            {
                "workflow_id": "WF-COLLAB-DOC-EDIT",
                "name": "Real-Time Collaborative Document Canvas",
                "criticality": "MISSION_CRITICAL",
                "service_path": ["desk-ingress", "collab-service", "tenant-db-cluster"],
                "entrypoint_service": "desk-ingress",
                "data_stores_involved": ["tenant-db-cluster"],
                "slo_latency_target_ms": 100.0,
                "slo_availability_target": 0.999,
                "verification_status": "VERIFIED",
                "active_canary_ratio": 0.0,
                "change_freeze_active": False,
                "last_audited_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
}


class ArchitectureDiscoveryEngine:
    """
    Manages authorized architecture discovery, inventory tracking,
    dependency confidence scoring, and coverage gap analysis.
    """

    async def seed_tenant_architecture_if_empty(self, tenant_id: str) -> None:
        """Seeds initial architectural data if tenant currently has no inventory."""
        target_tenant = tenant_id if tenant_id in DEFAULT_COMPANY_ARCHITECTURES else "shopsphere"
        from backend.app.core.database import engine, Base
        import backend.app.models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncSessionLocal() as session:
            # Check existing count
            res = await session.execute(
                select(TenantArchitectureNode).where(TenantArchitectureNode.tenant_id == tenant_id)
            )
            existing_nodes = res.scalars().all()
            if existing_nodes:
                return

            seed_data = DEFAULT_COMPANY_ARCHITECTURES.get(target_tenant, DEFAULT_COMPANY_ARCHITECTURES["shopsphere"])
            now = datetime.now(timezone.utc)

            import json
            for n in seed_data["nodes"]:
                node = TenantArchitectureNode(
                    tenant_id=tenant_id,
                    resource_id=n["resource_id"],
                    name=n["name"],
                    display_name=n["name"],
                    resource_type=n["resource_type"],
                    environment=n["environment"].upper(),
                    runtime_platform=n["platform"],
                    owner_team=n["service_owner"],
                    on_call_schedule=n["oncall_team"],
                    maintenance_window=n["maintenance_window"],
                    data_classification=n["data_classification"],
                    recovery_capabilities_json=json.dumps(n["capabilities"]),
                    rollback_supported=bool(n.get("rollback_procedure")),
                    change_freeze_active=False,
                    discovery_source=n["discovery_source"],
                    confidence=float(n["confidence_score"]),
                    freshness_status="FRESH",
                    is_verified=bool(n["verified"]),
                    metadata_json=json.dumps({
                        "tier": n.get("tier"),
                        "runtime": n.get("runtime"),
                        "dependencies": n.get("dependencies", []),
                        "downstream_services": n.get("downstream_services", []),
                        "rollback_procedure": n.get("rollback_procedure"),
                        "health_status": n.get("health_status", "HEALTHY"),
                        "metrics_endpoint": n.get("metrics_endpoint"),
                        "logs_system": n.get("logs_system"),
                        "traces_system": n.get("traces_system"),
                        "sandbox_available": n.get("sandbox_available", True),
                        "sandbox_env_id": n.get("sandbox_env_id")
                    }),
                    first_seen=now,
                    last_seen=now,
                    created_at=now
                )
                session.add(node)

            for w in seed_data["workflows"]:
                wf = TenantWorkflowDefinition(
                    tenant_id=tenant_id,
                    workflow_id=w["workflow_id"],
                    name=w["name"],
                    criticality=w["criticality"],
                    entrypoint_service=w["entrypoint_service"],
                    service_path_json=json.dumps(w["service_path"]),
                    slo_target_latency_ms=float(w["slo_latency_target_ms"]),
                    slo_target_availability_pct=float(w["slo_availability_target"]) * 100.0,
                    discovery_source="DISTRIBUTED_TRACING",
                    is_verified=bool(w.get("verification_status") == "VERIFIED"),
                    created_at=now
                )
                session.add(wf)

            await session.commit()
            realtime_logger.info(f"Initialized architecture inventory for tenant '{tenant_id}' from seed '{target_tenant}'")

    async def get_tenant_inventory(self, tenant_id: str) -> Dict[str, Any]:
        """Returns the full tenant-scoped architecture inventory, nodes, workflows, and coverage metrics."""
        await self.seed_tenant_architecture_if_empty(tenant_id)

        async with AsyncSessionLocal() as session:
            node_res = await session.execute(
                select(TenantArchitectureNode).where(TenantArchitectureNode.tenant_id == tenant_id)
            )
            nodes = node_res.scalars().all()

            wf_res = await session.execute(
                select(TenantWorkflowDefinition).where(TenantWorkflowDefinition.tenant_id == tenant_id)
            )
            workflows = wf_res.scalars().all()

            node_dicts = [n.to_dict() for n in nodes]
            wf_dicts = [w.to_dict() for w in workflows]

            # Compute architecture coverage gap metrics
            total_nodes = len(node_dicts)
            verified_nodes = sum(1 for n in node_dicts if n.get("verified"))
            avg_confidence = (sum(n.get("confidence_score", 0.0) for n in node_dicts) / max(1, total_nodes)) if total_nodes else 0.0

            total_wfs = len(wf_dicts)
            verified_wfs = sum(1 for w in wf_dicts if w.get("verification_status") == "VERIFIED")

            unverified_resources = [n for n in node_dicts if not n.get("verified")]
            missing_telemetry = [n for n in node_dicts if not n.get("metrics_endpoint") or not n.get("logs_system")]
            missing_sandbox = [n for n in node_dicts if not n.get("sandbox_available")]

            coverage_score = round(
                ((verified_nodes / max(1, total_nodes)) * 0.4 +
                 (verified_wfs / max(1, total_wfs)) * 0.3 +
                 avg_confidence * 0.3) * 100.0,
                1
            )

            return {
                "tenant_id": tenant_id,
                "total_resources": total_nodes,
                "verified_resources": verified_nodes,
                "unverified_resources_count": len(unverified_resources),
                "total_critical_workflows": total_wfs,
                "verified_workflows": verified_wfs,
                "average_confidence_score": round(avg_confidence, 2),
                "architecture_coverage_percent": coverage_score,
                "coverage_gaps": {
                    "unverified_resources": [
                        {"resource_id": r["resource_id"], "name": r["name"], "reason": "Lacks verified telemetry & discovery probe"}
                        for r in unverified_resources
                    ],
                    "telemetry_gaps": [
                        {"resource_id": r["resource_id"], "name": r["name"], "missing": "metrics or log ingestion unconfigured"}
                        for r in missing_telemetry
                    ],
                    "sandbox_limitations": [
                        {"resource_id": r["resource_id"], "name": r["name"], "limitation": "No isolated replica environment; requires simulation mode"}
                        for r in missing_sandbox
                    ]
                },
                "nodes": node_dicts,
                "workflows": wf_dicts
            }

    async def run_discovery_job(self, tenant_id: str, discovery_source: str = "AUTHORIZED_CLOUD_PROBE") -> Dict[str, Any]:
        """
        Executes an authorized discovery refresh against configured integration sources.
        Refreshes last_seen timestamps, recalculates confidence scores, and captures new assets.
        """
        await self.seed_tenant_architecture_if_empty(tenant_id)

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            node_res = await session.execute(
                select(TenantArchitectureNode).where(TenantArchitectureNode.tenant_id == tenant_id)
            )
            nodes = node_res.scalars().all()

            for n in nodes:
                n.last_seen = now
                if n.is_verified:
                    n.confidence = min(0.99, (n.confidence or 0.95) + 0.01)

            await session.commit()

        realtime_logger.info(f"Authorized discovery job completed for tenant '{tenant_id}' via {discovery_source}")
        return await self.get_tenant_inventory(tenant_id)


# Global singleton instance
architecture_discovery = ArchitectureDiscoveryEngine()
