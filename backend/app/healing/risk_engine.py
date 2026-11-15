"""
Risk Classification Engine
Evaluates service criticality, data impact, reversibility, and downtime to assign risk rating.
"""

from typing import Dict, Any, Tuple
from backend.app.healing.actions import AVAILABLE_ACTIONS


class RiskEngine:
    @staticmethod
    def assess_risk(
        action_key: str,
        target_service: str,
        service_criticality: str = "HIGH",
        confidence: float = 0.90
    ) -> Dict[str, Any]:
        """
        Computes composite risk score (0-100) and classifies as LOW, MEDIUM, HIGH, or CRITICAL.
        Determines whether autonomous self-healing is permitted or human approval is mandatory.
        """
        action_meta = AVAILABLE_ACTIONS.get(action_key, {
            "base_risk": "HIGH",
            "estimated_duration_sec": 5.0,
            "reversible": False
        })
        
        # 1. Base action risk points (LOW=20, MEDIUM=45, HIGH=75)
        base_points = {"LOW": 20.0, "MEDIUM": 45.0, "HIGH": 75.0}.get(action_meta["base_risk"], 60.0)
        
        # 2. Target Service Criticality Multiplier
        crit_multiplier = {
            "CRITICAL": 1.3,
            "HIGH": 1.1,
            "MEDIUM": 0.9,
            "LOW": 0.7
        }.get(service_criticality.upper(), 1.0)
        
        # 3. Confidence Factor (Lower confidence increases risk)
        confidence_penalty = max(0.0, (0.85 - confidence) * 50.0)
        
        raw_risk_score = (base_points * crit_multiplier) + confidence_penalty
        risk_score = round(min(100.0, max(10.0, raw_risk_score)), 1)
        
        # Classification
        if risk_score >= 80.0 or action_key == "ROLLBACK_CONFIG":
            risk_level = "CRITICAL"
            approval_required = True
            decision_rationale = "Critical risk action with potential service disruption. Administrator approval mandatory."
        elif risk_score >= 55.0 or (action_meta["base_risk"] in ["MEDIUM", "HIGH"] and service_criticality in ["CRITICAL", "HIGH"]):
            risk_level = "HIGH"
            approval_required = True
            decision_rationale = "High-impact remediation action on tier-1 service. Human approval required."
        elif risk_score >= 35.0:
            risk_level = "MEDIUM"
            approval_required = True
            decision_rationale = "Moderate risk remediation. Human review recommended."
        else:
            risk_level = "LOW"
            approval_required = False
            decision_rationale = "Safe, reversible, non-destructive low-risk action. Eligible for autonomous execution."

        return {
            "action": action_key,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "approval_required": approval_required,
            "decision_rationale": decision_rationale,
            "reversible": action_meta.get("reversible", True),
            "estimated_downtime_sec": int(action_meta.get("estimated_duration_sec", 3))
        }
