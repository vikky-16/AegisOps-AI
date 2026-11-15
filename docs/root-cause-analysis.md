# AegisOps AI — Dynamic Root Cause Analysis & Blast Radius

## 1. The Challenge: Cascading Multi-Service Failures
In distributed microservice architectures, an upstream database connection pool exhaustion rapidly cascades down the call stack, causing timeouts on dependent business services and 502/504 errors on API gateways. Naive alert monitors alert on the gateway rather than the true root cause.

AegisOps AI isolates the true origin service using dynamic topology graph analysis and telemetry event correlation.

---

## 2. Dynamic Dependency Topology Graph
The graph engine maintains a directed acyclic graph (DAG) representing service relationships:
```
[Ingress Gateway] ──▶ [Order Service A] ──▶ [Payment Service B] ──▶ [Database Service]
         │                                         │
         └─────────────────────────────────────────┴──────────────▶ [Auth Service]
```

---

## 3. Dynamic Candidate Ranking Algorithm
Candidates are ranked using a combination of topological centrality, temporal onset, and anomaly severity:
1. **Temporal Precedence**: Events occurring earliest in the correlation window receive higher initial weight.
2. **Topological Centrality**: Betweenness centrality and PageRank identify services that act as structural chokepoints.
3. **Cascade Directionality**: Dependencies propagating errors downstream confirm that the dependency is the root cause, not the dependent caller.

---

## 4. Blast Radius Score Calculation
The blast radius score ($0 - 100$) quantifies the operational impact across the cluster:
$$\text{Blast Radius} = w_1 \cdot \text{Affected Services Count} + w_2 \cdot \text{Cumulative Error Rate} + w_3 \cdot \text{Criticality Multiplier}$$

- **`LOW` (0 – 30)**: Isolated single-service degradation.
- **`MEDIUM` (31 – 60)**: Multi-service impact without gateway impairment.
- **`HIGH` (61 – 80)**: Critical infrastructure failure impacting payment or authentication.
- **`CRITICAL` (81 – 100)**: Widespread outage impacting ingress routing and persistent databases.
