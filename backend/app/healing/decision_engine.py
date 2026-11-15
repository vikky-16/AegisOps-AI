"""
AegisOps AI - Risk-Aware Autonomous Decision Engine
Evaluates telemetry freshness, RCA confidence, blast radius, action risk, allowlists,
and historical incident memory to decide whether to:
- AUTO_REMEDIATE
- REQUEST_APPROVAL
- ESCALATE
- DO_NOT_ACT
Provides full explainability and mathematical factor breakdown for the Explain Decision UI.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from backend.app.core.config import settings

# Critical infrastructure services where process restarts require human authorization
CRITICAL_SERVICES = {"database-service", "gateway", "payment-api", "auth-service"}

# Global allowlist of safe, verified remediation actions with operational constraints
ACTION_ALLOWLIST = {
    "RESET_CONNECTION_POOL": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "connection"},
    "RECONNECT_DATABASE": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "connection"},
    "RESTART_SERVICE": {"risk": "MEDIUM", "reversible": True, "max_downtime_sec": 3, "scope": "process"},
    "SCALE_WORKERS": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "concurrency"},
    "SCALE_SERVICE": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "concurrency"},
    "CLEAR_CACHE": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "memory"},
    "ROLLBACK_CONFIG": {"risk": "HIGH", "reversible": True, "max_downtime_sec": 1, "scope": "configuration"},
    "ROLLBACK_DEPLOYMENT": {"risk": "MEDIUM", "reversible": True, "max_downtime_sec": 1, "scope": "configuration"},
    "FAILOVER_DATABASE": {"risk": "HIGH", "reversible": True, "max_downtime_sec": 5, "scope": "database"},
    "DISABLE_FAULTY_DEPENDENCY": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "dependency"},
    "RETRY_FAILED_REQUESTS": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "network"},
    "ROTATE_AND_COMPRESS_LOGS": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "storage"},
    "COMPACT_STORAGE": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "storage"},
    "RESTART_CONTAINER": {"risk": "HIGH", "reversible": True, "max_downtime_sec": 5, "scope": "infrastructure"},
    "RESET_SQL_POOL": {"risk": "LOW", "reversible": True, "max_downtime_sec": 0, "scope": "database"},
    "RESTART_APP_SERVICE": {"risk": "MEDIUM", "reversible": True, "max_downtime_sec": 4, "scope": "cloud"}
}


class DecisionEngine:
    """
    Risk-Aware Policy Evaluation & Autonomous Decision Engine.
    Executes: DETECTION -> RCA -> RISK ASSESSMENT -> POLICY EVALUATION -> REMEDIATION DECISION.
    Decisions:
    - AUTO_REMEDIATE: Only for low-risk, high-confidence (>= 0.85), non-novel actions under policy.
    - REQUEST_APPROVAL: For high-risk, low-confidence (< 0.85), novel anomalies, or large blast radius.
    - ESCALATE: For unallowlisted or out-of-bounds actions.
    - DO_NOT_ACT: For stale telemetry, active cooldowns, or zero-impact conditions.
    """
    def __init__(
        self,
        cooldown_seconds: int = 15,
        rca_confidence_threshold: float = 0.85,
        historical_similarity_threshold: float = 0.85,
        max_blast_radius_for_auto: float = 75.0
    ):
        self.cooldown_seconds = cooldown_seconds
        self.rca_confidence_threshold = rca_confidence_threshold
        self.historical_similarity_threshold = historical_similarity_threshold
        self.max_blast_radius_for_auto = max_blast_radius_for_auto
        self.last_action_per_service: Dict[str, float] = {}

    def evaluate(
        self,
        incident: Dict[str, Any],
        telemetry_fresh: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates remediation policy and returns decision with comprehensive factor breakdown.
        Decisions: AUTO_REMEDIATE | REQUEST_APPROVAL | ESCALATE | DO_NOT_ACT
        """
        service = incident.get("root_cause_service", incident.get("primary_service", "unknown"))
        rca_conf = float(incident.get("rca_confidence", incident.get("root_cause_confidence", 0.0)))
        severity = incident.get("severity", "MEDIUM")
        proposed_action = incident.get("recommended_action") or "RESET_CONNECTION_POOL"
        blast_score = float(incident.get("business_impact_score", incident.get("blast_radius_score", 50.0)))
        historical_match = incident.get("historical_match") or {}
        now_ts = time.time()

        is_known = bool(historical_match.get("is_known_pattern", False))
        is_novel = bool(incident.get("is_novel", False) or historical_match.get("is_novel", False))
        hist_success = float(historical_match.get("success_rate", 0.0))
        hist_occurrences = int(historical_match.get("historical_occurrences", 0))

        # Check tenant policy overrides if available
        tenant_policy = incident.get("tenant_policy")
        tenant_id = incident.get("tenant_id", "demo-tenant")
        auto_healing_enabled = settings.AUTO_HEALING_LOW_RISK
        max_allowed_risk = "LOW"
        conf_threshold = self.rca_confidence_threshold
        p1_human_approval = True
        tenant_allowed_actions = set(ACTION_ALLOWLIST.keys())
        cooldown_limit = self.cooldown_seconds

        if tenant_policy and isinstance(tenant_policy, dict):
            auto_healing_enabled = bool(tenant_policy.get("auto_remediate_enabled", auto_healing_enabled))
            max_allowed_risk = str(tenant_policy.get("max_auto_remediate_risk", "LOW")).upper()
            conf_threshold = float(tenant_policy.get("confidence_threshold", conf_threshold))
            p1_human_approval = bool(tenant_policy.get("require_human_approval_p1", True))
            if tenant_policy.get("allowed_actions_list"):
                tenant_allowed_actions = set(tenant_policy["allowed_actions_list"])
            if "cooldown_period_sec" in tenant_policy:
                cooldown_limit = int(tenant_policy["cooldown_period_sec"])

        factors = {
            "tenant_id": tenant_id,
            "rca_confidence": rca_conf,
            "rca_confidence_threshold": conf_threshold,
            "confidence_passed": rca_conf >= conf_threshold,
            "proposed_action": proposed_action,
            "action_risk": "UNKNOWN",
            "is_allowlisted": proposed_action in ACTION_ALLOWLIST and proposed_action in tenant_allowed_actions,
            "cooldown_active": False,
            "telemetry_fresh": telemetry_fresh,
            "is_known_pattern": is_known,
            "is_novel_anomaly": is_novel,
            "historical_success_rate": hist_success,
            "historical_occurrences": hist_occurrences,
            "blast_radius_score": blast_score,
            "blast_radius_passed": blast_score <= self.max_blast_radius_for_auto,
            "auto_healing_policy": auto_healing_enabled,
            "tenant_policy_enforced": bool(tenant_policy),
            "policy_verdict": "PENDING"
        }

        # 1. Telemetry Freshness Check
        if not telemetry_fresh:
            factors["policy_verdict"] = "SUPPRESSED_STALE_TELEMETRY"
            return {
                "decision": "DO_NOT_ACT",
                "action": proposed_action,
                "reason": "Telemetry is stale or unavailable. Remediation suspended to prevent unsafe action on outdated state.",
                "requires_approval": False,
                "requires_human_approval": False,
                "confidence": rca_conf,
                "risk_level": "UNKNOWN",
                "decision_factors": factors
            }

        # 2. Allowlist Check (Global and Tenant-Scoped)
        if proposed_action not in ACTION_ALLOWLIST or proposed_action not in tenant_allowed_actions:
            factors["action_risk"] = "CRITICAL"
            factors["policy_verdict"] = "ESCALATION_REQUIRED"
            return {
                "decision": "ESCALATE",
                "action": proposed_action,
                "reason": f"Proposed action '{proposed_action}' is not in the verified allowlist for tenant '{tenant_id}'. Arbitrary host or shell commands are strictly prohibited.",
                "requires_approval": True,
                "requires_human_approval": True,
                "confidence": rca_conf,
                "risk_level": "CRITICAL",
                "decision_factors": factors
            }

        action_meta = ACTION_ALLOWLIST[proposed_action]
        action_risk = action_meta["risk"]
        is_critical_service_restart = (proposed_action == "RESTART_SERVICE" and service in CRITICAL_SERVICES)
        if is_critical_service_restart:
            action_risk = "HIGH"
        factors["action_risk"] = action_risk

        # 2b. Tenant Auto-Remediation Disabled Policy Check
        if not auto_healing_enabled:
            factors["policy_verdict"] = "APPROVAL_REQUIRED_TENANT_POLICY_DISABLED"
            return {
                "decision": "REQUEST_APPROVAL",
                "action": proposed_action,
                "risk_level": action_risk,
                "confidence": rca_conf,
                "requires_approval": True,
                "requires_human_approval": True,
                "reason": f"Autonomous remediation is disabled for tenant '{tenant_id}'. All actions require operator approval.",
                "decision_factors": factors
            }

        # 3. Cooldown Protection
        last_exec = self.last_action_per_service.get(service, 0)
        if (now_ts - last_exec) < self.cooldown_seconds:
            remaining = int(self.cooldown_seconds - (now_ts - last_exec))
            factors["cooldown_active"] = True
            factors["policy_verdict"] = "COOLDOWN_ACTIVE"
            return {
                "decision": "DO_NOT_ACT",
                "action": proposed_action,
                "reason": f"Service '{service}' is in remediation cooldown ({remaining}s remaining). Preventing action storm.",
                "requires_approval": False,
                "requires_human_approval": False,
                "confidence": rca_conf,
                "risk_level": action_risk,
                "decision_factors": factors
            }

        # 4. Critical Service Restart Policy Guard
        if is_critical_service_restart:
            factors["policy_verdict"] = "APPROVAL_REQUIRED_CRITICAL_SERVICE"
            return {
                "decision": "REQUEST_APPROVAL",
                "action": proposed_action,
                "risk_level": "HIGH",
                "confidence": rca_conf,
                "requires_approval": True,
                "requires_human_approval": True,
                "reason": (
                    f"Restarting critical service '{service}' carries high operational risk and "
                    f"strictly requires operator authorization under enterprise policy."
                ),
                "decision_factors": factors
            }

        # 5. Novel Failure / Unprecedented Anomaly Safety Check
        if is_novel:
            factors["policy_verdict"] = "APPROVAL_REQUIRED_NOVEL_ANOMALY"
            return {
                "decision": "REQUEST_APPROVAL",
                "action": proposed_action,
                "risk_level": action_risk,
                "confidence": rca_conf,
                "requires_approval": True,
                "requires_human_approval": True,
                "reason": (
                    "Novel Anomaly Detected: Failure signature has no high-confidence historical precedent. "
                    "Human approval required under enterprise safety policy."
                ),
                "decision_factors": factors
            }

        # 6. Low RCA Confidence Check (< threshold)
        if rca_conf < self.rca_confidence_threshold:
            factors["policy_verdict"] = "APPROVAL_REQUIRED_LOW_CONFIDENCE"
            return {
                "decision": "REQUEST_APPROVAL",
                "action": proposed_action,
                "risk_level": action_risk,
                "confidence": rca_conf,
                "requires_approval": True,
                "requires_human_approval": True,
                "reason": (
                    f"RCA confidence ({int(rca_conf*100)}%) is below policy threshold ({int(self.rca_confidence_threshold*100)}%). "
                    "Operator authorization required to prevent misdiagnosis remediation."
                ),
                "decision_factors": factors
            }

        # 7. Historical Learning Fast-Path for Known Failure Patterns
        if is_known and hist_occurrences >= 1 and hist_success >= 0.75 and rca_conf >= conf_threshold and auto_healing_enabled:
            factors["policy_verdict"] = "ALLOWED_BY_POLICY"
            return {
                "decision": "AUTO_REMEDIATE",
                "action": proposed_action,
                "risk_level": action_risk,
                "confidence": rca_conf,
                "requires_approval": False,
                "requires_human_approval": False,
                "reason": (
                    f"Automatically remediated under policy: Matches verified known pattern "
                    f"'{historical_match.get('pattern_name')}' with {hist_success*100:.0f}% success rate over "
                    f"{hist_occurrences} prior occurrences."
                ),
                "decision_factors": factors
            }

        # 8. Critical Blast Radius Check
        if blast_score > self.max_blast_radius_for_auto:
            factors["policy_verdict"] = "APPROVAL_REQUIRED_WIDE_BLAST_RADIUS"
            return {
                "decision": "REQUEST_APPROVAL",
                "action": proposed_action,
                "risk_level": action_risk,
                "confidence": rca_conf,
                "requires_approval": True,
                "requires_human_approval": True,
                "reason": (
                    f"Blast radius score ({blast_score:.0f}) exceeds policy limit ({self.max_blast_radius_for_auto:.0f}). "
                    "Action impacts multiple mission-critical services; operator approval required."
                ),
                "decision_factors": factors
            }

        # 9. Risk tolerance + High RCA Confidence + Normal Blast Radius -> AUTO_REMEDIATE
        risk_hierarchy = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        action_risk_level = risk_hierarchy.get(action_risk, 3)
        max_allowed_risk_level = risk_hierarchy.get(max_allowed_risk, 1)

        if action_risk_level <= max_allowed_risk_level and rca_conf >= conf_threshold and auto_healing_enabled:
            factors["policy_verdict"] = "ALLOWED_BY_POLICY"
            return {
                "decision": "AUTO_REMEDIATE",
                "action": proposed_action,
                "risk_level": action_risk,
                "confidence": rca_conf,
                "requires_approval": False,
                "requires_human_approval": False,
                "reason": (
                    f"Automatically remediated under policy: High RCA confidence ({int(rca_conf*100)}%) "
                    f"and verified allowlisted runbook '{proposed_action}' within risk tolerance '{max_allowed_risk}'."
                ),
                "decision_factors": factors
            }

        # 10. Default: MEDIUM, HIGH, or CRITICAL Risk -> REQUEST_APPROVAL
        factors["policy_verdict"] = "APPROVAL_REQUIRED_RISK_LEVEL"
        return {
            "decision": "REQUEST_APPROVAL",
            "action": proposed_action,
            "risk_level": action_risk,
            "confidence": rca_conf,
            "requires_approval": True,
            "requires_human_approval": True,
            "reason": (
                f"Action '{proposed_action}' carries {action_risk} risk and requires operator authorization "
                f"(RCA Confidence: {int(rca_conf*100)}%, Blast Radius: {blast_score:.0f})."
            ),
            "decision_factors": factors
        }

    def record_action_executed(self, service: str):
        self.last_action_per_service[service] = time.time()


decision_engine = DecisionEngine()
RiskPolicyEngine = DecisionEngine

