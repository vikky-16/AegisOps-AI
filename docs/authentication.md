# AegisOps AI — Authentication & Identity Governance

## 1. Overview

AegisOps AI provides a multi-tenant enterprise authentication suite supporting username/email credentials, pre-seeded evaluation personas, TOTP multi-factor authentication (MFA), secure member invitations, self-service password recovery, and fine-grained Role-Based Access Control (RBAC).

---

## 2. Pre-Seeded Enterprise Personas

For streamlined demonstration, sales evaluation, and automated testing, the following enterprise personas are pre-seeded with standardized credentials:

| Username / Email | Pre-Seeded Password | Enterprise Role | Organization / Tenant | Key Responsibility |
|---|---|---|---|---|
| `admin` / `admin@aegisops.ai` | `admin123` | **SUPER_ADMIN** | Global / Platform Admin | Fleet-wide platform governance & tenant creation |
| `ceo_acme` / `ceo@acme.com` | `acme123` | **CEO** | Acme Corporation (`tenant-alpha`) | Executive business impact & availability oversight (Technical remediation blocked) |
| `cto_acme` / `cto@acme.com` | `acme123` | **CTO** | Acme Corporation (`tenant-alpha`) | Distributed architecture & DORA engineering posture |
| `sre_acme` / `sre@acme.com` | `acme123` | **SRE_LEAD** | Acme Corporation (`tenant-alpha`) | Full remediation approval & guardrail override authority |
| `devops_acme` / `devops@acme.com` | `acme123` | **DEVOPS_ENGINEER** | Acme Corporation (`tenant-alpha`) | Pipeline operations & low-risk remediation execution |
| `sec_acme` / `sec@acme.com` | `acme123` | **SECURITY_ENGINEER** | Acme Corporation (`tenant-alpha`) | SecOps posture, SOC2 compliance & audit log inspection |
| `ic_acme` / `ic@acme.com` | `acme123` | **INCIDENT_COMMANDER** | Acme Corporation (`tenant-alpha`) | Incident triage & multi-service response coordination |

---

## 3. Authentication Flow & Endpoints

### 3.1 Login (`POST /v1/auth/login`)
- Accepts `username` or `email` and plaintext `password`.
- Verifies hashed password via bcrypt / PBKDF2.
- Issues JWT token with 12-hour validity and embedded tenant/role claims.

### 3.2 Password Self-Service Recovery
- **Request (`POST /v1/auth/forgot-password`):** Generates a high-entropy 32-byte URL-safe reset token with 60-minute expiration.
- **Reset (`POST /v1/auth/reset-password`):** Validates the token and updates the user's password hash in the database.

### 3.3 Multi-Factor Authentication (MFA)
- **Setup (`POST /v1/auth/mfa/setup`):** Generates a cryptographically random 160-bit hex secret and returns standard `otpauth://` URI and 5 backup codes.
- **Verify (`POST /v1/auth/mfa/verify`):** Confirms initial code entry and flags `mfa_enabled = true` on the user record.

### 3.4 Member Invitations (`POST /v1/auth/invite`)
- Allows `ORG_ADMIN` or `SUPER_ADMIN` to invite new members by email with designated roles (`DEVELOPER`, `SRE_LEAD`, `DEVOPS_ENGINEER`, etc.).
- Records an immutable entry in the `tenant_audit_logs`.

### 3.5 Tenant Context Switching (`POST /v1/auth/switch-tenant`)
- Authorizes `PLATFORM_ADMIN` and `SUPER_ADMIN` callers to switch active tenant context dynamically while recording the administrative event for compliance auditing.
