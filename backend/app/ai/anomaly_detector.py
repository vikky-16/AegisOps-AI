"""
Isolation Forest + Dynamic Statistical Ensemble Anomaly Detector
CPU-optimized, scikit-learn backed, with feature attribution.
"""

import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from sklearn.ensemble import IsolationForest
from backend.app.ai.base_model import BaseAnomalyDetector

FEATURE_NAMES = [
    "cpu_percent",
    "memory_mb",
    "error_rate",
    "latency_p95_ms",
    "request_count",
    "active_connections"
]

FEATURE_THRESHOLDS = {
    "cpu_percent": {"warn": 75.0, "crit": 90.0},
    "memory_mb": {"warn": 300.0, "crit": 500.0},
    "error_rate": {"warn": 0.05, "crit": 0.20},
    "latency_p95_ms": {"warn": 200.0, "crit": 800.0},
    "active_connections": {"warn": 30, "crit": 60}
}


class EnsembleAnomalyDetector(BaseAnomalyDetector):
    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.feature_names = FEATURE_NAMES
        self.is_fitted = False
        
        # Scikit-learn Isolation Forest
        self.iso_forest = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=1  # CPU friendly
        )
        
        # Moving window statistics for Z-score calculation
        self.feature_history: Dict[str, List[float]] = {f: [] for f in self.feature_names}
        self.max_history = 200
        
        # Pre-seed baseline normal operational profile
        self._seed_normal_baseline()

    def _seed_normal_baseline(self):
        """Generates synthetic normal operational baseline data to initialize model."""
        np.random.seed(42)
        n_samples = 150
        
        # Baseline normal distributions
        cpu = np.random.normal(12.0, 4.0, n_samples).clip(2.0, 35.0)
        mem = np.random.normal(140.0, 15.0, n_samples).clip(100.0, 200.0)
        err = np.zeros(n_samples)  # 0% errors normally
        lat = np.random.normal(15.0, 5.0, n_samples).clip(5.0, 45.0)
        req = np.random.normal(25.0, 8.0, n_samples).clip(5.0, 60.0)
        conn = np.random.normal(4.0, 2.0, n_samples).clip(1.0, 10.0)
        
        X_init = np.column_stack([cpu, mem, err, lat, req, conn])
        self.fit(X_init.tolist())

    def fit(self, X: List[List[float]]) -> None:
        if len(X) < 10:
            return
        X_arr = np.array(X)
        self.iso_forest.fit(X_arr)
        self.is_fitted = True
        
        # Update feature history
        for i, name in enumerate(self.feature_names):
            self.feature_history[name] = X_arr[:, i].tolist()[-self.max_history:]

    def predict(self, features: List[float]) -> Tuple[bool, float, List[str]]:
        """
        Calculates ensemble anomaly prediction using Isolation Forest score + Z-scores.
        Returns (is_anomaly, normalized_score, dominant_evidence).
        """
        feat_dict = {name: val for name, val in zip(self.feature_names, features)}
        
        # 1. Update online rolling history
        for name, val in feat_dict.items():
            self.feature_history[name].append(val)
            if len(self.feature_history[name]) > self.max_history:
                self.feature_history[name].pop(0)

        # 2. Scikit-learn Isolation Forest decision score
        # score_samples returns negative values (lower means more anomalous)
        X_vec = np.array([features])
        raw_iso_score = self.iso_forest.score_samples(X_vec)[0]
        # Map raw score [-0.8, -0.2] to [1.0, 0.0]
        iso_anomaly_prob = float(np.clip(( -raw_iso_score - 0.35 ) / 0.45, 0.0, 1.0))

        # 3. Statistical Z-Score & Rule-Based Metric Deviations
        z_scores = {}
        evidence_lines = []
        rule_penalty = 0.0

        for name, val in feat_dict.items():
            hist = self.feature_history[name]
            if len(hist) > 10:
                mean = np.mean(hist[:-1])
                std = np.std(hist[:-1]) or 1.0
                z = (val - mean) / std
                z_scores[name] = z
                
                if z > 2.5:
                    evidence_lines.append(f"{name.replace('_', ' ').title()} abnormal elevation (z={z:.1f}, current={val:.1f})")
            
            # Check hard threshold limits
            if name in FEATURE_THRESHOLDS:
                thresholds = FEATURE_THRESHOLDS[name]
                if val >= thresholds["crit"]:
                    rule_penalty = max(rule_penalty, 0.85)
                    evidence_lines.append(f"CRITICAL threshold breached: {name}={val:.1f} >= {thresholds['crit']}")
                elif val >= thresholds["warn"]:
                    rule_penalty = max(rule_penalty, 0.50)
                    evidence_lines.append(f"WARNING threshold breached: {name}={val:.1f} >= {thresholds['warn']}")

        # 4. Ensemble weighted combination
        combined_score = max(iso_anomaly_prob, rule_penalty)
        if any(z > 3.0 for z in z_scores.values()):
            combined_score = max(combined_score, 0.75)

        is_anomaly = combined_score >= 0.45 or rule_penalty >= 0.50

        # Sort evidence to show most severe first
        unique_evidence = list(dict.fromkeys(evidence_lines))[:4]
        
        return is_anomaly, round(float(combined_score), 4), unique_evidence
