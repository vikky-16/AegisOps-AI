# AegisOps AI - Security & Authorization

## 1. Authentication
- **Password Security**: Passwords hashed using standard `bcrypt` with dynamic salt.
- **Token Management**: Stateless JSON Web Tokens (JWT) signed with HMAC-SHA256 (`HS256`).
- **Token Expiration**: Default 24-hour configurable token TTL.

---

## 2. Role-Based Access Control (RBAC)

| Role | Permissions |
| :--- | :--- |
| **Administrator (`admin`)** | Approve high-risk actions, configure policies, trigger failure simulations, view all telemetry and audit logs. |
| **Operator (`operator`)** | Monitor telemetry, investigate active incidents, trigger low-risk proactive remediations, view Knowledge Base. |
| **Viewer (`viewer`)** | Read-only access to dashboards, service observatory, and reliability reports. |

---

## 3. Immutable SRE Audit Trail
All security-sensitive operations (approval grants, rejections, manual remediation triggers, log archival, and failure simulations) are permanently recorded in the `audit_logs` table with actor identity, action type, target resource, timestamp, and metadata.
