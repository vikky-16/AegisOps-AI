# AegisOps AI — Enterprise Security & Governance Model

## 1. Zero-Trust Security Philosophy

AegisOps AI enforces a Zero-Trust architecture across all ingestion layers, API interfaces, autonomous remediation engines, and administrative consoles. Every incoming request, trace span, metric datapoint, and human action is authenticated, verified, scoped, and cryptographically recorded.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ZERO-TRUST PERIMETER                            │
│  [Human Actor]        [OTel Collector]        [External Webhook]       │
│        │                     │                        │                │
│  Bearer JWT           Single-Reveal API Key   HMAC-SHA256 Signature    │
│        ▼                     ▼                        ▼                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Cryptographic Token Gate                      │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Fine-Grained RBAC Policy                      │  │
│  │     (CEO Restricted / SRE Authorized / SecOps Auditing)          │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              Row-Level & In-Memory Tenant Boundaries             │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                Immutable Cryptographic Audit Trail               │  │
│  │                 (Action, Actor, Role, IP, Verdict)               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Authentication & Credential Architecture

### 2.1 Passwords & Cryptographic Hashing
- User passwords are never stored in plaintext. Passwords are salted and hashed using **bcrypt** with a work factor of 12 rounds or PBKDF2 with SHA-256 (600,000 iterations).

### 2.2 JWT Session Tokens
- Stateless JSON Web Tokens (JWT) signed with HMAC-SHA256 (`HS256`).
- Standard claims:
  - `sub`: Username or user ID
  - `user_id`: Integer primary key
  - `tenant_id`: Partition identifier (`tenant-alpha`, `tenant-beta`, etc.)
  - `role`: Enterprise role (`SUPER_ADMIN`, `ORG_ADMIN`, `CEO`, `CTO`, `SRE_LEAD`, `DEVOPS_ENGINEER`, `SECURITY_ENGINEER`, `DEVELOPER`, `INCIDENT_COMMANDER`, `VIEWER`)
  - `exp`: Expiration time (12 hours)
  - `iat`: Issued at timestamp

### 2.3 Time-Based One-Time Password (TOTP) MFA
- Multi-factor authentication is required for all administrative, SRE, and executive roles.
- Standard RFC 6238 TOTP with 6-digit codes and 30-second time windows.
- Cryptographically random 160-bit base32 secrets with 5 single-use hexadecimal recovery codes.

---

## 3. Single-Reveal Ingestion API Keys

- OpenTelemetry Collectors and application SDKs authenticate via dedicated Ingestion API Keys (`aegis_live_...`).
- **Single-Reveal Security Policy:** Upon creation, the secret key is displayed to the administrator **exactly once**. AegisOps AI stores only a SHA-256 hash of the token.
- If a key is compromised, administrators can revoke it immediately from the Organization Settings console without interrupting other active tenant keys.

---

## 4. Role-Based Access Control (RBAC) Matrix

| Enterprise Role | Read Observability | Request Approval | Approve Remediation | Override Guardrails | Manage Teams & Keys | SOC2 Audit Export |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **SUPER_ADMIN** | YES | YES | YES | YES | YES | YES |
| **ORG_ADMIN** | YES | YES | YES | NO | YES | YES |
| **CEO** | YES | NO | **BLOCKED (403)** | NO | NO | YES |
| **CTO** | YES | YES | YES (Review) | NO | YES | YES |
| **SRE_LEAD** | YES | YES | **YES (Full)** | YES | NO | YES |
| **DEVOPS_ENGINEER** | YES | YES | Low-Risk Only | NO | NO | NO |
| **SECURITY_ENGINEER** | YES | NO | NO | NO | YES | **YES (Full)** |
| **INCIDENT_COMMANDER** | YES | YES | **YES (Full)** | YES | NO | YES |
| **DEVELOPER** | YES | NO | NO | NO | NO | NO |
| **VIEWER** | YES (Read) | NO | NO | NO | NO | NO |

> [!IMPORTANT]
> **CEO Remediation Restriction:** To prevent catastrophic operational changes by non-technical executive personas, direct remediation approval by a `CEO` token is architecturally blocked in the backend engine with an explicit `HTTP 403 Forbidden` response.

---

## 5. SOC2 Type II & Compliance Controls

1. **CC6.1 (Logical Access Control):** RBAC enforced at the API route dependency layer via `require_permission`.
2. **CC6.6 (Boundary Protection):** Tenant data queries enforce row-level scoping (`WHERE tenant_id = :id`).
3. **CC7.2 (Security Monitoring):** Auth failure anomalies (> 5 attempts / 60s) trigger IP rate throttling and automated alert dispatch.
4. **CC7.3 (Incident Remediation):** All autonomous remediation actions log both the proposed runbook and the active verification verdict.
