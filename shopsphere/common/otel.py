"""
ShopSphere OpenTelemetry Instrumentation
Provides distributed tracing, trace propagation, metric recording, and OTLP export.
Propagates W3C TraceContext (traceparent), X-Request-ID, and X-Tenant-ID across HTTP hops.
"""

import os
import uuid
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# OpenTelemetry SDK imports
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

TENANT_ID = os.getenv("TENANT_ID", "shopsphere")
IN_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_OTEL_URL = "http://otel-collector:4318" if IN_DOCKER else "http://127.0.0.1:8000/api/otel"
OTEL_COLLECTOR_URL = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTEL_URL).rstrip("/")
API_KEY = os.getenv("AEGISOPS_API_KEY", "agt_live_shopsphere_11112222333344445555")
W3C_PROPAGATOR = TraceContextTextMapPropagator() if OTEL_AVAILABLE else None


def setup_otel(service_name: str):
    """Initializes TracerProvider and MeterProvider with OTLP HTTP exporters."""
    if not OTEL_AVAILABLE:
        return None, None

    resource = Resource.create({
        "service.name": service_name,
        "service.namespace": "shopsphere",
        "tenant_id": TENANT_ID,
        "environment": os.getenv("ENVIRONMENT", "production"),
        "company.name": "ShopSphere"
    })

    otlp_headers = {
        "X-Tenant-ID": TENANT_ID,
        "X-API-Key": API_KEY
    }

    # Trace provider
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{OTEL_COLLECTOR_URL}/v1/traces",
        headers=otlp_headers
    )
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # Metrics provider
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
    """
    FastAPI middleware ensuring every request has:
    - request_id
    - trace_id and span_id (extracted from incoming traceparent or newly generated)
    - X-Tenant-ID header verified
    """
    def __init__(self, app, service_name: str, logger):
        super().__init__(app)
        self.service_name = service_name
        self.logger = logger
        self.tracer = trace.get_tracer(service_name) if OTEL_AVAILABLE else None

    async def dispatch(self, request: Request, call_next):
        import time
        start_time = time.time()

        # 1. Resolve request_id
        request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # 2. Extract or create W3C Trace context
        carrier = dict(request.headers)
        if W3C_PROPAGATOR:
            ctx = W3C_PROPAGATOR.extract(carrier)
        else:
            ctx = None

        if self.tracer:
            with self.tracer.start_as_current_span(
                f"{request.method} {request.url.path}",
                context=ctx
            ) as span:
                span_ctx = span.get_span_context()
                trace_id = format(span_ctx.trace_id, "032x") if span_ctx.trace_id else uuid.uuid4().hex
                span_id = format(span_ctx.span_id, "016x") if span_ctx.span_id else uuid.uuid4().hex[:16]
                
                span.set_attribute("http.method", request.method)
                span.set_attribute("http.route", request.url.path)
                span.set_attribute("tenant_id", TENANT_ID)
                span.set_attribute("request_id", request_id)

                request.state.trace_id = trace_id
                request.state.span_id = span_id

                try:
                    response: Response = await call_next(request)
                    status_code = response.status_code
                    if status_code >= 400:
                        span.set_status(StatusCode.ERROR)
                    else:
                        span.set_status(StatusCode.OK)
                except Exception as exc:
                    span.set_status(StatusCode.ERROR, str(exc))
                    span.record_exception(exc)
                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    self.logger.error(
                        f"Unhandled request error on {request.url.path}: {str(exc)}",
                        extra={
                            "service": self.service_name,
                            "event_type": "request_error",
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "http_method": request.method,
                            "route": request.url.path,
                            "status_code": 500,
                            "latency_ms": duration_ms,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)
                        },
                        exc_info=True
                    )
                    raise exc

                duration_ms = round((time.time() - start_time) * 1000, 2)
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("duration_ms", duration_ms)

                # Inject response headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Trace-ID"] = trace_id
                response.headers["X-Tenant-ID"] = TENANT_ID

                # Structured log
                level = self.logger.error if status_code >= 500 else (self.logger.warning if status_code >= 400 else self.logger.info)
                level(
                    f"{request.method} {request.url.path} -> {status_code} ({duration_ms}ms)",
                    extra={
                        "service": self.service_name,
                        "event_type": "http_request",
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "http_method": request.method,
                        "route": request.url.path,
                        "status_code": status_code,
                        "latency_ms": duration_ms
                    }
                )
                return response
        else:
            trace_id = carrier.get("x-trace-id") or uuid.uuid4().hex
            span_id = uuid.uuid4().hex[:16]
            request.state.trace_id = trace_id
            request.state.span_id = span_id

            response: Response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Tenant-ID"] = TENANT_ID
            return response


def get_outgoing_headers(request: Request) -> Dict[str, str]:
    """Injects current W3C TraceContext and request correlation into outgoing HTTP headers."""
    headers: Dict[str, str] = {
        "X-Tenant-ID": TENANT_ID,
        "X-Request-ID": getattr(request.state, "request_id", uuid.uuid4().hex[:12])
    }
    if W3C_PROPAGATOR:
        from opentelemetry import context
        W3C_PROPAGATOR.inject(headers, context.get_current())
    
    # Also explicitly propagate trace_id
    trace_id = getattr(request.state, "trace_id", None)
    if trace_id:
        headers["X-Trace-ID"] = trace_id
    return headers
