# AegisOps AI - AI & Machine Learning Architecture

## 1. Design Overview
AegisOps AI is built exclusively with **CPU-compatible**, low-latency, real-time machine learning models:
1. **Isolation Forest + Statistical Z-Score Ensemble**: Multi-metric anomaly detection.
2. **Linear & Polynomial Trend Forecaster**: Time-to-exhaustion storage prediction and resource drift detection.
3. **TF-IDF Vector Cosine Similarity Matcher**: Case-Based Reasoning (CBR) against historical incident post-mortems.
4. **Grounded Operational Assistant**: Telemetry-indexed query processor with zero hallucination.

---

## 2. Anomaly Detection Ensemble

### Feature Vector
Each microservice is evaluated every 1.0 second on a 6-dimensional operational feature vector:
$$\mathbf{x} = \left[ \text{CPU}\%, \text{Memory (MB)}, \text{Error Rate}, \text{Latency } p95\text{ (ms)}, \text{Request Count}, \text{Active Connections} \right]$$

### Model Architecture
- **Isolation Forest (`scikit-learn`)**: Partitioning trees identify rare multidimensional deviations from normal baselines without requiring explicit anomaly labels.
- **Dynamic Z-Score**: Evaluates moving mean $\mu$ and standard deviation $\sigma$ across rolling 200-sample windows. Deviations exceeding $z > 2.5$ generate specific diagnostic attribution tags.
- **Ensemble Fusion**: Combines isolation decision probabilities with statistical threshold violations into a normalized anomaly score $S \in [0.0, 1.0]$. Anomaly triggered when $S \ge 0.45$.

---

## 3. Storage & Resource Trend Prediction

- **Capacity Exhaustion**: Linear regression over recent hourly storage snapshots calculates slope $m = \frac{\Delta \text{GB}}{\Delta t}$. Time to 95% critical capacity is calculated as:
  $$t_{\text{crit}} = \frac{C_{\text{crit}} - C_{\text{current}}}{m}$$
- **Resource Drift**: Identifies persistent memory leak slopes ($\Delta \text{RAM} > 2.5 \text{ MB/min}$) or CPU queue saturation trends before hard service outages occur.

---

## 4. Case-Based Reasoning & Similarity Matching

- **Vector Representation**: Incoming incident symptoms and error messages are transformed into high-dimensional TF-IDF vectors.
- **Cosine Similarity**: Measures cosine angle between active incident vector $\mathbf{q}$ and historical knowledge base vectors $\mathbf{d}_i$:
  $$\text{Similarity}(\mathbf{q}, \mathbf{d}_i) = \frac{\mathbf{q} \cdot \mathbf{d}_i}{\|\mathbf{q}\| \|\mathbf{d}_i\|}$$
- **Output**: Surfaces top similar historical incidents, root causes, proven remedies, and verified resolution success rates (e.g. 94.5%).
