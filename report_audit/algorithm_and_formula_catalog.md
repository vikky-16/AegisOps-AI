# AegisOps AI — Algorithm and Formula Catalog

**Specification**: Rigorous Mathematical & Implementation Catalog for SRE Algorithms  
**Authoritative Path**: `C:\Users\admin\AegisOps AI`  

---

## 1. Multi-Detector Anomaly Detection Algorithms

### 1.1 Z-Score Statistical Anomaly Detector
- **Purpose**: Detect sudden parametric metric shifts against a Gaussian rolling baseline.
- **Source File**: [`backend/app/ai/detectors/zscore_detector.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/ai/detectors/zscore_detector.py#L15) (`ZScoreDetector.evaluate`)
- **Mathematical Formulation**:
  $$z = \frac{x_t - \mu}{\sigma}$$
  $$\text{Is\_Anomaly} = (|z| \ge \theta_{\text{zscore}})$$
- **Parameters**:
  - $\theta_{\text{zscore}} = 3.0$ (standard deviations threshold)
  - Minimum sample size $N_{\text{min}} = 5$
  - Default $\sigma_{\text{floor}} = 0.001$ (prevents division by zero on static signals)
- **Pseudocode**:
  ```python
  def evaluate_zscore(current_val, baseline_mean, baseline_std, threshold=3.0):
      if baseline_std <= 0:
          baseline_std = 0.001
      z = abs(current_val - baseline_mean) / baseline_std
      return {
          "is_anomaly": z >= threshold,
          "score": round(min(z / threshold, 1.0), 3),
          "z_value": round(z, 2)
      }
  ```
- **Example Input/Output**: Input `current_val = 2350ms`, `mean = 45ms`, `std = 12ms` -> `z = 192.08` -> `is_anomaly = True`, `score = 1.0`.
- **Complexity**: $O(1)$ evaluation time; $O(N)$ rolling mean/std calculation over window.
- **Strengths**: Sub-millisecond evaluation; mathematically optimal for normal distributions.
- **Limitations**: Sensitive to extreme outliers inflating standard deviation; assumes unimodal distribution.

---

### 1.2 Exponentially Weighted Moving Average (EWMA) Detector
- **Purpose**: Detect progressive metric drift and persistent shifts with exponential recency weighting.
- **Source File**: [`backend/app/ai/detectors/ewma_detector.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/ai/detectors/ewma_detector.py#L20) (`EWMADetector.evaluate`)
- **Mathematical Formulation**:
  $$S_t = \alpha \cdot x_t + (1 - \alpha) \cdot S_{t-1}$$
  $$\sigma_{\text{ewma}}^2 = \frac{\alpha}{2 - \alpha} \cdot \sigma^2$$
  $$\text{Residual} = |x_t - S_t| \ge k \cdot \sigma_{\text{ewma}}$$
- **Parameters**:
  - Smoothing factor $\alpha = 0.3$
  - Multiplier $k = 3.0$
- **Complexity**: $O(1)$ constant time and space.
- **Strengths**: Smooths high-frequency noise while reacting rapidly to sustained structural degradation.
- **Limitations**: Lags slightly behind instantaneous impulse spikes.

---

### 1.3 Interquartile Range (IQR) Non-Parametric Outlier Detector
- **Purpose**: Robust outlier detection on non-Gaussian, skewed telemetry (e.g., long-tail latency).
- **Source File**: [`backend/app/ai/detectors/iqr_detector.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/ai/detectors/iqr_detector.py#L18) (`IQRDetector.evaluate`)
- **Mathematical Formulation**:
  $$\text{IQR} = Q_3 - Q_1$$
  $$\text{Upper\_Fence} = Q_3 + 1.5 \cdot \text{IQR}$$
  $$\text{Lower\_Fence} = Q_1 - 1.5 \cdot \text{IQR}$$
- **Parameters**: Tukey fence multiplier $= 1.5$.
- **Complexity**: $O(N \log N)$ window sorting.
- **Strengths**: Completely immune to severe outlier distortions.

---

### 1.4 Consecutive Breach Flapping Prevention Algorithm
- **Purpose**: Eliminate false-positive transient alert storms by requiring persistent breach cycles.
- **Source File**: [`backend/app/ai/detectors/consecutive_breach_detector.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/ai/detectors/consecutive_breach_detector.py#L22)
- **Algorithm**:
  - Maintains stateful integer counter $C_{\text{breach}}$ per service metric tuple.
  - If detector fires: $C_{\text{breach}} \leftarrow C_{\text{breach}} + 1$.
  - If normal: $C_{\text{breach}} \leftarrow \max(0, C_{\text{breach}} - 1)$.
  - Confirmed Alert triggered **only when** $C_{\text{breach}} \ge 3$.
- **Strengths**: Prevents alert thrashing from momentary network spikes.

---

## 2. Event & Incident Correlation Algorithm

- **Purpose**: Cluster fragmented multi-service telemetry breaches into unified incident aggregates.
- **Source File**: [`backend/app/services/event_correlator.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/services/event_correlator.py#L35)
- **Mathematical Formulation**:
  $$\text{Correlation\_Score}(E_1, E_2) = w_{\text{time}} \cdot S_{\text{time}} + w_{\text{topo}} \cdot S_{\text{topo}} + w_{\text{trace}} \cdot S_{\text{trace}}$$
  $$S_{\text{time}} = \max\left(0, 1 - \frac{|\Delta t|}{T_{\text{window}}}\right), \quad T_{\text{window}} = 300\text{ s}$$
  $$S_{\text{topo}} = 1.0 \text{ if direct dependency, } 0.5 \text{ if shared cluster, else } 0.0$$
  $$S_{\text{trace}} = 1.0 \text{ if } \text{TraceID}(E_1) == \text{TraceID}(E_2), \text{ else } 0.0$$
- **Weights**: $w_{\text{time}} = 0.35$, $w_{\text{topo}} = 0.35$, $w_{\text{trace}} = 0.30$.
- **Decision Rule**: Correlate into single incident if $\text{Score} \ge 0.65$.
- **Complexity**: $O(K)$ matching against active incident window ($K \le 50$).

---

## 3. Root Cause Analysis Scoring & Ranking

- **Purpose**: Rank candidate failure causes and compute diagnostic confidence.
- **Source File**: [`backend/app/rca/engine.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/rca/engine.py#L85) & [`evidence_package.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/rca/evidence_package.py)
- **Mathematical Formulation**:
  $$\text{Score}(S_i) = \sum_{j=1}^{7} w_j \cdot f_j(S_i)$$
  Where the 7 normalized factors ($f_j \in [0, 1]$) are:
  1. $f_1$: Temporal precedence (earliest anomaly onset).
  2. $f_2$: Error rate severity magnitude.
  3. $f_3$: Latency P95 degradation ratio.
  4. $f_4$: Topological centrality in dependency graph.
  5. $f_5$: Downstream blast propagation ratio.
  6. $f_6$: Historical recurrence frequency.
  7. $f_7$: Diagnostic log error pattern density.
- **Weights**: $\vec{w} = [0.25, 0.20, 0.15, 0.15, 0.10, 0.08, 0.07]$ ($\sum w_j = 1.0$).
- **Confidence Equation**:
  $$\text{Confidence} = \frac{\text{Score}(S_{\text{top}}) - \text{Score}(S_{\text{second}})}{\text{Score}(S_{\text{top}})} \cdot \left(1 - \frac{\text{Missing\_Evidence\_Count}}{15}\right)$$

---

## 4. Blast Radius Graph Traversal Algorithm

- **Purpose**: Calculate structural impact boundary across microservice mesh.
- **Source File**: [`backend/app/services/dependency_graph.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/services/dependency_graph.py#L60)
- **Algorithm (Breadth-First Directed Traversal)**:
  ```python
  def calculate_blast_radius(graph, root_service):
      visited = set([root_service])
      queue = [root_service]
      downstream = []
      
      while queue:
          curr = queue.pop(0)
          for dependent in graph.get_dependents(curr):
              if dependent not in visited:
                  visited.add(dependent)
                  downstream.append(dependent)
                  queue.append(dependent)
                  
      total_services = graph.total_node_count()
      blast_score = len(downstream) / max(total_services - 1, 1)
      return {
          "direct_dependents": graph.get_dependents(root_service),
          "downstream_impact": downstream,
          "blast_radius_score": round(blast_score, 3)
      }
  ```
- **Complexity**: $O(V + E)$ where $V$ is service count and $E$ is dependency edge count.

---

## 5. Replica Lab Candidate Evaluation & Ranking

- **Purpose**: Rank candidate remediation strategies tested in isolated digital twin.
- **Source File**: [`backend/app/replica/remediation_lab.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/replica/remediation_lab.py#L225)
- **Multi-Objective Composite Score Formulation**:
  $$\text{Rank\_Score} = w_{\text{eff}} \cdot \Delta_{\text{error}} + w_{\text{lat}} \cdot \Delta_{\text{latency}} + w_{\text{safe}} \cdot (1 - \text{Risk}) - w_{\text{cost}} \cdot \text{Cost}$$
- **Weights**: $w_{\text{eff}} = 0.40$, $w_{\text{lat}} = 0.30$, $w_{\text{safe}} = 0.20$, $w_{\text{cost}} = 0.10$.
- **Regression Check Penalty**: If any dependent service exhibits increased latency $\Delta > 15\%$, Rank Score is multiplied by $0.2$ (disqualified from pre-approval).

---

## 6. Independent 8-Point Post-Recovery Empirical Validation

- **Purpose**: Empirically verify target microservice recovery prior to closing incident.
- **Source File**: [`backend/app/healing/sandbox_engine.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/healing/sandbox_engine.py#L150)
- **Evaluation Criteria Matrix**:
  | Criterion | Evaluation Formula | Acceptance Threshold |
  | :--- | :--- | :--- |
  | 1. Service Reachability | HTTP status of `GET /health` | Status == 200 OK |
  | 2. Error Rate Floor | $\text{Errors} / \text{Total\_Requests}$ | Error Rate $\le 1.0\%$ |
  | 3. Latency Envelope | $P95_{\text{post}} \le P95_{\text{baseline}} \cdot 1.15$ | Latency within 15% of baseline |
  | 4. Telemetry Freshness | $t_{\text{now}} - t_{\text{last\_event}}$ | Age $\le 60$ seconds |
  | 5. Downstream Health | All dependent service health states | State == `HEALTHY` |
  | 6. Resource Ceiling | $\max(\text{CPU}\%, \text{Mem}\%)$ | Utilization $\le 85.0\%$ |
  | 7. Synthetic Probes | Replayed test transactions pass rate | Pass Rate $== 100\%$ |
  | 8. Connection State | Active handles in pool | Active / Max Pool $\le 50\%$ |

---

## 7. Bounded Refinement & Exponential Escalation

- **Purpose**: Prevent runaway remediation retry storms and guarantee deterministic convergence.
- **Source File**: [`backend/app/healing/closed_loop_engine.py`](file:///C:/Users/admin/AegisOps%20AI/backend/app/healing/closed_loop_engine.py#L110)
- **Algorithm**:
  - Given attempt counter $k \in \{1, 2, \dots, K_{\text{max}}\}$ where $K_{\text{max}} = 3$.
  - Backoff cooldown: $\tau_{\text{cooldown}} = 2^{k-1} \cdot 5\text{ seconds}$ (5s, 10s, 20s).
  - If validation fails at attempt $k < K_{\text{max}}$:
    - Retract failed candidate.
    - Exclude failed candidate from hypothesis space.
    - Select next highest ranked candidate from Replica Lab matrix.
  - If validation fails at attempt $k == K_{\text{max}}$:
    - Trigger hard circuit breaker.
    - Set incident state to `UNRESOLVED`.
    - Dispatch high-priority SLA breach alert to human SRE commander via webhook.

