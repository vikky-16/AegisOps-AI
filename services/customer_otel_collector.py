"""
Customer OpenTelemetry Collector (OTel Bridge) - Port 4318
Receives native OTLP HTTP telemetry (Traces, Metrics, Logs) from customer microservices,
batches the events, injects the customer's tenant credentials (X-API-Key, X-Tenant-ID),
and forwards them to the AegisOps AI Telemetry Ingestion Gateway.
"""

import os
import sys
import time
import json
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, status
from pydantic import BaseModel

# Try importing protobuf OTLP collectors
try:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
    from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False


class CollectorConfig:
    def __init__(self):
        self.gateway_url: str = os.getenv("AEGISOPS_GATEWAY_URL", "http://127.0.0.1:8000/api/v1/telemetry").rstrip("/")
        self.api_key: str = os.getenv("AEGISOPS_API_KEY", "")
        self.tenant_id: str = os.getenv("AEGISOPS_TENANT_ID", "tenant-alpha")
        self.batch_max_size: int = 100
        self.batch_max_wait_ms: int = 250


class ConfigureRequest(BaseModel):
    api_key: Optional[str] = None
    tenant_id: Optional[str] = None
    gateway_url: Optional[str] = None


collector_config = CollectorConfig()
stats = {
    "traces_received": 0,
    "metrics_received": 0,
    "logs_received": 0,
    "events_forwarded": 0,
    "batches_sent": 0,
    "forward_errors": 0,
    "last_forward_timestamp": None,
    "start_time": time.time()
}

batch_queue: asyncio.Queue = asyncio.Queue()
client: Optional[httpx.AsyncClient] = None

