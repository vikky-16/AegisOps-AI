"""
AegisOps AI - Company-Specific Architecture & Workflow Database Models
Models tenant-scoped architecture inventories, runtime platforms, dependency paths,
critical business workflows, service ownership, data classification, and discovery coverage.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Index
from backend.app.core.database import Base


class TenantArchitectureNode(Base):
    """
    Tenant-scoped infrastructure, service, database, cache, or queue resource.
    Records provenance, runtime environment, capabilities, and data classification.
    """
    __tablename__ = "tenant_architecture_nodes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, nullable=False)
    resource_id = Column(String(64), index=True, nullable=False)
    name = Column(String(128), index=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    resource_type = Column(String(64), index=True, default="SERVICE")
    # SERVICE, DATABASE, CACHE, MESSAGE_QUEUE, API_GATEWAY, KUBERNETES_CLUSTER, CLOUD_STORAGE, CI_CD_PIPELINE
    environment = Column(String(32), index=True, default="PRODUCTION")
    # PRODUCTION, STAGING, TESTING, SANDBOX, DEVELOPMENT
    runtime_platform = Column(String(64), default="KUBERNETES")
    # KUBERNETES, DOCKER, AWS_ECS, BARE_METAL, SERVERLESS, CLOUD_SQL

    owner_team = Column(String(128), default="Core Platform SRE")
    on_call_schedule = Column(String(128), default="PagerDuty: Primary On-Call")
    maintenance_window = Column(String(128), default="Sundays 02:00-04:00 UTC")
    data_classification = Column(String(32), default="CONFIDENTIAL")
    # RESTRICTED, CONFIDENTIAL, INTERNAL, PUBLIC

    recovery_capabilities_json = Column(Text, default="[]")
    # e.g. ["RESET_CONNECTION_POOL", "CLEAR_CACHE", "SCALE_WORKERS", "RESTART_CONTROLLED_SERVICE"]
    rollback_supported = Column(Boolean, default=True)
    change_freeze_active = Column(Boolean, default=False)

    discovery_source = Column(String(64), default="OTEL_COLLECTOR")
    # OTEL_COLLECTOR, KUBERNETES_API, CLOUD_DISCOVERY, INTEGRATION_SYNC, STATIC_MANIFEST
    confidence = Column(Float, default=0.95)
    freshness_status = Column(String(32), default="FRESH")  # FRESH, STALE, UNVERIFIED
    is_verified = Column(Boolean, default=True)
    
    metadata_json = Column(Text, default="{}")
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_arch_tenant_resource", "tenant_id", "resource_id", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        def _parse(field, default_val):
            if not field:
                return default_val
            try:
                return json.loads(field) if isinstance(field, str) else field
            except Exception:
                return default_val

        meta = _parse(self.metadata_json, {})
        caps = _parse(self.recovery_capabilities_json, [])
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "name": self.name,
            "display_name": self.display_name,
            "resource_type": self.resource_type,
            "environment": self.environment,
            "runtime_platform": self.runtime_platform,
            "platform": self.runtime_platform,
            "tier": meta.get("tier", "Tier-1"),
            "runtime": meta.get("runtime", "container"),
            "owner_team": self.owner_team,
            "service_owner": self.owner_team,
            "on_call_schedule": self.on_call_schedule,
            "oncall_team": self.on_call_schedule,
            "maintenance_window": self.maintenance_window,
            "data_classification": self.data_classification,
            "recovery_capabilities": caps,
            "capabilities": caps,
            "rollback_supported": self.rollback_supported,
            "rollback_procedure": meta.get("rollback_procedure", "STANDARD_ROLLBACK"),
            "change_freeze_active": self.change_freeze_active,
            "discovery_source": self.discovery_source,
            "confidence": self.confidence,
            "confidence_score": self.confidence,
            "freshness_status": self.freshness_status,
            "is_verified": self.is_verified,
            "verified": self.is_verified,
            "health_status": meta.get("health_status", "HEALTHY"),
            "dependencies": meta.get("dependencies", []),
            "downstream_services": meta.get("downstream_services", []),
            "metrics_endpoint": meta.get("metrics_endpoint"),
            "logs_system": meta.get("logs_system"),
            "traces_system": meta.get("traces_system"),
            "sandbox_available": meta.get("sandbox_available", True),
            "sandbox_env_id": meta.get("sandbox_env_id"),
            "metadata": meta,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantWorkflowDefinition(Base):
    """
    End-to-end critical business workflow (e.g. Checkout flow, Auth flow, Ingestion pipeline).
    Maps communication sequence across services, SLA thresholds, and change boundaries.
    """
    __tablename__ = "tenant_workflow_definitions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, nullable=False)
    workflow_id = Column(String(64), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    criticality = Column(String(32), default="CRITICAL")  # CRITICAL, HIGH, MEDIUM
    entrypoint_service = Column(String(64), nullable=False)
    service_path_json = Column(Text, default="[]")  # Ordered service names
    slo_target_latency_ms = Column(Float, default=250.0)
    slo_target_availability_pct = Column(Float, default=99.95)
    discovery_source = Column(String(64), default="DISTRIBUTED_TRACING")
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_wf_tenant_workflow", "tenant_id", "workflow_id", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        def _parse(field, default_val):
            if not field:
                return default_val
            try:
                return json.loads(field) if isinstance(field, str) else field
            except Exception:
                return default_val

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "criticality": self.criticality,
            "entrypoint_service": self.entrypoint_service,
            "service_path": _parse(self.service_path_json, []),
            "slo_target_latency_ms": self.slo_target_latency_ms,
            "slo_latency_target_ms": self.slo_target_latency_ms,
            "slo_target_availability_pct": self.slo_target_availability_pct,
            "slo_availability_target": round(self.slo_target_availability_pct / 100.0, 5),
            "discovery_source": self.discovery_source,
            "is_verified": self.is_verified,
            "verification_status": "VERIFIED" if self.is_verified else "UNVERIFIED",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
