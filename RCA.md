# AegisOps AI - Root-Cause Analysis (RCA) & Correlation Engine

## 1. Dependency Graph Representation
The distributed environment is modeled as a Directed Acyclic Graph (DAG):
$$\text{Gateway (Port 8001)} \longrightarrow \text{Service A (Port 8002)} \longrightarrow \text{Service B (Port 8003)} \longrightarrow \text{Database Service (Port 8004)}$$

---

## 2. Multi-Factor Root Cause Scoring Algorithm

When a cascade failure occurs, multiple microservices exhibit errors almost simultaneously. AegisOps AI scores candidate root causes using a 4-factor scoring model:

1. **Temporal Onset Order (40%)**:
   - Earliest anomalous timestamp receives 45 points.
   - Subsequent cascading failures receive lower temporal weights.
2. **Topological Depth in Dependency DAG (30%)**:
   - Deepest dependencies (e.g. Database = depth 3, Service B = depth 2) receive higher weight because upstream services (Gateway, Service A) inevitably suffer secondary effects when downstream data layers fail.
3. **Intrinsic Error Signature (20%)**:
   - Fatal root causes (e.g. `CONNECTION_POOL_EXHAUSTION`, `DISK_SPACE_CRITICAL`, `PROCESS_CRASH`) receive +30 points.
   - Generic downstream symptoms (e.g. `502 Bad Gateway`, `504 Gateway Timeout`) receive +2 points.
4. **Historical Knowledge Prior (10%)**:
   - Knowledge base recurrence frequency provides Bayesian prior weighting.

$$\text{Confidence Score} = \min\left(0.96, 0.75 + \frac{\text{Score}_{\text{top}} - \text{Score}_{\text{second}}}{\text{Score}_{\text{top}}} \times 0.22\right)$$

---

## 3. Event Correlation & Alert Storm Deduplication

- **Sliding Time Window**: Anomalous events within a 20-second window across connected services in the DAG are automatically clustered.
- **Log Fingerprinting**: SHA256 hashes of `(service, event_type, normalized_template)` group thousands of identical error logs (e.g. 500 `DATABASE_TIMEOUT` logs) into a single fingerprinted counter, preventing alert storms and alert fatigue.
