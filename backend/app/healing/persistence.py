"""
Database Persistence for Recovery Executions
Persists self-healing execution audit records to SQLite / SQLAlchemy database.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select, desc
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.recovery import RecoveryExecution
from backend.app.logger import realtime_logger


def _parse_datetime(val: Any) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        if isinstance(val, str):
            # Parse ISO 8601
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt
    except Exception:
        pass
    return datetime.now(timezone.utc)


async def save_recovery_execution(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Asynchronously persists a RecoveryExecution audit record into the database.
    """
    now_dt = datetime.now(timezone.utc)
    started_at = _parse_datetime(entry.get("started_at") or entry.get("executed_at")) or now_dt
    completed_at = _parse_datetime(entry.get("completed_at")) or now_dt
    executed_at = _parse_datetime(entry.get("executed_at")) or started_at

    verif_res = entry.get("verification_result") or entry.get("verification_details") or {}
    verif_status = entry.get("verification_status")
    if not verif_status:
        if isinstance(verif_res, dict) and verif_res.get("verified"):
            verif_status = "VERIFIED"
        elif isinstance(verif_res, dict) and "verified" in verif_res:
            verif_status = "VERIFICATION_FAILED"
        else:
            verif_status = "SKIPPED"

    success = bool(entry.get("success", entry.get("status") == "SUCCESS"))
    status = entry.get("status", "SUCCESS" if success else "FAILED")

    result_data = entry.get("result") or entry.get("execution", {}).get("details") or "Remediation executed"
    result_json_str = json.dumps(result_data) if not isinstance(result_data, str) else result_data

    rec = RecoveryExecution(
        execution_id=entry.get("execution_id", f"REC-{int(now_dt.timestamp())}"),
        incident_id=entry.get("incident_id", "MANUAL_OVERRIDE"),
        approval_id=entry.get("approval_id"),
        service_name=entry.get("service_name", "unknown"),
        runbook_id=entry.get("runbook_id"),
        plan_id=entry.get("plan_id"),
        plan_version=entry.get("plan_version", "v1.0"),
        solution_source=entry.get("solution_source"),
        remediation_run_id=entry.get("remediation_run_id"),
        is_simulated=bool(entry.get("is_simulated", False)),
        action=entry.get("action", "UNKNOWN"),
        risk_level=entry.get("risk_level", "LOW"),
        execution_mode=entry.get("execution_mode", "CONTROLLED_DEMO"),
        executor=entry.get("executor", "AegisOps_Remediation_Engine"),
        status=status,
        success=success,
        duration_ms=float(entry.get("duration_ms", 0.0)),
        verification_status=verif_status,
        verification_metrics_json=json.dumps(verif_res),
        steps_json=json.dumps(entry.get("steps", [])),
        result_json=result_json_str,
        error_message=entry.get("error"),
        started_at=started_at,
        executed_at=executed_at,
        completed_at=completed_at,
        verified_at=completed_at
    )

    try:
        async with AsyncSessionLocal() as session:
            session.add(rec)
            await session.commit()
            await session.refresh(rec)
            entry_dict = rec.to_dict()
            realtime_logger.info(f"Persisted recovery execution {rec.execution_id} to database.")
            return entry_dict
    except Exception as exc:
        realtime_logger.error(f"Failed to persist recovery execution to database: {exc}")
        # Return normalized entry even if DB write fails
        entry["status"] = status
        entry["success"] = success
        entry["verification_status"] = verif_status
        return entry


async def get_recovery_executions(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches persisted recovery executions from the database ordered by execution time desc.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(RecoveryExecution).order_by(desc(RecoveryExecution.id)).limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()
            return [r.to_dict() for r in records]
    except Exception as exc:
        realtime_logger.error(f"Failed to load recovery executions from database: {exc}")
        return []


async def get_latest_execution_for_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the most recent persisted recovery execution for a specific incident.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(RecoveryExecution).where(RecoveryExecution.incident_id == incident_id).order_by(desc(RecoveryExecution.id)).limit(1)
            result = await session.execute(stmt)
            rec = result.scalars().first()
            if rec:
                return rec.to_dict()
    except Exception as exc:
        realtime_logger.error(f"Failed to fetch execution for incident {incident_id}: {exc}")
    return None


async def sync_history_from_db():
    """
    Loads persisted executions into the central collector recovery history.
    """
    from backend.app.monitoring.collector import collector
    db_records = await get_recovery_executions(limit=100)
    if db_records:
        collector.recovery_history = db_records
        realtime_logger.info(f"Loaded {len(db_records)} historical recovery executions from database.")
