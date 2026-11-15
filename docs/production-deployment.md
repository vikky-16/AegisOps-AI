# AegisOps AI — Production Deployment Guide

## 1. Production Architecture Overview

For enterprise scale (10,000 to 100,000+ Events Per Second across dozens of corporate tenants), AegisOps AI is deployed on Kubernetes with a distributed streaming and columnar persistence topology:

```mermaid
graph TD
    subgraph Edge Tier
        DNS[Global DNS / Route53] --> LB[Cloud Load Balancer / Ingress Controller]
        LB -->|TLS Termination (HTTPS / WSS)| GW[AegisOps Ingestion Gateway Pods (HPA 3-20)]
    end

    subgraph Streaming Tier
        GW -->|Kafka Producer Pool| KAFKA[Apache Kafka / Redpanda Cluster (3-5 Brokers)]
        KAFKA --> TOPIC1[Topic: aegisops-telemetry-raw]
        KAFKA --> TOPIC2[Topic: aegisops-telemetry-metrics]
        KAFKA --> TOPIC3[Topic: aegisops-telemetry-logs]
        KAFKA --> TOPIC4[Topic: aegisops-telemetry-traces]
    end

    subgraph Processing Tier
        TOPIC1 --> WORKER[AegisOps Stream Processors / Anomaly Detectors]
        WORKER --> RCA_ENG[RCA & Decision Engine]
        RCA_ENG --> REMED[Remediation & Policy Engine]
    end

    subgraph Columnar Persistence Tier
        TOPIC1 --> CH_WRITER[ClickHouse Ingestion Sink]
        CH_WRITER --> CLICKHOUSE[(ClickHouse Cluster (2x Replicas))]
        REMED --> POSTGRES[(PostgreSQL 16 / TimescaleDB)]
    end

    subgraph Operations & Presentation
        GW --> REDIS[(Redis Cluster)]
        GW -->|Tenant WebSocket| UI[React Operations Dashboard]
    end
```

---

## 2. Infrastructure Sizing Guidelines

| Deployment Tier | Ingestion Throughput | Ingestion Pods | Kafka Brokers | ClickHouse Nodes | Postgres/Timescale | Est. Daily Volume |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Starter / PoC** | 1,000 EPS | 2 pods (2 CPU, 4GB) | 1 broker | 1 node (4 CPU, 16GB) | Single node (4 CPU, 16GB) | ~86 Million events / ~86 GB |
| **Standard Production** | 10,000 EPS | 4-8 pods (4 CPU, 8GB) | 3 brokers | 2 nodes (8 CPU, 32GB) | Primary + Read Replica | ~860 Million events / ~860 GB |
| **Enterprise Scale** | 100,000+ EPS | 12-30 pods (8 CPU, 16GB) | 5 brokers | 4 nodes (16 CPU, 64GB) | Distributed Sharded Cluster | ~8.6 Billion events / ~8.6 TB |

---

## 3. Kubernetes Deployment Configuration

### 3.1 Namespace and Ingress
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: aegisops-system
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: aegisops-ingress
  namespace: aegisops-system
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/websocket-services: "aegisops-backend"
spec:
  tls:
  - hosts:
    - aegisops.company.com
    secretName: aegisops-tls-cert
  rules:
  - host: aegisops.company.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: aegisops-backend
            port:
              number: 8000
```

### 3.2 Horizontal Pod Autoscaler (HPA)
The Ingestion Gateway should scale horizontally based on CPU and request latency:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aegisops-gateway-hpa
  namespace: aegisops-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aegisops-backend
  minReplicas: 3
  maxReplicas: 25
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 65
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 75
```

---

## 4. ClickHouse Columnar Storage Integration

For production, configure ClickHouse with the schema defined in `backend/app/storage/telemetry_store.py`:

```sql
CREATE DATABASE IF NOT EXISTS aegisops;

CREATE TABLE IF NOT EXISTS aegisops.telemetry_events (
    event_id String,
    tenant_id LowCardinality(String),
    integration_id LowCardinality(String),
    timestamp DateTime64(3, 'UTC'),
    ingestion_timestamp DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    severity LowCardinality(String),
    service_name LowCardinality(String),
    service_instance String,
    environment LowCardinality(String),
    host String,
    k8s_namespace LowCardinality(String),
    k8s_pod_name String,
    trace_id String,
    span_id String,
    parent_span_id String,
    message String,
    metric_name LowCardinality(String),
    metric_value Float64,
    latency_ms Float64,
    http_status UInt16,
    attributes_json String
)
ENGINE = MergeTree()
PARTITION BY (toYYYYMM(timestamp), tenant_id)
ORDER BY (tenant_id, event_type, service_name, timestamp)
TTL timestamp + INTERVAL 30 DAY DELETE
SETTINGS index_granularity = 8192;
```

To connect AegisOps to ClickHouse, set the environment variables:
```bash
TELEMETRY_STORE_BACKEND=clickhouse
CLICKHOUSE_HOST=clickhouse.aegisops-system.svc.cluster.local
CLICKHOUSE_PORT=9000
CLICKHOUSE_DATABASE=aegisops
CLICKHOUSE_USER=aegisops_writer
CLICKHOUSE_PASSWORD=vault:secret/clickhouse/password
```

---

## 5. Security & TLS Configuration

1. **mTLS for Ingestion**:
   In enterprise environments requiring mutual TLS between the customer's OTel Collector and the AegisOps Ingestion Gateway:
   - Configure NGINX Ingress with `nginx.ingress.kubernetes.io/auth-tls-verify-client: "on"`.
   - Distribute customer-specific client certificates during tenant onboarding.
2. **API Key Fast Caching**:
   - In production, configure Redis (`REDIS_URL=redis://redis-cluster:6379`) to share the active API key cache across all gateway replicas.
   - Key revocation invalidates the Redis cache key in $< 5\text{ ms}$, ensuring instant cross-cluster revocation.
3. **Outbound Webhooks**:
   - Outbound incident alert webhooks use non-blocking HTTP timeouts ($3\text{ seconds}$ default).
   - Egress firewalls should permit HTTPS outbound to customer-configured Slack/PagerDuty webhook URLs.

---

## 6. Self-Observability & Health Monitoring

The platform continuously self-monitors through `GET /api/platform/health`:
```bash
curl -s https://aegisops.company.com/api/platform/health | jq .
```
Key health KPIs to alert on:
- `ingestion_gateway.status == "ONLINE"`
- `streaming_backbone.collector.status == "HEALTHY"`
- `pipeline_queues.remediation_queue_depth < 50`
- `system_resources.host_cpu_percent < 85`
- `system_resources.host_memory_percent < 85`

Integrate with Prometheus via standard scraping or scrape endpoint `/api/platform/health`.
