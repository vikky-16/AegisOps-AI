"""
Pydantic Schemas for AegisOps AI
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# User Schemas
class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "operator"


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


# Service Schemas
class ServiceBase(BaseModel):
    name: str
    display_name: str
    role: str
    port: int
    url: str
    dependencies: List[str] = []
    criticality: str = "HIGH"
    sla_target_pct: float = 99.9


class ServiceOut(ServiceBase):
    id: int
    status: str
    is_monitored: bool
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


# Metric Schemas
class MetricOut(BaseModel):
    service_name: str
    timestamp: datetime
    status: str
    cpu_percent: float
    memory_mb: float
    request_count: int
    error_count: int
    error_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    active_connections: int
    anomaly_score: float
    is_anomaly: int

    class Config:
        from_attributes = True


# Incident Schemas
class IncidentCreate(BaseModel):
    title: str
    primary_service: str
    severity: str = "MEDIUM"
    description: Optional[str] = None


class IncidentOut(BaseModel):
    id: int
    incident_id: str
    title: str
    description: Optional[str]
    severity: str
    status: str
    primary_service: str
    affected_services: List[str] = []
    correlated_event_count: int
    anomaly_score: float
    root_cause_service: Optional[str]
    root_cause_category: Optional[str]
    root_cause_summary: Optional[str]
    rca_confidence: float
    rca_evidence: List[str] = []
    business_impact_score: float
    estimated_users_affected: int
    sla_breach_risk: str
    recommended_action: Optional[str]
    alternative_action: Optional[str]
    action_risk_level: str
    recovery_status: str
    timeline: List[Dict[str, Any]] = []
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Approval Schemas
class ApprovalOut(BaseModel):
    id: int
    approval_id: str
    incident_id: str
    service_name: str
    proposed_action: str
    risk_level: str
    risk_score: float
    reason: str
    expected_outcome: Optional[str]
    estimated_downtime_sec: int
    rollback_plan: Optional[str]
    status: str
    reviewed_by: Optional[str]
    review_notes: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    decision: str  # APPROVE, REJECT, DEFER
    notes: Optional[str] = None


# Recovery Schemas
class RecoveryOut(BaseModel):
    id: int
    execution_id: str
    incident_id: str
    approval_id: Optional[str]
    service_name: str
    action: str
    risk_level: str
    execution_mode: str
    status: str
    duration_ms: float
    pre_health_score: float
    post_health_score: float
    error_message: Optional[str]
    executed_at: datetime
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Storage Schemas
class StorageOut(BaseModel):
    timestamp: datetime
    total_gb: float
    used_gb: float
    free_gb: float
    used_percentage: float
    growth_rate_gb_per_hour: float
    predicted_critical_hours: float
    log_files_count: int
    total_log_size_mb: float
    archive_size_mb: float
    top_consumers: List[Dict[str, Any]] = []


# Knowledge Base Schemas
class KnowledgeOut(BaseModel):
    id: int
    incident_code: str
    title: str
    primary_service: str
    symptoms_summary: str
    root_cause: str
    recommended_remedy: str
    recovery_action_taken: str
    recovery_duration_sec: float
    outcome: str
    historical_success_rate: float
    tags: List[str] = []
    times_referenced: int
    created_at: datetime

    class Config:
        from_attributes = True


# Assistant Query Schema
class AssistantQuery(BaseModel):
    question: str
    context_incident_id: Optional[str] = None


class AssistantResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[str] = []
    suggested_actions: List[str] = []
    timestamp: datetime
