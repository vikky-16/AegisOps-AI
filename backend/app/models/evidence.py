"""
AegisOps AI - Evidence Database Model
Stores structured, summarized operational evidence for closed-loop recovery validation.
Supports pre-fix and post-fix execution iterations, multi-signal telemetry deviations,
and correlation context without persisting raw telemetry floods.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from backend.app.core.database import Base


class EvidenceItem(Base):
    __tablename__ = "incident_evidence"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(Float, default=lambda: datetime.now(timezone.utc).timestamp(), index=True)
    source = Column(String(64), nullable=False)  # e.g., metric_collector, log_analyzer, trace_probe, health_check
    service = Column(String(64), index=True, nullable=False)  # e.g., database-service, gateway
    component = Column(String(64), nullable=False)  # e.g., connection_pool, http_server, heap, disk, worker_pool
    signal_type = Column(String(32), index=True, nullable=False)  # METRIC, LOG, TRACE, HEALTH, ANOMALY
    metric_or_log_value = Column(String(256), nullable=False)  # e.g., "active_connections=98", "HTTP 503 PoolExhausted"
    baseline = Column(String(64), nullable=True)  # Baseline reference value (e.g., "10.0")
    deviation = Column(String(64), nullable=True)  # Statistical or percentage deviation (e.g., "+880%", "Z=4.82")
    correlation_info_json = Column(Text, default="{}")  # JSON metadata: trace_id, causal_depth, onset_lag
    execution_iteration = Column(Integer, default=0, index=True)  # 0 for initial pre-fix, 1..N for post-fix loops
    before_after_state = Column(String(16), default="BEFORE", index=True)  # "BEFORE" or "AFTER"
    # Extended evidence model fields for closed-loop recovery validation
    evidence_type = Column(String(32), default="metric", index=True)  # metric, log, trace, stack_trace, error_signature, dependency, temporal, execution, before_after, historical
    metric_name = Column(String(64), nullable=True)  # e.g., latency_p95, error_rate, active_connections
    before_val = Column(Float, nullable=True)  # Numerical before value
    after_val = Column(Float, nullable=True)  # Numerical after value
    threshold_val = Column(Float, nullable=True)  # Threshold criteria
    status = Column(String(32), default="PASS", index=True)  # PASS, FAIL, WARNING, ANOMALOUS

    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        correlation_data = {}
        if self.correlation_info_json:
            try:
                correlation_data = json.loads(self.correlation_info_json)
            except Exception:
                correlation_data = {"raw": self.correlation_info_json}

        # Resolve evidence_type: if not explicitly set, derive from signal_type
        ev_type = self.evidence_type or (self.signal_type.lower() if self.signal_type else "metric")

        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "evidence_type": ev_type,
            "metric": self.metric_name or self.component,
            "metric_name": self.metric_name or self.component,
            "before": self.before_val,
            "after": self.after_val,
            "threshold": self.threshold_val,
            "status": self.status or "PASS",
            "timestamp": self.timestamp,
            "source": self.source,
            "service": self.service,
            "component": self.component,
            "signal_type": self.signal_type,
            "metric_or_log_value": self.metric_or_log_value,
            "baseline": self.baseline,
            "deviation": self.deviation,
            "correlation_info": correlation_data,
            "execution_iteration": self.execution_iteration,
            "before_after_state": self.before_after_state,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


IncidentEvidence = EvidenceItem

