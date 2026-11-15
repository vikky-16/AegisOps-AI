# AegisOps AI — Demo Scenarios & Environment Modes

## 1. Environment Mode Distinction
To ensure complete transparency and enterprise credibility, AegisOps AI clearly distinguishes between three operating modes in the user interface and API headers:

- **`LIVE_EXTERNAL_TENANT` (Emerald Badge)**:
  Real telemetry streaming from external enterprise clusters, OpenTelemetry collectors, or live cloud environments. Full cryptographic isolation and dedicated policy enforcement.
- **`LIVE_DEMO_ENVIRONMENT` (Cyan Badge)**:
  Real multi-service backend running locally across 5 microservices (`gateway:8001`, `service-a:8002`, `service-b:8003`, `database-service:8004`, `auth-service:8005`). Emits real HTTP traffic, active connection pools, CPU, and memory metrics.
- **`SIMULATED_DEMO` (Purple Badge)**:
  Deterministic failure injection or historical log replay (e.g. LogHub datasets) for training, testing, or controlled demonstrations.

---

## 2. Expanded 44-Failure Scenario Catalog
The platform provides 44 realistic failure scenarios across 13 operational categories in `backend/app/monitoring/failure_scheduler.py`:

1. **Database Failures**: Connection Pool Exhaustion, Read Replica Lag, Write Deadlocks, Slow Query Table Scan.
2. **Application Failures**: Unhandled Null Pointer Exception, Microservice Thread Pool Exhaustion, Memory Leak & OOM, Goroutine / Thread Lock.
3. **Network Failures**: Network Partition, DNS Resolution Timeout, Packet Loss & Re-transmission, Egress Proxy Blackhole.
4. **Dependency Failures**: Downstream Payment Gateway Timeout, Auth Service Intermittent 503, Redis Cache Cold Start, Third-Party Rate Limit.
5. **Resource Failures**: CPU Core Saturation, Memory Buffer Pressure, Disk I/O Saturation, Ephemeral Storage Exhaustion.
6. **Performance Failures**: P99 Latency Regression, GC Pause Duration Spike, TCP Socket Saturated, Slow Disk Write Wait.
7. **Cache Failures**: Cache Stampede / Thundering Herd, Cache Eviction Spike, Cache Serialization Failure, Redis Out of Memory.
8. **Security Failures**: Ingress DDoS Flood, Credential Stuffing Surge, Malformed Token Injection, Unauthorized Port Scan.
9. **Behavioral Failures**: Cascading Microservice Retry Storm, Circular Dependency Deadlock, Traffic Imbalance / Hotspot, Split-Brain Configuration.
10. **Message Queue Failures**: Kafka Consumer Lag Accumulation, Dead Letter Queue Flooding, Partition Rebalance Storm, Message Serialization Failure.
11. **Configuration Failures**: Malformed Environment Variable, Stale Service Discovery Cache, Misconfigured Timeout Mismatch, Expired TLS Certificate.
12. **Cascade Failures**: Database Failure -> Payment Timeout -> Ingress 504 Gateway Collapse.
13. **Novel Anomaly**: Unprecedented metric correlation signature (forces Scenario F human approval).
