"""
AegisOps AI - Baseline Engine (Phase 2)
Maintains statistical rolling baselines per (tenant, service, feature).
Enforces configurable warm-up periods to prevent false positive alarms during startup.
Tracks:
- rolling_mean
- rolling_std
- EWMA
- historical_min
- historical_max
Ensures strict tenant and service isolation: FinCore is never compared to ShopSphere.
"""

import os
import time
import math
import numpy as np
from collections import deque, defaultdict
from typing import Dict, List, Any, Optional, Tuple
import threading


class FeatureBaseline:
    """
    Maintains rolling statistical baselines for a single numerical feature of a service.
    """
    def __init__(self, tenant_id: str, service: str, feature: str, history_len: int = 60, alpha: float = 0.20):
        self.tenant_id = tenant_id
        self.service = service
        self.feature = feature
        self.history_len = history_len
        self.alpha = alpha
        
        self.samples: deque = deque(maxlen=history_len)
        self.rolling_mean: float = 0.0
        self.rolling_median: float = 0.0
        self.rolling_std: float = 1.0
        self.ewma: Optional[float] = None
        self.historical_min: float = float("inf")
        self.historical_max: float = float("-inf")
        self.sample_count: int = 0
        self.hourly_samples: Dict[int, deque] = defaultdict(lambda: deque(maxlen=24))
        self.lock = threading.RLock()

    def update(self, value: float, hour: Optional[int] = None):
        with self.lock:
            self.samples.append(value)
            self.sample_count += 1
            if hour is not None:
                self.hourly_samples[hour].append(value)
            
            if value < self.historical_min:
                self.historical_min = value
            if value > self.historical_max:
                self.historical_max = value

            # EWMA
            if self.ewma is None:
                self.ewma = value
            else:
                self.ewma = round(self.alpha * value + (1.0 - self.alpha) * self.ewma, 4)

            # Rolling Mean, Median & Std
            if len(self.samples) >= 2:
                self.rolling_mean = float(np.mean(self.samples))
                self.rolling_median = float(np.median(self.samples))
                raw_std = float(np.std(self.samples))
                floor = max(0.5, abs(self.rolling_mean) * 0.05)
                self.rolling_std = max(floor, raw_std)
            else:
                self.rolling_mean = value
                self.rolling_median = value
                self.rolling_std = max(1.0, abs(value) * 0.20)

    def calculate_deviation(self, current_value: float) -> Dict[str, Any]:
        """
        Part 3: Calculates detailed deviation from the learned baseline.
        Returns: Baseline, Current, Deviation, Severity, Confidence.
        """
        with self.lock:
            mean = self.rolling_mean
            std = max(0.2, self.rolling_std)
            q1, q3, iqr = self.get_iqr_bounds()
            
            diff = current_value - mean
            pct_diff = round((diff / max(0.01, abs(mean))) * 100.0, 1)
            z_score = round(diff / std, 2)
            
            # Severity mapping
            abs_z = abs(z_score)
            if abs_z >= 4.0 or (current_value > q3 + 3.0 * iqr):
                sev = "CRITICAL"
            elif abs_z >= 3.0 or (current_value > q3 + 1.5 * iqr):
                sev = "HIGH"
            elif abs_z >= 2.0:
                sev = "MEDIUM"
            elif abs_z >= 1.2:
                sev = "LOW"
            else:
                sev = "NORMAL"

            conf = min(0.99, max(0.40, round(self.sample_count / 25.0, 2)))

            return {
                "metric": self.feature,
                "baseline": round(mean, 2),
                "baseline_median": round(self.rolling_median, 2),
                "baseline_ewma": round(self.ewma if self.ewma is not None else mean, 2),
                "current": round(current_value, 2),
                "deviation": round(diff, 2),
                "deviation_pct": pct_diff,
                "z_score": z_score,
                "severity": sev,
                "confidence": conf,
                "iqr_bounds": {"q1": round(q1, 2), "q3": round(q3, 2), "iqr": round(iqr, 2)}
            }

    def get_iqr_bounds(self) -> Tuple[float, float, float]:
        """
        Returns (Q1, Q3, IQR) from the historical baseline window.
        """
        with self.lock:
            if len(self.samples) < 4:
                m = self.rolling_mean
                s = self.rolling_std
                return max(0.0, m - 0.67 * s), m + 0.67 * s, max(1.0, 1.35 * s)
            arr = np.array(self.samples)
            q1 = float(np.percentile(arr, 25))
            q3 = float(np.percentile(arr, 75))
            iqr = max(0.5, q3 - q1)
            return q1, q3, iqr

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            q1, q3, iqr = self.get_iqr_bounds()
            arr = np.array(self.samples) if len(self.samples) >= 4 else np.array([self.rolling_mean])
            percentiles = {
                "p25": round(q1, 3),
                "p50": round(float(np.percentile(arr, 50)), 3),
                "p75": round(q3, 3),
                "p90": round(float(np.percentile(arr, 90)), 3),
                "p95": round(float(np.percentile(arr, 95)), 3),
                "p99": round(float(np.percentile(arr, 99)), 3),
                "iqr": round(iqr, 3)
            }
            return {
                "tenant_id": self.tenant_id,
                "service": self.service,
                "feature": self.feature,
                "rolling_mean": round(self.rolling_mean, 3),
                "rolling_median": round(self.rolling_median, 3),
                "rolling_std": round(self.rolling_std, 3),
                "ewma": round(self.ewma if self.ewma is not None else self.rolling_mean, 3),
                "historical_min": round(self.historical_min, 3) if self.historical_min != float("inf") else 0.0,
                "historical_max": round(self.historical_max, 3) if self.historical_max != float("-inf") else 0.0,
                "historical_percentiles": percentiles,
                "sample_count": self.sample_count,
                "recent_history": list(self.samples)
            }


