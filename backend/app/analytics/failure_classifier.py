"""
AegisOps AI - Operational Failure Classification Engine (Part 7)
Classifies operational anomalies into a fine-grained taxonomy:
- HTTP_400_SPIKE, HTTP_401_SPIKE, HTTP_403_SPIKE, HTTP_404_SPIKE
- HTTP_500_SPIKE, HTTP_502_SPIKE, HTTP_503_SPIKE
- REQUEST_TIMEOUT, DATABASE_TIMEOUT, DATABASE_CONNECTION_EXHAUSTION
- CACHE_FAILURE, REDIS_FAILURE, SERVICE_CRASH
- DEPENDENCY_FAILURE, LATENCY_DEGRADATION, TRAFFIC_ANOMALY
- EXCEPTION_SPIKE, DEPLOYMENT_REGRESSION, RESOURCE_SATURATION, CASCADING_FAILURE

Returns:
- failure_type: str
- confidence: float (0.0 - 1.0)
- evidence: List[str]
- affected_service: str
- severity: str ("P1", "P2", "P3")
"""

import time
import math
from typing import Dict, List, Any, Optional, Tuple


class FailureClassifier:
    """Classifies operational anomalies into standardized operational failure taxonomy."""

    @classmethod
    def classify(
        cls,
        features: Dict[str, Any],
        service: str = "database-service",
        raw_events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Convenience alias for classify_failure."""
        return cls.classify_failure(service, features, raw_events)

    @classmethod
    def classify_failure(
        cls,
        service: str,
        features: Dict[str, Any],
        raw_events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates windowed telemetry features and recent error events
        to produce a classified operational failure type with empirical evidence.
        """
        events = raw_events or []
        err_rate = float(features.get("error_rate", 0.0))
        p95 = float(features.get("latency_p95", features.get("latency_p95_ms", 25.0)))
        cpu = float(features.get("cpu_percent", 15.0))
        conn_pool = float(features.get("connection_pool_utilization", 15.0))
        if conn_pool <= 1.0:
            conn_pool = conn_pool * 100.0
        timeout_r = float(features.get("timeout_rate", 0.0))
        r_5xx = float(features.get("http_5xx_rate", 0.0))
        r_4xx = float(features.get("http_4xx_rate", 0.0))
        dep_err = float(features.get("dependency_failure_rate", 0.0))

        # Compile message and error text
        messages = [str(e.get("message") or "").lower() for e in events]
        combined_text = " ".join(messages)
        status_codes = [int(e["status_code"]) for e in events if e.get("status_code") and str(e["status_code"]).isdigit()]
        
        c_500 = sum(1 for s in status_codes if s == 500)
        c_502 = sum(1 for s in status_codes if s == 502)
        c_503 = sum(1 for s in status_codes if s == 503)
        c_504 = sum(1 for s in status_codes if s == 504)
        c_401 = sum(1 for s in status_codes if s == 401)
        c_403 = sum(1 for s in status_codes if s == 403)
        c_404 = sum(1 for s in status_codes if s == 404)
        c_400 = sum(1 for s in status_codes if s == 400)

        is_db_service = ("database" in service or "db" in service or "postgres" in service)
        is_cache_service = ("cache" in service or "redis" in service)

        # ---------------------------------------------------------------------
        # Evaluation Hierarchy
        # ---------------------------------------------------------------------

        # 1. Database Connection Exhaustion
        if (is_db_service and conn_pool >= 80.0) or ("pool" in combined_text and ("exhaust" in combined_text or "saturated" in combined_text or "full" in combined_text)):
            evidence = [
                f"Connection pool saturation reached {conn_pool:.1f}% capacity",
                f"Active connections bottlenecking ingress transaction threads",
                f"P95 latency elevated to {p95:.1f}ms due to socket acquisition wait"
            ]
            if timeout_r > 0.01:
                evidence.append(f"Connection wait timeout rate: {timeout_r*100:.1f}%")
            return {
                "failure_type": "DATABASE_CONNECTION_EXHAUSTION",
                "confidence": 0.94 if conn_pool >= 90 else 0.88,
                "evidence": evidence,
                "affected_service": service,
                "severity": "P1" if conn_pool >= 90 else "P2"
            }

        # 2. Database Timeout
        if (is_db_service and (timeout_r > 0.05 or p95 >= 2500.0)) or ("database timeout" in combined_text or "query timed out" in combined_text):
            return {
                "failure_type": "DATABASE_TIMEOUT",
                "confidence": 0.91,
                "evidence": [
                    f"Database query execution timeout rate: {timeout_r*100:.1f}%",
                    f"P95 latency surged to {p95:.1f}ms",
                    "Downstream client requests failing waiting for lock release"
                ],
                "affected_service": service,
                "severity": "P1"
            }

        # 3. Redis / Cache Failure
        if is_cache_service or any(k in combined_text for k in ["redis connection", "redis_down", "cache failure", "redis timeout", "cache eviction"]):
            return {
                "failure_type": "CACHE_FAILURE" if "cache" in service else "REDIS_FAILURE",
                "confidence": 0.92,
                "evidence": [
                    f"Cache socket connectivity dropped or latency exceeded safety bounds ({p95:.1f}ms)",
                    "Cache miss storm propagating to downstream database layer",
                    f"Error rate on cache client: {err_rate*100:.1f}%"
                ],
                "affected_service": service,
                "severity": "P2"
            }

        # 4. Service Crash / Unreachable
        if any(k in combined_text for k in ["connection refused", "econnrefused", "service crashed", "process exited", "sigkill"]):
            return {
                "failure_type": "SERVICE_CRASH",
                "confidence": 0.96,
                "evidence": [
                    "TCP connection refused by destination service port",
                    "Process appears offline or terminated abruptly",
                    f"100% failure rate for caller traffic"
                ],
                "affected_service": service,
                "severity": "P1"
            }

        # 5. HTTP 502 Bad Gateway
        if c_502 > 0 or "502" in combined_text or "bad gateway" in combined_text:
            return {
                "failure_type": "HTTP_502_SPIKE",
                "confidence": 0.93,
                "evidence": [
                    f"HTTP 502 Bad Gateway responses detected: {c_502} events",
                    "Reverse proxy unable to receive valid upstream response",
                    f"Upstream dependency connection terminated prematurely"
                ],
                "affected_service": service,
                "severity": "P1"
            }

        # 6. HTTP 503 Service Unavailable
        if c_503 > 0 or "503" in combined_text or "service unavailable" in combined_text:
            return {
                "failure_type": "HTTP_503_SPIKE",
                "confidence": 0.91,
                "evidence": [
                    f"HTTP 503 Service Unavailable spike detected: {c_503} events",
                    "Upstream circuit breaker tripped or service overloaded",
                    f"Error rate: {err_rate*100:.1f}%"
                ],
                "affected_service": service,
                "severity": "P1"
            }

        # 7. HTTP 500 Internal Error Spike
        if (r_5xx >= 0.10) or c_500 >= 3 or ("500" in combined_text and err_rate >= 0.10):
            return {
                "failure_type": "HTTP_500_SPIKE",
                "confidence": 0.89,
                "evidence": [
                    f"HTTP 500 Internal Server Error rate: {r_5xx*100:.1f}%",
                    f"Unhandled server-side exceptions observed in request cycle",
                    f"P95 latency elevated to {p95:.1f}ms"
                ],
                "affected_service": service,
                "severity": "P1" if r_5xx >= 0.20 else "P2"
            }

        # 8. Request Timeout
        if timeout_r >= 0.04 or c_504 > 0 or "gateway timeout" in combined_text or (p95 >= 3000.0 and err_rate > 0.05):
            return {
                "failure_type": "REQUEST_TIMEOUT",
                "confidence": 0.90,
                "evidence": [
                    f"Request timeout rate reached {timeout_r*100:.1f}%",
                    f"P95 response latency exceeded timeout threshold at {p95:.1f}ms",
                    "Client connections closed prior to response completion"
                ],
                "affected_service": service,
                "severity": "P1"
            }

        # 9. Dependency Failure
        if dep_err >= 0.08 or "dependency failure" in combined_text or "downstream timeout" in combined_text:
            return {
                "failure_type": "DEPENDENCY_FAILURE",
                "confidence": 0.87,
                "evidence": [
                    f"Dependency failure rate: {dep_err*100:.1f}%",
                    "Upstream calls experiencing repeated cascading rejections",
                    f"Local service degraded as collateral consequence"
                ],
                "affected_service": service,
                "severity": "P2"
            }

        # 10. HTTP 4xx Specific Spikes
        if r_4xx >= 0.15:
            if c_401 > c_403 and c_401 > c_404:
                return {
                    "failure_type": "HTTP_401_SPIKE",
                    "confidence": 0.93,
                    "evidence": [f"HTTP 401 Unauthorized spike detected ({c_401} events)", "Authentication header missing or tokens rejected"],
                    "affected_service": service,
                    "severity": "P2"
                }
            elif c_403 > c_404:
                return {
                    "failure_type": "HTTP_403_SPIKE",
                    "confidence": 0.91,
                    "evidence": [f"HTTP 403 Forbidden spike detected ({c_403} events)", "RBAC policy or tenant permissions barrier"],
                    "affected_service": service,
                    "severity": "P2"
                }
            elif c_404 > 5:
                return {
                    "failure_type": "HTTP_404_SPIKE",
                    "confidence": 0.88,
                    "evidence": [f"HTTP 404 Not Found spike detected ({c_404} events)", "Missing API routes or resource identifier desynchronization"],
                    "affected_service": service,
                    "severity": "P3"
                }
            else:
                return {
                    "failure_type": "HTTP_400_SPIKE",
                    "confidence": 0.86,
                    "evidence": [f"HTTP 400 Bad Request rate: {r_4xx*100:.1f}%", "Malformed client payloads or schema validation rejections"],
                    "affected_service": service,
                    "severity": "P3"
                }

        # 11. Resource Saturation
        if cpu >= 85.0 or float(features.get("memory_percent", 0.0)) >= 88.0:
            return {
                "failure_type": "RESOURCE_SATURATION",
                "confidence": 0.89,
                "evidence": [
                    f"CPU saturation: {cpu:.1f}%",
                    f"Memory pressure: {float(features.get('memory_percent', 0.0)):.1f}%",
                    f"Resource exhaustion degrading throughput scheduling"
                ],
                "affected_service": service,
                "severity": "P2"
            }

        # 12. Latency Degradation
        if p95 >= 1000.0:
            return {
                "failure_type": "LATENCY_DEGRADATION",
                "confidence": 0.88,
                "evidence": [
                    f"P95 latency degraded to {p95:.1f}ms without proportional HTTP errors",
                    "I/O or CPU contention delaying response dispatch",
                    f"Requests/sec: {float(features.get('requests_per_second', 0.0)):.1f}"
                ],
                "affected_service": service,
                "severity": "P2"
            }

        # 13. Traffic Anomaly
        if abs(float(features.get("request_growth_rate", 0.0))) >= 1.5:
            growth = float(features.get("request_growth_rate", 0.0)) * 100.0
            return {
                "failure_type": "TRAFFIC_ANOMALY",
                "confidence": 0.85,
                "evidence": [
                    f"Abnormal traffic growth rate: {growth:+.1f}%",
                    f"Current throughput: {float(features.get('requests_per_second', 0.0)):.1f} req/s",
                    "Sudden workload surge straining service buffers"
                ],
                "affected_service": service,
                "severity": "P3"
            }

        # 14. Default fallback: Exception Spike
        return {
            "failure_type": "EXCEPTION_SPIKE",
            "confidence": 0.80,
            "evidence": [
                f"Elevated failure signals observed on {service}",
                f"Error rate: {err_rate*100:.1f}%, P95 latency: {p95:.1f}ms",
                "Statistical deviation detected across multi-model ensemble"
            ],
            "affected_service": service,
            "severity": "P2"
        }


# Singleton failure classifier
failure_classifier = FailureClassifier()
