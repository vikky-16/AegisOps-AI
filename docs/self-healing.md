# AegisOps AI — Policy-Controlled Self-Healing & Active Verification

## 1. Safety-First Autonomy Philosophy
AegisOps AI rejects dangerous, unrestricted auto-remediation. Autonomous execution is strictly governed by risk-aware policies, declarative allowlists, and mathematical confidence gates.

```
Incident Opened
       │
       ▼
[Decision Engine Evaluation]
       │
       ├───────────────────────────────────────────────────────┐
       ▼                                                       ▼
[Autonomous Path]                                     [Human Approval Gate]
- Allowlisted Runbook                                 - High-Risk Action
- Risk Level <= Policy Limit                          - Critical Service Restart
- RCA Confidence >= 0.85                              - Blast Radius > 75
- Known Incident Signature (CBR)                      - Novel Failure Pattern (< 0.80)
- Telemetry Fresh (No Stale Data)                     - Auto-Remediation Disabled
       │                                                       │
       ▼                                                       ▼
[Execute Runbook]                                     [SRE Approves / Rejects]
       │                                                       │
       └───────────────────────────┬───────────────────────────┘
                                   ▼
                [Active Multi-Point Verification Probe]
                - Query Service /health endpoint
                - Inspect Error Rate < 0.05
                - Execute Synthetic Transaction Probe
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
            [Probe Passed: 100%]        [Probe Failed]
                     │                           │
                     ▼                           ▼
          [Status: RESOLVED]          [Execute Fallback / Rollback]
```

---

## 2. Declarative Allowlisted Runbooks

| Action Name | Risk Level | Reversible | Target Scope | Autonomous Eligible? |
| :--- | :---: | :---: | :---: | :---: |
| `RESET_CONNECTION_POOL` | **LOW** | Yes | Database Connection | ✅ Yes (Policy-Allowed) |
| `CLEAR_CACHE` | **LOW** | Yes | Memory / Buffer | ✅ Yes (Policy-Allowed) |
| `SCALE_WORKERS` | **LOW** | Yes | Concurrency / Thread | ✅ Yes (Policy-Allowed) |
| `ROTATE_AND_COMPRESS_LOGS` | **LOW** | Yes | Storage / Disk | ✅ Yes (Policy-Allowed) |
| `RESTART_SERVICE` | **MEDIUM** | Yes | Process / Container | ⚠️ Non-Critical Only |
| `ROLLBACK_CONFIG` | **HIGH** | Yes | Configuration | ❌ Requires Human Approval |
| `RESTART_CRITICAL_SERVICE` | **HIGH** | Yes | Ingress / DB / Auth | ❌ Strictly Requires Approval |

---

## 3. Active Verification Protocol
AegisOps AI never assumes a command succeeded simply because the executor returned zero exit status. Before transitioning an incident to `RESOLVED`:
1. **Direct Health Check Probe**: Queries `/health` on all affected services.
2. **Error Rate Evaluation**: Verifies that error rate drops below 5% across subsequent telemetry windows.
3. **Synthetic Work Probe**: Submits an active end-to-end synthetic request (`POST /work`) to confirm transaction success.
