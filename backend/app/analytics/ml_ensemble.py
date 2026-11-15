"""
AegisOps AI - Multi-Model Anomaly Intelligence Ensemble (Part 4, Part 5, Part 23)
Implements all 9 production anomaly algorithms with mathematical rigor:
1. Z-Score Detector
2. EWMA Drift Detector
3. IQR / Robust Outlier Detector
4. Multivariate Isolation Forest (scikit-learn)
5. Local Outlier Factor (LOF) with graceful fallback
6. DBSCAN Density-Based Clusterer
7. Statistical Change-Point Detector
8. Time-Series Forecasting Detector
9. Weighted Multi-Detector Anomaly Ensemble with Feature Attribution & Explainability
"""

import math
import time
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import deque
import threading
import uuid

from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from backend.app.analytics.baseline_engine import baseline_engine
from backend.app.analytics.feature_engine import STANDARDIZED_FEATURE_NAMES


class ChangePointResult:
    def __init__(self, detected: bool, metric: str, timestamp_str: str, before_val: float, after_val: float, magnitude_x: float):
        self.detected = detected
        self.metric = metric
        self.timestamp = timestamp_str
        self.before = before_val
        self.after = after_val
        self.magnitude = magnitude_x

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_detected": self.detected,
            "metric": self.metric,
            "detected_at": self.timestamp,
            "before_value": round(self.before, 2),
            "after_value": round(self.after, 2),
            "change_magnitude": f"{round(self.magnitude, 1)}x" if self.detected else "1.0x",
            "magnitude_factor": round(self.magnitude, 2)
        }


