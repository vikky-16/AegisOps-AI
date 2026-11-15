# AegisOps AI — Platform Security, PII Masking & Secrets Redaction

## 1. Authentication & Cryptographic Keys
- **API Key Hashing**: Raw API keys (`agt_live_...`) are never stored in plaintext. They are hashed using SHA-256 before persistence in the `tenant_api_keys` table.
- **In-Memory Cache**: To ensure microsecond validation latency without database transaction lock contention, hashed API keys are verified against an in-memory dictionary.
- **JWT Authorization**: User sessions authenticate via signed JSON Web Tokens (JWT) containing tenant ID and role claims.

---

## 2. PII & Secrets Redaction Engine
The `PIIMasker` regex pipeline scrubs incoming telemetry at the ingestion gateway before any event is persisted or broadcast over WebSockets.

### Redaction Rules:
1. **Authorization Headers**: Bearer tokens and JWTs are replaced with `[REDACTED_JWT]` or `[REDACTED_TOKEN]`.
2. **Database Passwords**: Database connection URIs (`postgres://user:pass@host`) are rewritten to redact passwords.
3. **API Keys**: Keys matching patterns (`sk_live_*`, `agt_live_*`, `api_key=*`) are replaced with `[REDACTED_KEY]`.
4. **Private Keys**: RSA, EC, and OpenSSH private key PEM blocks are replaced with `[REDACTED_PRIVATE_KEY]`.
5. **Sensitive Keys**: Dictionary keys named `password`, `secret`, `client_secret`, `db_password` are masked automatically.

---

## 3. Server-Side Security Enforcement
Frontend UI controls never serve as the sole security boundary:
- Missing or invalid API keys return `401 Unauthorized`.
- Cross-tenant resource queries return `403 Forbidden` or `404 Not Found`.
- Privilege escalation attempts on approval endpoints return `403 Forbidden`.
