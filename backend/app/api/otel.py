"""
OpenTelemetry Ingestion API Endpoints
Receives standard OTLP HTTP payloads for Traces, Metrics, and Logs with multi-tenant resolution.
"""

from fastapi import APIRouter, Request, status, Response, Header
from typing import Dict, Any, List, Optional
import json

from backend.app.integrations.normalizer import telemetry_normalizer
from backend.app.monitoring.collector import collector
from backend.app.core.security import resolve_api_key_identity
from backend.app.api.ingestion_gateway import ingestion_tracker
from backend.app.schemas.telemetry_contract import TelemetrySourceMode
from backend.app.storage.telemetry_store import telemetry_store
from backend.app.api.websocket import ws_manager

router = APIRouter(prefix="/otel", tags=["OpenTelemetry Ingestion"])


async def _resolve_otel_tenant(request: Request) -> str:
    """Derives tenant_id from X-API-Key, X-Tenant-ID, or query parameters."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        identity = await resolve_api_key_identity(api_key)
        if identity:
            return identity.tenant_id
    
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header and tenant_header.strip():
        return tenant_header.strip()

    tenant_query = request.query_params.get("tenant_id") or request.query_params.get("tenant")
    if tenant_query and tenant_query.strip():
        return tenant_query.strip()

    return "shopsphere"


@router.post("/v1/traces")
@router.post("/traces")
async def ingest_otel_traces(request: Request):
    """Standard OpenTelemetry OTLP /v1/traces HTTP receiver."""
    try:
        body_bytes = await request.body()
    except Exception:
        return {"status": "CLIENT_DISCONNECTED", "ingested_count": 0}
    tenant_id = await _resolve_otel_tenant(request)
    try:
        payload = json.loads(body_bytes) if body_bytes else {}
    except Exception:
        payload = {}
    
    events = telemetry_normalizer.normalize_event(payload, source="otel-trace")
    for ev in events:
        ev.tenant_id = tenant_id
        ev.company_id = tenant_id
        ev.source_mode = TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value if tenant_id != "demo-tenant" else TelemetrySourceMode.LIVE_DEMO_ENVIRONMENT.value
        collector.ingest_unified_event(ev)
        ingestion_tracker.add_service(tenant_id, ev.service_name)
        await ws_manager.broadcast_tenant_event(tenant_id, ev.to_log_dict())
    
    if events:
        await telemetry_store.write_events(events)

    ingestion_tracker.record_ingest(
        tenant_id,
        len(events),
        len(body_bytes),
        has_traces=True,
        trace_count=len(events)
    )
    return {
        "status": "SUCCESS",
        "ingested_count": len(events),
        "tenant_id": tenant_id,
        "source": "otel-traces"
    }


@router.post("/v1/metrics")
@router.post("/metrics")
async def ingest_otel_metrics(request: Request):
    """Standard OpenTelemetry OTLP /v1/metrics HTTP receiver."""
    try:
        body_bytes = await request.body()
    except Exception:
        return {"status": "CLIENT_DISCONNECTED", "ingested_count": 0}
    tenant_id = await _resolve_otel_tenant(request)
    try:
        payload = json.loads(body_bytes) if body_bytes else {}
    except Exception:
        payload = {}
    
    events = telemetry_normalizer.normalize_event(payload, source="otel-metrics")
    for ev in events:
        ev.tenant_id = tenant_id
        ev.company_id = tenant_id
        ev.source_mode = TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value if tenant_id != "demo-tenant" else TelemetrySourceMode.LIVE_DEMO_ENVIRONMENT.value
        collector.ingest_unified_event(ev)
        ingestion_tracker.add_service(tenant_id, ev.service_name)
        await ws_manager.broadcast_tenant_event(tenant_id, ev.to_log_dict())
    
    if events:
        await telemetry_store.write_events(events)

    ingestion_tracker.record_ingest(
        tenant_id,
        len(events),
        len(body_bytes),
        has_metrics=True,
        metric_count=len(events)
    )
    return {
        "status": "SUCCESS",
        "ingested_count": len(events),
        "tenant_id": tenant_id,
        "source": "otel-metrics"
    }


@router.post("/v1/logs")
@router.post("/logs")
async def ingest_otel_logs(request: Request):
    """Standard OpenTelemetry OTLP /v1/logs HTTP receiver."""
    try:
        body_bytes = await request.body()
    except Exception:
        return {"status": "CLIENT_DISCONNECTED", "ingested_count": 0}
    tenant_id = await _resolve_otel_tenant(request)
    try:
        payload = json.loads(body_bytes) if body_bytes else {}
    except Exception:
        payload = {}
    
    events = telemetry_normalizer.normalize_event(payload, source="otel-logs")
    error_count = sum(1 for e in events if (e.severity and e.severity.upper() in ("ERROR", "CRITICAL")))
    for ev in events:
        ev.tenant_id = tenant_id
        ev.company_id = tenant_id
        ev.source_mode = TelemetrySourceMode.LIVE_EXTERNAL_TENANT.value if tenant_id != "demo-tenant" else TelemetrySourceMode.LIVE_DEMO_ENVIRONMENT.value
        collector.ingest_unified_event(ev)
        ingestion_tracker.add_service(tenant_id, ev.service_name)
        await ws_manager.broadcast_tenant_event(tenant_id, ev.to_log_dict())
    
    if events:
        await telemetry_store.write_events(events)

    ingestion_tracker.record_ingest(
        tenant_id,
        len(events),
        len(body_bytes),
        has_logs=True,
        log_count=len(events),
        error_count=error_count
    )
    return {
        "status": "SUCCESS",
        "ingested_count": len(events),
        "tenant_id": tenant_id,
        "source": "otel-logs"
    }


@router.get("/health")
async def otel_health():
    return {
        "status": "HEALTHY",
        "connector": "OpenTelemetry Collector Gateway",
        "receivers": ["otlp/grpc:4317", "otlp/http:4318", "otlp/http-api:8000/api/otel/v1/*"],
        "batch_size": 256,
        "supported_telemetry": ["traces", "metrics", "logs"]
    }
