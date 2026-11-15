# AegisOps AI — Streaming Telemetry Ingestion & OpenTelemetry Gateway

## 1. Streaming vs Static Ingestion
AegisOps AI rejects static CSV datasets or pre-canned batch files for its core processing loop. Telemetry is continuously streamed via:
1. **Live HTTP/gRPC Ingestion Gateway**: Receives OpenTelemetry OTLP packets from external collectors.
2. **Kafka Streaming Pipeline**: Streams events through partitioned Kafka topics for decoupled asynchronous consumption.
3. **Continuous Real-Time Telemetry Generator**: Microservice generator synthesizing production-like load (requests, errors, latencies, CPU, connection pools) across backend microservices with millisecond precision.

---

## 2. Ingestion Endpoints Reference

All endpoints accept standard JSON or OTLP protobuf payloads and require authentication via `X-API-Key` header or `Authorization: Bearer <jwt>`.

- `POST /api/v1/telemetry/logs`: Ingest single log record.
- `POST /api/v1/telemetry/metrics`: Ingest single metric measurement.
- `POST /api/v1/telemetry/traces`: Ingest single trace span.
- `POST /api/v1/telemetry/events`: Ingest operational lifecycle event.
- `POST /api/v1/telemetry/batch`: High-throughput multi-event ingestion (up to 5,000 events/request).
- `GET /api/v1/telemetry/stats`: Live throughput KPIs (measured EPS, bytes/sec, active services).

---

## 3. Real Throughput Computation
The `IngestionTracker` computes throughput using sliding time windows ($W = 2.0\text{s}$):
$$\text{EPS} = \frac{\sum \text{Events in Window}}{\Delta t}$$
$$\text{Throughput (Bytes/sec)} = \frac{\sum \text{Bytes in Window}}{\Delta t}$$
These numbers reflect actual ingested payload volume and network transfer rates. Synthetic hardcoded numbers are strictly prohibited.

---

## 4. OpenTelemetry Collector Setup
To stream external telemetry into AegisOps AI, deploy the OpenTelemetry Collector using the configuration below:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 256
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75

exporters:
  otlphttp/aegisops:
    endpoint: http://aegisops.internal:8000/api/v1/telemetry
    headers:
      X-API-Key: "agt_live_your_tenant_key"
      X-Tenant-ID: "your-tenant-id"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlphttp/aegisops]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlphttp/aegisops]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlphttp/aegisops]
```
