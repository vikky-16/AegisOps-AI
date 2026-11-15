"""
AegisOps AI - Multi-Detector Telemetry Anomaly Engine (Phases 3, 4, 5, 7)
Centralizes detection algorithms and configuration:
- Phase 3: Z-Score Detector (|z| >= 3.0)
- Phase 4: EWMA Drift Detector
- Phase 5: Multivariate Isolation Forest (evaluated on window features, not per log)
- Phase 6: Error Pattern Detector integration
- Phase 7: Normalized Combined Anomaly Scoring and behavioral severity assignment
"""

import math
import uuid
import time
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from backend.app.analytics.baseline_engine import baseline_engine
from backend.app.analytics.error_pattern_detector import error_pattern_detector
from sklearn.ensemble import IsolationForest


class DetectorConfig:
    """Centralized detector configuration."""
    def __init__(
        self,
        z_threshold: float = 3.0,
        ewma_threshold: float = 2.5,
        iqr_threshold: float = 1.5,
        isolation_contamination: float = 0.08,
        weights: Optional[Dict[str, float]] = None
    ):
        self.z_threshold = z_threshold
        self.ewma_threshold = ewma_threshold
        self.iqr_threshold = iqr_threshold
        self.isolation_contamination = isolation_contamination
        self.weights = weights or {
            "z_score": 0.30,
            "ewma": 0.20,
            "iqr": 0.20,
            "isolation_forest": 0.30
        }


class IsolationForestEngine:
    """
    Multivariate Isolation Forest trained and evaluated safely on windowed feature vectors.
    Single-threaded execution (n_jobs=1) ensures complete stability on Windows.
    """
    FEATURE_NAMES = [
        "requests_per_second",
        "error_rate",
        "p95_latency",
        "p99_latency",
        "timeout_rate",
        "http_5xx_rate",
        "database_latency",
        "redis_latency"
    ]

    def __init__(self, contamination: float = 0.08, min_samples_to_fit: int = 30):
        self.contamination = contamination
        self.min_samples_to_fit = min_samples_to_fit
        self.model: Optional[IsolationForest] = None
        self.is_fitted: bool = False
        self.model_status: str = "INSUFFICIENT_HISTORY"
        self.training_samples: List[List[float]] = []
        self.max_training_samples = 300

    def extract_vector(self, features: Dict[str, Any]) -> List[float]:
        p95 = float(features.get("p95_latency", features.get("latency_p95_ms", 25.0)))
        p99 = float(features.get("p99_latency", features.get("latency_p99_ms", 35.0)))
        db_lat = float(features.get("database_latency", features.get("db_latency_ms", 5.0)))
        redis_lat = float(features.get("cache_latency", features.get("redis_latency_ms", 1.5)))

        return [
            float(features.get("requests_per_second", 0.0)),
            float(features.get("error_rate", 0.0)),
            p95,
            p99,
            float(features.get("timeout_rate", 0.0)),
            float(features.get("http_5xx_rate", 0.0)),
            db_lat,
            redis_lat
        ]

    def fit(self, samples: List[List[float]]):
        if len(samples) < self.min_samples_to_fit:
            self.model_status = "INSUFFICIENT_HISTORY"
            return
        X = np.array(samples)
        model = IsolationForest(
            n_estimators=50,
            contamination=self.contamination,
            random_state=42,
            n_jobs=1
        )
        model.fit(X)
        self.model = model
        self.is_fitted = True
        self.model_status = "OPERATIONAL"

    def record_normal_sample(self, vector: List[float]):
        """Only train on real normal baseline windows, never corrupted incident windows."""
        err_rate = vector[1]
        p95 = vector[2]
        if err_rate < 0.03 and p95 < 150.0:
            self.training_samples.append(vector)
            if len(self.training_samples) > self.max_training_samples:
                self.training_samples.pop(0)
            if len(self.training_samples) >= self.min_samples_to_fit and not self.is_fitted:
                self.fit(self.training_samples)
            elif len(self.training_samples) % 50 == 0:
                self.fit(self.training_samples)

    def detect(self, vector: List[float]) -> Tuple[bool, float, Dict[str, Any]]:
        """Returns: (is_anomaly, anomaly_score, explanation)"""
        if not self.is_fitted or self.model is None or self.model_status == "INSUFFICIENT_HISTORY":
            if not self.training_samples:
                np.random.seed(42)
                seed = [
                    [15.0 + float(np.random.normal(0, 1.5)), 0.005 + float(max(0, np.random.normal(0, 0.002))), 25.0 + float(np.random.normal(0, 3.0)), 35.0, 0.0, 0.0, 5.0, 1.5]
                    for _ in range(self.min_samples_to_fit + 15)
                ]
                self.fit(seed)
            else:
                return False, 0.0, {
                    "model_status": "INSUFFICIENT_HISTORY",
                    "sample_count": len(self.training_samples),
                    "required_samples": self.min_samples_to_fit,
                    "reason": f"Insufficient historical telemetry ({len(self.training_samples)}/{self.min_samples_to_fit}); statistical detectors active"
                }

        X = np.array([vector])
        pred = self.model.predict(X)[0]  # -1 for anomaly, 1 for normal
        raw_score = -float(self.model.score_samples(X)[0])  # higher = more anomalous

        # Extreme metric check
        has_extreme_features = (vector[1] >= 0.10 or vector[2] >= 500.0 or vector[6] >= 500.0)

        # Normalize score to 0.0 - 1.0 range
        norm_score = round(max(0.0, min(1.0, (raw_score - 0.40) / 0.35)), 3)
        if has_extreme_features:
            norm_score = max(norm_score, 0.75)
        is_anom = (pred == -1 or norm_score >= 0.50 or has_extreme_features)

        return is_anom, norm_score, {
            "model_status": "OPERATIONAL",
            "raw_score": round(raw_score, 3),
            "normalized_score": norm_score,
            "prediction": int(pred)
        }