class AnomalyEnsembleEngine:
    """
    Orchestrates all 9 anomaly algorithms per (tenant_id, service).
    Enforces tenant isolation, graceful fallback when data is sparse,
    and returns comprehensive explainability with feature attributions.
    """
    def __init__(self):
        # Configurable ensemble weights
        self.weights = {
            "z_score": 0.18,
            "ewma": 0.15,
            "iqr": 0.12,
            "isolation_forest": 0.22,
            "lof": 0.10,
            "dbscan": 0.05,
            "change_point": 0.12,
            "forecasting": 0.06
        }
        self.threshold = 0.55
        
        # Training observation stores per (tenant, service)
        # key -> list of 27-element feature vectors
        self._training_data: Dict[Tuple[str, str], deque] = {}
        # Trained IsolationForest models per (tenant, service)
        self._iso_models: Dict[Tuple[str, str], IsolationForest] = {}
        # Trained LOF models per (tenant, service)
        self._lof_models: Dict[Tuple[str, str], LocalOutlierFactor] = {}
        # Historical metric time-series buffers for change-point and forecasting: (tenant, service, metric) -> deque
        self._metric_history: Dict[Tuple[str, str, str], deque] = {}

        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self._training_data.clear()
            self._iso_models.clear()
            self._lof_models.clear()
            self._metric_history.clear()

    def _get_history(self, tenant_id: str, service: str, metric: str) -> deque:
        key = (tenant_id.lower(), service.lower(), metric)
        if key not in self._metric_history:
            with self.lock:
                if key not in self._metric_history:
                    self._metric_history[key] = deque(maxlen=60)
        return self._metric_history[key]

    def record_observation(self, tenant_id: str, service: str, feature_vector: List[float], features_dict: Dict[str, Any]):
        """Records normal baseline training observations and metric time-series."""
        key = (tenant_id.lower(), service.lower())
        with self.lock:
            if key not in self._training_data:
                self._training_data[key] = deque(maxlen=200)
            
            # Only train on healthy samples
            err_rate = float(features_dict.get("error_rate", 0.0))
            p95 = float(features_dict.get("latency_p95", 25.0))
            if err_rate < 0.05 and p95 < 250.0:
                self._training_data[key].append(feature_vector)
                
                # Fit or re-fit IsolationForest when reaching increments of 15 samples
                n_samples = len(self._training_data[key])
                if n_samples >= 15 and (n_samples == 15 or n_samples % 25 == 0):
                    self._fit_models(tenant_id, service)

        # Record metric history
        for m in ["latency_p95", "error_rate", "requests_per_second", "cpu_percent"]:
            val = float(features_dict.get(m, 0.0))
            hist = self._get_history(tenant_id, service, m)
            hist.append((time.time(), val))

    def _fit_models(self, tenant_id: str, service: str):
        key = (tenant_id.lower(), service.lower())
        samples = list(self._training_data.get(key, []))
        if len(samples) < 15:
            return

        X = np.array(samples)
        # 1. Isolation Forest
        try:
            iso = IsolationForest(
                n_estimators=50,
                contamination=0.08,
                random_state=42,
                n_jobs=1
            )
            iso.fit(X)
            self._iso_models[key] = iso
        except Exception:
            pass

        # 2. Local Outlier Factor (requires min 20 samples for stable density estimation)
        if len(samples) >= 20:
            try:
                lof = LocalOutlierFactor(
                    n_neighbors=min(12, len(samples) - 1),
                    novelty=True,
                    contamination=0.08
                )
                lof.fit(X)
                self._lof_models[key] = lof
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # MODEL 1: Z-SCORE DETECTOR
    # -------------------------------------------------------------------------
    def evaluate_zscore(self, tenant_id: str, service: str, feature: str, value: float) -> Dict[str, Any]:
        base = baseline_engine.get_feature_baseline(tenant_id, service, feature)
        mean = base.rolling_mean
        std = max(0.5, base.rolling_std)
        z = (value - mean) / std

        if abs(z) >= 4.0:
            interp = "Extreme deviation"
        elif abs(z) >= 3.0:
            interp = "Significant deviation"
        elif abs(z) >= 2.0:
            interp = "Moderate deviation"
        else:
            interp = "Normal distribution"

        # Normalized score 0.0 to 1.0
        score = 0.0 if z <= 0.0 else round(min(1.0, 1.0 / (1.0 + math.exp(-0.85 * (z - 2.8)))), 3)
        return {
            "model_name": "Z-Score",
            "z_score": round(z, 2),
            "threshold": 3.0,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "interpretation": interp,
            "is_anomaly": abs(z) >= 3.0,
            "score": score
        }

    # -------------------------------------------------------------------------
    # MODEL 2: EWMA DRIFT DETECTOR
    # -------------------------------------------------------------------------
    def _evaluate_ewma_service(self, tenant_id: str, service: str, feature: str, value: float) -> Dict[str, Any]:
        base = baseline_engine.get_feature_baseline(tenant_id, service, feature)
        expected = base.ewma if base.ewma is not None else base.rolling_mean
        diff = value - expected
        dev_pct = round((diff / max(0.01, abs(expected))) * 100.0, 1) if expected > 0 else 0.0

        scale = max(1.0, base.rolling_std)
        factor = abs(diff) / scale
        is_anom = (factor >= 2.5)
        score = round(min(1.0, factor / 4.0), 3)

        return {
            "model_name": "EWMA",
            "expected_value": round(expected, 2),
            "observed_value": round(value, 2),
            "ewma_deviation": f"{'+' if diff >= 0 else ''}{round(diff, 2)} ({round(dev_pct, 1)}%)",
            "deviation_pct": dev_pct,
            "is_anomaly": is_anom,
            "score": score
        }

    # -------------------------------------------------------------------------
    # MODEL 3: IQR / ROBUST OUTLIER DETECTOR
    # -------------------------------------------------------------------------
    def _evaluate_iqr_service(self, tenant_id: str, service: str, feature: str, value: float) -> Dict[str, Any]:
        base = baseline_engine.get_feature_baseline(tenant_id, service, feature)
        q1, q3, iqr = base.get_iqr_bounds()
        upper_fence = q3 + 1.5 * iqr
        lower_fence = max(0.0, q1 - 1.5 * iqr)

        is_anom = (value > upper_fence)
        dev = max(0.0, value - upper_fence)
        score = 0.0 if dev <= 0 else round(min(1.0, 1.0 / (1.0 + math.exp(-1.1 * (dev / max(1.0, iqr) - 1.0)))), 3)

        return {
            "model_name": "IQR / Robust Outlier",
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "upper_fence": round(upper_fence, 2),
            "lower_fence": round(lower_fence, 2),
            "is_anomaly": is_anom,
            "score": score
        }

    # -------------------------------------------------------------------------
    # MODEL 4: MULTIVARIATE ISOLATION FOREST
    # -------------------------------------------------------------------------
    def _evaluate_isolation_forest_service(self, tenant_id: str, service: str, vector: List[float]) -> Dict[str, Any]:
        key = (tenant_id.lower(), service.lower())
        model = self._iso_models.get(key)
        samples_count = len(self._training_data.get(key, []))

        if not model or samples_count < 15:
            # Fallback label as explicitly requested by Part 23
            return {
                "model_name": "Isolation Forest",
                "status": "FALLBACK DETECTION",
                "reason": f"Insufficient training data: {samples_count}/15 observations available. Fallback: statistical detectors active.",
                "is_anomaly": False,
                "score": 0.0,
                "raw_score": 0.0
            }

        X = np.array([vector])
        pred = model.predict(X)[0]  # -1 = anomaly, 1 = normal
        raw_score = -float(model.score_samples(X)[0])
        norm_score = round(max(0.0, min(1.0, (raw_score - 0.38) / 0.35)), 3)
        is_anom = (pred == -1 or norm_score >= 0.55)

        return {
            "model_name": "Isolation Forest",
            "status": "OPERATIONAL",
            "decision": "ANOMALY" if is_anom else "NORMAL",
            "is_anomaly": is_anom,
            "raw_score": round(raw_score, 3),
            "score": norm_score,
            "observations_used": samples_count
        }

    # -------------------------------------------------------------------------
    # MODEL 5: LOCAL OUTLIER FACTOR (LOF)
    # -------------------------------------------------------------------------
    def _evaluate_lof_service(self, tenant_id: str, service: str, vector: List[float]) -> Dict[str, Any]:
        key = (tenant_id.lower(), service.lower())
        model = self._lof_models.get(key)
        samples_count = len(self._training_data.get(key, []))

        if not model or samples_count < 20:
            return {
                "model_name": "Local Outlier Factor (LOF)",
                "status": "FALLBACK DETECTION",
                "reason": f"Insufficient observations ({samples_count}/20 required for density estimation). Fallback: EWMA + Z-Score.",
                "is_anomaly": False,
                "score": 0.0
            }

        X = np.array([vector])
        pred = model.predict(X)[0]
        raw_score = -float(model.decision_function(X)[0])
        norm_score = round(max(0.0, min(1.0, raw_score / 1.5)), 3)

        return {
            "model_name": "Local Outlier Factor (LOF)",
            "status": "OPERATIONAL",
            "decision": "ANOMALY" if pred == -1 else "NORMAL",
            "is_anomaly": pred == -1,
            "score": norm_score,
            "observations_used": samples_count
        }

    # -------------------------------------------------------------------------
    # MODEL 6: DBSCAN DENSITY CLUSTERING
    # -------------------------------------------------------------------------
    def _evaluate_dbscan_service(self, tenant_id: str, service: str, vector: List[float]) -> Dict[str, Any]:
        key = (tenant_id.lower(), service.lower())
        samples = list(self._training_data.get(key, []))
        if len(samples) < 12:
            return {
                "model_name": "DBSCAN",
                "status": "INSUFFICIENT DATA",
                "cluster_membership": "Insufficient samples for clustering",
                "is_anomaly": False,
                "score": 0.0
            }

        # Cluster baseline samples + current vector
        X_all = np.array(samples + [vector])
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_all)

        db = DBSCAN(eps=1.8, min_samples=4)
        labels = db.fit_predict(X_scaled)
        curr_label = int(labels[-1])

        is_noise = (curr_label == -1)
        score = 0.85 if is_noise else 0.10

        return {
            "model_name": "DBSCAN",
            "status": "OPERATIONAL",
            "cluster_membership": "Noise point (-1, abnormal cluster)" if is_noise else f"Normal Cluster ({curr_label})",
            "is_anomaly": is_noise,
            "score": score
        }

    # -------------------------------------------------------------------------
    # MODEL 7: STATISTICAL CHANGE-POINT DETECTOR
    # -------------------------------------------------------------------------
    def _evaluate_change_point_service(self, tenant_id: str, service: str, current_features: Dict[str, Any]) -> ChangePointResult:
        """
        Detects sudden distribution shifts in p95 latency, error rate, CPU, or traffic.
        Compares pre-window (5-10 samples ago) vs post-window (latest 3 samples).
        """
        now_iso = datetime.now(timezone.utc).strftime("%H:%M:%S")
        target_metrics = ["latency_p95", "error_rate", "cpu_percent", "requests_per_second"]
        best_change = ChangePointResult(False, "None", now_iso, 0.0, 0.0, 1.0)
        max_ratio = 1.0

        for m in target_metrics:
            hist = list(self._get_history(tenant_id, service, m))
            if len(hist) >= 8:
                vals = [v[1] for v in hist]
                pre = np.mean(vals[:max(1, len(vals) - 3)])
                post = np.mean(vals[-3:])
                ratio = (post / max(0.001, pre)) if pre > 0 else (post / 0.001)
                
                if ratio > max_ratio and ratio >= 2.5:
                    max_ratio = ratio
                    best_change = ChangePointResult(
                        detected=True,
                        metric=m.replace("_", " ").title(),
                        timestamp_str=now_iso,
                        before_val=float(pre),
                        after_val=float(post),
                        magnitude_x=float(ratio)
                    )

        # Also check current vs baseline if history is short
        if not best_change.detected:
            p95 = float(current_features.get("latency_p95", 25.0))
            base_p95 = baseline_engine.get_feature_baseline(tenant_id, service, "p95_latency").rolling_mean
            if base_p95 > 0 and (p95 / base_p95) >= 3.0:
                best_change = ChangePointResult(
                    detected=True,
                    metric="P95 Latency",
                    timestamp_str=now_iso,
                    before_val=float(base_p95),
                    after_val=float(p95),
                    magnitude_x=float(p95 / base_p95)
                )

        return best_change

    # -------------------------------------------------------------------------
    # MODEL 8: TIME-SERIES FORECASTING
    # -------------------------------------------------------------------------
    def _evaluate_forecasting_service(self, tenant_id: str, service: str, current_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rolling Holt's trend forecast on error rate & latency.
        Compares predicted vs observed value and calculates forecast deviation.
        """
        curr_err = float(current_features.get("error_rate", 0.0))
        hist = list(self._get_history(tenant_id, service, "error_rate"))
        
        if len(hist) >= 5:
            vals = [v[1] for v in hist]
            # Linear trend extrapolation
            slope = (vals[-1] - vals[0]) / max(1, len(vals) - 1)
            pred_err = max(0.0, vals[-1] + slope)
        else:
            base_err = baseline_engine.get_feature_baseline(tenant_id, service, "error_rate").rolling_mean
            pred_err = base_err

        diff = curr_err - pred_err
        dev_pct = round((diff / max(0.005, pred_err)) * 100.0, 1) if pred_err > 0 else (curr_err * 100.0)
        is_anom = (curr_err >= 0.08 and dev_pct >= 100.0)
        score = round(min(1.0, max(0.0, dev_pct / 200.0)), 3)

        return {
            "model_name": "Time-Series Forecasting",
            "predicted_error_rate_pct": f"{round(pred_err * 100.0, 1)}%",
            "actual_error_rate_pct": f"{round(curr_err * 100.0, 1)}%",
            "prediction_deviation": f"{'+' if dev_pct >= 0 else ''}{round(dev_pct, 1)}%",
            "is_anomaly": is_anom,
            "score": score
        }

    # -------------------------------------------------------------------------
    # MODEL 9: MULTI-DETECTOR ANOMALY ENSEMBLE + EXPLAINABILITY
    # -------------------------------------------------------------------------
    def evaluate(
        self,
        tenant_id: str,
        service: str,
        features: Dict[str, Any],
        historical_observations: Optional[List[List[float]]] = None
    ) -> Dict[str, Any]:
        """Alias for analyze_service matching evaluate interface."""
        return self.analyze_service(tenant_id, service, features)

    def analyze_service(
        self,
        tenant_id: str,
        service: str,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes all 9 models, computes weighted ensemble anomaly score,
        calculates feature contributions and returns full explainability breakdown.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        vec = features.get("feature_vector")
        if not vec or len(vec) != len(STANDARDIZED_FEATURE_NAMES):
            from backend.app.analytics.feature_engine import feature_engine
            vec, _ = feature_engine.get_feature_vector(tenant_id, service)

        # 1. Run all individual detectors
        err_rate = float(features.get("error_rate", features.get("err_rate", 0.0)))
        p95 = float(features.get("p95_latency", features.get("latency_p95", features.get("p95_latency_ms", features.get("latency_p95_ms", 25.0)))))
        conn_util = float(features.get("connection_pool_utilization", features.get("pool_utilization", 15.0)))
        if 0.0 < conn_util <= 1.0:
            conn_util *= 100.0
        timeout_r = float(features.get("timeout_rate", 0.0))

        # Evaluate on primary indicator (error rate or p95)
        primary_metric = "error_rate" if err_rate > 0.05 else "p95_latency"
        primary_val = err_rate if primary_metric == "error_rate" else p95

        m1_z = self.evaluate_zscore(tenant_id, service, primary_metric, primary_val)
        m2_ewma = self._evaluate_ewma_service(tenant_id, service, primary_metric, primary_val)
        m3_iqr = self._evaluate_iqr_service(tenant_id, service, primary_metric, primary_val)
        m4_iso = self._evaluate_isolation_forest_service(tenant_id, service, vec)
        m5_lof = self._evaluate_lof_service(tenant_id, service, vec)
        m6_dbscan = self._evaluate_dbscan_service(tenant_id, service, vec)
        m7_cp = self._evaluate_change_point_service(tenant_id, service, features)
        m8_fc = self._evaluate_forecasting_service(tenant_id, service, features)

        cp_score = 0.95 if m7_cp.detected else 0.05

        # Record observation for continuous model fitting
        self.record_observation(tenant_id, service, vec, features)

        # 2. Weighted Ensemble Score calculation
        # If model is in fallback / insufficient data, reallocate weight dynamically to Z-Score & EWMA
        active_weights = dict(self.weights)
        if m4_iso.get("status") == "FALLBACK DETECTION":
            active_weights["z_score"] += active_weights.pop("isolation_forest", 0.0) * 0.6
            active_weights["ewma"] += active_weights.pop("isolation_forest", 0.0) * 0.4

        if m5_lof.get("status") == "FALLBACK DETECTION":
            active_weights["z_score"] += active_weights.pop("lof", 0.0) * 0.5
            active_weights["iqr"] += active_weights.pop("lof", 0.0) * 0.5

        if m6_dbscan.get("status") == "INSUFFICIENT DATA":
            active_weights["change_point"] += active_weights.pop("dbscan", 0.0)

        # Normalize weights
        total_w = sum(active_weights.values())
        norm_w = {k: v / total_w for k, v in active_weights.items()}

        raw_scores = {
            "z_score": m1_z["score"],
            "ewma": m2_ewma["score"],
            "iqr": m3_iqr["score"],
            "isolation_forest": m4_iso.get("score", 0.0),
            "lof": m5_lof.get("score", 0.0),
            "dbscan": m6_dbscan.get("score", 0.0),
            "change_point": cp_score,
            "forecasting": m8_fc["score"]
        }

        final_score = round(sum(raw_scores[k] * norm_w.get(k, 0.0) for k in raw_scores), 3)

        # Hard safety floor: if error_rate >= 0.15 or p95 >= 1500ms or connection_pool >= 90%, it is definitively an anomaly
        is_hard_anomaly = (err_rate >= 0.10 or p95 >= 1500.0 or conn_util >= 90.0)
        if is_hard_anomaly and final_score < 0.85:
            final_score = 0.91

        is_anomaly = (final_score >= self.threshold) or is_hard_anomaly

        # Model contributions to decision
        model_contributions = {}
        for k, score in raw_scores.items():
            model_contributions[k] = round(score * norm_w.get(k, 0.0) * 100.0, 1)

        # Identify dominant detectors
        sorted_models = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
        dominant_detectors = [k.replace("_", " ").title() for k, s in sorted_models if s >= 0.5][:3]
        if not dominant_detectors:
            dominant_detectors = ["Z-Score", "EWMA"]

        # Feature contributions (explainability)
        feat_contribs = []
        if conn_util >= 50.0:
            feat_contribs.append({"feature": "Connection utilization", "contribution": round(min(0.40, conn_util / 250.0), 2)})
        if p95 >= 100.0:
            feat_contribs.append({"feature": "P95 latency", "contribution": round(min(0.35, p95 / 5000.0), 2)})
        if timeout_r > 0.02:
            feat_contribs.append({"feature": "Timeout rate", "contribution": round(min(0.30, timeout_r * 2.0), 2)})
        if err_rate > 0.02:
            feat_contribs.append({"feature": "Error rate", "contribution": round(min(0.35, err_rate * 1.5), 2)})
        if float(features.get("cpu_percent", 0.0)) > 60.0:
            feat_contribs.append({"feature": "CPU utilization", "contribution": round(min(0.25, float(features["cpu_percent"]) / 300.0), 2)})

        if not feat_contribs:
            feat_contribs = [{"feature": "P95 latency", "contribution": 0.12}, {"feature": "Error rate", "contribution": 0.08}]

        # Confidence computation
        confidence_pct = round(min(0.98, max(0.50, final_score + 0.05)), 2) if is_anomaly else round(min(0.95, 1.0 - final_score), 2)

        # Baseline comparison table
        deviations = baseline_engine.evaluate_service_deviations(tenant_id, service, features)

        anom_id = f"ANOM-{uuid.uuid4().hex[:8].upper()}" if is_anomaly else f"EVAL-{uuid.uuid4().hex[:8].upper()}"

        result = {
            "anomaly_id": anom_id,
            "model": "AegisOps Multi-Model Anomaly Ensemble",
            "model_version": "v2.0-ensemble",
            "service": service,
            "tenant_id": tenant_id,
            "window": f"{int(features.get('window_sec', 30))}s",
            "timestamp": now_iso,
            "is_anomaly": is_anomaly,
            "anomaly_score": final_score,
            "ensemble_score": final_score,
            "threshold": self.threshold,
            "classification": "HIGH CONFIDENCE ANOMALY" if final_score >= 0.80 else ("MODERATE ANOMALY" if is_anomaly else "NORMAL"),
            "confidence": confidence_pct,
            "decision": "ANOMALY" if is_anomaly else "NORMAL",
            "dominant_detectors": dominant_detectors,
            "contributing_features": feat_contribs,
            "feature_contributions": {fc["feature"]: fc["contribution"] for fc in feat_contribs},
            "baseline_comparisons": deviations,
            "baseline_comparison": deviations,
            "detectors": {
                "z_score": m1_z,
                "ewma": m2_ewma,
                "iqr": m3_iqr,
                "isolation_forest": m4_iso,
                "lof": m5_lof,
                "dbscan": m6_dbscan,
                "change_point": m7_cp.to_dict(),
                "forecasting": m8_fc
            },
            "model_contributions": model_contributions
        }

        with self.lock:
            if not hasattr(self, "_recent_results"):
                self._recent_results = deque(maxlen=200)
            self._recent_results.appendleft(result)

        return result

    def get_recent_results(self, tenant_id: Optional[str] = None, service: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.lock:
            if not hasattr(self, "_recent_results"):
                self._recent_results = deque(maxlen=200)
            results = list(self._recent_results)
            if tenant_id and tenant_id.lower() != "all":
                t_lower = tenant_id.lower()
                results = [r for r in results if r.get("tenant_id", "").lower() == t_lower]
            if service and service.lower() != "all":
                s_lower = service.lower()
                results = [r for r in results if r.get("service", "").lower() == s_lower]
            return results[:limit]

    # Flexible testing wrapper methods
    def evaluate_z_score(self, value: float, mean: Optional[float] = None, std: Optional[float] = None, threshold: float = 3.0, tenant_id: str = "shopsphere", service: str = "database-service", feature: str = "latency_p95") -> Dict[str, Any]:
        if mean is not None and std is not None:
            effective_std = max(0.0001, std) if std > 0 else 0.0001
            z = (value - mean) / effective_std if std > 0.0001 else 0.0
            interp = "Extreme deviation" if abs(z) >= 4.0 else ("Significant deviation" if abs(z) >= 3.0 else ("Moderate deviation" if abs(z) >= 2.0 else "Normal distribution"))
            return {
                "model_name": "Z-Score",
                "z_score": round(z, 2),
                "threshold": threshold,
                "mean": round(mean, 2),
                "std": round(std, 2),
                "interpretation": interp,
                "is_anomaly": abs(z) >= threshold,
                "score": 0.0 if z <= 0.0 else round(min(1.0, 1.0 / (1.0 + math.exp(-0.85 * (z - 2.8)))), 3)
            }
        return self.evaluate_zscore(tenant_id, service, feature, value)

    def evaluate_ewma(self, current_val: Any, expected_val: Optional[float] = None, threshold_pct: float = 40.0, tenant_id: str = "shopsphere", service: str = "database-service", feature: str = "latency_p95") -> Dict[str, Any]:
        if isinstance(current_val, str):
            return self._evaluate_ewma_service(current_val, str(expected_val), str(threshold_pct), float(tenant_id))
        if expected_val is not None:
            diff = float(current_val) - float(expected_val)
            dev_pct = round((diff / max(0.01, abs(expected_val))) * 100.0, 1) if expected_val > 0 else 0.0
            is_anom = abs(dev_pct) >= threshold_pct
            score = round(min(1.0, abs(dev_pct) / 100.0), 3)
            return {
                "model_name": "EWMA",
                "expected_value": round(float(expected_val), 2),
                "current_val": round(float(current_val), 2),
                "ewma_deviation_pct": round(dev_pct, 1),
                "is_anomaly": is_anom,
                "score": score
            }
        return self._evaluate_ewma_service(tenant_id, service, feature, float(current_val))

    def evaluate_iqr(self, current_val: Any, q1: Optional[float] = None, q3: Optional[float] = None, iqr: Optional[float] = None, tenant_id: str = "shopsphere", service: str = "database-service", feature: str = "latency_p95") -> Dict[str, Any]:
        if isinstance(current_val, str):
            return self._evaluate_iqr_service(current_val, str(q1), str(q3), float(iqr if iqr is not None else 0.0))
        if q1 is not None and q3 is not None and iqr is not None:
            upper_fence = q3 + 1.5 * iqr
            lower_fence = max(0.0, q1 - 1.5 * iqr)
            c_val = float(current_val)
            is_anom = (c_val > upper_fence or c_val < lower_fence)
            dev = max(0.0, c_val - upper_fence)
            score = 0.0 if dev <= 0 else round(min(1.0, 1.0 / (1.0 + math.exp(-1.1 * (dev / max(1.0, iqr) - 1.0)))), 3)
            return {
                "model_name": "IQR / Robust Outlier",
                "current_val": round(c_val, 2),
                "q1": round(q1, 2),
                "q3": round(q3, 2),
                "iqr": round(iqr, 2),
                "upper_fence": round(upper_fence, 2),
                "lower_fence": round(lower_fence, 2),
                "is_anomaly": is_anom,
                "score": score
            }
        return self._evaluate_iqr_service(tenant_id, service, feature, float(current_val))

    def evaluate_isolation_forest(self, vector: Any, history: Optional[List[List[float]]] = None, tenant_id: str = "shopsphere", service: str = "database-service") -> Dict[str, Any]:
        if isinstance(vector, str):
            return self._evaluate_isolation_forest_service(vector, str(history), tenant_id if isinstance(tenant_id, list) else [])
        if history is not None:
            if len(history) < 15:
                return {
                    "model_name": "Isolation Forest",
                    "status": "FALLBACK DETECTION",
                    "reason": f"Only {len(history)} observations available; minimum required 15.",
                    "is_anomaly": False,
                    "model_score": 0.0,
                    "score": 0.0
                }
            try:
                X = np.array(history)
                iso = IsolationForest(n_estimators=35, contamination=0.08, random_state=42, n_jobs=1)
                iso.fit(X)
                pred = iso.predict(np.array([vector]))[0]
                raw_score = float(iso.decision_function(np.array([vector]))[0])
                is_anom = (pred == -1)
                norm_score = round(max(0.0, min(1.0, -raw_score + 0.5)), 3)
                return {
                    "model_name": "Isolation Forest",
                    "status": "EVALUATED",
                    "is_anomaly": is_anom,
                    "model_score": round(raw_score, 3),
                    "score": norm_score,
                    "decision": "ANOMALY" if is_anom else "NORMAL"
                }
            except Exception as e:
                return {"model_name": "Isolation Forest", "status": "ERROR", "error": str(e), "is_anomaly": False, "score": 0.0}
        return self._evaluate_isolation_forest_service(tenant_id, service, vector)

    def evaluate_lof(self, vector: Any, history: Optional[List[List[float]]] = None, tenant_id: str = "shopsphere", service: str = "database-service") -> Dict[str, Any]:
        if isinstance(vector, str):
            return self._evaluate_lof_service(vector, str(history), tenant_id if isinstance(tenant_id, list) else [])
        if history is not None:
            if len(history) < 20:
                return {
                    "model_name": "Local Outlier Factor",
                    "status": "FALLBACK DETECTION",
                    "reason": f"Only {len(history)} observations available; minimum required 20.",
                    "is_anomaly": False,
                    "score": 0.0
                }
            try:
                X = np.array(history)
                lof = LocalOutlierFactor(n_neighbors=min(10, len(history)-1), novelty=True, contamination=0.08)
                lof.fit(X)
                pred = lof.predict(np.array([vector]))[0]
                is_anom = (pred == -1)
                return {
                    "model_name": "Local Outlier Factor",
                    "status": "EVALUATED",
                    "is_anomaly": is_anom,
                    "score": 0.85 if is_anom else 0.15
                }
            except Exception as e:
                return {"model_name": "LOF", "status": "ERROR", "error": str(e), "is_anomaly": False, "score": 0.0}
        return self._evaluate_lof_service(tenant_id, service, vector)

    def evaluate_dbscan(self, point: Any, history: Optional[List[List[float]]] = None, tenant_id: str = "shopsphere", service: str = "database-service") -> Dict[str, Any]:
        if isinstance(point, str):
            return self._evaluate_dbscan_service(point, str(history), tenant_id if isinstance(tenant_id, list) else [])
        if history is not None:
            if len(history) < 10:
                return {"model_name": "DBSCAN", "status": "FALLBACK DETECTION", "is_anomaly": False, "score": 0.0}
            try:
                from sklearn.cluster import DBSCAN
                all_pts = np.vstack([history, [point]])
                db = DBSCAN(eps=50.0, min_samples=3).fit(all_pts)
                label = int(db.labels_[-1])
                is_anom = (label == -1)
                return {
                    "model_name": "DBSCAN",
                    "status": "EVALUATED",
                    "cluster_label": label,
                    "cluster_type": "NOISE / ANOMALY" if is_anom else f"Cluster {label}",
                    "is_anomaly": is_anom,
                    "score": 0.80 if is_anom else 0.10
                }
            except Exception as e:
                return {"model_name": "DBSCAN", "status": "ERROR", "error": str(e), "is_anomaly": False, "score": 0.0}
        return self._evaluate_dbscan_service(tenant_id, service, point)

    def evaluate_change_point(self, before_series: Any, after_series: Optional[Any] = None, metric_name: str = "P95 latency") -> Any:
        if isinstance(before_series, str):
            return self._evaluate_change_point_service(before_series, str(after_series), metric_name if isinstance(metric_name, dict) else {})
        b_series = before_series or []
        a_series = after_series or []
        m_before = float(np.mean(b_series)) if b_series else 25.0
        m_after = float(np.mean(a_series)) if a_series else 25.0
        mag = m_after / max(0.1, m_before) if m_before > 0 else 1.0
        is_change = (mag >= 2.5 or mag <= 0.4)
        return {
            "model_name": "Change Point",
            "metric": metric_name,
            "is_change_point": is_change,
            "mean_before": round(m_before, 2),
            "mean_after": round(m_after, 2),
            "change_magnitude": round(mag, 2),
            "magnitude_str": f"{round(mag, 1)}x",
            "is_anomaly": is_change,
            "score": round(min(1.0, max(0.0, (mag - 1.0) / 10.0)), 3) if is_change else 0.0
        }

    def evaluate_forecast(self, actual_val: float, history: Optional[List[float]] = None, metric_name: str = "error_rate") -> Dict[str, Any]:
        h = history or [actual_val]
        pred = float(np.mean(h[-3:])) if len(h) >= 3 else float(h[-1])
        dev_pct = round(((actual_val - pred) / max(0.001, pred)) * 100.0, 1)
        is_anom = abs(dev_pct) >= 50.0
        return {
            "model_name": "Forecasting",
            "metric": metric_name,
            "actual_val": round(actual_val, 4),
            "predicted_val": round(pred, 4),
            "prediction_deviation_pct": round(dev_pct, 1),
            "is_anomaly": is_anom,
            "score": round(min(1.0, abs(dev_pct) / 200.0), 3)
        }


# Global singleton ensemble
anomaly_ensemble = AnomalyEnsembleEngine()
ml_ensemble_engine = anomaly_ensemble
