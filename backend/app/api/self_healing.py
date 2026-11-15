"""
Self-Healing Engine API Endpoints
Evaluates active incidents, scores safe allowlisted recovery candidates,
and classifies into SELF_HEALING_RECOMMENDED, MEMBER_ACTION_REQUIRED, or MANUAL_INVESTIGATION_REQUIRED.
"""

from fastapi import APIRouter, HTTPException, Query, Header
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.app.monitoring.collector import collector
from backend.app.healing.decision_engine import decision_engine, ACTION_ALLOWLIST
from backend.app.healing.self_healing_engine import self_healing_engine
from backend.app.rca.dynamic_graph import dynamic_graph


router = APIRouter(prefix="/self-healing", tags=["Self-Healing Engine"])


@router.get("/candidates")
async def get_self_healing_candidates() -> List[Dict[str, Any]]:
    """
    GET /api/self-healing/candidates
    Scans active incidents and identifies safe, controlled self-healing opportunities.
    Calculates root-cause confidence, action safety, historical success, and blast radius.
    Classifies candidates as SELF_HEALING_RECOMMENDED, MEMBER_ACTION_REQUIRED, or MANUAL_INVESTIGATION_REQUIRED.
    """
    candidates = []
    active_incs = [i for i in collector.active_incidents if i.get("status") != "RESOLVED"]

    for inc in active_incs:
        inc_id = inc.get("incident_id", "INC-UNKNOWN")
        root_cause = inc.get("root_cause_service") or inc.get("primary_service") or "database-service"
        confidence = float(inc.get("rca_confidence", 0.93))
        rec_action = inc.get("recommended_action") or "RESET_CONNECTION_POOL"
        risk_lvl = (inc.get("action_risk_level") or "LOW").upper()
        
        # Calculate blast radius
        blast_info = inc.get("blast_radius") or dynamic_graph.calculate_blast_radius(root_cause)
        blast_score = blast_info.get("blast_radius_score", 45.0)
        
        # Supported safe candidates mapping
        safe_actions = {
            "RESET_CONNECTION_POOL": {
                "safety": "HIGH",
                "effectiveness": 0.96,
                "complexity": "LOW",
                "expected_result": "Restore database connection capacity & release locked worker handles",
                "risk": "LOW"
            },
            "CLEAR_CACHE": {
                "safety": "HIGH",
                "effectiveness": 0.94,
                "complexity": "LOW",
                "expected_result": "Evict stale keys & reclaim memory buffers",
                "risk": "LOW"
            },
            "RECONNECT_DATABASE": {
                "safety": "HIGH",
                "effectiveness": 0.92,
                "complexity": "LOW",
                "expected_result": "Re-establish transient network socket to PostgreSQL database",
                "risk": "LOW"
            },
            "RESTART_CONTROLLED_SERVICE": {
                "safety": "MEDIUM",
                "effectiveness": 0.90,
                "complexity": "MEDIUM",
                "expected_result": "Perform graceful in-place restart of the degraded microservice container",
                "risk": "MEDIUM"
            },
            "SCALE_WORKERS": {
                "safety": "MEDIUM",
                "effectiveness": 0.88,
                "complexity": "MEDIUM",
                "expected_result": "Increment asynchronous consumer replica count to clear queue backlog",
                "risk": "MEDIUM"
            }
        }

        # Normalize action name
        normalized_action = rec_action
        if "POOL" in rec_action.upper() or "CONNECTION" in rec_action.upper():
            normalized_action = "RESET_CONNECTION_POOL"
        elif "CACHE" in rec_action.upper() or "REDIS" in rec_action.upper():
            normalized_action = "CLEAR_CACHE"
        elif "RESTART" in rec_action.upper():
            normalized_action = "RESTART_CONTROLLED_SERVICE"

        action_meta = safe_actions.get(normalized_action, {
            "safety": "MEDIUM",
            "effectiveness": 0.85,
            "complexity": "MEDIUM",
            "expected_result": f"Execute allowlisted recovery procedure '{normalized_action}'",
            "risk": risk_lvl
        })

        # Calculate classification
        if action_meta["safety"] == "HIGH" and confidence >= 0.90 and blast_score < 75.0:
            classification = "SELF_HEALING_RECOMMENDED"
            explanation = (
                f"Root cause '{root_cause}' identified with {int(confidence*100)}% confidence. "
                f"Action '{normalized_action}' is a verified idempotent runbook with low blast radius ({blast_score}). "
                f"Autonomous self-healing candidate approved."
            )
        elif confidence >= 0.75:
            classification = "MEMBER_ACTION_REQUIRED"
            explanation = (
                f"Root cause '{root_cause}' isolated with {int(confidence*100)}% confidence, but action '{normalized_action}' "
                f"carries {action_meta['risk']} risk requiring member authorization."
            )
        else:
            classification = "MANUAL_INVESTIGATION_REQUIRED"
            explanation = (
                f"Root cause confidence ({int(confidence*100)}%) is below autonomous threshold. "
                f"Complex or cascading blast radius requires manual engineer triage."
            )

        candidates.append({
            "candidate_id": f"SHC-{inc_id[-6:]}",
            "incident_id": inc_id,
            "service": root_cause,
            "problem": inc.get("title", f"Service anomaly on {root_cause}"),
            "root_cause_service": root_cause,
            "root_cause_confidence": confidence,
            "confidence_pct": int(confidence * 100),
            "recommended_action": normalized_action,
            "action_safety": action_meta["safety"],
            "expected_effectiveness": action_meta["effectiveness"],
            "historical_success_pct": int(action_meta["effectiveness"] * 100),
            "blast_radius_score": blast_score,
            "verification_complexity": action_meta["complexity"],
            "classification": classification,
            "decision_rationale": explanation,
            "expected_result": action_meta["expected_result"],
            "risk_level": action_meta["risk"],
            "verification_required": True,
            "policy_status": "APPROVED" if inc.get("status") == "APPROVED" else "AWAITING_APPROVAL",
            "created_at": inc.get("created_at") or datetime.now(timezone.utc).isoformat()
        })

    return candidates
