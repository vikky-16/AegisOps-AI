# AegisOps AI — Machine Learning & Anomaly Detection Architecture

## 1. Multi-Detector Detection Pipeline
AegisOps AI evaluates incoming telemetry against dynamic statistical and machine-learning models rather than static threshold rules.

```
Incoming Telemetry Event
           │
           ├──────────────────────────────┐
           ▼                              ▼
[Dynamic Baselines Engine]      [Isolation Forest Detector]
(Welford's Algorithm: μ, σ)     (Multivariate Point Outliers)
           │                              │
           └──────────────┬───────────────┘
                          ▼
             [Z-Score & IQR Evaluator]
             (Threshold: |Z| >= 3.0 or IQR > 1.5)
                          │
                          ▼
            [Ensemble Consensus Engine]
            - Anomaly Score: 0.00 – 1.00
            - Multi-Point Evidence Collection
```

---

## 2. Dynamic Baseline Tracking
The baseline manager tracks continuous streaming statistics per microservice and metric using Welford's algorithm for numerically stable mean and variance calculation without storing unbounded historical windows:

$$M_k = M_{k-1} + \frac{x_k - M_{k-1}}{k}$$
$$S_k = S_{k-1} + (x_k - M_{k-1})(x_k - M_k)$$
$$\sigma^2 = \frac{S_k}{k - 1}$$

---

## 3. Anomaly Scoring & Evidence Generation
When an anomaly is detected, the engine outputs:
- **`anomaly_score`**: Continuous probability value between 0.00 and 1.00.
- **`is_anomaly`**: Boolean flag set to `True` when confidence surpasses detection threshold (default: 0.85).
- **`evidence`**: Human-readable and machine-verifiable explanation of which telemetry signals breached baselines (e.g. `Error rate 85% is 4.2 standard deviations above baseline (1.2%)`).
