# ShopSphere Real-Time Telemetry Pipeline for AegisOps AI

This document provides a comprehensive operational guide for the **ShopSphere** simulated enterprise e-commerce platform and its real-time telemetry streaming integration with **AegisOps AI**.

---

## 1. Architecture Overview

ShopSphere is an actual running microservice environment orchestrated via Docker Compose. Telemetry is produced organically by real traffic flowing across services, instrumented with the OpenTelemetry Python SDK, exported to an OpenTelemetry Collector, streamed into Redpanda (Kafka-compatible broker), and ingested into the existing AegisOps Ingestion Gateway and ML intelligence engine.

```
                           +----------------------------+
                           |  Traffic Generator (Load)  |
                           +--------------+-------------+
                                          | HTTP Requests (~20-100 req/sec)
                                          v
                           +----------------------------+
                           |     API Gateway (:8100)    |
                           +-------+------------+-------+
                                   |            |
                     +-------------+            +-------------+
                     |                                        |
                     v                                        v
        +-------------------------+              +-------------------------+
        |  Order Service (:8101)  |              | Inventory Service(:8102)|
        +----+---------------+----+              +----+---------------+----+
             |               |                        |               |
             v               v                        v               v
  +--------------------+ +--------------------+ +-----------+ +-------------+
  |Payment Svc (:8103) | |Notification (:8104)| |PostgreSQL | | Redis Cache |
  +--------------------+ +--------------------+ |  (:5433)  | |   (:6380)   |
                                                +-----------+ +-------------+

  ====================== DISTRIBUTED OBSERVABILITY PIPELINE ======================

   Running Microservices (FastAPI + OTel SDK + W3C TraceContext)
                           |
                           | OTLP HTTP/gRPC (:4317 / :4318)
                           v
   +-------------------------------------------------------------+
   |             OpenTelemetry Collector Contrib                 |
   |   (Processors: batch, memory_limiter, resource attributes)  |
   +---------------+-----------------------------+---------------+
                   |                             |
      OTLP JSON    |                             | OTLP HTTP
                   v                             v
   +-------------------------------+   +------------------------------------+
   | Redpanda Broker (:9092/:9644) |   |  AegisOps Direct OTel Ingestion    |
   | - shopsphere-logs             |   |  (/api/otel/v1/traces, metrics)    |
   | - shopsphere-metrics          |   +------------------------------------+
   | - shopsphere-traces           |
   +---------------+---------------+
                   |
                   | High-throughput consumer
                   v
   +-------------------------------------------------------------+
   |              ShopSphere AegisOps Streamer                   |
   |   (Parses OTLP spans/metrics/logs, preserves tenant_id)     |
   +-------------------------------+-----------------------------+
                                   |
                                   | POST /api/v1/telemetry/batch (200 OK)
                                   v
   +-------------------------------------------------------------+
   |                EXISTING AEGISOPS BACKEND                    |
   |  - Telemetry Ingestion Gateway & Token Auth                 |
   |  - Multi-detector Ensemble Anomaly Isolation                |
   |  - Dynamic Graph RCA & Root Cause Candidates                |
   |  - Automated Incident Engine & Self-Healing Recommender     |
   |  - WebSocket / SSE Live Multi-Tenant Distribution           |
   |  - Live Operational Dashboard (http://127.0.0.1:5173)       |
   +-------------------------------------------------------------+
```

---

## 2. Microservice Descriptions

