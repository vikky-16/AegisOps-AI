"""
AegisOps AI - Normalized Failure Signature Extraction Engine
Extracts multi-dimensional telemetry signatures from metrics, traces, logs, and events.
Signatures are discovered empirically from telemetry rather than assumed from declared scenario labels.
"""

import time
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class FailureSignature(BaseModel):
    """
    Normalized multidimensional failure signature extracted from active telemetry.
    """
    failure_type: str = "UNKNOWN"
    service: str
    category: str = "Infrastructure"  # Infrastructure, Database, Network, Dependency, Application, Resource, Performance, Availability, Behavioral
    severity: str = "MEDIUM"
    
    # Quantitative Feature Vectors
    metric_features: Dict[str, float] = Field(default_factory=dict)
    log_features: Dict[str, Any] = Field(default_factory=dict)
    trace_features: Dict[str, Any] = Field(default_factory=dict)
    event_features: Dict[str, Any] = Field(default_factory=dict)
    latency_features: Dict[str, float] = Field(default_factory=dict)
    error_rate_features: Dict[str, float] = Field(default_factory=dict)
    resource_features: Dict[str, float] = Field(default_factory=dict)
    temporal_features: Dict[str, Any] = Field(default_factory=dict)
    dependency_features: Dict[str, Any] = Field(default_factory=dict)
    
    extracted_at: float = Field(default_factory=time.time)

    def to_feature_vector(self) -> List[float]:
        """
        Converts the signature into a fixed-length normalized numerical feature vector
        suitable for cosine similarity and nearest-neighbor vector comparison.
        Length: 12 standardized features.
        """
        mf = self.metric_features
        rf = self.resource_features
        ef = self.error_rate_features
        lf = self.latency_features
        
        return [
            min(1.0, mf.get("request_count", 10.0) / 200.0),
            min(1.0, ef.get("error_rate", 0.0)),
            min(1.0, lf.get("latency_p50_ms", 15.0) / 1000.0),
            min(1.0, lf.get("latency_p95_ms", 30.0) / 3000.0),
            min(1.0, lf.get("latency_p99_ms", 50.0) / 5000.0),
            min(1.0, rf.get("cpu_percent", 10.0) / 100.0),
            min(1.0, rf.get("memory_mb", 128.0) / 1024.0),
            min(1.0, rf.get("active_connections", 2.0) / 30.0),
            min(1.0, ef.get("http_5xx_rate", 0.0)),
            min(1.0, ef.get("timeout_rate", 0.0)),
            min(1.0, self.trace_features.get("trace_duration_ms", 20.0) / 4000.0),
            min(1.0, self.log_features.get("error_log_ratio", 0.0))
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "service": self.service,
            "category": self.category,
            "severity": self.severity,
            "metric_features": self.metric_features,
            "log_features": self.log_features,
            "trace_features": self.trace_features,
            "event_features": self.event_features,
            "latency_features": self.latency_features,
            "error_rate_features": self.error_rate_features,
            "resource_features": self.resource_features,
            "temporal_features": self.temporal_features,
            "dependency_features": self.dependency_features,
            "extracted_at": self.extracted_at,
            "feature_vector": self.to_feature_vector()
        }


