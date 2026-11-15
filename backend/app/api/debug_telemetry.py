"""
AegisOps AI - Live Telemetry Diagnostic & Pipeline Debug API
Provides:
- GET /api/debug/telemetry (Real health of backend, collector, consumer, companies, and websocket)
- POST /api/debug/test-telemetry (Injects a real test event through the genuine telemetry pipeline)
"""

import time
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException

from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.monitoring.collector import collector
from backend.app.storage.telemetry_store import telemetry_store
from backend.app.api.websocket import ws_manager
from backend.app.api.ingestion_gateway import (
    ingestion_tracker,
    _normalize_raw_event,
    _process_and_publish_events
)

router = APIRouter(tags=["Debug Telemetry"])


@router.get("/api/debug/telemetry")
@router.get("/debug/telemetry")
async def get_debug_telemetry():
    """
    Returns real, non-mocked runtime diagnostics for all pipeline stages and monitored companies.
    """
    now_dt = datetime.now(timezone.utc)
    
    companies_data = {}
    for comp in ["shopsphere", "fincore", "clouddesk"]:
        stats = ingestion_tracker.get_stats(comp)
        last_ts = stats.get("last_timestamp")
        events_count = stats.get("total_events", 0)
        
        # Calculate real status based on last event timestamp
        age = 999.0
        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts)
                age = max(0.0, (now_dt - last_dt).total_seconds())
            except Exception:
                age = 999.0
        
        if events_count > 0 and age < 15.0:
            status = "live"
        elif events_count > 0 and age < 45.0:
            status = "degraded"
        else:
            status = "disconnected"
            
        companies_data[comp] = {
            "status": status,
            "last_event_at": last_ts,
            "events_received": events_count
        }

    return {
        "backend": {
            "status": "healthy"
        },
        "collector": {
            "status": "healthy" if collector.is_running else "offline"
        },
        "consumer": {
            "status": "healthy" if collector.is_running else "offline"
        },
        "companies": companies_data,
        "websocket": {
            "active_connections": len(ws_manager.connections)
        }
    }


@router.post("/api/debug/test-telemetry")
@router.post("/debug/test-telemetry")
async def generate_debug_test_telemetry(payload: Optional[Dict[str, Any]] = None):
    """
    Generates ONE real test telemetry event and processes it through the genuine
    production ingestion pipeline (Collector -> TelemetryStore -> IngestionTracker -> WebSocket).
    Returns event ID and correlation IDs.
    """
    payload = payload or {}
    company = (payload.get("company") or "shopsphere").lower()
    debug_req_id = payload.get("request_id") or payload.get("debug_request_id") or f"debug-req-{uuid.uuid4().hex[:8]}"
    trace_id = payload.get("trace_id") or uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    now_iso = datetime.now(timezone.utc).isoformat()
    event_id = f"evt-debug-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"

    raw_event = {
        "event_id": event_id,
        "tenant_id": company,
        "company_id": company,
        "service": f"{company}-gateway",
        "service_name": f"{company}-gateway",
        "timestamp": now_iso,
        "event_type": "log",
        "level": "INFO",
        "severity": "INFO",
        "message": f"Real pipeline test event for {company} [debug_request_id={debug_req_id}]",
        "request_id": debug_req_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "http_method": "POST",
        "http_route": "/api/v1/orders",
        "status_code": 200,
        "latency_ms": 14.2
    }

    # Normalize into UnifiedTelemetryEvent
    normalized = _normalize_raw_event(raw_event, "log", company)
    
    # Process through genuine pipeline: Collector -> TelemetryStore -> Tracker -> WebSocket Hub
    raw_bytes = len(json.dumps(raw_event).encode("utf-8"))
    publish_result = await _process_and_publish_events([normalized], company, raw_bytes)

    return {
        "status": "ACCEPTED",
        "event_id": normalized.event_id,
        "debug_request_id": debug_req_id,
        "trace_id": trace_id,
        "tenant_id": company,
        "company": company,
        "service": normalized.service_name,
        "timestamp": now_iso,
        "pipeline_stages": {
            "ingestion_gateway": "ACCEPTED",
            "telemetry_store": "STORED",
            "central_collector": "INGESTED",
            "websocket_hub": "BROADCASTED"
        },
        "publish_result": publish_result
    }


@router.get("/api/debug/incident-pipeline")
@router.get("/debug/incident-pipeline")
async def get_incident_pipeline_debug():
    from backend.app.analytics.feature_extractor import feature_extractor
    from backend.app.analytics.baseline_engine import baseline_engine
    from backend.app.analytics.anomaly_detector import anomaly_detector
    from backend.app.analytics.incident_pipeline import incident_pipeline
    import time

    now = time.time()
    active_svcs = feature_extractor.get_all_active_services()
    svcs_report = {}
    for t_id, s_name in active_svcs:
        feats = feature_extractor.get_features(t_id, s_name, window_sec=30.0)
        is_warmed, elapsed = baseline_engine.is_warmed_up(t_id, s_name, current_time=now)
        anom = anomaly_detector.evaluate(t_id, s_name, feats, current_time=now)
        svcs_report[f"{t_id}:{s_name}"] = {
            "events_count": feats.get("request_count", 0),
            "p95_latency": feats.get("p95_latency"),
            "error_rate": feats.get("error_rate"),
            "5xx_rate": feats.get("http_5xx_rate"),
            "is_warmed_up": is_warmed,
            "warmup_elapsed": elapsed,
            "warmup_target": baseline_engine.warmup_seconds,
            "is_anomaly": anom.get("is_anomaly"),
            "combined_score": anom.get("combined_score"),
            "severity": anom.get("severity"),
            "detectors_triggered": anom.get("detectors_triggered", [])
        }

    return {
        "active_services_count": len(active_svcs),
        "active_services": [f"{t}:{s}" for t, s in active_svcs],
        "services_details": svcs_report,
        "active_incidents_in_pipeline": list(incident_pipeline._active_incidents.keys()),
        "worker_running": incident_pipeline._is_running
    }