app = FastAPI(
    title="Customer OpenTelemetry Collector Bridge",
    description="Bridge collector forwarding OTLP telemetry to AegisOps Gateway with tenant authentication",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    global client
    client = httpx.AsyncClient(timeout=5.0)
    asyncio.create_task(_batch_forwarder())


@app.on_event("shutdown")
async def shutdown_event():
    global client
    if client:
        await client.aclose()


async def _batch_forwarder():
    """Continuously drains queue in batches and POSTs to AegisOps Gateway."""
    global stats
    while True:
        items = []
        try:
            # Wait for at least one item
            item = await asyncio.wait_for(batch_queue.get(), timeout=0.25)
            items.append(item)
            # Drain additional available items up to batch_max_size
            while len(items) < collector_config.batch_max_size and not batch_queue.empty():
                items.append(batch_queue.get_nowait())
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            pass

        if not items:
            continue

        if not collector_config.api_key:
            # If API key not yet configured, re-queue or drop silently to avoid crashes
            for it in items:
                await asyncio.sleep(0.01)
                await batch_queue.put(it)
            await asyncio.sleep(0.5)
            continue

        try:
            target_url = f"{collector_config.gateway_url}/batch"
            headers = {
                "X-API-Key": collector_config.api_key,
                "X-Tenant-ID": collector_config.tenant_id,
                "Content-Type": "application/json"
            }
            resp = await client.post(target_url, json=items, headers=headers)
            if resp.status_code in (200, 201, 202):
                stats["batches_sent"] += 1
                stats["events_forwarded"] += len(items)
                stats["last_forward_timestamp"] = datetime.now(timezone.utc).isoformat()
            else:
                stats["forward_errors"] += 1
        except Exception:
            stats["forward_errors"] += 1


# =========================================================================
# OTLP PROTOBUF & JSON EXTRACTION HELPERS
# =========================================================================

def _extract_traces_from_protobuf(body: bytes) -> List[Dict[str, Any]]:
    events = []
    try:
        req = ExportTraceServiceRequest.FromString(body)
        for r_span in req.resource_spans:
            service_name = "customer-service"
            for attr in r_span.resource.attributes:
                if attr.key == "service.name":
                    service_name = attr.value.string_value

            for s_span in r_span.scope_spans:
                for span in s_span.spans:
                    trace_id = span.trace_id.hex() if span.trace_id else uuid.uuid4().hex
                    span_id = span.span_id.hex() if span.span_id else uuid.uuid4().hex[:16]
                    parent_id = span.parent_span_id.hex() if span.parent_span_id else None
                    
                    # Attributes
                    attrs = {}
                    for a in span.attributes:
                        if a.value.HasField("string_value"):
                            attrs[a.key] = a.value.string_value
                        elif a.value.HasField("int_value"):
                            attrs[a.key] = a.value.int_value
                        elif a.value.HasField("double_value"):
                            attrs[a.key] = a.value.double_value
                        elif a.value.HasField("bool_value"):
                            attrs[a.key] = a.value.bool_value

                    # Duration in milliseconds
                    duration_ms = max(0.1, (span.end_time_unix_nano - span.start_time_unix_nano) / 1_000_000.0) if span.end_time_unix_nano > span.start_time_unix_nano else 10.0

                    events.append({
                        "event_type": "trace",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_id,
                        "service_name": service_name,
                        "message": f"Span: {span.name}",
                        "latency": round(duration_ms, 2),
                        "http_route": attrs.get("http.route") or attrs.get("http.target") or span.name,
                        "http_status": attrs.get("http.status_code"),
                        "http_method": attrs.get("http.method", "GET"),
                        "attributes": attrs,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
    except Exception:
        pass
    return events


def _extract_metrics_from_protobuf(body: bytes) -> List[Dict[str, Any]]:
    events = []
    try:
        req = ExportMetricsServiceRequest.FromString(body)
        for r_metric in req.resource_metrics:
            service_name = "customer-service"
            for attr in r_metric.resource.attributes:
                if attr.key == "service.name":
                    service_name = attr.value.string_value

            for s_metric in r_metric.scope_metrics:
                for m in s_metric.metrics:
                    val = 0.0
                    if m.HasField("gauge"):
                        for dp in m.gauge.data_points:
                            val = dp.as_double if dp.as_double != 0.0 else float(dp.as_int)
                    elif m.HasField("sum"):
                        for dp in m.sum.data_points:
                            val = dp.as_double if dp.as_double != 0.0 else float(dp.as_int)

                    events.append({
                        "event_type": "metric",
                        "service_name": service_name,
                        "metric_name": m.name,
                        "metric_value": round(val, 2),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "metrics": {m.name: round(val, 2)}
                    })
    except Exception:
        pass
    return events


def _extract_logs_from_protobuf(body: bytes) -> List[Dict[str, Any]]:
    events = []
    try:
        req = ExportLogsServiceRequest.FromString(body)
        for r_log in req.resource_logs:
            service_name = "customer-service"
            for attr in r_log.resource.attributes:
                if attr.key == "service.name":
                    service_name = attr.value.string_value

            for s_log in r_log.scope_logs:
                for l_rec in s_log.log_records:
                    body_str = l_rec.body.string_value if l_rec.body.HasField("string_value") else "OTel Log Record"
                    trace_id = l_rec.trace_id.hex() if l_rec.trace_id else None
                    span_id = l_rec.span_id.hex() if l_rec.span_id else None
                    severity = l_rec.severity_text or "INFO"
                    events.append({
                        "event_type": "log",
                        "service_name": service_name,
                        "severity": severity,
                        "message": body_str,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
    except Exception:
        pass
    return events


# =========================================================================
# COLLECTOR ENDPOINTS
# =========================================================================

@app.get("/health")
async def health():
    return {
        "status": "UP",
        "service": "customer-otel-collector",
        "port": 4318,
        "configured_tenant": collector_config.tenant_id,
        "api_key_configured": bool(collector_config.api_key),
        "gateway_url": collector_config.gateway_url,
        "queue_size": batch_queue.qsize()
    }


@app.get("/stats")
async def get_stats():
    return {
        "stats": stats,
        "config": {
            "gateway_url": collector_config.gateway_url,
            "tenant_id": collector_config.tenant_id,
            "api_key_set": bool(collector_config.api_key),
            "queue_depth": batch_queue.qsize()
        },
        "uptime_sec": round(time.time() - stats["start_time"], 2)
    }


@app.post("/configure")
async def configure_collector(payload: ConfigureRequest):
    if payload.api_key:
        collector_config.api_key = payload.api_key.strip()
    if payload.tenant_id:
        collector_config.tenant_id = payload.tenant_id.strip()
    if payload.gateway_url:
        collector_config.gateway_url = payload.gateway_url.rstrip("/")
    return {
        "message": "Collector configuration updated successfully",
        "tenant_id": collector_config.tenant_id,
        "api_key_set": bool(collector_config.api_key),
        "gateway_url": collector_config.gateway_url
    }


@app.post("/v1/traces")
async def receive_traces(request: Request):
    global stats
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    events = []

    if "application/x-protobuf" in content_type or (PROTOBUF_AVAILABLE and not content_type.startswith("application/json")):
        events = _extract_traces_from_protobuf(body)

    if not events:
        try:
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, list):
                events = payload
            elif "resourceSpans" in payload or "resource_spans" in payload:
                # OTLP JSON format
                spans_key = "resourceSpans" if "resourceSpans" in payload else "resource_spans"
                for rs in payload.get(spans_key, []):
                    res_attrs = {a.get("key"): a.get("value", {}).get("stringValue") for a in rs.get("resource", {}).get("attributes", [])}
                    svc = res_attrs.get("service.name", "customer-service")
                    scope_key = "scopeSpans" if "scopeSpans" in rs else "scope_spans"
                    for ss in rs.get(scope_key, []):
                        for sp in ss.get("spans", []):
                            events.append({
                                "event_type": "trace",
                                "service_name": svc,
                                "trace_id": sp.get("traceId") or sp.get("trace_id") or uuid.uuid4().hex,
                                "span_id": sp.get("spanId") or sp.get("span_id") or uuid.uuid4().hex[:16],
                                "parent_span_id": sp.get("parentSpanId") or sp.get("parent_span_id"),
                                "message": f"Span: {sp.get('name', 'operation')}",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
            else:
                events = [payload]
        except Exception:
            pass

    stats["traces_received"] += len(events) or 1
    for ev in events:
        ev["event_type"] = "trace"
        await batch_queue.put(ev)

    return Response(content=b"{}", media_type="application/json", status_code=status.HTTP_200_OK)


@app.post("/v1/metrics")
async def receive_metrics(request: Request):
    global stats
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    events = []

    if "application/x-protobuf" in content_type or (PROTOBUF_AVAILABLE and not content_type.startswith("application/json")):
        events = _extract_metrics_from_protobuf(body)

    if not events:
        try:
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, list):
                events = payload
            elif "metrics" in payload and isinstance(payload["metrics"], dict):
                # Custom microservice metric dictionary format
                svc = payload.get("service_name", "customer-service")
                for k, v in payload["metrics"].items():
                    events.append({
                        "event_type": "metric",
                        "service_name": svc,
                        "metric_name": k,
                        "metric_value": v,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "metrics": {k: v}
                    })
            elif "resource_metrics" in payload or "resourceMetrics" in payload:
                rm_key = "resource_metrics" if "resource_metrics" in payload else "resourceMetrics"
                for rm in payload.get(rm_key, []):
                    res_attrs = {a.get("key"): a.get("value", {}).get("string_value") or a.get("value", {}).get("stringValue") for a in rm.get("resource", {}).get("attributes", [])}
                    svc = res_attrs.get("service.name", "customer-service")
                    sm_key = "scope_metrics" if "scope_metrics" in rm else "scopeMetrics"
                    for sm in rm.get(sm_key, []):
                        for m in sm.get("metrics", []):
                            events.append({
                                "event_type": "metric",
                                "service_name": svc,
                                "metric_name": m.get("name"),
                                "metric_value": m.get("value", 0.0),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "metrics": {m.get("name"): m.get("value", 0.0)}
                            })
            else:
                events = [payload]
        except Exception:
            pass

    stats["metrics_received"] += len(events) or 1
    for ev in events:
        ev["event_type"] = "metric"
        await batch_queue.put(ev)

    return Response(content=b"{}", media_type="application/json", status_code=status.HTTP_200_OK)


@app.post("/v1/logs")
async def receive_logs(request: Request):
    global stats
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    events = []

    if "application/x-protobuf" in content_type or (PROTOBUF_AVAILABLE and not content_type.startswith("application/json")):
        events = _extract_logs_from_protobuf(body)

    if not events:
        try:
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, list):
                events = payload
            elif "resource_logs" in payload or "resourceLogs" in payload:
                rl_key = "resource_logs" if "resource_logs" in payload else "resourceLogs"
                for rl in payload.get(rl_key, []):
                    res_attrs = {a.get("key"): a.get("value", {}).get("string_value") or a.get("value", {}).get("stringValue") for a in rl.get("resource", {}).get("attributes", [])}
                    svc = res_attrs.get("service.name", "customer-service")
                    sl_key = "scope_logs" if "scope_logs" in rl else "scopeLogs"
                    for sl in rl.get(sl_key, []):
                        for lr in sl.get("log_records", []):
                            events.append({
                                "event_type": "log",
                                "service_name": svc,
                                "severity": lr.get("severity_text", "INFO"),
                                "message": lr.get("body", {}).get("string_value", "Log entry"),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
            else:
                events = [payload]
        except Exception:
            pass

    stats["logs_received"] += len(events) or 1
    for ev in events:
        ev["event_type"] = "log"
        await batch_queue.put(ev)

    return Response(content=b"{}", media_type="application/json", status_code=status.HTTP_200_OK)


@app.post("/flush")
async def flush_collector():
    """Immediately drains and forwards all queued events."""
    items = []
    while not batch_queue.empty():
        items.append(batch_queue.get_nowait())
    if items and collector_config.api_key:
        try:
            target_url = f"{collector_config.gateway_url}/batch"
            headers = {
                "X-API-Key": collector_config.api_key,
                "X-Tenant-ID": collector_config.tenant_id,
                "Content-Type": "application/json"
            }
            resp = await client.post(target_url, json=items, headers=headers)
            return {"status": "FLUSHED", "count": len(items), "gateway_status": resp.status_code}
        except Exception as exc:
            return {"status": "ERROR", "count": len(items), "error": str(exc)}
    return {"status": "EMPTY", "count": len(items)}


if __name__ == "__main__":
    port = int(os.getenv("OTEL_COLLECTOR_PORT", "4318"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
