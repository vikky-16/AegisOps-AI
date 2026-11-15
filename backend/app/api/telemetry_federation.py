"""
AegisOps AI - Telemetry Federation & Query API
Unified endpoints for querying live telemetry feeds, correlated multi-signal context,
anomalies, and learned metric baselines.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.monitoring.collector import collector
from backend.app.ai.baselines import baseline_manager
from backend.app.rca.dynamic_graph import dynamic_graph

router = APIRouter(prefix="/telemetry", tags=["Telemetry Federation"])


@router.get("/live")
async def get_live_telemetry(
    limit: int = Query(50, ge=1, le=200),
    service: Optional[str] = None,
    severity: Optional[str] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """Returns live streaming telemetry events with optional filtering."""
    events = list(collector.live_operations_feed)
    
    if service:
        events = [e for e in events if e.get("service") == service or e.get("service_name") == service]
    if severity:
        events = [e for e in events if str(e.get("severity", "")).upper() == severity.upper()]
    if trace_id:
        events = [e for e in events if e.get("metadata", {}).get("trace_id") == trace_id]

    return {
        "events": events[:limit],
        "total_buffered": len(collector.live_operations_feed),
        "system_health": collector.system_health_score,
        "operating_mode": collector.operating_mode
    }


@router.get("/correlated-context")
async def get_correlated_context(
    service: Optional[str] = None,
    incident_id: Optional[str] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves unified multi-signal context (logs, metrics, traces, topology, anomalies)."""
    incident = None
    if incident_id:
        incident = next((i for i in collector.active_incidents + collector.resolved_incidents if i.get("incident_id") == incident_id), None)
    
    target_svc = service or (incident.get("root_cause_service") if incident else "gateway")
    metrics = collector.latest_metrics.get(target_svc, {})
    deps = dynamic_graph.get_dependencies(target_svc)
    baselines = baseline_manager.get_baseline(target_svc, "latency_p95_ms")

    return {
        "service": target_svc,
        "incident": incident,
        "metrics_snapshot": metrics,
        "dependencies": deps,
        "baseline_profile": baselines,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/anomalies")
async def get_active_anomalies() -> Dict[str, Any]:
    """Returns currently detected anomalies across all services."""
    anomalies = []
    for svc, m in collector.latest_metrics.items():
        score = m.get("anomaly_score", 0.0)
        if score >= 0.45 or m.get("is_anomaly", 0) == 1:
            anomalies.append({
                "service": svc,
                "anomaly_score": score,
                "error_rate": m.get("error_rate", 0.0),
                "latency_p95_ms": m.get("latency_p95_ms", 0.0),
                "timestamp": m.get("timestamp")
            })

    return {
        "anomalies": anomalies,
        "count": len(anomalies)
    }


@router.get("/baselines")
async def get_baselines() -> List[Dict[str, Any]]:
    """Returns learned normal operational baselines for all services and metrics."""
    return baseline_manager.get_all_baselines()