| Service | Port | Description & Responsibilities |
|---|---|---|
| **API Gateway** | 8100 | Ingress proxy, extracts/injects W3C traceparents, routes orders, catalog queries, and health checks. |
| **Order Service** | 8101 | Orchestrates multi-step checkout pipeline: reserves stock, processes card payment, persists order to PostgreSQL, and triggers confirmation alerts. Includes chaos failure injection endpoints (`/inject/db-latency`). |
| **Inventory Service**| 8102 | Real-time warehouse catalog inventory. Queries PostgreSQL `inventory` table with Redis caching (`inv:<sku>`). Includes auto-replenishment on low-stock conditions under continuous load. |
| **Payment Service** | 8103 | Card transaction settlement engine. Simulates authorization gateway, logs masked audit trails, records settlement ledgers to PostgreSQL `payments`. |
| **Notification Service** | 8104 | Customer confirmation dispatcher. Generates transactional email/SMS delivery logs and records alerts to PostgreSQL `notifications`. |
| **PostgreSQL** | 5433 | Relational database holding tables: `inventory`, `orders`, `order_items`, `payments`, `notifications`. |
| **Redis** | 6380 | In-memory key-value cache holding active catalog item caches with TTLs. |
| **Redpanda** | 9092 / 9644 | Single-binary Kafka API-compatible high-performance streaming broker. Manages topics `shopsphere-logs`, `shopsphere-metrics`, `shopsphere-traces`. |
| **OTel Collector** | 4317 / 4318 | Aggregates microservice telemetry, applies tenant attributes, exports to Redpanda topics and AegisOps endpoints. |
| **AegisOps Streamer** | Internal | Bridges Redpanda topics directly into the AegisOps unified ingestion batch endpoint (`/api/v1/telemetry/batch`). |
| **Traffic Generator** | Internal | Generates realistic, continuous HTTP client traffic through the API Gateway at configurable rates. |

---

## 3. How Traffic is Generated

The traffic generator (`shopsphere/traffic/generator.py`) runs asynchronously inside the Docker network.
- **Configurable Rate**: Controlled by `TRAFFIC_REQUESTS_PER_SECOND` (default 50-100 req/sec).
- **Realistic Operations**:
  - `60%`: Query item availability from inventory/catalog (`GET /api/v1/inventory/{sku}`).
  - `25%`: Full end-to-end checkout (`POST /api/v1/orders`), traversing Gateway -> Order Service -> Inventory Service -> Payment Service -> Database -> Notification Service.
  - `10%`: Retrieve existing order details (`GET /api/v1/orders/{order_id}`).
  - `5%`: Read full catalog index (`GET /api/v1/catalog`).
- **Telemetry Measurements**: Measures latency percentiles (p50, p95), actual requests/sec, and error rates every 2 seconds.

---

## 4. How Structured JSON Logging Works

Every microservice uses the standardized `shopsphere/common/logger.py` module:
- Formats logs into single-line JSON with standard attributes:
  - `timestamp`: ISO-8601 UTC timestamp
  - `tenant_id`: Strictly enforced as `"shopsphere"`
  - `service`: Service name (e.g. `order-service`)
  - `environment`: `production`
  - `hostname`: Container ID / hostname
  - `level`: `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - `event_type`: Specific operational event (e.g. `order_created`, `db_query`, `inventory_reserved`)
  - `request_id`: Request correlation ID (`req-...`)
  - `trace_id`: 32-character W3C OpenTelemetry trace ID
  - `span_id`: 16-character OpenTelemetry span ID
  - `latency_ms`: Duration of operation in milliseconds
  - `status_code`: HTTP response status
- **Sensitive Data Redaction**: Automatic regular-expression redaction masks credit card numbers, passwords, bearer tokens, API keys, and CVVs before logs are emitted.

---

## 5. How OpenTelemetry & Distributed Tracing Work

- Services are instrumented with the official OpenTelemetry Python SDK (`opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`).
- **Trace Context Propagation**: Every outgoing HTTP call propagates the standard W3C `traceparent` header (`00-<trace_id>-<span_id>-01`).
- Incoming requests in `TraceContextMiddleware` read the `traceparent` header to maintain continuous distributed spans across hops:
  `API Gateway -> Order Service -> Inventory Service -> Payment Service -> PostgreSQL/Redis`.
- Spans and runtime metrics are automatically pushed via OTLP/HTTP to the OpenTelemetry Collector on `http://otel-collector:4318`.

---

## 6. How Redpanda / Kafka Works

The OpenTelemetry Collector (`otel-collector-config.yaml`) defines Kafka exporters pointing to `redpanda:9092`:
- `shopsphere-logs`: Receives log records
- `shopsphere-metrics`: Receives runtime metrics
- `shopsphere-traces`: Receives distributed trace spans

