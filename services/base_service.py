"""
Base Microservice for AegisOps AI Distributed Environment
Provides standard endpoints, metrics, structured JSON logging,
failure simulation, and remediation hooks.
"""

import os
import sys
import time
import json
import uuid
import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure data/logs directory exists
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "logs"))
os.makedirs(LOGS_DIR, exist_ok=True)

# OpenTelemetry SDK Integration
try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


class FailureRequest(BaseModel):
    type: str  # crash, high_cpu, memory_leak, latency_spike, error_spike, db_timeout, connection_exhaustion, log_explosion, storage_pressure, cascade_failure
    duration_sec: Optional[int] = 60
    intensity: Optional[float] = 1.0  # 0.0 to 1.0
    error_message: Optional[str] = None


class RemedyRequest(BaseModel):
    action: str  # restart, reset_connections, scale_workers, clear_cache, rotate_logs, compact_storage, rollback_config
    parameters: Optional[Dict[str, Any]] = None


class BaseService:
    _httpx_instrumented = False

    def __init__(self, name: str, port: int, role: str = "service", dependencies: Optional[List[str]] = None):
        self.name = os.getenv("SERVICE_NAME", name)
        self.port = port
        self.role = role
        self.dependencies = dependencies or []
        self.start_time = time.time()
        
        # State tracking
        self.is_running = True
        self.is_healthy = True
        self.status_state = "HEALTHY"  # HEALTHY, DEGRADED, UNHEALTHY, CRASHED
        self.failure_mode: Optional[str] = None
        self.failure_expires_at: Optional[float] = None
        self.failure_intensity: float = 0.0
        
        # Telemetry metrics
        self.request_count = 0
        self.error_count = 0
        self.recent_latencies: List[float] = []
        self.max_latency_history = 100
        self.active_connections = 0
        self.simulated_memory_mb = 128.0
        self.simulated_cpu_percent = 5.0
        self.memory_leak_buffer: List[bytes] = []
        
        # Setup structured logger
        self.log_file_path = os.path.join(LOGS_DIR, f"{self.name}.log")
        self.setup_logging()

        # Initialize FastAPI app
        self.app = FastAPI(
            title=f"AegisOps Microservice - {self.name}",
            description=f"Simulated {self.role} microservice for AegisOps AI SRE platform",
            version="1.0.0"
        )
        self.setup_middleware()
        self.setup_routes()

        # Setup OpenTelemetry SDK instrumentation & OTLP export
        self.tracer = None
        self.tracer_provider = None
        self.setup_opentelemetry()

        # Continuous background telemetry loop to local collector
        self._telemetry_task = None
        self._log_queue: List[Dict[str, Any]] = []
        self._setup_lifecycle()

    def _setup_lifecycle(self):
        @self.app.on_event("startup")
        async def on_startup():
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())

        @self.app.on_event("shutdown")
        async def on_shutdown():
            if self._telemetry_task:
                self._telemetry_task.cancel()

    async def _telemetry_loop(self):
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:8000/api/otel").rstrip("/")
        metrics_url = f"{endpoint}/v1/metrics"
        logs_url = f"{endpoint}/v1/logs"
        tenant_id = os.getenv("TENANT_ID", "fincore")
        headers = {"X-Tenant-ID": tenant_id}
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            while self.is_running:
                try:
                    await asyncio.sleep(1.5)
                    # Flush queued logs if any
                    if self._log_queue:
                        batch = self._log_queue[:25]
                        self._log_queue = self._log_queue[25:]
                        try:
                            await client.post(logs_url, json=batch, headers=headers)
                        except Exception:
                            pass

                    latencies = self.recent_latencies or [10.0]
                    sorted_lat = sorted(latencies)
                    p95 = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]
                    payload = {
                        "service_name": self.name,
                        "attributes": {
                            "service.name": self.name,
                            "service.instance.id": f"{self.name}-{self.port}",
                            "deployment.environment": os.getenv("ENVIRONMENT", "production")
                        },
                        "metrics": {
                            "cpu_percent": self.get_current_cpu(),
                            "memory_mb": self.get_current_memory(),
                            "active_connections": self.active_connections,
                            "request_count": self.request_count,
                            "error_count": self.error_count,
                            "latency_p95_ms": round(p95, 2)
                        }
                    }
                    await client.post(metrics_url, json=payload, headers=headers)
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

    def setup_opentelemetry(self):
        """Initializes OpenTelemetry SDK with OTLP HTTP exporter and FastAPI / HTTPX instrumentation."""
        if not OPENTELEMETRY_AVAILABLE:
            return

        if os.getenv("OTEL_SDK_DISABLED", "false").lower() in ("true", "1", "yes"):
            return

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:8000/api/otel")
        traces_endpoint = endpoint.rstrip("/")
        if not traces_endpoint.endswith("/v1/traces"):
            traces_endpoint = f"{traces_endpoint}/v1/traces"

        resource = Resource.create({
            "service.name": self.name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            "service.instance.id": f"{self.name}-{self.port}"
        })

        self.tracer_provider = TracerProvider(resource=resource)
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=traces_endpoint)
            span_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(span_processor)
        except Exception as exc:
            self.logger.warning(f"Failed to initialize OTLPSpanExporter: {exc}")

        self.tracer = self.tracer_provider.get_tracer(self.name, "1.0.0")

        # Instrument FastAPI app
        try:
            FastAPIInstrumentor.instrument_app(self.app, tracer_provider=self.tracer_provider)
        except Exception:
            pass

        # Inbound FastAPI instrumentation
        pass

    def setup_logging(self):
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        # Clear existing handlers
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log_event(self, level: str, event_type: str, message: str, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.name,
            "level": level.upper(),
            "event_type": event_type,
            "message": message,
            "trace_id": trace_id or str(uuid.uuid4()),
            "metadata": metadata or {}
        }
        self.logger.info(json.dumps(entry))

        # Add event to active OTel span if recording
        if OPENTELEMETRY_AVAILABLE:
            try:
                active_span = trace.get_current_span()
                if active_span and active_span.is_recording():
                    active_span.add_event(
                        name=event_type,
                        attributes={
                            "log.level": level.upper(),
                            "log.message": message,
                            "service.name": self.name
                        }
                    )
            except Exception:
                pass

        # Add log to buffer for background OTel emission
        if len(self._log_queue) < 100:
            self._log_queue.append(entry)

    def setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.app.middleware("http")
        async def telemetry_middleware(request: Request, call_next):
            start_t = time.time()
            self.active_connections += 1
            
            # Sync with OpenTelemetry W3C Trace context
            active_span = trace.get_current_span() if OPENTELEMETRY_AVAILABLE else None
            span_ctx = active_span.get_span_context() if active_span else None
            
            if span_ctx and span_ctx.is_valid:
                trace_id = format(span_ctx.trace_id, "032x")
                span_id = format(span_ctx.span_id, "016x")
                parent_span_id = request.headers.get("X-Parent-Span-ID")
            else:
                raw_traceparent = request.headers.get("traceparent")
                trace_id = request.headers.get("X-Trace-ID")
                parent_span_id = request.headers.get("X-Parent-Span-ID")
                
                if raw_traceparent and not trace_id:
                    parts = raw_traceparent.split("-")
                    if len(parts) >= 3:
                        trace_id = parts[1]
                        parent_span_id = parts[2]
                
                if not trace_id:
                    trace_id = uuid.uuid4().hex
                span_id = uuid.uuid4().hex[:16]

            # Enrich active OTel span with service metadata
            if active_span and active_span.is_recording():
                active_span.set_attribute("service.name", self.name)
                active_span.set_attribute("service.role", self.role)
                active_span.set_attribute("service.port", self.port)
                if self.failure_mode:
                    active_span.set_attribute("failure.mode", self.failure_mode)
                    active_span.set_attribute("failure.intensity", self.failure_intensity)
            
            # Check failure conditions
            self.check_failure_expiration()

            # Management endpoints (/remedy, /simulate/failure, /metrics, /health) bypass artificial fault injection
            if request.url.path in ["/remedy", "/simulate/failure", "/metrics", "/health"]:
                try:
                    resp = await call_next(request)
                    return resp
                finally:
                    self.active_connections = max(0, self.active_connections - 1)
            
            # Crash simulation: immediately return 503 or disconnect
            crash_modes = ["crash", "service_a_crash", "service_b_crash"]
            if (self.failure_mode in crash_modes) or not self.is_running:
                self.active_connections = max(0, self.active_connections - 1)
                self.error_count += 1
                if active_span and active_span.is_recording():
                    active_span.set_status(StatusCode.ERROR, f"Service {self.name} is down (simulated crash)")
                self.log_event("ERROR", "SERVICE_UNAVAILABLE", f"Service {self.name} is down (simulated crash)", trace_id, {"span_id": span_id, "parent_span_id": parent_span_id})
                return Response(
                    content=json.dumps({"error": f"Service {self.name} unavailable (simulated crash)", "service": self.name}),
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    media_type="application/json"
                )

            # High Latency & Slow Response Behavior
            latency_modes = ["latency_spike", "database_latency_spike", "network_latency_spike", "slow_response_behavior"]
            if self.failure_mode in latency_modes:
                extra_delay = (2.2 + random.random() * 1.5) * self.failure_intensity
                await asyncio.sleep(extra_delay)
            elif self.failure_mode in ["behavioral_latency_anomaly", "behavioral_anomaly_without_error_logs"]:
                # Pure behavioral anomaly: subtle latency distribution shift without error logs or 5xx codes
                extra_delay = (0.28 + random.random() * 0.18) * self.failure_intensity
                await asyncio.sleep(extra_delay)
            elif self.failure_mode in ["high_cpu", "cpu_spike"]:
                self.simulated_cpu_percent = min(98.0, 75.0 + random.uniform(10.0, 22.0) * self.failure_intensity)
                burn_target = time.time() + (0.05 * self.failure_intensity)
                while time.time() < burn_target:
                    _ = [x * x for x in range(2000)]
            elif self.failure_mode in ["thread_pool_exhaustion"]:
                await asyncio.sleep(1.2 * self.failure_intensity)
                if random.random() < 0.4:
                    self.error_count += 1
                    return Response(
                        content=json.dumps({"error": "Thread pool exhausted: task rejected", "service": self.name}),
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        media_type="application/json"
                    )
            elif self.failure_mode in ["dependency_timeout", "db_timeout", "payment_dependency_failure"]:
                await asyncio.sleep(3.5 * self.failure_intensity)
                self.error_count += 1
                return Response(
                    content=json.dumps({"error": "Gateway/Dependency Timeout: upstream failed to respond within 3500ms", "service": self.name}),
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    media_type="application/json"
                )
            elif self.failure_mode in ["cache_failure", "redis_connection_failure"]:
                await asyncio.sleep(0.4 * self.failure_intensity)
                if random.random() < (0.80 * self.failure_intensity):
                    self.error_count += 1
                    if active_span and active_span.is_recording():
                        active_span.set_status(StatusCode.ERROR, f"Redis connection failure in {self.name}")
                    self.log_event("ERROR", "REDIS_CONNECTION_FAILURE", f"Redis connection pool timeout / cache cluster read failure in {self.name}", trace_id, {"span_id": span_id})
                    return Response(
                        content=json.dumps({"error": "Redis connection failure / cache cluster read timeout", "service": self.name, "trace_id": trace_id}),
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        media_type="application/json"
                    )
            elif self.failure_mode in ["traffic_spike"]:
                self.request_count += 3
                await asyncio.sleep(0.15)

            # Error injection
            error_5xx_modes = ["error_spike", "high_http_5xx_rate", "database_query_failure", "error_rate_spike", "cascade_failure"]
            if self.failure_mode in error_5xx_modes:
                if random.random() < (0.8 * self.failure_intensity):
                    self.active_connections = max(0, self.active_connections - 1)
                    self.error_count += 1
                    if active_span and active_span.is_recording():
                        active_span.set_status(StatusCode.ERROR, f"Simulated internal failure in {self.name}")
                    self.log_event("ERROR", "HTTP_500_INTERNAL_ERROR", f"Simulated internal failure in {self.name}", trace_id, {"span_id": span_id})
                    return Response(
                        content=json.dumps({"error": "Internal Server Error", "service": self.name, "trace_id": trace_id}),
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        media_type="application/json"
                    )

            if self.failure_mode in ["high_http_503_rate"]:
                if random.random() < (0.75 * self.failure_intensity):
                    self.active_connections = max(0, self.active_connections - 1)
                    self.error_count += 1
                    return Response(
                        content=json.dumps({"error": "Service temporarily overloaded (HTTP 503)", "service": self.name}),
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        media_type="application/json"
                    )

            try:
                response = await call_next(request)
                elapsed_ms = (time.time() - start_t) * 1000
                self.request_count += 1
                self.recent_latencies.append(elapsed_ms)
                if len(self.recent_latencies) > self.max_latency_history:
                    self.recent_latencies.pop(0)
                
                if response.status_code >= 400:
                    self.error_count += 1
                    if active_span and active_span.is_recording():
                        active_span.set_status(StatusCode.ERROR, f"HTTP status {response.status_code}")
                
                # Emit normal behavioral log or latency deviation log
                if self.failure_mode == "behavioral_latency_anomaly" and elapsed_ms > 1500:
                    self.log_event("INFO", "BEHAVIORAL_LATENCY_SHIFT", f"Request processed with high latency ({elapsed_ms:.1f}ms)", trace_id, {"latency_ms": elapsed_ms, "span_id": span_id})
                
                response.headers["X-Trace-ID"] = trace_id
                response.headers["X-Span-ID"] = span_id
                response.headers["X-Service-Name"] = self.name
                response.headers["traceparent"] = f"00-{trace_id}-{span_id}-01"
                return response
            except Exception as exc:
                self.error_count += 1
                if active_span and active_span.is_recording():
                    active_span.record_exception(exc)
                    active_span.set_status(StatusCode.ERROR, str(exc))
                self.log_event("ERROR", "UNHANDLED_EXCEPTION", str(exc), trace_id, {"span_id": span_id})
                raise exc
            finally:
                self.active_connections = max(0, self.active_connections - 1)

    def check_failure_expiration(self):
        if self.failure_expires_at and time.time() > self.failure_expires_at:
            prev_mode = self.failure_mode
            self.failure_mode = None
            self.failure_expires_at = None
            self.failure_intensity = 0.0
            self.status_state = "HEALTHY"
            self.is_healthy = True
            self.log_event("INFO", "FAILURE_EXPIRED", f"Failure simulation '{prev_mode}' timed out. State restored to HEALTHY.")

    def setup_routes(self):
        @self.app.get("/health")
        async def health():
            self.check_failure_expiration()
            is_ok = self.is_running and (self.failure_mode != "crash") and (self.status_state != "CRASHED")
            status_code = status.HTTP_200_OK if is_ok else status.HTTP_503_SERVICE_UNAVAILABLE
            return Response(
                content=json.dumps({
                    "status": "UP" if is_ok else "DOWN",
                    "service": self.name,
                    "role": self.role,
                    "healthy": is_ok,
                    "state": self.status_state,
                    "failure_mode": self.failure_mode,
                    "uptime_seconds": round(time.time() - self.start_time, 2),
                    "version": "1.0.0"
                }),
                status_code=status_code,
                media_type="application/json"
            )

        @self.app.get("/status")
        async def get_status():
            self.check_failure_expiration()
            return {
                "service": self.name,
                "role": self.role,
                "port": self.port,
                "dependencies": self.dependencies,
                "status": self.status_state,
                "is_running": self.is_running,
                "failure_mode": self.failure_mode,
                "failure_expires_in_sec": round(max(0, self.failure_expires_at - time.time()), 1) if self.failure_expires_at else 0,
                "uptime_seconds": round(time.time() - self.start_time, 2),
                "metrics_summary": {
                    "total_requests": self.request_count,
                    "total_errors": self.error_count,
                    "active_connections": self.active_connections,
                    "simulated_cpu_percent": self.get_current_cpu(),
                    "simulated_memory_mb": self.get_current_memory(),
                }
            }

        @self.app.get("/metrics")
        async def get_metrics():
            self.check_failure_expiration()
            latencies = self.recent_latencies or [5.0]
            sorted_lat = sorted(latencies)
            p50 = sorted_lat[int(len(sorted_lat) * 0.5)]
            p95 = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]
            p99 = sorted_lat[min(int(len(sorted_lat) * 0.99), len(sorted_lat) - 1)]
            
            error_rate = (self.error_count / max(1, self.request_count)) if self.request_count > 0 else 0.0
            
            return {
                "service": self.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": self.status_state,
                "healthy": self.is_healthy and (self.failure_mode != "crash"),
                "cpu_percent": self.get_current_cpu(),
                "memory_mb": self.get_current_memory(),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": round(error_rate, 4),
                "latency_p50_ms": round(p50, 2),
                "latency_p95_ms": round(p95, 2),
                "latency_p99_ms": round(p99, 2),
                "active_connections": self.active_connections,
                "uptime_seconds": round(time.time() - self.start_time, 2)
            }

        @self.app.post("/simulate/failure")
        async def simulate_failure(payload: FailureRequest):
            self.failure_mode = payload.type
            self.failure_intensity = payload.intensity or 1.0
            self.failure_expires_at = time.time() + (payload.duration_sec or 60)
            
            if payload.type in ["crash", "service_a_crash", "service_b_crash"]:
                self.is_running = False
                self.is_healthy = False
                self.status_state = "CRASHED"
                self.log_event("CRITICAL", "SERVICE_CRASHED", f"Service {self.name} simulated crash triggered")
            elif payload.type in ["high_cpu", "cpu_spike"]:
                self.status_state = "DEGRADED"
                self.simulated_cpu_percent = 92.0
                self.log_event("WARNING", "HIGH_CPU_LOAD", f"High CPU simulation started on {self.name} (intensity {self.failure_intensity})")
            elif payload.type in ["memory_leak", "memory_pressure"]:
                self.status_state = "DEGRADED"
                for _ in range(5):
                    self.memory_leak_buffer.append(b"0" * 1024 * 1024 * 10)  # 50MB
                self.simulated_memory_mb += 350 * self.failure_intensity
                self.log_event("WARNING", "MEMORY_PRESSURE", f"Memory pressure/leak simulation on {self.name}")
            elif payload.type in ["latency_spike", "database_latency_spike", "network_latency_spike", "slow_response_behavior"]:
                self.status_state = "DEGRADED"
                self.recent_latencies = [2400.0, 3100.0, 2800.0, 3500.0]
                self.log_event("WARNING", "LATENCY_SPIKE", f"Artificial latency spike injected into {self.name}")
            elif payload.type in ["behavioral_latency_anomaly", "behavioral_anomaly_without_error_logs"]:
                self.status_state = "HEALTHY"  # Notice: Health check passes, no error logs!
                self.recent_latencies = [320.0, 360.0, 290.0, 410.0]
                self.log_event("INFO", "BEHAVIORAL_ANOMALY_INJECTED", f"Subtle latency degradation injected into {self.name} (no explicit error logs)")
            elif payload.type in ["error_spike", "high_http_5xx_rate", "error_rate_spike"]:
                self.status_state = "UNHEALTHY"
                self.error_count += 15
                self.log_event("ERROR", "ERROR_STORM", f"Error rate spike injected into {self.name}")
            elif payload.type in ["high_http_503_rate"]:
                self.status_state = "UNHEALTHY"
                self.error_count += 12
                self.log_event("ERROR", "HTTP_503_STORM", f"HTTP 503 service unavailable storm on {self.name}")
            elif payload.type in ["dependency_timeout", "db_timeout", "payment_dependency_failure"]:
                self.status_state = "DEGRADED"
                self.error_count += 8
                self.log_event("ERROR", "DEPENDENCY_TIMEOUT", f"Downstream dependency timeout simulation on {self.name}")
            elif payload.type in ["connection_exhaustion", "connection_pool_exhaustion"]:
                self.status_state = "DEGRADED"
                self.active_connections = 20
                self.log_event("ERROR", "CONNECTION_POOL_EXHAUSTED", f"Connection pool exhaustion on {self.name}")
            elif payload.type in ["thread_pool_exhaustion"]:
                self.status_state = "DEGRADED"
                self.active_connections = 18
                self.log_event("WARNING", "THREAD_POOL_SATURATED", f"Thread pool capacity exhausted on {self.name}")
            elif payload.type in ["cache_failure", "redis_connection_failure"]:
                self.status_state = "UNHEALTHY"
                self.error_count += 15
                self.log_event("ERROR", "REDIS_CONNECTION_FAILURE", f"Redis connection pool exhausted / cache cluster partition on {self.name}")
            elif payload.type in ["traffic_spike"]:
                self.status_state = "DEGRADED"
                self.request_count += 50
                self.log_event("INFO", "TRAFFIC_SURGE", f"Inbound request volume surge on {self.name}")
            elif payload.type in ["database_query_failure"]:
                self.status_state = "UNHEALTHY"
                self.error_count += 10
                self.log_event("ERROR", "SQL_EXECUTION_FAILURE", f"Database query deadlock / statement abort on {self.name}")
            elif payload.type in ["cascading_service_degradation"]:
                self.status_state = "DEGRADED"
                self.error_count += 10
                self.log_event("ERROR", "CASCADE_DEGRADATION", f"Cascading upstream saturation initiated on {self.name}")
            elif payload.type == "log_explosion":
                self.status_state = "HEALTHY"
                for i in range(100):
                    self.log_event("ERROR", "REPEATED_LOG_BURST", f"Database transaction connection lock timeout ref-{i % 5}")
            elif payload.type == "storage_pressure":
                self.status_state = "DEGRADED"
                self.log_event("WARNING", "STORAGE_EXHAUSTION_WARNING", f"Disk capacity nearing threshold on {self.name}")
            else:
                self.status_state = "DEGRADED"
                self.log_event("WARNING", "GENERIC_ANOMALY", f"Simulation {payload.type} triggered on {self.name}")

            return {
                "message": f"Failure simulation '{payload.type}' applied to {self.name}",
                "service": self.name,
                "failure_mode": self.failure_mode,
                "intensity": self.failure_intensity,
                "expires_in_sec": payload.duration_sec
            }

        @self.app.post("/remedy")
        async def execute_remedy(payload: RemedyRequest):
            action = payload.action.lower()
            prev_mode = self.failure_mode
            
            if action == "restart":
                self.is_running = True
                self.is_healthy = True
                self.status_state = "HEALTHY"
                self.failure_mode = None
                self.failure_expires_at = None
                self.failure_intensity = 0.0
                self.error_count = 0
                self.request_count = 0
                self.active_connections = 0
                self.simulated_memory_mb = 128.0
                self.memory_leak_buffer.clear()
                self.recent_latencies = [12.0, 15.0, 10.0]
                self.log_event("INFO", "SERVICE_RESTARTED", f"Service {self.name} successfully restarted and state restored.")
                return {"success": True, "action": action, "service": self.name, "result": "Service restarted and metrics reset to baseline"}
                
            elif action == "reset_connections":
                self.active_connections = 2
                self.is_running = True
                self.is_healthy = True
                self.error_count = 0
                if self.failure_mode in ["connection_exhaustion", "db_timeout"]:
                    self.failure_mode = None
                    self.status_state = "HEALTHY"
                self.log_event("INFO", "CONNECTION_POOL_RESET", f"Connection pool on {self.name} flushed and reset.")
                return {"success": True, "action": action, "service": self.name, "result": "Connection pool reset"}

            elif action == "scale_workers":
                self.simulated_cpu_percent = 15.0
                self.is_running = True
                self.is_healthy = True
                self.error_count = 0
                if self.failure_mode == "high_cpu":
                    self.failure_mode = None
                    self.status_state = "HEALTHY"
                self.log_event("INFO", "WORKERS_SCALED", f"Scaled worker threads on {self.name} to handle load.")
                return {"success": True, "action": action, "service": self.name, "result": "Worker capacity doubled, CPU pressure relieved"}

            elif action == "clear_cache":
                self.simulated_memory_mb = 128.0
                self.memory_leak_buffer.clear()
                self.is_running = True
                self.is_healthy = True
                self.error_count = 0
                if self.failure_mode == "memory_leak":
                    self.failure_mode = None
                    self.status_state = "HEALTHY"
                self.log_event("INFO", "CACHE_PURGED", f"Memory caches cleared and buffers flushed on {self.name}.")
                return {"success": True, "action": action, "service": self.name, "result": "Memory cache cleared"}

            elif action == "rotate_logs":
                self.log_event("INFO", "LOGS_ROTATED", f"Log rotation triggered on {self.name}.")
                return {"success": True, "action": action, "service": self.name, "result": "Logs rotated successfully"}

            elif action == "compact_storage":
                self.log_event("INFO", "STORAGE_COMPACTED", f"Storage tables compacted on {self.name}.")
                return {"success": True, "action": action, "service": self.name, "result": "Storage compacted and reclaimed"}

            elif action == "rollback_config":
                self.failure_mode = None
                self.is_running = True
                self.is_healthy = True
                self.error_count = 0
                self.status_state = "HEALTHY"
                self.log_event("INFO", "CONFIG_ROLLBACK", f"Configuration rolled back to last known good snapshot on {self.name}.")
                return {"success": True, "action": action, "service": self.name, "result": "Configuration restored"}

            else:
                self.failure_mode = None
                self.is_running = True
                self.is_healthy = True
                self.status_state = "HEALTHY"
                return {"success": True, "action": action, "service": self.name, "result": f"Generic remedy {action} applied"}

    def get_current_cpu(self) -> float:
        if self.failure_mode == "high_cpu":
            return round(85.0 + random.random() * 12.0 * self.failure_intensity, 1)
        elif self.failure_mode == "crash" or not self.is_running:
            return 0.0
        elif self.failure_mode == "latency_spike":
            return round(20.0 + random.random() * 10.0, 1)
        base = 8.0 + (self.active_connections * 1.5) + (random.random() * 4.0)
        return round(min(100.0, base), 1)

    def get_current_memory(self) -> float:
        if self.failure_mode == "memory_leak":
            return round(self.simulated_memory_mb + (random.random() * 20.0), 1)
        elif self.failure_mode == "crash" or not self.is_running:
            return 0.0
        base = 120.0 + (self.active_connections * 4.0) + (random.random() * 8.0)
        return round(base, 1)