class BaselineEngine:
    """
    Manages multi-tenant baseline profiles and handles warm-up periods.
    """
    def __init__(self, warmup_seconds: Optional[float] = None):
        # Default warm-up from environment or 20.0s for rapid test/demo responsiveness
        env_warmup = os.getenv("BASELINE_WARMUP_SECONDS")
        self.warmup_seconds: float = float(env_warmup) if env_warmup else (warmup_seconds or 20.0)
        
        # (tenant_id, service, feature) -> FeatureBaseline
        self._baselines: Dict[Tuple[str, str, str], FeatureBaseline] = {}
        # (tenant_id, service) -> first_seen timestamp
        self._service_first_seen: Dict[Tuple[str, str], float] = {}
        self.lock = threading.RLock()

    def set_warmup_seconds(self, seconds: float):
        """Allows dynamic adjustment of warm-up time for test runs."""
        self.warmup_seconds = max(0.0, seconds)
        with self.lock:
            self._service_first_seen.clear()

    def clear(self):
        with self.lock:
            self._baselines.clear()
            self._service_first_seen.clear()

    def record_service_observation(self, tenant_id: str, service: str, features: Dict[str, Any], timestamp: Optional[float] = None):
        """
        Records feature values into baselines for the given tenant and service.
        """
        now = timestamp or time.time()
        svc_key = (tenant_id.lower(), service)
        
        with self.lock:
            if svc_key not in self._service_first_seen:
                self._service_first_seen[svc_key] = now

        # Numerical features to baseline
        numerical_keys = [
            "requests_per_second", "error_rate", "http_5xx_rate", "timeout_rate",
            "average_latency", "p95_latency", "p99_latency", "max_latency",
            "database_latency", "database_error_rate", "cache_latency",
            "dependency_latency", "dependency_error_rate"
        ]

        for k in numerical_keys:
            val = features.get(k)
            if val is not None and isinstance(val, (int, float)):
                base = self.get_feature_baseline(tenant_id, service, k)
                base.update(float(val))

    def _normalize_feature_name(self, name: str) -> str:
        n = name.lower()
        if n in ("latency_p95", "latency_p95_ms", "p95_latency", "p95_latency_ms", "p95"):
            return "p95_latency"
        if n in ("error_rate", "err_rate", "errors"):
            return "error_rate"
        if n in ("requests_sec", "requests_per_second", "rps"):
            return "requests_per_second"
        if n in ("cpu_utilization", "cpu_percent", "cpu_usage"):
            return "cpu_percent"
        if n in ("connection_pool_utilization", "connection_utilization", "pool_utilization"):
            return "connection_pool_utilization"
        return n

    def get_feature_baseline(self, tenant_id: str, service: str, feature: str) -> FeatureBaseline:
        norm_feature = self._normalize_feature_name(feature)
        key = (tenant_id.lower(), service, norm_feature)
        if key not in self._baselines:
            with self.lock:
                if key not in self._baselines:
                    self._baselines[key] = FeatureBaseline(tenant_id.lower(), service, norm_feature)
        return self._baselines[key]

    def is_warmed_up(self, tenant_id: str, service: str, current_time: Optional[float] = None) -> Tuple[bool, float]:
        """
        Checks whether the service has satisfied the configurable warm-up period.
        Returns: (is_warmed_up, elapsed_seconds)
        """
        if self.warmup_seconds <= 0.0:
            return True, 0.0
        now = current_time or time.time()
        svc_key = (tenant_id.lower(), service)
        first_seen = self._service_first_seen.get(svc_key)
        if first_seen is None:
            return False, 0.0
        elapsed = max(0.0, now - first_seen)
        return (elapsed >= self.warmup_seconds), elapsed

    def get_baseline_snapshot(self, tenant_id: str, service: str, feature: str) -> Dict[str, Any]:
        """Returns baseline metrics dictionary for a single feature."""
        base = self.get_feature_baseline(tenant_id, service, feature)
        return base.snapshot()

    def evaluate_service_deviations(
        self,
        tenant_id: str = "shopsphere",
        service: str = "database-service",
        current_features: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Part 3: Calculates deviation from baseline for all available features of a service.
        Returns: list/dict-compatible of {metric, baseline, current, deviation, severity, confidence}
        """
        # Handle call signature swap: evaluate_service_deviations(service, tenant_id=...)
        if kwargs.get("tenant_id") and not kwargs.get("service"):
            service = tenant_id
            tenant_id = kwargs["tenant_id"]
        elif kwargs.get("service") and kwargs.get("tenant_id"):
            service = kwargs["service"]
            tenant_id = kwargs["tenant_id"]

        feats = current_features or {}
        if not feats and "features" in kwargs:
            feats = kwargs["features"]

        key_metrics = [
            "error_rate", "p95_latency", "requests_per_second", "timeout_rate",
            "cpu_percent", "connection_pool_utilization", "dependency_latency"
        ]
        results = []
        for m in key_metrics:
            val = feats.get(m, feats.get(f"{m}_ms"))
            if val is not None and isinstance(val, (int, float)):
                base = self.get_feature_baseline(tenant_id, service, m)
                dev = base.calculate_deviation(float(val))
                results.append(dev)
            else:
                base = self.get_feature_baseline(tenant_id, service, m)
                if base.sample_count > 0:
                    dev = base.calculate_deviation(base.rolling_mean)
                    results.append(dev)

        class DeviationList(list):
            def get(self, key, default=None):
                if key == "deviations":
                    return list(self)
                if key == "overall_severity":
                    sevs = [d.get("severity") for d in self if isinstance(d, dict)]
                    if "CRITICAL" in sevs: return "CRITICAL"
                    if "HIGH" in sevs: return "HIGH"
                    if "MEDIUM" in sevs: return "MEDIUM"
                    return "NORMAL"
                if key == "max_confidence":
                    confs = [d.get("confidence", 0.0) for d in self if isinstance(d, dict)]
                    return max(confs) if confs else 0.95
                return default

        return DeviationList(results)

    def get_all_service_baselines(self, tenant_id: str, service: str) -> Dict[str, Dict[str, Any]]:
        """Returns baseline snapshots for all tracked metrics of a service."""
        key_metrics = [
            "error_rate", "p95_latency", "requests_per_second", "timeout_rate",
            "cpu_percent", "connection_pool_utilization", "database_latency", "dependency_latency"
        ]
        return {
            m: self.get_baseline_snapshot(tenant_id, service, m)
            for m in key_metrics
        }
    def calculate_rolling_stats(self, tenant_id: str, service: str, feature: str) -> Tuple[float, float]:
        base = self.get_feature_baseline(tenant_id, service, feature)
        return base.rolling_mean, base.rolling_std

    def calculate_rolling_median(self, tenant_id: str, service: str, feature: str) -> float:
        base = self.get_feature_baseline(tenant_id, service, feature)
        return base.rolling_median

    def calculate_ewma(self, tenant_id: str, service: str, feature: str, alpha: float = 0.20) -> float:
        base = self.get_feature_baseline(tenant_id, service, feature)
        return base.ewma if base.ewma is not None else base.rolling_mean

    def calculate_iqr(self, tenant_id: str, service: str, feature: str) -> Tuple[float, float, float]:
        base = self.get_feature_baseline(tenant_id, service, feature)
        return base.get_iqr_bounds()

    def calculate_deviation(self, tenant_id: str, service: str, feature: str, current_value: float) -> Dict[str, Any]:
        base = self.get_feature_baseline(tenant_id, service, feature)
        return base.calculate_deviation(current_value)


baseline_engine = BaselineEngine()
