# AegisOps AI — Live Telemetry Explorer & Ingestion Pipeline

## 1. Overview

The AegisOps AI **Live Telemetry Explorer** provides real-time, zero-drop observability across distributed Kubernetes clusters, virtual machines, cloud serverless functions, and external SaaS dependencies. Telemetry streams continuously through OpenTelemetry (OTel) collectors, Kafka event buses, and AegisOps normalization pipelines.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LIVE TELEMETRY WORKFLOW                         │
│                                                                        │
│   Applications / Containers / Hosts                                    │
│        │ (OTel OTLP / gRPC :4317 or OTLP / HTTP :4318)                 │
│        ▼                                                               │
│   OpenTelemetry Collector DaemonSet                                    │
│        │ (Batching, Compression, Tenant Header Injection)              │
│        ▼                                                               │
│   Kafka Event Bus (`aegisops-telemetry`)                               │
│        │ (Zero Buffer Loss, Partition Scoped)                          │
│        ▼                                                               │
│   AegisOps Normalized Ingestion Engine                                 │
│        ├──► Virtualized Telemetry Table (Live UI)                      │
│        ├──► Dynamic Dependency Topology Graph                          │
│        ├──► Anomaly Detectors & Error Budget Trackers                  │
│        └──► Historical Replay & Incident Memory Store                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Telemetry Controls & Capabilities

- **Pause / Resume:** Operators can freeze the live stream at any millisecond to inspect microsecond-level stack traces without dropping incoming data in the background buffer.
- **Search & Highlighting:** Full-text regex search across message payloads, trace IDs, service names, and attributes.
- **Multi-Dimensional Filtering:** Filter instantly by service name (`auth-service`, `payment-gateway`, etc.), severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`), and event type.
- **Live Throughput Metrics:** Real-time calculation of Events Per Second (EPS), Kafka throughput (MB/s), consumer lag, and end-to-end pipeline ingestion latency (typically < 2.5ms).

---

## 3. OTel Collector Production Configuration

Below is the standard production `otel-collector-daemonset.yaml` used to forward telemetry into AegisOps AI with tenant partition tagging:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: aegisops-system
data:
  otel-collector-config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      batch:
        send_batch_size: 1000
        timeout: 1s
      attributes:
        actions:
          - key: aegisops.tenant.id
            value: "tenant-alpha"
            action: insert
          - key: aegisops.environment
            value: "production"
            action: insert

    exporters:
      otlphttp/aegisops:
        endpoint: "https://ingest.aegisops.ai/v1/telemetry"
        headers:
          X-API-Key: "${AEGISOPS_INGEST_KEY}"
          X-Tenant-ID: "tenant-alpha"

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch, attributes]
          exporters: [otlphttp/aegisops]
        metrics:
          receivers: [otlp]
          processors: [batch, attributes]
          exporters: [otlphttp/aegisops]
        logs:
          receivers: [otlp]
          processors: [batch, attributes]
          exporters: [otlphttp/aegisops]
```
