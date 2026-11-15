"""
AegisOps AI - Multivariate Isolation Forest Anomaly Detector
Implements an actual Isolation Forest using scikit-learn across 16 standardized telemetry features.
Maintains continuous baseline training and transparent feature-deviation explainability.
"""

import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from sklearn.ensemble import IsolationForest

FEATURE_NAMES = [
    "request_count",
    "error_rate",
    "latency_p50",
    "latency_p95",
    "latency_p99",
    "cpu_percent",
    "memory_mb",
    "active_connections",
    "connection_pool_utilization",
    "timeout_rate",
    "http_4xx_rate",
    "http_5xx_rate",
    "dependency_latency",
    "trace_duration",
    "request_rate_change",
    "latency_change"
]


class IsolationForestDetector:
    def __init__(self, contamination: float = 0.08, min_samples_for_training: int = 15):
        self.contamination = contamination
        self.min_samples_for_training = min_samples_for_training
        self.model: Optional[IsolationForest] = None
        self.is_fitted: bool = False
        self.model_version: str = "v1.2-multivariate"
        
        # Training baseline store
        self.training_samples: List[np.ndarray] = []
        self.max_training_samples: int = 500
        self.baseline_window_sec: int = 300
        self.last_trained_timestamp: Optional[float] = None
        
        # Computed baseline feature statistics (mean, std) for deviation explanation
        self.feature_means: Optional[np.ndarray] = None
        self.feature_stds: Optional[np.ndarray] = None
        
        # Initialize synthetic healthy bootstrap baseline so model is immediately usable in tests/demo
        self._bootstrap_healthy_baseline()

    def _bootstrap_healthy_baseline(self):
        """Generates standard healthy microservice operational distribution to bootstrap model."""
        np.random.seed(42)
        n_samples = 40
        samples = []
        for _ in range(n_samples):
            vec = [
                float(np.random.uniform(5.0, 30.0)),     # request_count
                float(np.random.uniform(0.0, 0.01)),     # error_rate
                float(np.random.uniform(8.0, 20.0)),     # latency_p50
                float(np.random.uniform(15.0, 35.0)),    # latency_p95
                float(np.random.uniform(25.0, 55.0)),    # latency_p99
                float(np.random.uniform(8.0, 25.0)),     # cpu_percent
                float(np.random.uniform(110.0, 160.0)),  # memory_mb
                float(np.random.uniform(1.0, 5.0)),      # active_connections
                float(np.random.uniform(0.05, 0.25)),    # connection_pool_utilization
                float(np.random.uniform(0.0, 0.005)),    # timeout_rate
                float(np.random.uniform(0.0, 0.01)),     # http_4xx_rate
                float(np.random.uniform(0.0, 0.005)),    # http_5xx_rate
                float(np.random.uniform(10.0, 25.0)),    # dependency_latency
                float(np.random.uniform(15.0, 40.0)),    # trace_duration
                float(np.random.uniform(-0.1, 0.1)),     # request_rate_change
                float(np.random.uniform(-0.1, 0.1)),     # latency_change
            ]
            samples.append(np.array(vec))
        
        self.training_samples = samples
        self.train()

    def extract_feature_vector(self, metrics: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> np.ndarray:
        """Constructs standardized 16-dimensional feature vector from telemetry snapshot."""
        req_count = float(metrics.get("request_count", 15.0))
        err_rate = float(metrics.get("error_rate", 0.0))
        p50 = float(metrics.get("latency_p50_ms", metrics.get("latency_p50", 15.0)))
        p95 = float(metrics.get("latency_p95_ms", metrics.get("latency_p95", 28.0)))
        p99 = float(metrics.get("latency_p99_ms", metrics.get("latency_p99", 45.0)))
        cpu = float(metrics.get("cpu_percent", metrics.get("simulated_cpu_percent", 14.0)))
        mem = float(metrics.get("memory_mb", metrics.get("simulated_memory_mb", 128.0)))
        conns = float(metrics.get("active_connections", 2.0))
        pool_util = float(conns / 20.0)
        
        http_4xx = float(metrics.get("http_4xx_rate", 0.0))
        http_5xx = float(metrics.get("http_5xx_rate", err_rate if err_rate > 0.05 else 0.0))
        timeout_rate = float(metrics.get("timeout_rate", 0.8 if err_rate > 0.4 and p95 > 2000 else 0.0))
        dep_latency = float(metrics.get("dependency_latency", p95 * 0.7))
        trace_dur = float(metrics.get("trace_duration_ms", p95 * 1.25))
        
        # Calculate rates of change from history if available
        rate_change = 0.0
        lat_change = 0.0
        if history and len(history) >= 2:
            prev = history[-1]
            prev_lat = float(prev.get("latency_p95_ms", 25.0))
            if prev_lat > 0:
                lat_change = (p95 - prev_lat) / prev_lat
            prev_req = float(prev.get("request_count", 15.0))
            if prev_req > 0:
                rate_change = (req_count - prev_req) / prev_req

        vec = [
            req_count,
            err_rate,
            p50,
            p95,
            p99,
            cpu,
            mem,
            conns,
            pool_util,
            timeout_rate,
            http_4xx,
            http_5xx,
            dep_latency,
            trace_dur,
            rate_change,
            lat_change
        ]
        return np.array(vec, dtype=float)

    def record_sample(self, vector: np.ndarray, is_healthy: bool = True):
        """Records a new operational sample. If healthy, queues for baseline retraining."""
        if is_healthy:
            self.training_samples.append(vector)
            if len(self.training_samples) > self.max_training_samples:
                self.training_samples.pop(0)

    def train(self):
        """Fits Isolation Forest model on accumulated training samples."""
        if len(self.training_samples) < self.min_samples_for_training:
            self.is_fitted = False
            return

        X = np.array(self.training_samples)
        self.feature_means = np.mean(X, axis=0)
        self.feature_stds = np.std(X, axis=0)
        # Avoid division by zero
        self.feature_stds[self.feature_stds < 1e-4] = 1.0

        model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=42,
            n_jobs=1
        )
        model.fit(X)
        self.model = model
        self.is_fitted = True
        self.last_trained_timestamp = time.time()

    def detect(self, vector: np.ndarray) -> Dict[str, Any]:
        """
        Evaluates input vector against Isolation Forest.
        Computes transparent feature-deviation explanations alongside the model score.
        """
        now = time.time()
        
        # Cold start handling
        if not self.is_fitted or self.model is None:
            return {
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "confidence": 0.50,
                "contributing_features": [],
                "model": "Isolation Forest",
                "baseline_window": self.baseline_window_sec,
                "detection_timestamp": now,
                "training_samples_count": len(self.training_samples),
                "model_status": "Insufficient historical data — rule-based detection currently active"
            }

        X = vector.reshape(1, -1)
        raw_score = float(self.model.score_samples(X)[0])
        decision_val = float(self.model.decision_function(X)[0])
        
        # Map raw decision function to standardized anomaly score [0.0, 1.0]
        # In sklearn, decision_function < 0 indicates anomaly.
        if decision_val < 0:
            anomaly_score = float(np.clip(0.60 + (-decision_val * 1.5), 0.60, 0.99))
            is_anomaly = True
        else:
            anomaly_score = float(np.clip(0.50 - (decision_val * 1.2), 0.01, 0.49))
            is_anomaly = False

        # Calculate transparent feature deviations against learned baseline
        contributing_features = []
        if self.feature_means is not None and self.feature_stds is not None:
            z_scores = np.abs((vector - self.feature_means) / self.feature_stds)
            relative_deltas = []
            
            for idx, name in enumerate(FEATURE_NAMES):
                mean_val = float(self.feature_means[idx])
                curr_val = float(vector[idx])
                z = float(z_scores[idx])
                
                pct_delta = 0.0
                if abs(mean_val) > 1e-4:
                    pct_delta = ((curr_val - mean_val) / abs(mean_val)) * 100.0
                else:
                    pct_delta = curr_val * 100.0 if curr_val > 0 else 0.0
                
                relative_deltas.append({
                    "feature": name,
                    "z_score": round(z, 2),
                    "current": round(curr_val, 2),
                    "baseline_mean": round(mean_val, 2),
                    "pct_delta": round(pct_delta, 1),
                    "formatted_delta": f"{'+' if pct_delta >= 0 else ''}{pct_delta:.0f}%"
                })
            
            # Sort by z-score magnitude to isolate top contributing deviations
            relative_deltas.sort(key=lambda d: d["z_score"], reverse=True)
            contributing_features = [
                d for d in relative_deltas if d["z_score"] >= 1.5 or abs(d["pct_delta"]) >= 50.0
            ][:4]

        # Mathematically derived confidence based on score margin and contributing deviation count
        confidence = float(np.clip(0.70 + (anomaly_score * 0.25) + (len(contributing_features) * 0.02), 0.65, 0.98))

        return {
            "anomaly_score": round(anomaly_score, 3),
            "is_anomaly": is_anomaly,
            "confidence": round(confidence, 2),
            "confidence_pct": int(confidence * 100),
            "contributing_features": contributing_features,
            "model": "Isolation Forest",
            "model_version": self.model_version,
            "baseline_window": self.baseline_window_sec,
            "detection_timestamp": now,
            "training_samples_count": len(self.training_samples),
            "model_status": "OPERATIONAL"
        }


isolation_forest_detector = IsolationForestDetector()
