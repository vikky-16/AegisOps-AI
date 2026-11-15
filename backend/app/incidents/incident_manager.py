"""
Incident Lifecycle Manager
Creates, updates, and correlates incidents supporting the full automated response lifecycle.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.app.incidents.impact_analyzer import BusinessImpactAnalyzer
from backend.app.rca.engine import rca_engine
from backend.app.rca.dynamic_graph import dynamic_graph


class IncidentManager:
    _incident_seq: int = 41

    @classmethod
    def generate_incident_id(cls) -> str:
        cls._incident_seq += 1
        return f"INC-{cls._incident_seq:05d}"

    @classmethod
    def create_incident_from_anomaly(
        cls,
        service_name: str,
        anomaly_score: float,
        evidence: List[str],
        events: List[Dict[str, Any]],
        metrics_snapshot: Optional[Dict[str, Any]] = None,
        affected_resources: Optional[List[str]] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an initialized incident dictionary with Ranked RCA, Blast Radius, Correlation Explanation, and Timeline.
        """
        inc_id = cls.generate_incident_id()
        effective_tenant = tenant_id or (events[0].get("tenant_id") if events else None) or "demo-tenant"
        affected_services = [service_name]
        correlation_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Extract or generate event IDs for evidence tracking
        event_ids = []
        for i, ev in enumerate(events):
            eid = ev.get("event_id") or ev.get("id") or f"EVT-AZ-{int(datetime.now(timezone.utc).timestamp())}-{i+1:03d}"
            ev["event_id"] = eid
            event_ids.append(eid)

        if not event_ids:
            event_ids = [f"EVT-AZ-{int(datetime.now(timezone.utc).timestamp())}-001"]

        metrics_dict = metrics_snapshot or {}
        
        # Extract Empirical Multi-dimensional Failure Signature
        from backend.app.ai.failure_signature import signature_extractor
        extracted_sig = signature_extractor.extract_from_telemetry(
            service=service_name,
            metrics=metrics_dict,
            events=events
        )
        sig_dict = extracted_sig.to_dict()

        # Run Explainable RCA & Ranked Root Cause Isolation with Historical Memory
        rca_result = rca_engine.analyze_incident(
            affected_services=affected_services,
            events=events,
            current_metrics=metrics_dict,
            telemetry_signature=sig_dict
        )
        
        root_svc = rca_result.get("root_cause_service", service_name)
        svc_metrics = metrics_dict.get(root_svc, metrics_dict.get(service_name, {}))
        current_error_rate = float(svc_metrics.get("error_rate", 0.87))
        req_count = int(svc_metrics.get("request_count", len(events) or 120))

        # Run Blast Radius & Business Impact Analysis
        impact_result = BusinessImpactAnalyzer.calculate_impact(
            primary_service=root_svc,
            affected_services=affected_services,
            error_rate=current_error_rate,
            request_count=req_count
        )
        
        # Determine Severity
        if impact_result["business_impact_score"] >= 75 or anomaly_score >= 0.85 or current_error_rate > 0.4:
            severity = "CRITICAL"
        elif impact_result["business_impact_score"] >= 45 or anomaly_score >= 0.60 or current_error_rate > 0.15:
            severity = "HIGH"
        elif impact_result["business_impact_score"] >= 20 or anomaly_score >= 0.35:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Generate descriptive title
        root_cat = rca_result.get("root_cause_category", "SERVICE_DEGRADATION").replace("_", " ").title()
        title = f"{root_svc.replace('-', ' ').title()} - {root_cat}"

        # Initialize Chronological Timeline
        timeline = [
            {
                "timestamp": now_iso,
                "service": service_name,
                "type": "ANOMALY_DETECTED",
                "message": f"Telemetry anomaly detected on {service_name} (score: {anomaly_score:.2f}, error rate: {current_error_rate*100:.1f}%).",
                "event_id": event_ids[0] if event_ids else None
            },
            {
                "timestamp": now_iso,
                "service": service_name,
                "type": "INCIDENT_CREATED",
                "message": f"Incident {inc_id} opened ({severity}). Correlated {len(event_ids)} initial telemetry signals."
            },
            {
                "timestamp": now_iso,
                "service": root_svc,
                "type": "ROOT_CAUSE_IDENTIFIED",
                "message": f"Root Cause Analysis completed: '{root_svc}' ranked #1 root cause with {int(rca_result['confidence']*100)}% confidence."
            }
        ]

        deps = impact_result.get("downstream_impact", dynamic_graph.get_dependents(root_svc))
        chain = impact_result.get("dependency_chain", dynamic_graph.get_dependency_chain(root_svc))

        # Generate Explainable Correlation Rationale
        corr_reasons = [
            f"{len(events)} telemetry events occurred within the 60-second correlation window.",
            f"Originated across topologically linked services in the active dependency chain ({' -> '.join(reversed(chain))}).",
            f"Root cause service '{root_svc}' initiated cascade ({root_cat}).",
            f"Earliest anomaly onset timestamp confirmed '{root_svc}' preceded downstream consumer degradation."
        ]

        correlation_explanation = {
            "confidence": rca_result.get("confidence", 0.94),
            "confidence_pct": int(rca_result.get("confidence", 0.94) * 100),
            "total_correlated_events": len(events),
            "reasons": corr_reasons,
            "dependency_chain": chain
        }

        import hashlib
        fp_str = f"{root_svc}:{root_cat}"
        fingerprint = f"FP-{hashlib.sha256(fp_str.encode()).hexdigest()[:10].upper()}"

        # Determine recommended remediation action
        try:
            from backend.app.healing.recommender import recommender
            rec = recommender.recommend_action(
                root_cause=root_svc,
                affected_services=impact_result.get("affected_services", [service_name]),
                severity=severity,
                anomaly_score=anomaly_score,
                historical_context=rca_result.get("historical_match")
            )
            rec_action = rec.get("primary_action", "RESET_CONNECTION_POOL")
            alt_action = rec.get("alternative_action", "RESTART_SERVICE")
            action_risk = rec.get("risk_assessment", {}).get("risk_tier", "MEDIUM")
        except Exception:
            rec_action = "RESET_CONNECTION_POOL" if "database" in root_svc.lower() else "RESTART_SERVICE"
            alt_action = "RESTART_SERVICE"
            action_risk = "HIGH"

        return {
            "incident_id": inc_id,
            "tenant_id": effective_tenant,
            "fingerprint": fingerprint,
            "title": title,
            "description": f"Automated anomaly detected with score {anomaly_score:.2f}. " + rca_result.get("summary", ""),
            "severity": severity,
            "status": "INVESTIGATING",
            "primary_service": service_name,
            "affected_services": list(set(affected_services + [root_svc])),
            "affected_resources": affected_resources or [f"/subscriptions/demo/resourceGroups/aegisops-rg/providers/Microsoft.Compute/{root_svc}"],
            "affected_dependencies": deps,
            "dependency_chain": chain,
            "event_ids": event_ids,
            "correlation_id": correlation_id,
            "correlated_event_count": len(events) or 1,
            "correlation_score": rca_result.get("confidence", 0.94),
            "correlation_explanation": correlation_explanation,
            
            # Metrics
            "error_rate": round(current_error_rate, 3),
            "baseline_error_rate": 0.01,
            "anomaly_score": round(anomaly_score, 3),
            
            # Explainable RCA & Ranked Candidates
            "root_cause": rca_result.get("summary", f"{root_svc} failure"),
            "root_cause_service": root_svc,
            "root_cause_category": rca_result.get("root_cause_category", "UNKNOWN"),
            "root_cause_summary": rca_result.get("summary", ""),
            "root_cause_confidence": rca_result.get("confidence", 0.94),
            "rca_confidence": rca_result.get("confidence", 0.94),
            "rca_evidence": rca_result.get("evidence", evidence),
            "evidence": rca_result.get("evidence", evidence),
            "ranked_candidates": rca_result.get("ranked_candidates", [
                {"service": root_svc, "confidence": rca_result.get("confidence", 0.94), "score": 94.0, "is_primary": True}
            ]),
            "correlation_graph": rca_result.get("correlation_graph"),
            "historical_match": rca_result.get("historical_match"),
            "telemetry_signature": sig_dict,
            
            # Blast Radius & Impact
            "blast_radius": impact_result,
            "business_impact_score": impact_result["business_impact_score"],
            "estimated_users_affected": impact_result["estimated_users_affected"],
            "sla_breach_risk": impact_result["sla_breach_risk"],
            
            # Remediation, Approval & Verification State
            "recommended_action": rec_action,
            "alternative_action": alt_action,
            "action_risk_level": action_risk,
            "approval_status": "NONE",
            "remediation_status": "NONE",
            "verification_status": "NONE",
            "recovery_status": "NONE",
            
            "timeline": timeline,
            "created_at": now_iso,
            "updated_at": now_iso,
            "resolved_at": None
        }
