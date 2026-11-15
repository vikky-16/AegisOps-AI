"""
AegisOps AI - Telemetry Feature Engine (Phase 1)
Extracts multi-windowed operational features across (tenant, service)
from live streaming telemetry events without running expensive ML on every individual log.
Maintains sliding windows (10s, 30s, 60s, 300s) and computes aggregated features for:
- TRAFFIC: requests_per_second, total_requests, request_rate_change
- ERRORS: errors_per_second, error_rate, http_4xx_rate, http_5xx_rate, exception_rate, timeout_rate
- LATENCY: average_latency, p50_latency, p95_latency, p99_latency, max_latency
- DEPENDENCIES: dependency_error_rate, dependency_latency, dependency_timeout_rate
- DATABASE: database_error_rate, database_latency, connection_failures
- REDIS/CACHE: cache_errors, cache_latency, connection_failures
"""

import time
import math
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from collections import deque, defaultdict
import threading


class MultiWindowServiceStats:
    """
    Maintains rolling event records and computes multi-window aggregated features
    (10s, 30s, 60s, 300s) for a single service in a tenant.
    """
    def __init__(self, tenant_id: str, service: str):
        self.tenant_id = tenant_id
        self.service = service
        self.lock = threading.Lock()
        
        # Max retention 300s (5 minutes)
        self.max_retention_sec: float = 300.0
        
        # Event record tuple:
        # (ts, latency_ms, is_error, is_timeout, is_5xx, is_4xx, is_exception,
        #  db_lat, is_db_err, is_db_conn_fail,
        #  redis_lat, is_redis_err, is_redis_conn_fail,
        #  dep_lat, is_dep_err, is_dep_timeout, is_warning)
        self.events: deque = deque()
        
        # Previous window metrics for rate-of-change calculation
        self._prev_window_rps: Dict[int, float] = {}
        self._prev_window_err_rate: Dict[int, float] = {}
        self._prev_window_latency: Dict[int, float] = {}

    def add_event(
        self,
        timestamp: float,
        latency_ms: Optional[float] = None,
        is_error: bool = False,
        is_timeout: bool = False,
        is_5xx: bool = False,
        is_4xx: bool = False,
        is_exception: bool = False,
        db_latency_ms: Optional[float] = None,
        is_db_err: bool = False,
        is_db_conn_fail: bool = False,
        redis_latency_ms: Optional[float] = None,
        is_redis_err: bool = False,
        is_redis_conn_fail: bool = False,
        dep_latency_ms: Optional[float] = None,
        is_dep_err: bool = False,
        is_dep_timeout: bool = False,
        is_warning: bool = False
    ):
        with self.lock:
            self.events.append((
                timestamp,
                latency_ms if latency_ms is not None else 0.0,
                is_error,
                is_timeout,
                is_5xx,
                is_4xx,
                is_exception,
                db_latency_ms,
                is_db_err,
                is_db_conn_fail,
                redis_latency_ms,
                is_redis_err,
                is_redis_conn_fail,
                dep_latency_ms,
                is_dep_err,
                is_dep_timeout,
                is_warning
            ))
            # Prune events older than 300s
            cutoff = timestamp - self.max_retention_sec
            while self.events and self.events[0][0] < cutoff:
                self.events.popleft()

    def compute_window_features(self, window_sec: float, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Computes aggregated features for the specified window duration (e.g. 10s, 30s, 60s, 300s).
        """
        now = current_time or time.time()
        window_start = now - window_sec
        window_end = now
        
        with self.lock:
            # Filter events inside [window_start, window_end]
            sub_events = [e for e in self.events if e[0] >= window_start]

        count = len(sub_events)
        duration = max(1.0, window_sec)
        
        if count == 0:
            rps = 0.0
            prev_rps = self._prev_window_rps.get(int(window_sec), 0.0)
            rate_change = 0.0
            self._prev_window_rps[int(window_sec)] = 0.0
            return {
                "tenant_id": self.tenant_id,
                "company": self.tenant_id,
                "service": self.service,
                "window_sec": window_sec,
                "window_start": window_start,
                "window_end": window_end,
                # Traffic
                "requests_per_second": 0.0,
                "total_requests": 0,
                "request_rate_change": 0.0,
                # Errors
                "errors_per_second": 0.0,
                "error_rate": 0.0,
                "http_4xx_rate": 0.0,
                "http_5xx_rate": 0.0,
                "exception_rate": 0.0,
                "timeout_rate": 0.0,
                # Latency
                "average_latency": 15.0,
                "p50_latency": 15.0,
                "p95_latency": 25.0,
                "p99_latency": 35.0,
                "max_latency": 35.0,
                # Dependencies
                "dependency_error_rate": 0.0,
                "dependency_latency": 15.0,
                "dependency_timeout_rate": 0.0,
                # Database
                "database_error_rate": 0.0,
                "database_latency": 5.0,
                "connection_failures": 0,
                # Redis
                "cache_errors": 0,
                "cache_latency": 1.5,
                "cache_connection_failures": 0,
                # Compatibility aliases
                "latency_p95_ms": 25.0,
                "latency_p99_ms": 35.0,
                "db_latency_ms": 5.0,
                "redis_latency_ms": 1.5
            }

        rps = round(count / duration, 2)
        prior_events = [e for e in self.events if e[0] < window_start]
        if prior_events:
            prev_rps = round(len(prior_events) / duration, 2)
            prev_errs = sum(1 for e in prior_events if e[2])
            prev_err = round(prev_errs / len(prior_events), 4)
            prev_lats = [e[1] for e in prior_events if e[1] > 0]
            prev_lat = round(sum(prev_lats) / len(prev_lats), 2) if prev_lats else 25.0
        else:
            prev_rps = self._prev_window_rps.get(int(window_sec), rps)
            prev_err = self._prev_window_err_rate.get(int(window_sec), 0.0)
            prev_lat = self._prev_window_latency.get(int(window_sec), 25.0)

        rate_change = round((rps - prev_rps) / max(0.1, prev_rps), 3) if prev_rps > 0 else 0.0
        self._prev_window_rps[int(window_sec)] = rps

        latencies = [e[1] for e in sub_events if e[1] > 0]
        errors = sum(1 for e in sub_events if e[2])
        timeouts = sum(1 for e in sub_events if e[3])
        c_5xx = sum(1 for e in sub_events if e[4])
        c_4xx = sum(1 for e in sub_events if e[5])
        c_exc = sum(1 for e in sub_events if e[6])

        # DB metrics
        db_lats = [e[7] for e in sub_events if e[7] is not None and e[7] > 0]
        db_errs = sum(1 for e in sub_events if e[8])
        db_conn_fails = sum(1 for e in sub_events if e[9])

        # Redis metrics
        redis_lats = [e[10] for e in sub_events if e[10] is not None and e[10] > 0]
        redis_errs = sum(1 for e in sub_events if e[11])
        redis_conn_fails = sum(1 for e in sub_events if e[12])

        # Dependency metrics
        dep_lats = [e[13] for e in sub_events if e[13] is not None and e[13] > 0]
        dep_errs = sum(1 for e in sub_events if e[14])
        dep_timeouts = sum(1 for e in sub_events if e[15])

        # Rates
        err_rate = round(errors / count, 4)
        eps = round(errors / duration, 2)
        timeout_rate = round(timeouts / count, 4)
        r_5xx = round(c_5xx / count, 4)
        r_4xx = round(c_4xx / count, 4)
        r_exc = round(c_exc / count, 4)

        dep_err_rate = round(dep_errs / count, 4)
        dep_timeout_rate = round(dep_timeouts / count, 4)
        dep_latency = round(sum(dep_lats) / len(dep_lats), 2) if dep_lats else 15.0

        db_err_rate = round(db_errs / count, 4)
        db_latency = round(sum(db_lats) / len(db_lats), 2) if db_lats else (25.0 if "db" in self.service else 5.0)

        cache_latency = round(sum(redis_lats) / len(redis_lats), 2) if redis_lats else 1.5

        if latencies:
            sorted_lats = sorted(latencies)
            n = len(sorted_lats)
            avg_lat = round(sum(sorted_lats) / n, 2)
            p50 = round(sorted_lats[int(n * 0.50)], 2)
            p95 = round(sorted_lats[min(n - 1, int(n * 0.95))], 2)
            p99 = round(sorted_lats[min(n - 1, int(n * 0.99))], 2)
            max_lat = round(sorted_lats[-1], 2)
        else:
            avg_lat, p50, p95, p99, max_lat = 15.0, 15.0, 25.0, 35.0, 35.0

        err_rate_change = round((err_rate - prev_err) / max(0.01, prev_err), 3) if prev_err > 0 else (err_rate if err_rate > 0 else 0.0)
        self._prev_window_err_rate[int(window_sec)] = err_rate

        latency_change = round((avg_lat - prev_lat) / max(1.0, prev_lat), 3) if prev_lat > 0 else 0.0
        self._prev_window_latency[int(window_sec)] = avg_lat

        warnings = sum(1 for e in sub_events if len(e) > 16 and e[16])
        warning_rate = round(warnings / count, 4) if count > 0 else 0.0

        return {
            "tenant_id": self.tenant_id,
            "company": self.tenant_id,
            "service": self.service,
            "window_sec": window_sec,
            "window_start": window_start,
            "window_end": window_end,
            # Traffic
            "request_count": count,
            "requests_per_second": rps,
            "total_requests": count,
            "request_rate_change": rate_change,
            "traffic_change": rate_change,
            # Errors
            "error_count": errors,
            "errors_per_second": eps,
            "error_rate": err_rate,
            "warning_count": warnings,
            "warning_rate": warning_rate,
            "error_rate_change": err_rate_change,
            "http_4xx_rate": r_4xx,
            "http_5xx_rate": r_5xx,
            "exception_count": c_exc,
            "exception_rate": r_exc,
            "timeout_count": timeouts,
            "timeout_rate": timeout_rate,
            # Latency
            "average_latency": avg_lat,
            "latency_change": latency_change,
            "p50_latency": p50,
            "p95_latency": p95,
            "p99_latency": p99,
            "max_latency": max_lat,
            # Dependencies
            "dependency_error_rate": dep_err_rate,
            "dependency_latency": dep_latency,
            "dependency_timeout_rate": dep_timeout_rate,
            # Database
            "database_error_rate": db_err_rate,
            "database_latency": db_latency,
            "connection_failures": db_conn_fails,
            # Redis
            "cache_errors": redis_errs,
            "cache_latency": cache_latency,
            "cache_connection_failures": redis_conn_fails,
            # Compatibility aliases
            "latency_p95_ms": p95,
            "latency_p99_ms": p99,
            "db_latency_ms": db_latency,
            "redis_latency_ms": cache_latency
        }


class TimeWindowFeatureExtractor:
    """
    Continuous Time-Windowed Telemetry Feature Extractor.
    Maintains sliding multi-windows (10s, 30s, 60s, 300s) per (tenant_id, service).
    Buffers raw events safely in memory and calculates aggregated features on demand or periodically.
    """
    SUPPORTED_WINDOWS = [10.0, 30.0, 60.0, 300.0]

    def __init__(self):
        # (tenant_id, service) -> MultiWindowServiceStats
        self._services: Dict[Tuple[str, str], MultiWindowServiceStats] = {}
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self._services.clear()

    def _get_service_stats(self, tenant_id: str, service: str) -> MultiWindowServiceStats:
        key = (tenant_id, service)
        if key not in self._services:
            with self.lock:
                if key not in self._services:
                    self._services[key] = MultiWindowServiceStats(tenant_id, service)
        return self._services[key]

    def process_event(self, event: Any) -> Dict[str, Any]:
        """
        Fast in-memory ingestion. Extracts fields and appends to sliding buffer (< 0.01ms).
        Returns the primary 30s window features for immediate inspection.
        """
        ts_val = getattr(event, "timestamp", None)
        if ts_val is None and isinstance(event, dict):
            ts_val = event.get("timestamp")

        now = time.time()
        if ts_val is not None:
            if isinstance(ts_val, (int, float)):
                now = float(ts_val)
            elif isinstance(ts_val, str):
                try:
                    dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                    now = dt.timestamp()
                except Exception:
                    pass

        tenant_id = (
            getattr(event, "tenant_id", None) 
            or getattr(event, "company_id", None) 
            or "shopsphere"
        ).lower()
        service = getattr(event, "service_name", None) or getattr(event, "service", "unknown-service")

        # Normalize latency
        latency = None
        for attr in ["latency", "latency_ms", "duration_ms"]:
            val = getattr(event, attr, None)
            if val is not None:
                try:
                    latency = float(val)
                    break
                except (ValueError, TypeError):
                    pass
        if latency is None and isinstance(event, dict):
            for attr in ["latency", "latency_ms", "duration_ms"]:
                val = event.get(attr)
                if val is not None:
                    try:
                        latency = float(val)
                        break
                    except (ValueError, TypeError):
                        pass

        # Normalize status code
        status_code = getattr(event, "http_status", None) or getattr(event, "status_code", None)
        if status_code is None and isinstance(event, dict):
            status_code = event.get("http_status") or event.get("status_code")
        status_int = int(status_code) if (status_code is not None and str(status_code).isdigit()) else None

        severity = str(getattr(event, "severity", "INFO")).upper()
        if hasattr(severity, "value"):
            severity = severity.value.upper()
        elif isinstance(event, dict) and not getattr(event, "severity", None):
            severity = str(event.get("severity") or event.get("level") or "INFO").upper()

        msg = str(getattr(event, "message", "")).lower()
        if not msg and isinstance(event, dict):
            msg = str(event.get("message", "")).lower()
        evt_type = str(getattr(event, "event_type", "")).lower()

        # Classification
        is_5xx = (status_int is not None and 500 <= status_int < 600)
        is_4xx = (status_int is not None and 400 <= status_int < 500)
        is_timeout = (
            status_int == 504 
            or "timeout" in msg 
            or "timeout" in evt_type 
            or "timed out" in msg 
            or (latency is not None and latency >= 2000.0)
        )
        is_exception = "exception" in msg or "error" in evt_type or "traceback" in msg
        is_error = (
            is_5xx 
            or is_timeout 
            or severity in ("ERROR", "CRITICAL") 
            or is_exception 
            or "failed" in msg
        )

        # Database telemetry classification
        is_db_related = (
            "database" in service 
            or "postgres" in service 
            or "db_" in evt_type 
            or "query" in msg 
            or "connection pool" in msg 
            or "sql" in msg
        )
        db_lat = latency if is_db_related else None
        is_db_err = is_error and is_db_related
        is_db_conn_fail = is_db_related and ("connection" in msg or "pool" in msg or "refused" in msg)

        # Redis / Cache telemetry classification
        is_redis_related = (
            "cache" in service 
            or "redis" in service 
            or "redis" in msg 
            or "cache" in msg
        )
        redis_lat = latency if is_redis_related else None
        is_redis_err = is_error and is_redis_related
        is_redis_conn_fail = is_redis_related and ("connection refused" in msg or "redis_down" in evt_type or "unavailable" in msg)

        # Dependency classification
        dep = getattr(event, "dependency", None)
        is_dep_err = is_error and dep is not None
        is_dep_timeout = is_timeout and dep is not None
        dep_lat = latency if dep is not None else None

        stats = self._get_service_stats(tenant_id, service)
        stats.add_event(
            timestamp=now,
            latency_ms=latency,
            is_error=is_error,
            is_timeout=is_timeout,
            is_5xx=is_5xx,
            is_4xx=is_4xx,
            is_exception=is_exception,
            db_latency_ms=db_lat,
            is_db_err=is_db_err,
            is_db_conn_fail=is_db_conn_fail,
            redis_latency_ms=redis_lat,
            is_redis_err=is_redis_err,
            is_redis_conn_fail=is_redis_conn_fail,
            dep_latency_ms=dep_lat,
            is_dep_err=is_dep_err,
            is_dep_timeout=is_dep_timeout,
            is_warning=(severity in ("WARN", "WARNING"))
        )

        try:
            from backend.app.analytics.feature_engine import feature_engine
            feature_engine.ingest_telemetry_event(event)
        except Exception:
            pass

        return stats.compute_window_features(window_sec=30.0, current_time=now)

    def get_features(self, tenant_id: str, service: str, window_sec: float = 30.0) -> Dict[str, Any]:
        """Returns the windowed features for a specific tenant and service."""
        try:
            from backend.app.analytics.feature_engine import feature_engine
            f_adv = feature_engine.get_features(tenant_id, service, window_sec)
            if f_adv.get("total_requests", 0) > 0 or f_adv.get("requests_per_second", 0) > 0:
                return f_adv
        except Exception:
            pass
        stats = self._get_service_stats(tenant_id.lower(), service)
        return stats.compute_window_features(window_sec=window_sec)

    def get_all_multi_window_features(self, tenant_id: str, service: str) -> Dict[str, Dict[str, Any]]:
        """Returns feature snapshots across all supported windows (10s, 30s, 60s, 300s)."""
        stats = self._get_service_stats(tenant_id.lower(), service)
        return {
            f"{int(w)}s": self.get_features(tenant_id, service, window_sec=w)
            for w in self.SUPPORTED_WINDOWS
        }

    def get_feature_vector(self, tenant_id: str, service: str, window_sec: float = 30.0) -> Tuple[List[float], List[str]]:
        from backend.app.analytics.feature_engine import feature_engine
        return feature_engine.get_feature_vector(tenant_id, service, window_sec)

    def get_all_active_services(self) -> List[Tuple[str, str]]:
        """Returns list of all (tenant_id, service) pairs with tracked telemetry."""
        with self.lock:
            return list(self._services.keys())


feature_extractor = TimeWindowFeatureExtractor()
