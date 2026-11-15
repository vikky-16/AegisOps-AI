"""
AegisOps AI - Multi-Tenant Data Models
Defines Tenant, TenantAPIKey, TenantIntegration, TenantPolicy, and TenantAuditLog.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey
from backend.app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "org_acme_001", "tenant-alpha", "demo-tenant"
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, index=True, nullable=False)
    tier = Column(String(32), default="ENTERPRISE", nullable=False)  # COMMUNITY, PRO, ENTERPRISE
    plan = Column(String(32), default="Enterprise", nullable=False)
    industry = Column(String(64), default="Financial Services", nullable=False)
    region = Column(String(64), default="India", nullable=False)
    logo_url = Column(String(256), nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)    # ACTIVE, SUSPENDED, TRIAL
    retention_days = Column(Integer, default=30, nullable=False)
    environments_json = Column(
        Text, 
        default='["PRODUCTION", "STAGING", "DEVELOPMENT", "CONTROLLED_CUSTOMER_TEST", "DEMO", "LOAD_TEST"]', 
        nullable=False
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    settings_json = Column(Text, nullable=True)

    def get_environments(self) -> List[str]:
        if not self.environments_json:
            return ["PRODUCTION", "STAGING", "DEVELOPMENT", "CONTROLLED_CUSTOMER_TEST", "DEMO", "LOAD_TEST"]
        try:
            return json.loads(self.environments_json)
        except Exception:
            return ["PRODUCTION", "STAGING", "DEVELOPMENT", "CONTROLLED_CUSTOMER_TEST", "DEMO", "LOAD_TEST"]

    def to_dict(self) -> Dict[str, Any]:
        settings = {}
        if self.settings_json:
            try:
                settings = json.loads(self.settings_json)
            except Exception:
                settings = {}
        return {
            "id": self.id,
            "organization_id": self.id,
            "name": self.name,
            "slug": self.slug,
            "tier": self.tier,
            "plan": self.plan or self.tier,
            "industry": self.industry,
            "region": self.region,
            "logo_url": self.logo_url,
            "status": self.status,
            "retention_days": self.retention_days,
            "environments": self.get_environments(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "settings": settings
        }



class TenantAPIKey(Base):
    __tablename__ = "tenant_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), index=True, nullable=False)
    key_prefix = Column(String(16), nullable=False)   # e.g. "agt_live_a1b2"
    hashed_key = Column(String(128), nullable=False, index=True)  # SHA-256 hash of secret key
    name = Column(String(128), nullable=False)
    scopes = Column(String(256), default="telemetry:write,telemetry:read", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "key_prefix": self.key_prefix,
            "name": self.name,
            "scopes": self.scopes.split(",") if self.scopes else [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }


class TenantIntegration(Base):
    __tablename__ = "tenant_integrations"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "intg-otel-prod"
    tenant_id = Column(String(64), ForeignKey("tenants.id"), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    type = Column(String(32), default="OTEL", nullable=False)  # OTEL, KAFKA, FLUENT_BIT, SYSLOG, HTTP
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, CONNECTED, DEGRADED, DISCONNECTED, ERROR
    config_json = Column(Text, nullable=True)
    last_telemetry_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_log_at = Column(DateTime, nullable=True)
    last_metric_at = Column(DateTime, nullable=True)
    last_trace_at = Column(DateTime, nullable=True)
    last_event_at = Column(DateTime, nullable=True)
    events_received = Column(Integer, default=0)
    bytes_received = Column(Integer, default=0)
    events_per_sec = Column(Float, default=0.0)
    bytes_per_sec = Column(Float, default=0.0)
    dropped_events = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def get_effective_status(self, now: Optional[datetime] = None) -> str:
        """Dynamically computes connection health based on actual telemetry arrival."""
        if not self.last_seen_at and not self.last_telemetry_at:
            return self.status or "PENDING"
        ref_time = self.last_seen_at or self.last_telemetry_at
        current_time = now or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        silence_sec = (current_time - ref_time).total_seconds()
        if silence_sec <= 60.0:
            return "CONNECTED"
        elif silence_sec <= 300.0:
            return "DEGRADED"
        else:
            return "DISCONNECTED"

    def to_dict(self) -> Dict[str, Any]:
        config = {}
        if self.config_json:
            try:
                config = json.loads(self.config_json)
            except Exception:
                config = {}
        
        effective_status = self.get_effective_status()

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "type": self.type,
            "status": effective_status,
            "stored_status": self.status,
            "config": config,
            "last_telemetry_at": self.last_telemetry_at.isoformat() if self.last_telemetry_at else None,
            "last_seen_at": (self.last_seen_at or self.last_telemetry_at).isoformat() if (self.last_seen_at or self.last_telemetry_at) else None,
            "last_log_at": self.last_log_at.isoformat() if self.last_log_at else None,
            "last_metric_at": self.last_metric_at.isoformat() if self.last_metric_at else None,
            "last_trace_at": self.last_trace_at.isoformat() if self.last_trace_at else None,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "events_received": int(self.events_received or 0),
            "bytes_received": int(self.bytes_received or 0),
            "events_per_sec": round(float(self.events_per_sec or 0.0), 2),
            "events_per_second": round(float(self.events_per_sec or 0.0), 2),
            "bytes_per_sec": round(float(self.bytes_per_sec or 0.0), 2),
            "dropped_events": int(self.dropped_events or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class TenantPolicy(Base):
    __tablename__ = "tenant_policies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), unique=True, index=True, nullable=False)
    auto_remediation_enabled = Column(Boolean, default=True, nullable=False)
    allowed_actions_json = Column(
        Text, 
        default='["RESET_CONNECTION_POOL", "CLEAR_CACHE", "DRAIN_QUEUE", "ROTATE_CONNECTIONS"]', 
        nullable=False
    )
    max_auto_risk_level = Column(String(32), default="LOW", nullable=False)  # LOW, MEDIUM, HIGH
    min_rca_confidence = Column(Float, default=0.85, nullable=False)
    max_blast_radius = Column(Float, default=60.0, nullable=False)
    cooldown_seconds = Column(Integer, default=300, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def get_allowed_actions(self) -> List[str]:
        try:
            return json.loads(self.allowed_actions_json)
        except Exception:
            return ["RESET_CONNECTION_POOL", "CLEAR_CACHE"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "auto_remediation_enabled": self.auto_remediation_enabled,
            "allowed_actions": self.get_allowed_actions(),
            "max_auto_risk_level": self.max_auto_risk_level,
            "min_rca_confidence": float(self.min_rca_confidence),
            "max_blast_radius": float(self.max_blast_radius),
            "cooldown_seconds": int(self.cooldown_seconds),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TenantAuditLog(Base):
    __tablename__ = "tenant_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, nullable=False)
    user_identifier = Column(String(128), nullable=False)
    user_role = Column(String(32), default="OPERATOR", nullable=False)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(128), nullable=True)
    details_json = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    result = Column(String(32), default="SUCCESS", nullable=False)  # SUCCESS, FAILURE, DENIED
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> Dict[str, Any]:
        details = {}
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except Exception:
                details = {"raw": self.details_json}
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "organization_id": self.tenant_id,
            "user": self.user_identifier,
            "user_identifier": self.user_identifier,
            "role": self.user_role,
            "user_role": self.user_role,
            "action": self.action,
            "resource": f"{self.resource_type or ''}:{self.resource_id or ''}".strip(":"),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": details,
            "ip": self.ip_address or "127.0.0.1",
            "ip_address": self.ip_address or "127.0.0.1",
            "result": self.result,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

