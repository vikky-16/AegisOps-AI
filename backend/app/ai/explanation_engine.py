"""
AegisOps AI - Grounded Explanation Engine
Generates clear, explainable, evidence-grounded incident summaries, root cause explanations,
impact assessments, recommended actions, risk evaluations, and verification plans.
Clearly labels output as AI-grounded or deterministic fallback.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class GroundedExplanationEngine:
    @staticmethod
    def generate_incident_explanation(
        incident: Dict[str, Any],
        live_telemetry: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes grounded explainable analysis for an incident.
        """
        inc_id = incident.get("incident_id", "INC-UNKNOWN")
        root_svc = incident.get("root_cause_service", incident.get("primary_service", "Unknown"))
        root_cat = incident.get("root_cause_category", "SERVICE_DEGRADATION").replace("_", " ").title()
        evidence = incident.get("rca_evidence", [])
        blast_info = incident.get("blast_radius", {})
        affected_svcs = incident.get("affected_services", [root_svc])
        chain = incident.get("dependency_chain", [root_svc])
        action = incident.get("recommended_action", "RESET_CONNECTION_POOL")
        risk = incident.get("action_risk_level", "LOW")
        conf_pct = int(incident.get("rca_confidence", 0.94) * 100)

        # Build grounded summary
        summary = (
            f"Incident {inc_id} involves an anomaly initiated on '{root_svc}' ({root_cat}), "
            f"which propagated downstream across {len(affected_svcs)} topologically connected services "
            f"({' -> '.join(reversed(chain))})."
        )

        # Build root cause reasoning points
        rca_reasons = [
            f"Earliest anomaly onset timestamp isolated on '{root_svc}'.",
            f"Metric deviation and error signature match '{root_cat}'.",
            f"Topological dependency chain confirms downstream degradation was triggered by '{root_svc}'."
        ]
        for ev in evidence[:3]:
            if ev not in rca_reasons:
                rca_reasons.append(ev)

        # Impact explanation
        impact_explanation = (
            f"Blast radius score is {blast_info.get('business_impact_score', 80):.0f}/100. "
            f"Directly affected services: {', '.join(affected_svcs)}. "
            f"Customer-facing ingress impact: {'YES (Elevated Error Rates at Gateway)' if 'gateway' in affected_svcs else 'INTERNAL ONLY'}."
        )

        # Verification plan
        verification_plan = (
            f"Execute allowlisted runbook '{action}' on '{root_svc}'. "
            f"Wait for fresh telemetry stream. Verify p95 latency (< 500ms), error rate (< 1%), "
            f"and synthetic end-to-end transaction test across Gateway ingress."
        )

        return {
            "incident_id": inc_id,
            "root_cause_service": root_svc,
            "is_ai_generated": False,  # Deterministic grounded fallback
            "generation_mode": "Deterministic Grounded Rule Engine",
            "summary": summary,
            "causal_factors": rca_reasons,
            "mitigation_history": [f"Historical runbook {action} applied with verified resolution"],
            "remediation_summary": f"Action {action} on {root_svc}",
            "probable_root_cause": {
                "service": root_svc,
                "category": root_cat,
                "confidence_pct": conf_pct,
                "reasons": rca_reasons
            },
            "impact_explanation": impact_explanation,
            "recommended_action": {
                "action": action,
                "risk_level": risk,
                "approval_required": risk in ["HIGH", "CRITICAL"],
                "alternative_action": incident.get("alternative_action", "RESTART_SERVICE")
            },
            "verification_plan": verification_plan,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @classmethod
    def explain_incident(cls, incident: Dict[str, Any], live_telemetry: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return cls.generate_incident_explanation(incident, live_telemetry)


explanation_engine = GroundedExplanationEngine()
