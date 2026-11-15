"""
AegisOps AI - Continuous Baseline Learning System
Calculates and tracks moving averages, medians, std dev, and percentiles (p50, p95, p99)
to establish dynamic normal operational envelopes per service and metric.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class BaselineProfile:
    def __init__(self, service: str, metric_name: str, window_size: int = 150):
        self.service = service
        self.metric_name = metric_name
        self.window_size = window_size
        self.samples: List[float] = []
        self.mean: float = 0.0
        self.median: float = 0.0
        self.std: float = 1.0
        self.p50: float = 0.0
        self.p95: float = 0.0
        self.p99: float = 0.0
        self.min_val: float = 0.0
        self.max_val: float = 0.0
        self.last_updated: str = datetime.now(timezone.utc).isoformat()

    def update(self, value: float):
        self.samples.append(float(value))
        if len(self.samples) > self.window_size:
            self.samples.pop(0)

        arr = np.array(self.samples)
        self.mean = float(np.mean(arr))
        self.median = float(np.median(arr))
        self.std = float(np.std(arr)) if len(arr) > 1 else 1.0
        self.p50 = float(np.percentile(arr, 50))
        self.p95 = float(np.percentile(arr, 95))
        self.p99 = float(np.percentile(arr, 99))
        self.min_val = float(np.min(arr))
        self.max_val = float(np.max(arr))
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "metric_name": self.metric_name,
            "sample_count": len(self.samples),
            "mean": round(self.mean, 2),
            "median": round(self.median, 2),
            "std": round(self.std, 2),
            "p50": round(self.p50, 2),
            "p95": round(self.p95, 2),
            "p99": round(self.p99, 2),
            "normal_range_min": round(max(0.0, self.mean - (2.0 * self.std)), 2),
            "normal_range_max": round(self.mean + (2.0 * self.std), 2),
            "min_val": round(self.min_val, 2),
            "max_val": round(self.max_val, 2),
            "last_updated": self.last_updated
        }


class BaselineManager:
    def __init__(self):
        self._profiles: Dict[str, BaselineProfile] = {}
        self._seed_default_profiles()

    def _get_key(self, service: str, metric: str) -> str:
        return f"{service}::{metric}"

    def record_sample(self, service: str, metric: str, value: float):
        key = self._get_key(service, metric)
        if key not in self._profiles:
            self._profiles[key] = BaselineProfile(service, metric)
        self._profiles[key].update(value)

    def get_baseline(self, service: str, metric: str) -> Optional[Dict[str, Any]]:
        key = self._get_key(service, metric)
        if key in self._profiles:
            return self._profiles[key].to_dict()
        return None

    def get_all_baselines(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._profiles.values()]

    def _seed_default_profiles(self):
        """Seeds standard normal operational baseline metrics for known microservices."""
        defaults = {
            "gateway": {"latency_p95_ms": (15.0, 4.0), "error_rate": (0.001, 0.002), "cpu_percent": (12.0, 3.0)},
            "service-a": {"latency_p95_ms": (22.0, 5.0), "error_rate": (0.002, 0.003), "cpu_percent": (15.0, 4.0)},
            "service-b": {"latency_p95_ms": (280.0, 35.0), "error_rate": (0.005, 0.004), "cpu_percent": (18.0, 4.0)},
            "database-service": {"latency_p95_ms": (18.0, 4.0), "error_rate": (0.001, 0.001), "cpu_percent": (20.0, 5.0)},
            "auth-service": {"latency_p95_ms": (10.0, 2.0), "error_rate": (0.001, 0.001), "cpu_percent": (8.0, 2.0)}
        }
        np.random.seed(42)
        for svc, metrics in defaults.items():
            for m_name, (mu, sigma) in metrics.items():
                prof = BaselineProfile(svc, m_name)
                samples = np.random.normal(mu, sigma, 40).clip(0.0, mu * 3.0)
                for s in samples:
                    prof.update(float(s))
                self._profiles[self._get_key(svc, m_name)] = prof


baseline_manager = BaselineManager()