class RealTelemetryAnomalyDetector:
    """
    Comprehensive Anomaly Detection Engine combining Z-Score, EWMA,
    Multivariate Isolation Forest, and Error Pattern Detection.
    """
    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self.isolation_forest = IsolationForestEngine(contamination=self.config.isolation_contamination)

    def detect_zscore(
        self,
        tenant_id: str,
        service: str,
        feature: str,
        current_value: float
    ) -> Dict[str, Any]:
        """
        Phase 3: Z-Score Anomaly Detector.
        z = (current_value - rolling_mean) / rolling_std
        """
        base = baseline_engine.get_feature_baseline(tenant_id, service, feature)
        mean = base.rolling_mean
        std = max(0.5, base.rolling_std)

        z = (current_value - mean) / std
        threshold = self.config.z_threshold
        is_anom = (abs(z) >= threshold)

        # Normalize to 0.0 - 1.0 sigmoid
        if z <= 0.0:
            anomaly_score = 0.0
        else:
            anomaly_score = round(min(1.0, 1.0 / (1.0 + math.exp(-0.8 * (z - 2.5)))), 3)

        return {
            "detector_name": "z_score",
            "feature": feature,
            "current_value": round(current_value, 2),
            "baseline": round(mean, 2),
            "rolling_std": round(std, 2),
            "z_score": round(z, 2),
            "threshold": threshold,
            "is_anomaly": is_anom,
            "anomaly_score": anomaly_score
        }

    def detect_ewma(
        self,
        tenant_id: str,
        service: str,
        feature: str,
        current_value: float
    ) -> Dict[str, Any]:
        """
        Phase 4: EWMA Anomaly Detector for gradual drift.
        """
        base = baseline_engine.get_feature_baseline(tenant_id, service, feature)
        ewma_val = base.ewma if base.ewma is not None else base.rolling_mean
        baseline = base.rolling_mean
        diff = current_value - ewma_val
        deviation = abs(diff)

        # Scale relative to rolling std
        scale = max(1.0, base.rolling_std)
        factor = deviation / scale
        is_anom = (factor >= self.config.ewma_threshold)
        anomaly_score = round(min(1.0, factor / 4.0), 3)

        trend = "increasing" if diff > 1.0 else ("decreasing" if diff < -1.0 else "stable")

        return {
            "detector_name": "ewma",
            "feature": feature,
            "current_value": round(current_value, 2),
            "ewma_value": round(ewma_val, 2),
            "baseline": round(baseline, 2),
            "deviation": round(deviation, 2),
            "trend": trend,
            "is_anomaly": is_anom,
            "anomaly_score": anomaly_score
        }

    def detect_iqr(
        self,
        tenant_id: str,
        service: str,
        feature: str,
        current_value: float
    ) -> Dict[str, Any]:
        """
        Part 6: IQR / Percentile Deviation Anomaly Detector.
        Identifies deviations beyond the interquartile range fences:
        Upper Fence = Q3 + 1.5 * IQR
        Lower Fence = Q1 - 1.5 * IQR
        """
        base = baseline_engine.get_feature_baseline(tenant_id, service, feature)
        q1, q3, iqr = base.get_iqr_bounds()
        multiplier = getattr(self.config, "iqr_threshold", 1.5)
        upper_fence = q3 + multiplier * iqr
        lower_fence = max(0.0, q1 - multiplier * iqr)
        
        is_anom = (current_value > upper_fence)
        deviation = max(0.0, current_value - upper_fence)
        if deviation <= 0.0:
            anomaly_score = 0.0
        else:
            scale = max(1.0, iqr)
            anomaly_score = round(min(1.0, 1.0 / (1.0 + math.exp(-1.2 * (deviation / scale - 1.0)))), 3)

        return {
            "detector_name": "iqr",
            "feature": feature,
            "current_value": round(current_value, 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "upper_fence": round(upper_fence, 2),
            "lower_fence": round(lower_fence, 2),
            "is_anomaly": is_anom,
            "anomaly_score": anomaly_score
        }

    def evaluate(
        self,
        tenant_id: str,
        service: str,
        features: Dict[str, Any],
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Part 6: Multi-Algorithm Anomaly Evaluation:
        1. Z-Score (|z| >= 3.0)
        2. EWMA (Drift factor >= 2.5)
        3. IQR (Percentile deviation > Q3 + 1.5 * IQR)
        4. Multivariate Isolation Forest
        """
        now = current_time or time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        tenant = tenant_id.lower()

        # Update baseline engine with current observation
        baseline_engine.record_service_observation(tenant, service, features, timestamp=now)

        # Check warm-up suppression (Phase 2 & Part 5)
        is_warmed, warmup_elapsed = baseline_engine.is_warmed_up(tenant, service, current_time=now)
        if not is_warmed:
            return {
                "anomaly_id": None,
                "tenant_id": tenant,
                "company": tenant,
                "service": service,
                "timestamp": now_iso,
                "is_anomaly": False,
                "is_warmup": True,
                "warmup_elapsed_sec": round(warmup_elapsed, 1),
                "combined_score": 0.0,
                "statistical_anomaly_score": 0.0,
                "ml_anomaly_score": 0.0,
                "severity": "NORMAL",
                "detectors_triggered": [],
                "summary": f"Service '{service}' is establishing baseline warm-up ({warmup_elapsed:.1f}s / {baseline_engine.warmup_seconds}s)"
            }

        # Select primary representative feature for univariate detectors
        p95 = float(features.get("p95_latency", features.get("latency_p95_ms", 25.0)))
        db_lat = float(features.get("database_latency", features.get("db_latency_ms", 0.0)))
        redis_lat = float(features.get("cache_latency", features.get("redis_latency_ms", 0.0)))
        effective_latency = max(p95, db_lat if db_lat > 50.0 else 0.0, redis_lat if redis_lat > 50.0 else 0.0)

        # 1. Z-Score Detector
        z_res = self.detect_zscore(tenant, service, "p95_latency", effective_latency)
        z_score = z_res["anomaly_score"]
        z_val = z_res["z_score"]

        # 2. EWMA Detector
        ewma_res = self.detect_ewma(tenant, service, "p95_latency", effective_latency)
        ewma_score = ewma_res["anomaly_score"]

        # 3. IQR / Percentile Deviation Detector
        iqr_res = self.detect_iqr(tenant, service, "p95_latency", effective_latency)
        iqr_score = iqr_res["anomaly_score"]

        # 4. Multivariate Isolation Forest
        vec = self.isolation_forest.extract_vector(features)
        if_anom, if_score, if_expl = self.isolation_forest.detect(vec)
        self.isolation_forest.record_normal_sample(vec)

        # 5. Error Pattern Surge (Supporting indicator)
        err_anom, err_pat_score, top_patterns = error_pattern_detector.evaluate_service_patterns(tenant, service, current_time=now)
        raw_err_rate = float(features.get("error_rate", 0.0))
        raw_timeout_rate = float(features.get("timeout_rate", 0.0))
        raw_5xx_rate = float(features.get("http_5xx_rate", 0.0))
        raw_4xx_rate = float(features.get("four_xx_rate", features.get("http_4xx_rate", 0.0)))
        raw_traffic_change = float(features.get("traffic_change", features.get("request_rate_change", 0.0)))

        if raw_err_rate >= 0.05 or raw_timeout_rate >= 0.05 or raw_5xx_rate >= 0.05 or raw_4xx_rate >= 0.15:
            fallback_err_score = min(1.0, max(raw_err_rate * 2.0, raw_timeout_rate * 2.5, raw_5xx_rate * 2.5, raw_4xx_rate * 1.8))
            err_pat_score = max(err_pat_score, fallback_err_score)

        # Part 6: Calculate Statistical Anomaly Score and ML Anomaly Score
        model_status = if_expl.get("model_status", "INSUFFICIENT_HISTORY")
        statistical_anomaly_score = round(max(z_score, (z_score * 0.4 + ewma_score * 0.3 + iqr_score * 0.3)), 3)
        ml_anomaly_score = round(if_score, 3)

        # Part 6: Combined Anomaly Score formula
        w = self.config.weights
        if model_status == "INSUFFICIENT_HISTORY":
            # If insufficient historical data, rely on statistical algorithms without penalizing model score
            combined_score = round(0.40 * z_score + 0.30 * ewma_score + 0.30 * iqr_score, 3)
        else:
            combined_score = round(
                (w.get("z_score", 0.30) * z_score)
                + (w.get("ewma", 0.20) * ewma_score)
                + (w.get("iqr", 0.20) * iqr_score)
                + (w.get("isolation_forest", 0.30) * if_score),
                3
            )

        detectors_triggered = []
        if z_res["is_anomaly"] or z_score >= 0.50:
            detectors_triggered.append(f"Z-Score ({z_val:.1f} sigma > threshold {z_res['threshold']})")
        if ewma_res["is_anomaly"] or ewma_score >= 0.45:
            detectors_triggered.append(f"EWMA Drift (+{ewma_res['deviation']}ms, {ewma_res['trend']})")
        if iqr_res["is_anomaly"] or iqr_score >= 0.45:
            detectors_triggered.append(f"IQR Fence Breach (+{iqr_res['current_value'] - iqr_res['upper_fence']:.1f}ms > Q3+1.5*IQR)")
        if if_anom or if_score >= 0.50:
            detectors_triggered.append(f"Isolation Forest (multivariate anomaly score {if_score:.2f})")
        if err_anom or err_pat_score >= 0.45:
            pat_desc = top_patterns[0]["template"] if top_patterns else f"error_rate {raw_err_rate*100:.1f}%"
            detectors_triggered.append(f"Error Pattern Surge ({pat_desc})")
        if raw_4xx_rate >= 0.20:
            detectors_triggered.append(f"HTTP 4xx Surge ({raw_4xx_rate*100:.1f}%)")
        if raw_traffic_change >= 2.0 and (raw_err_rate >= 0.05 or effective_latency >= 200.0):
            detectors_triggered.append(f"Traffic Surge (+{raw_traffic_change*100:.0f}%)")

        is_overall_anomaly = (
            combined_score >= 0.45
            or (len(detectors_triggered) >= 2 and combined_score >= 0.38)
            or (z_res["is_anomaly"] and if_anom and combined_score >= 0.40)
            or (raw_err_rate >= 0.15)
            or (raw_5xx_rate >= 0.15)
            or (raw_4xx_rate >= 0.20)
            or (raw_timeout_rate >= 0.15)
            or (raw_traffic_change >= 2.5 and raw_err_rate >= 0.05)
            or (effective_latency >= 1000.0)
        )

        # Assign Severity based on measurable behavior
        if combined_score >= 0.75 or raw_err_rate >= 0.40 or effective_latency >= 2500.0:
            severity = "CRITICAL"
        elif combined_score >= 0.55 or raw_err_rate >= 0.15 or effective_latency >= 800.0:
            severity = "HIGH"
        elif (combined_score >= 0.45 or raw_err_rate >= 0.05 or effective_latency >= 300.0) and (raw_err_rate >= 0.02 or effective_latency >= 80.0):
            severity = "MEDIUM"
        elif combined_score >= 0.25 and (raw_err_rate >= 0.01 or effective_latency >= 50.0):
            severity = "LOW"
        else:
            severity = "NORMAL"

        anomaly_id = f"ANOM-{uuid.uuid4().hex[:8].upper()}" if is_overall_anomaly else None

        return {
            "anomaly_id": anomaly_id,
            "tenant_id": tenant,
            "company": tenant,
            "service": service,
            "timestamp": now_iso,
            "is_anomaly": is_overall_anomaly,
            "is_warmup": False,
            "model_status": model_status,
            "combined_score": combined_score,
            "statistical_anomaly_score": statistical_anomaly_score,
            "ml_anomaly_score": ml_anomaly_score,
            "severity": severity,
            "scores": {
                "statistical_score": statistical_anomaly_score,
                "z_score": z_score,
                "ewma_score": ewma_score,
                "iqr_score": iqr_score,
                "ml_score": ml_anomaly_score,
                "isolation_score": if_score,
                "error_pattern_score": err_pat_score
            },
            "detector_details": {
                "z_score": z_res,
                "ewma": ewma_res,
                "iqr": iqr_res,
                "isolation_forest": {
                    "model_status": model_status,
                    "is_anomaly": if_anom,
                    "anomaly_score": if_score,
                    "vector": vec,
                    "explanation": if_expl
                },
                "error_pattern": {
                    "is_anomaly": err_anom,
                    "score": err_pat_score,
                    "top_patterns": top_patterns
                }
            },
            "detectors_triggered": detectors_triggered,
            "features": features,
            "summary": f"{severity} anomaly on '{service}': {'; '.join(detectors_triggered)}" if is_overall_anomaly else f"Normal telemetry on '{service}' (score: {combined_score:.2f})"
        }


anomaly_detector = RealTelemetryAnomalyDetector()
