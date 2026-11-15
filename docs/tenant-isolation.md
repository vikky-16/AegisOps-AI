# AegisOps AI — Multi-Tenancy & Tenant Data Isolation

## 1. Overview & Architectural Guarantees

AegisOps AI is architected from the ground up for strict multi-tenant software-as-a-service (SaaS) operations. Customers operate within logical and cryptographically partitioned boundaries. Under no circumstances can Tenant A view, query, ingest into, or manipulate telemetry, metrics, spans, incident records, or runbook approvals belonging to Tenant B.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TENANT BOUNDARY ISOLATION                        │
├───────────────────────────────────┬─────────────────────────────────────┤
│      TENANT A (Acme Corp)         │     TENANT B (Cyberdyne Systems)    │
│      ID: tenant-alpha             │     ID: tenant-beta                 │
├───────────────────────────────────┼─────────────────────────────────────┤
│  • OTel Collector DaemonSet       │  • OTel Collector DaemonSet         │
│  • Ingest Token: aegis_live_acme  │  • Ingest Token: aegis_live_cyber   │
│  • Isolated Telemetry Buffer      │  • Isolated Telemetry Buffer        │
│  • Distinct Dependency Topology   │  • Distinct Dependency Topology     │
│  • Scoped Incidents & Approvals   │  • Scoped Incidents & Approvals     │
│  • Isolated Vector CBR Memory     │  • Isolated Vector CBR Memory       │
│  • Row-Level DB: tenant-alpha     │  • Row-Level DB: tenant-beta        │
└───────────────────────────────────┴─────────────────────────────────────┘
```

---

## 2. Ingress & Token Boundary Enforcement

Every API call, WebSocket frame, and OpenTelemetry batch is authenticated at the ingress gateway:
1. **API Key Token Verification:** OpenTelemetry Collectors pass `X-API-Key: aegis_live_...`. The gateway resolves the associated `tenant_id` from the fast SHA-256 in-memory cache.
2. **Bearer Token Claims:** Enterprise console requests pass `Authorization: Bearer <JWT>`. The JWT claims are validated for `tenant_id` and `role`.
3. **Automatic Query Scoping:** Route handlers extract the `tenant_id` from the authenticated identity. Direct query parameters cannot override the caller's assigned tenant boundary unless caller holds `PLATFORM_ADMIN` or `SUPER_ADMIN` privileges.

---

## 3. Database & Persistence Layer Isolation

- **Foreign Key Enforcement:** All database entities (`tenants`, `users`, `teams`, `tenant_audit_logs`, `incidents`, `approvals`) maintain a non-nullable `tenant_id` foreign key.
- **Query Scoping:**
  ```python
  stmt = select(Incident).where(Incident.tenant_id == identity.tenant_id)
  ```
- **Audit Logging:** Every administrative action, user invite, and role modification is stored in `tenant_audit_logs` with the actor's username, role, IP address, and execution verdict.

---

## 4. In-Memory & AI Memory Scoping

1. **Circular Telemetry Buffers:** High-throughput streaming logs are segmented into per-tenant circular buffers.
2. **Topology Graphs:** Microservice dependency graphs are computed strictly from trace spans carrying the caller's `tenant_id`.
3. **Incident Memory (Case-Based Reasoning):** Vector embeddings of past resolved incidents are indexed per-tenant. Tenant A's proprietary runbook patterns are never exposed to or queried by Tenant B.

---

## 5. Security Validation & Automated Testing

The tenant boundary engine is continuously validated by automated pytest suites:
- `backend/tests/test_multi_tenant_isolation.py`:
  - Scenario A: Tenant A cannot view Tenant B incidents (HTTP 404 / filtered out).
  - Scenario B: Cross-tenant approval attempt returns HTTP 403 Forbidden.
  - Scenario C: Platform Admin cross-tenant targeting permitted only with explicit `X-Tenant-ID`.