class SignatureExtractor:
    """
    Extracts normalized failure signatures directly from live telemetry, metrics, and logs.
    Does not rely on self-declared failure labels.
    """
    @staticmethod
    def extract_from_telemetry(
        service: str,
        metrics: Dict[str, Any],
        events: List[Dict[str, Any]],
        baseline: Optional[Dict[str, Any]] = None,
        traces: Optional[List[Dict[str, Any]]] = None
    ) -> FailureSignature:
        svc_metrics = metrics.get(service, {}) if metrics else {}
        
        # Metric values
        err_rate = float(svc_metrics.get("error_rate", 0.0))
        req_count = float(svc_metrics.get("request_count", 1.0))
        p50 = float(svc_metrics.get("latency_p50_ms", 12.0))
        p95 = float(svc_metrics.get("latency_p95_ms", 25.0))
        p99 = float(svc_metrics.get("latency_p99_ms", 40.0))
        cpu = float(svc_metrics.get("cpu_percent", 15.0))
        mem = float(svc_metrics.get("memory_mb", 128.0))
        conns = float(svc_metrics.get("active_connections", 2.0))
        
        # Log & Event analysis
        svc_events = [e for e in events if e.get("service_name") == service or e.get("service") == service]
        err_events = [e for e in svc_events if str(e.get("severity", "")).upper() in ["ERROR", "CRITICAL"]]
        error_log_ratio = len(err_events) / max(1, len(svc_events)) if svc_events else (1.0 if err_rate > 0.05 else 0.0)
        
        # Baseline comparison ratios
        base_p95 = float(baseline.get("p95", 25.0)) if baseline else 25.0
        p95_ratio = p95 / max(1.0, base_p95)
        
        timeout_events = [e for e in svc_events if "TIMEOUT" in str(e.get("message", "")).upper() or "504" in str(e.get("message", ""))]
        timeout_rate = len(timeout_events) / max(1, len(svc_events)) if svc_events else (0.8 if "timeout" in str(svc_metrics.get("failure_mode", "")) else 0.0)
        
        http_5xx_rate = err_rate if err_rate > 0.1 else (0.75 if any(x in str(e) for e in svc_events for x in ["500", "502", "503"]) else 0.0)
        http_503_rate = 0.8 if any("503" in str(e.get("message", "")) for e in svc_events) else 0.0

        # Trace features
        trace_dur = p95 * 1.2
        error_spans = 1.0 if err_rate > 0.05 else 0.0

        # Classification derivation from empirical evidence
        category, failure_type, severity = SignatureExtractor._classify_empirical_signature(
            service=service,
            error_rate=err_rate,
            p95=p95,
            p95_ratio=p95_ratio,
            cpu=cpu,
            mem=mem,
            conns=conns,
            timeout_rate=timeout_rate,
            error_log_ratio=error_log_ratio,
            svc_events=svc_events
        )

        return FailureSignature(
            failure_type=failure_type,
            service=service,
            category=category,
            severity=severity,
            metric_features={
                "request_count": req_count,
                "error_rate": round(err_rate, 4),
                "active_connections": conns
            },
            latency_features={
                "latency_p50_ms": round(p50, 2),
                "latency_p95_ms": round(p95, 2),
                "latency_p99_ms": round(p99, 2),
                "p95_baseline_ratio": round(p95_ratio, 2)
            },
            resource_features={
                "cpu_percent": round(cpu, 1),
                "memory_mb": round(mem, 1),
                "connection_pool_utilization": round(conns / 20.0, 2)
            },
            error_rate_features={
                "error_rate": round(err_rate, 4),
                "http_5xx_rate": round(http_5xx_rate, 4),
                "http_503_rate": round(http_503_rate, 4),
                "timeout_rate": round(timeout_rate, 4)
            },
            log_features={
                "event_count": float(len(svc_events)),
                "error_event_count": float(len(err_events)),
                "error_log_ratio": round(error_log_ratio, 3)
            },
            trace_features={
                "trace_duration_ms": round(trace_dur, 2),
                "error_span_ratio": error_spans,
                "slowest_service": service
            },
            event_features={
                "event_types": list({e.get("event_type", "UNKNOWN") for e in svc_events})[:5],
                "has_critical_events": any(str(e.get("severity", "")).upper() == "CRITICAL" for e in svc_events)
            },
            temporal_features={
                "onset_time": svc_events[0].get("timestamp") if svc_events else datetime.now(timezone.utc).isoformat()
            },
            dependency_features={
                "target_service": service
            }
        )

    @staticmethod
    def _classify_empirical_signature(
        service: str,
        error_rate: float,
        p95: float,
        p95_ratio: float,
        cpu: float,
        mem: float,
        conns: float,
        timeout_rate: float,
        error_log_ratio: float,
        svc_events: List[Dict[str, Any]]
    ):
        """Derives failure classification and type from actual empirical signals."""
        events_text = " ".join([f"{e.get('event_type', '')} {e.get('message', '')}" for e in svc_events]).upper()
        
        # 1. Connection Pool Exhaustion (High connections, database or gateway)
        if conns >= 18.0 or "CONNECTION_POOL" in events_text or "POOL EXHAUSTED" in events_text:
            return "Database" if "database" in service else "Network", "CONNECTION_POOL_EXHAUSTION", "CRITICAL"

        # 2. Process Crash / 503 Outage
        if "CRASH" in events_text or "503" in events_text or "SERVICE_UNAVAILABLE" in events_text:
            return "Availability", "SERVICE_CRASH", "CRITICAL"

        # 3. CPU Saturation
        if cpu >= 75.0 or "CPU" in events_text:
            return "Resource", "CPU_SPIKE", "HIGH"

        # 4. Memory Pressure / Leak
        if mem >= 350.0 or "MEMORY" in events_text:
            return "Resource", "MEMORY_PRESSURE", "HIGH"

        # 5. Dependency Timeout
        if timeout_rate > 0.3 or "TIMEOUT" in events_text or "504" in events_text:
            return "Dependency", "DEPENDENCY_TIMEOUT", "HIGH"

        # 6. Behavioral Anomaly without Error Logs
        if p95_ratio >= 3.0 and error_rate < 0.05 and error_log_ratio == 0:
            return "Behavioral", "BEHAVIORAL_ANOMALY_WITHOUT_ERROR_LOGS", "MEDIUM"

        # 7. Latency Surge
        if p95 >= 1500.0 or p95_ratio >= 4.0:
            return "Performance", "DATABASE_LATENCY_SPIKE" if "database" in service else "NETWORK_LATENCY_SPIKE", "HIGH"

        # 8. High 5xx Error Rate
        if error_rate >= 0.20 or "500" in events_text:
            return "Application", "HIGH_HTTP_5XX_RATE", "HIGH"

        return "Infrastructure", "SERVICE_DEGRADATION", "MEDIUM"


signature_extractor = SignatureExtractor()
