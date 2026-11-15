# AegisOps AI - Self-Healing & Recovery Verification

## 1. Philosophical Principle
Restarting a service is only ONE possible recovery action. AegisOps AI incorporates a diverse catalog of operational remediation actions paired with risk scoring and closed-loop verification.

---

## 2. Remediation Actions Catalog

| Action Key | Action Title | Target Fault | Risk Level | Autonomous? |
| :--- | :--- | :--- | :---: | :---: |
| `RESTART_SERVICE` | Graceful Process Restart | Process crash / Segmentation fault | MEDIUM | If Confidence > 0.85 |
| `RESET_CONNECTION_POOL` | Flush & Reset DB Pool | Connection exhaustion / Stalled locks | LOW | Yes (Autonomous) |
| `SCALE_WORKERS` | Scale Thread Pool | High CPU saturation / Concurrency spike | LOW | Yes (Autonomous) |
| `CLEAR_CACHE` | Purge Heap Buffers | Memory pressure / Memory leak | LOW | Yes (Autonomous) |
| `ROTATE_AND_COMPRESS_LOGS` | Rotate & Gzip Archival | Log explosion / Tablespace growth | LOW | Yes (Autonomous) |
| `COMPACT_STORAGE` | Tablespace Compaction | Disk capacity warning | MEDIUM | Approval Required |
| `ROLLBACK_CONFIG` | Restore Known Good Config | Corrupted configuration / Buggy rollout | HIGH | Approval Mandatory |

---

## 3. Risk Engine & Human Approval

The Risk Engine calculates composite risk score $R \in [0, 100]$:
$$R = (\text{Base Risk} \times \text{Criticality Multiplier}) + \text{Confidence Penalty}$$

- **LOW RISK ($R < 35$)**: Safely executed autonomously by the orchestrator.
- **MEDIUM / HIGH / CRITICAL RISK ($R \ge 35$)**: Generates an Approval Ticket in the **Human Approvals Center** with RCA justification, estimated downtime, and rollback plan.

---

## 4. Multi-Point Recovery Verification Probe

After executing any recovery action, the Recovery Verifier initiates a 4-point probe:
1. **Target Health Check**: `GET /health` must return `HTTP 200` with `state: HEALTHY`.
2. **Error Rate Threshold**: Error rate must drop below `1.0%`.
3. **Latency Baseline**: Latency $p95$ must recover within normal baseline ($< 100\text{ms}$).
4. **End-to-End Synthetic Transaction**: Synthetic request through the Ingress Gateway (`GET /work`) must succeed end-to-end across all 4 microservices.

### Handling Failed Recovery
If verification fails, the system **never falsely marks the incident as resolved**. Instead, it flags `RECOVERY_FAILED`, escalates incident severity to `CRITICAL`, generates an alternative recommendation (e.g. `RESET_CONNECTION_POOL` instead of soft restart), and notifies administrators for authorization.
