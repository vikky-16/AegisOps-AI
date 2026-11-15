"""
Service Dependency & Intelligent Correlation Database Models
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, Index
from backend.app.core.database import Base


class Service(Base):
    __tablename__ = "registered_services"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(64), unique=True, index=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    service_type = Column(String(64), default="api")  # gateway, api, database, cache, message-queue, auth
    environment = Column(String(32), default="production", index=True)  # production, staging, demo
    resource_id = Column(String(256), index=True, nullable=True)  # Service workload URI
    resource_group = Column(String(128), default="aegisops-mesh", index=True)
    status = Column(String(32), default="HEALTHY", index=True)  # HEALTHY, DEGRADED, FAILED, UNKNOWN
    owner = Column(String(128), default="Core SRE Team")
    criticality = Column(String(32), default="HIGH", index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ServiceDependency(Base):
    __tablename__ = "service_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    dependency_id = Column(String(64), unique=True, index=True, nullable=False)  # e.g., DEP-GW-SVCA
    source_service = Column(String(64), index=True, nullable=False)  # Caller (e.g. gateway)
    target_service = Column(String(64), index=True, nullable=False)  # Downstream (e.g. payment-api)
    relationship_type = Column(String(64), default="HTTP_UPSTREAM")  # HTTP_UPSTREAM, DATABASE_QUERY, CACHE_ACCESS, ASYNC_MESSAGE, INFERRED
    confidence = Column(Float, default=0.95)  # 0.0 to 1.0 (e.g. 0.96 for 96%)
    observation_count = Column(Integer, default=1)  # Observed transaction count
    correlated_failures_count = Column(Integer, default=0)
    evidence_json = Column(Text, default="[]")  # JSON list of evidence strings
    status = Column(String(32), default="INFERRED", index=True)  # INFERRED, VALIDATED, ACTIVE, DEGRADED, STALE
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class EventSignature(Base):
    __tablename__ = "event_signatures"

    id = Column(Integer, primary_key=True, index=True)
    signature = Column(String(128), index=True, nullable=False)  # e.g. DATABASE_CONNECTION_TIMEOUT
    original_message_sample = Column(Text, nullable=False)
    service = Column(String(64), index=True, nullable=False)
    frequency = Column(Integer, default=1)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)


class IncidentCorrelation(Base):
    __tablename__ = "incident_correlations"

    id = Column(Integer, primary_key=True, index=True)
    correlation_id = Column(String(64), unique=True, index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    temporal_score = Column(Float, default=1.0)
    dependency_score = Column(Float, default=1.0)
    trace_score = Column(Float, default=1.0)
    signature_score = Column(Float, default=1.0)
    resource_score = Column(Float, default=1.0)
    causal_score = Column(Float, default=1.0)
    overall_score = Column(Float, default=0.94)  # 0.0 to 1.0
    explanation_json = Column(Text, default="[]")  # JSON list of human-readable bullet points
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class IncidentImpact(Base):
    __tablename__ = "incident_impacts"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(64), unique=True, index=True, nullable=False)
    criticality = Column(String(32), default="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    direct_impact_json = Column(Text, default="[]")  # Root failing service(s)
    downstream_impact_json = Column(Text, default="[]")  # Cascading dependent services
    affected_services_count = Column(Integer, default=1)
    affected_requests_count = Column(Integer, default=0)
    customer_facing = Column(Boolean, default=True)
    impact_level = Column(String(32), default="CRITICAL")  # CRITICAL, HIGH, MEDIUM, LOW
    blast_radius_score = Column(Float, default=85.0)  # 0 to 100
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RootCauseCandidate(Base):
    __tablename__ = "root_cause_candidates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), index=True, default="shopsphere", nullable=False)
    incident_id = Column(String(64), index=True, nullable=False)
    service = Column(String(64), index=True, nullable=False)
    rank = Column(Integer, default=1)  # 1, 2, 3...
    confidence = Column(Float, default=0.94)  # 0.0 to 1.0 (e.g. 0.94)
    score = Column(Float, default=94.0)
    causal_onset_time = Column(String(64), nullable=True)  # Earliest failure timestamp
    rationale = Column(Text, nullable=True)  # Chronological & topological reasoning
    is_primary = Column(Boolean, default=False)

