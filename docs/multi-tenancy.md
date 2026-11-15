# AegisOps AI — Multi-Tenancy & Data Isolation Architecture

## 1. Principles of Tenant Isolation
AegisOps AI enforces strict multi-tenancy at the data model, API gateway, operational memory, and database layers. Tenant boundaries are cryptographic and programmatic:
- **No Shared Telemetry**: Company A users cannot view, query, or receive telemetry belonging to Company B.
- **No Cross-Tenant Approvals**: An operator belonging to Tenant A cannot approve, reject, or inspect tickets from Tenant B.
- **Isolated Incident Memory**: Vector similarity searches for failure patterns are scoped strictly by tenant. Known patterns from Company A never populate Company B's Case-Based Reasoning database.
- **Server-Side Enforcement**: Tenant isolation is validated at the backend security layer; frontend views reflect strictly authorized scopes.

---

## 2. Tenant Models & Security Entities

```
┌─────────────────────────────────────────┐
│                 Tenant                  │
│  - id: VARCHAR(64) [PK]                 │
│  - name: VARCHAR(128)                   │
│  - slug: VARCHAR(64)                    │
│  - plan: VARCHAR(32)                    │
│  - is_active: BOOLEAN                   │
└───────────────────┬─────────────────────┘
                    │ 1:N
    ┌───────────────┼───────────────┬────────────────┐
    ▼               ▼               ▼                ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌────────────────┐
│ TenantAPIKey ││ TenantPolicy ││Integration   ││TenantAuditLog  │
│ - hashed_key ││ - auto_heal  ││ - type       ││ - actor        │
│ - scopes     ││ - max_risk   ││ - config     ││ - action       │
│ - is_active  ││ - pii_mask   ││ - is_healthy ││ - target       │
└──────────────┘└──────────────┘└──────────────┘└────────────────┘
```

---

## 3. Role-Based Access Control (RBAC) Matrix

| Role | Telemetry & Observability | View Incidents | Trigger Manual Remediation | Approve Low/Med Risk | Approve High/Critical Risk | Manage API Keys & Policies |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **VIEWER** | Read-Only | Read-Only | ❌ Denied | ❌ Denied | ❌ Denied | ❌ Denied |
| **OPERATOR** | Full View | Full View | Low Risk | Low Risk | ❌ Denied | ❌ Denied |
| **SRE_ENGINEER** | Full View | Full View | Allowed | Allowed | Allowed | ❌ Denied |
| **SRE_MANAGER** | Full View | Full View | Allowed | Allowed | Allowed | Allowed |
| **TENANT_ADMIN** | Full View | Full View | Allowed | Allowed | Allowed | Full Tenant Admin |
| **PLATFORM_ADMIN** | Cross-Tenant | Cross-Tenant | Cross-Tenant | Cross-Tenant | Cross-Tenant | Full System Admin |

---

## 4. Cross-Tenant Boundary Enforcement Test Results
Automated test suite `backend/tests/test_multi_tenant_isolation.py` proves that:
1. When Company A queries `/api/incidents`, zero incidents from Company B are returned.
2. When Company A attempts to inspect `/api/incidents/INC-CYBER-999` (Tenant B), the server returns `403 Forbidden`.
3. When Company A attempts to approve `/api/approvals/APR-CYBER-001/approve` (Tenant B), the server returns `403 Forbidden`.
4. When Company A searches incident memory with identical failure vectors, it receives a `Novel Anomaly` verdict rather than matching Company B's precedent.
