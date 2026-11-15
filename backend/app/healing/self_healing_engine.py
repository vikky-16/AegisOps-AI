"""
AegisOps AI - Central Self-Healing Engine
Orchestrates the complete closed-loop recovery lifecycle:
Validation -> Freshness -> Policy -> Allowlist -> Action Lock -> Execution -> Fresh Telemetry -> Multi-Point Verification -> Resolution.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.healing.decision_engine import decision_engine, ACTION_ALLOWLIST
from backend.app.healing.executor import executor
from backend.app.healing.verifier import verifier
from backend.app.knowledge.incident_memory import incident_memory


class SelfHealingEngine:
    def __init__(self):
        self.decision_engine = decision_engine
        self.executor = executor
        self.verifier = verifier
        self.active_locks: Dict[str, str] = {}  # service_name -> action_id

    def acquire_lock(self, service_name: str, action: str) -> bool:
        """Acquires an exclusive action lock on a service to prevent double remediation."""
        if service_name in self.active_locks:
            return False
        self.active_locks[service_name] = f"{action}:{time.time()}"
        return True

    def release_lock(self, service_name: str):
        self.active_locks.pop(service_name, None)

    async def execute_recovery_loop(
        self,
        incident: Dict[str, Any],
        action: str,
        caller: str = "AegisOps_Autonomous_SelfHealer",
        fresh_telemetry_wait_sec: float = 1.0
    ) -> Dict[str, Any]:
        """
        Executes the verified closed-loop recovery for an incident.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        svc = incident.get("root_cause_service", incident.get("primary_service", "database-service"))
        affected_services = incident.get("affected_services", [svc])
        
        # 1. Action Lock Check
        if not self.acquire_lock(svc, action):
            return {
                "success": False,
                "error": f"Service '{svc}' currently has an active remediation lock. Execution skipped to prevent race conditions.",
                "status": "LOCK_HELD"
            }

        try:
            # 2. Transition state to REMEDIATING
            incident["status"] = "REMEDIATING"
            incident["remediation_status"] = "EXECUTING"
            incident["timeline"].append({
                "timestamp": now_iso,
                "service": svc,
                "type": "REMEDIATION_STARTED",
                "message": f"Executing allowlisted recovery action '{action}' on '{svc}' by {caller}."
            })
            try:
                from backend.app.monitoring.failure_scheduler import failure_scheduler
                await failure_scheduler.transition_lifecycle("REMEDIATING")
            except Exception:
                pass

            # 3. Execute Allowlisted Action
            exec_res = await self.executor.execute_action(svc, action)
            self.decision_engine.record_action_executed(svc)

            incident["timeline"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": svc,
                "type": "REMEDIATION_APPLIED",
                "message": f"Action '{action}' executed ({exec_res.get('duration_ms', 100)}ms). Waiting for fresh telemetry to verify recovery."
            })

            # 4. Wait for FRESH telemetry to arrive (do not verify immediately on stale samples)
            incident["status"] = "VERIFYING"
            incident["verification_status"] = "WAITING_FOR_FRESH_TELEMETRY"
            try:
                from backend.app.monitoring.failure_scheduler import failure_scheduler
                await failure_scheduler.transition_lifecycle("VERIFYING")
            except Exception:
                pass

            if fresh_telemetry_wait_sec > 0:
                await asyncio.sleep(fresh_telemetry_wait_sec)

            # 5. Multi-Point Verification Probe
            verif_res = await self.verifier.verify_recovery(svc, affected_services, probe_delay_sec=0.5)

            exec_ok = bool(exec_res.get("success", False))
            verif_ok = bool(verif_res.get("verified", False))

            if exec_ok and verif_ok:
                status = "SUCCESS"
                incident_status = "RESOLVED"
                recovery_status = "SUCCESS"
                remediation_status = "EXECUTION_SUCCESS"
            elif (not exec_ok) and verif_ok:
                status = "RECOVERED_AFTER_EXECUTION_ERROR"
                incident_status = "RECOVERED_AFTER_EXECUTION_ERROR"
                recovery_status = "RECOVERED_AFTER_EXECUTION_ERROR"
                remediation_status = "REMEDIATION_FAILED"
            else:
                status = "FAILED"
                incident_status = "REMEDIATION_FAILED"
                recovery_status = "FAILED"
                remediation_status = "FAILED"
            
            recovery_entry = {
                "execution_id": f"REC-{incident['incident_id'][-8:]}",
                "incident_id": incident["incident_id"],
                "service_name": svc,
                "action": action,
                "status": status,
                "success": (status in ["SUCCESS", "RECOVERED_AFTER_EXECUTION_ERROR"]),
                "duration_ms": exec_res.get("duration_ms", 120),
                "verification_status": "VERIFIED" if verif_ok else "VERIFICATION_FAILED",
                "verification_result": verif_res,
                "verification_details": verif_res,
                "result": exec_res.get("details", "Remediation executed on controlled demo service"),
                "error": exec_res.get("error") or (None if verif_ok else verif_res.get("failure_reason")),
                "started_at": now_iso,
                "executed_at": now_iso,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "caller": caller,
                "execution_mode": "CONTROLLED_DEMO"
            }
            try:
                from backend.app.healing.persistence import save_recovery_execution
                persisted = await save_recovery_execution(recovery_entry)
                recovery_entry = persisted
            except Exception:
                pass

            # 6. Evaluate Verification Outcome
            if verif_ok:
                incident["status"] = incident_status
                incident["recovery_status"] = recovery_status
                incident["remediation_status"] = remediation_status
                incident["verification_status"] = "VERIFIED"
                incident["resolved_at"] = datetime.now(timezone.utc).isoformat()

                msg_verif = (
                    f"Fresh telemetry verified healthy metric baselines on '{svc}'. Incident status: {incident_status}."
                    if status == "SUCCESS" else
                    f"Remediation reported execution error, but independent probes verified '{svc}' healthy: {incident_status}."
                )
                incident["timeline"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": svc,
                    "type": "RECOVERY_VERIFIED" if status == "SUCCESS" else "RECOVERED_AFTER_EXECUTION_ERROR",
                    "message": msg_verif
                })

                # 7. Index into Incident Memory for Historical Learning
                incident_memory.index_resolved_incident(incident, action, verif_res)

                # 8. Advance Failure Scheduler Lifecycle
                try:
                    from backend.app.monitoring.failure_scheduler import failure_scheduler
                    await failure_scheduler.transition_lifecycle("RESOLVED")
                    await failure_scheduler.transition_lifecycle("LEARNED")
                except Exception:
                    pass

                return {
                    "success": (status in ["SUCCESS", "RECOVERED_AFTER_EXECUTION_ERROR"]),
                    "status": incident_status,
                    "incident": incident,
                    "recovery_entry": recovery_entry,
                    "verification": verif_res
                }
            else:
                incident["status"] = "REMEDIATION_FAILED"
                incident["recovery_status"] = "FAILED"
                incident["remediation_status"] = "FAILED"
                incident["verification_status"] = "VERIFICATION_FAILED"

                incident["timeline"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": svc,
                    "type": "VERIFICATION_FAILED",
                    "message": f"Verification probe failed post-remediation: {'; '.join(verif_res.get('failure_reasons', ['Metrics remained degraded']))}."
                })

                return {
                    "success": False,
                    "incident": incident,
                    "recovery_entry": recovery_entry,
                    "verification": verif_res
                }

        finally:
            self.release_lock(svc)


self_healing_engine = SelfHealingEngine()