The `shopsphere-aegisops-streamer` service:
1. Connects to `redpanda:9092` with an `AIOKafkaConsumer`.
2. Subscribes to `shopsphere-logs`, `shopsphere-metrics`, `shopsphere-traces`.
3. Normalizes OTLP JSON protobuf structures into `UnifiedTelemetryEvent` dictionaries.
4. Streams batches of 50-100 events every 250ms via HTTP POST to the AegisOps Ingestion Gateway.

---

## 7. How AegisOps Consumes Telemetry & Multi-Tenant Isolation

1. **Authentication**: The streamer supplies header `X-API-Key: agt_live_shopsphere_11112222333344445555`.
2. **Ingestion**: AegisOps verifies the key, extracts `tenant_id="shopsphere"`, and writes events to the continuous `TelemetryStore`.
3. **Multi-Detector Ensemble**: Evaluates throughput drops, error rate surges, and latency spikes against dynamic service baselines.
4. **Tenant Boundary Enforcement**:
   - `tenant_id` is cryptographically validated at the ingestion boundary.
   - The Incident Correlator (`backend/app/incidents/correlator.py`) enforces strict tenant matching (`evt_tenant != inc_tenant` rejects merging).
   - The Incident API (`GET /api/incidents?tenant_id=shopsphere`) isolates incidents on the backend.
5. **Dynamic DAG RCA**: Maps cascading anomalies back to the root cause service.
6. **Live Dashboard & WebSockets**: Ingested events are broadcast over WebSocket to dashboard clients subscribed to `shopsphere`.

---

## 8. Exact Commands

### Start the Entire Environment
```bash
# 1. Start ShopSphere containers (in WSL or Linux)
wsl -u root -d Ubuntu docker-compose -f "/mnt/c/Users/admin/AegisOps AI/shopsphere/docker-compose.yml" up -d

# 2. Start AegisOps Backend (Windows Host)
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 3. Start AegisOps Frontend (Windows Host)
npm run dev -- --host 127.0.0.1 --port 5173
```

### Stop the Environment
```bash
wsl -u root -d Ubuntu docker-compose -f "/mnt/c/Users/admin/AegisOps AI/shopsphere/docker-compose.yml" down
```

### Verify Container Health & Status
```bash
wsl -u root -d Ubuntu docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Verify Redpanda Topics & Message Counts
```bash
# List topics
wsl -u root -d Ubuntu docker exec shopsphere-redpanda rpk topic list

# View topic metadata & partition state
wsl -u root -d Ubuntu docker exec shopsphere-redpanda rpk topic describe shopsphere-traces
```

### Inspect Live Service Logs
```bash
# View Order Service structured JSON logs
wsl -u root -d Ubuntu docker logs --tail 30 -f shopsphere-order-service

# View Streamer batch throughput
wsl -u root -d Ubuntu docker logs --tail 30 -f shopsphere-aegisops-streamer

# View Traffic Generator request rates
wsl -u root -d Ubuntu docker logs --tail 30 -f shopsphere-traffic-generator
```

### Run End-to-End Automated Pipeline Verification
```bash
wsl -u root -d Ubuntu docker exec shopsphere-traffic-generator python /app/shopsphere/verify_pipeline.py
```

### Inject the Test Failure (PostgreSQL Degradation)
```bash
# Inject 2500ms database latency into Order Service PostgreSQL queries:
curl -X POST http://127.0.0.1:8101/inject/db-latency -H "Content-Type: application/json" -d "{\"latency_ms\": 2500.0, \"exhaust_connections\": false}"

# Observe cascaded timeouts on API Gateway:
curl -X POST http://127.0.0.1:8100/api/v1/orders -H "Content-Type: application/json" -d "{\"customer_id\": \"cust-test\", \"items\": [{\"sku\": \"SKU-LAPTOP-01\", \"quantity\": 1, \"price\": 1299.99}], \"payment_method\": \"credit_card\"}"

# Inspect incidents created in AegisOps for ShopSphere:
curl -s "http://127.0.0.1:8000/api/incidents?tenant_id=shopsphere"

# Reset failure injection (restores normal latency):
curl -X POST http://127.0.0.1:8101/inject/db-reset
```
