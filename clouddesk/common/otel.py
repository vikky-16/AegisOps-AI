"""
CloudDesk OpenTelemetry Instrumentation
Provides distributed tracing, W3C trace propagation, metric recording, and OTLP export.
Enforces tenant_id="clouddesk", propagates traceparent, X-Request-ID, and X-Tenant-ID across cloud service calls.
"""

import os
import uuid
import time
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from opentelemetry import trace, metrics
    from opentelemetry.trace import Tracer, Span, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

TENANT_ID = os.getenv("TENANT_ID", "clouddesk")
IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_OTEL_URL = "http://otel-collector:4318" if IN_DOCKER else "http://127.0.0.1:8000/api/otel"
OTEL_COLLECTOR_URL = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTEL_URL).rstrip("/")
API_KEY = os.getenv("AEGISOPS_API_KEY", "agt_live_clouddesk_xxxx9999yyyy8888zzzz")
W3C_PROPAGATOR = TraceContextTextMapPropagator() if OTEL_AVAILABLE else None


def setup_otel(service_name: str):
    if not OTEL_AVAILABLE:
        return None, None

    resource = Resource.create({
        "service.name": service_name,
        "service.namespace": "clouddesk",
        "tenant_id": TENANT_ID,
        "environment": os.getenv("ENVIRONMENT", "production"),
        "company.name": "CloudDesk SaaS Platform"
    })

    otlp_headers = {
        "X-Tenant-ID": TENANT_ID,
        "X-API-Key": API_KEY
    }

    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{OTEL_COLLECTOR_URL}/v1/traces",
        headers=otlp_headers
    )
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=f"{OTEL_COLLECTOR_URL}/v1/metrics",
            headers=otlp_headers
        ),
        export_interval_millis=2000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    tracer = trace.get_tracer(service_name)
    meter = metrics.get_meter(service_name)
    return tracer, meter


class TraceContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str, logger):
        super().__init__(app)
        self.service_name = service_name
        self.logger = logger
        self.tracer = trace.get_tracer(service_name) if OTEL_AVAILABLE else None

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = request.headers.get("x-request-id") or f"cloud-req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        trace_id = None
        span_id = None
        traceparent = request.headers.get("traceparent")

        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 4:
                trace_id = parts[1]
                span_id = parts[2]
        
        if not trace_id:
            trace_id = uuid.uuid4().hex
            span_id = uuid.uuid4().hex[:16]

        request.state.trace_id = trace_id
        request.state.span_id = span_id

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Tenant-ID"] = TENANT_ID

            self.logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
                extra={
                    "service": self.service_name,
                    "event_type": "http_request",
                    "http_method": request.method,
                    "http_route": request.url.path,
                    "route": request.url.path,
                    "http_status": response.status_code,
                    "status_code": response.status_code,
                    "latency_ms": duration_ms,
                    "latency": duration_ms,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                }
            )
            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            self.logger.error(
                f"Unhandled error in {request.method} {request.url.path}: {str(exc)}",
                exc_info=True,
                extra={
                    "service": self.service_name,
                    "event_type": "unhandled_exception",
                    "http_method": request.method,
                    "http_route": request.url.path,
                    "route": request.url.path,
                    "http_status": 500,
                    "status_code": 500,
                    "latency_ms": duration_ms,
                    "latency": duration_ms,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)
                }
            )
            raise exc


def get_outgoing_headers(request: Request) -> Dict[str, str]:
    req_id = getattr(request.state, "request_id", f"cloud-req-{uuid.uuid4().hex[:12]}")
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
    span_id = uuid.uuid4().hex[:16]

    return {
        "x-request-id": req_id,
        "x-tenant-id": TENANT_ID,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "x-trace-id": trace_id
    }
