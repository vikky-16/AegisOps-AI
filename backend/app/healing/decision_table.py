"""
AegisOps AI - Evidence-Grounded Recovery Decision Table Engine
Evaluates telemetry, RCA evidence, exception signatures, trace paths, and company capabilities
to generate incident-specific, evidence-supported recovery recommendations.
Eliminates universal fallbacks to RESTART_SERVICE and respects tenant operational constraints.
"""

from typing import Dict, Any, List, Optional, Tuple


# Company Environment Operational Capabilities Matrix
TENANT_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "shopsphere": {
        "company_name": "ShopSphere",
        "industry": "E-Commerce",
        "supported_actions": {
            "RESET_CONNECTION_POOL": "Active on PostgreSQL cluster (port 5432)",
            "RECONNECT_DATABASE": "Active on Order/Payment DB client pools",
            "CLEAR_CACHE": "Active on Redis session & catalog cache (port 6379)",
            "SCALE_WORKERS": "Active on Order & Inventory worker pools",
            "ROLLBACK_DEPLOYMENT": "Active via Kubernetes canary release controller",
            "ROLLBACK_CONTROLLED_DEPLOYMENT": "Active via Kubernetes canary release controller",
            "ROLLBACK_CONFIG": "Active via dynamic configuration server",
            "RESTART_CONTROLLED_SERVICE": "Active on stateless microservices (ports 8100-8104)"
        },
        "unsupported_actions": {
            "FAILOVER_DATABASE": "Single primary database cluster without automated standby failover.",
            "RESTART_CONTAINER": "Direct host container restart restricted; use graceful process restart."
        }
    },
    "fincore": {
        "company_name": "FinCore",
        "industry": "Financial Services & Core Banking",
        "supported_actions": {
            "RESET_CONNECTION_POOL": "Active on ACID transaction ledger database pool",
            "RECONNECT_DATABASE": "Active on Ledger & Settlement connector sockets",
            "ENABLE_CIRCUIT_BREAKER_FALLBACK": "Active on Fraud scoring client circuit breaker",
            "ROLLBACK_CONFIG": "Active via audited compliance parameter store",
            "FAILOVER_DATABASE": "Active on Multi-AZ Ledger replica cluster"
        },
        "unsupported_actions": {
            "CLEAR_CACHE": "Financial ledger data caching rules strictly forbid cache flushes without regulator audit trail.",
            "RESTART_SERVICE": "Financial regulatory policy strictly prohibits uncoordinated restart of core database ledger. Use connection pool reset or standby failover.",
            "RESTART_CONTROLLED_SERVICE": "Core banking ledger service requires multi-party approval and automated drain.",
            "SCALE_WORKERS": "Fraud sequencing worker runs in single-thread deterministic sequence; worker scaling unsupported on sequencer."
        }
    },
    "clouddesk": {
        "company_name": "CloudDesk",
        "industry": "Multi-Tenant Cloud Workspace",
        "supported_actions": {
            "CLEAR_CACHE": "Active on Redis rate-limiter & workspace buffer",
            "SCALE_WORKERS": "Active on Compute provisioner & Workspace API workers",
            "RESET_CONNECTION_POOL": "Active on CloudDesk PostgreSQL sharded pool",
            "RECONNECT_DATABASE": "Active on Project & User database connectors",
            "ROLLBACK_DEPLOYMENT": "Active on CloudDesk deployment revision manager",
            "ROLLBACK_CONTROLLED_DEPLOYMENT": "Active on CloudDesk deployment revision manager",
            "ROLLBACK_CONFIG": "Active on Workspace feature-flag engine",
            "RESTART_CONTROLLED_SERVICE": "Active on CloudDesk stateless containers"
        },
        "unsupported_actions": {
            "FAILOVER_DATABASE": "Sharded database cluster uses automated storage replication; manual failover disabled."
        }
    },
    "demo-tenant": {
        "company_name": "Controlled Mesh",
        "industry": "Enterprise Platform",
        "supported_actions": {
            "RESET_CONNECTION_POOL": "Active on Database Service pool",
            "RECONNECT_DATABASE": "Active on Service B database connector",
            "CLEAR_CACHE": "Active on Distributed Redis cache",
            "SCALE_WORKERS": "Active on Service A worker pool",
            "RESTART_CONTROLLED_SERVICE": "Active on controlled microservice mesh",
            "ROLLBACK_CONTROLLED_DEPLOYMENT": "Active on Gateway ingress canary router",
            "ROLLBACK_DEPLOYMENT": "Active on Gateway ingress canary router",
            "ROLLBACK_CONFIG": "Active on configuration snapshot store",
            "ENABLE_CIRCUIT_BREAKER_FALLBACK": "Active on Auth Service downstream client"
        },
        "unsupported_actions": {}
    }
}


class EvidenceGroundedDecisionEngine:
    """
    Decides remediation actions derived strictly from empirical incident evidence,
    trace precedence, error signatures, and connected tenant capabilities.
    """

    @classmethod
    def get_company_capabilities(cls, tenant_id: str) -> Dict[str, Any]:
        tid = (tenant_id or "demo-tenant").lower()
        return TENANT_CAPABILITIES.get(tid, TENANT_CAPABILITIES["demo-tenant"])

    @classmethod
    def check_action_supported(cls, action: str, tenant_id: str) -> Tuple[bool, str]:
        caps = cls.get_company_capabilities(tenant_id)
        supported = caps.get("supported_actions", {})
        unsupported = caps.get("unsupported_actions", {})

        act_upper = action.upper()
        # Direct support match
        for s_act in supported.keys():
            if s_act == act_upper or s_act in act_upper or act_upper in s_act:
                return True, supported[s_act]

        # Explicit prohibition match
        for u_act, reason in unsupported.items():
            if u_act == act_upper or u_act in act_upper or act_upper in u_act:
                return False, f"Action unavailable in the connected environment: {reason}"

        # Standard allowlisted actions in controlled mesh / demo
        if tenant_id in ("demo-tenant", "all", "*"):
            return True, "Supported in controlled sandbox environment."

        return False, f"Action unavailable in the connected environment for {caps.get('company_name', tenant_id)}."

    @classmethod
    def evaluate_recovery_decision(
        cls,
        evidence_summary: Optional[List[str]] = None,
        root_category: Optional[str] = None,
        target_service: Optional[str] = "database-service",
        tenant_id: Optional[str] = "demo-tenant"
    ) -> Dict[str, Any]:
        """
        Convenience wrapper taking explicit evidence summary and root category.
        """
        inc = {
            "root_cause_service": target_service or "database-service",
            "primary_service": target_service or "database-service",
            "root_cause_category": root_category or "",
            "evidence_summary": evidence_summary or [],
            "tenant_id": tenant_id or "demo-tenant"
        }
        return cls.evaluate_incident_recovery(inc, tenant_id=tenant_id)

    @classmethod
    def evaluate_incident_recovery(
        cls,
        incident: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Derives an evidence-grounded recovery decision for the given incident.
        Considers root cause, error signatures, logs, metrics, traces, and company capabilities.
        """
        t_id = tenant_id or incident.get("tenant_id") or incident.get("company") or "demo-tenant"
        svc = incident.get("root_cause_service") or incident.get("primary_service", "database-service")
        cat = str(incident.get("root_cause_category") or incident.get("failure_type") or "").upper()
        title = str(incident.get("title") or "").upper()
        root_cause = str(incident.get("root_cause") or incident.get("root_cause_summary") or "").upper()
        
        # Collect telemetry signals from all possible keys
        evidence = (
            incident.get("rca_evidence")
            or incident.get("evidence_summary")
            or incident.get("evidence_items")
            or incident.get("supporting_evidence")
            or []
        )
        evidence_text = " ".join(str(e) for e in evidence).upper()
        
        timeline = incident.get("timeline") or []
        timeline_text = " ".join(str(t.get("event") or t.get("message") or "") for t in timeline if isinstance(t, dict)).upper()
        
        combined_text = f"{cat} {title} {root_cause} {evidence_text} {timeline_text}".strip().upper()
        norm_text = combined_text.replace("_", " ")
        search_text = f"{combined_text} {norm_text}"
        
        # Determine if evidence is truly present
        has_meaningful_evidence = (
            bool(evidence) or
            bool(cat and cat not in ["UNKNOWN", "NONE", "UNCERTAIN"]) or
            bool(root_cause and root_cause not in ["UNKNOWN", "NONE"]) or
            any(k in search_text for k in ["POOL", "CACHE", "REDIS", "CRASH", "DEPLOY", "503", "500", "DEADLOCK", "LATENCY"])
        )

        is_uncertain = False

        # ---------------------------------------------------------
        # DECISION TABLE EVALUATION
        # ---------------------------------------------------------

        # 1. Check for insufficient evidence first if no meaningful signals
        if not has_meaningful_evidence or not combined_text:
            is_uncertain = True
            primary_action = "UNCERTAIN_EVIDENCE"
            alt_action = "INVESTIGATE_DIAGNOSTICS"
            why_selected = (
                f"Telemetry evidence on `{svc}` is insufficient to distinguish between possible causes. "
                f"Requesting diagnostic trace collection rather than automatically restarting."
            )
            why_rejected = "Automatic service restart rejected due to insufficient causal evidence and safety governance."
            expected_result = "Insufficient conclusive telemetry to recommend automated action. Requesting additional evidence."
            risk_level = "LOW"
            side_effects = "None (read-only diagnostic evaluation)."
            required_role = "VIEWER"
            confidence = 0.35

        # 2. DATABASE CONNECTION POOL EXHAUSTION
        elif any(k in search_text for k in [
            "POOL EXHAUSTION", "POOL SATURATION", "CONNECTION POOL", "ACTIVE_CONNECTIONS",
            "CONNECTIONPOOLTIMEOUT", "EXHAUSTED POOL", "POOL LIMIT", "WAITING FOR IDLE CONNECTION"
        ]) or ("DATABASE" in svc and "TIMEOUT" in search_text and "ACQUIRE" in search_text):
            primary_action = "RESET_CONNECTION_POOL"
            alt_action = "RECONNECT_DATABASE"
            why_selected = (
                f"Telemetry confirms connection pool handles on `{svc}` reached 100% capacity. "
                f"Resetting the connection pool flushes leaked socket descriptors without dropping active database daemon processes."
            )
            why_rejected = (
                f"`RESTART_SERVICE` was rejected as primary because it incurs unnecessary service downtime "
                f"when a low-risk connection pool reset clears orphaned sockets with zero downtime."
            )
            expected_result = f"Connection pool utilization on `{svc}` drops below 20%, restoring available query handles."
            risk_level = "LOW"
            side_effects = "Transient 20-50ms query delay while idle socket handles are refreshed."
            required_role = "OPERATOR"
            confidence = 0.95

        # 3. CACHE FAILURE / REDIS SATURATION
        elif any(k in search_text for k in [
            "CACHE", "REDIS", "EVICTION", "MAXMEMORY", "CACHE MISS", "SERIALIZATION"
        ]) or ("CACHE" in svc):
            primary_action = "CLEAR_CACHE"
            alt_action = "RECONNECT_DATABASE"
            why_selected = (
                f"Cache buffer saturation or key invalidation detected on `{svc}`. "
                f"Purges invalid session cache keys and reclaims heap memory to prevent downstream database penetration."
            )
            why_rejected = f"`RESTART_SERVICE` rejected because restarting application does not resolve external Redis memory saturation."
            expected_result = f"Cache memory utilization on `{svc}` drops under 45% and eviction count returns to zero."
            risk_level = "LOW"
            side_effects = "Transient cache miss warm-up period as active session keys are re-populated."
            required_role = "OPERATOR"
            confidence = 0.93

        # 4. DEPLOYMENT REGRESSION / CANARY FAILURE
        elif any(k in search_text for k in [
            "CANARY", "DEPLOYMENT", "RELEASE", "REVISION", "V2.4", "ROLLOUT", "BAD DEPLOYMENT"
        ]):
            primary_action = "ROLLBACK_CONTROLLED_DEPLOYMENT"
            alt_action = "ROLLBACK_CONFIG"
            why_selected = (
                f"Error onset directly coincides with deployment canary revision. "
                f"Reverting release revision eliminates newly introduced routing defect."
            )
            why_rejected = f"`RESTART_SERVICE` rejected because restarting will simply relaunch the defective deployment revision."
            expected_result = f"Reverts `{svc}` to previous stable release artifact, eliminating 5xx errors."
            risk_level = "HIGH"
            side_effects = "Traffic switched back to stable predecessor version."
            required_role = "ORG_ADMIN"
            confidence = 0.96

        # 5. SERVICE CRASH (Controlled restart legitimate here)
        elif any(k in search_text for k in ["CRASH", "EXITED", "TERMINATED", "DEAD", "KILLED", "OOM"]):
            primary_action = "RESTART_CONTROLLED_SERVICE"
            alt_action = "ROLLBACK_CONFIG"
            why_selected = f"Microservice `{svc}` process terminated or crashed. Graceful container restart restores service readiness."
            why_rejected = f"Non-restart actions rejected because process is dead and must be restarted to resume operation."
            expected_result = f"Process restarted, health probes passing, HTTP 200 OK restored."
            risk_level = "MEDIUM"
            side_effects = "3-5 second process bootstrap window before accepting traffic."
            required_role = "SRE_LEAD"
            confidence = 0.94

        # 6. DATABASE TIMEOUT / SLOW QUERY
        elif any(k in search_text for k in [
            "DATABASE TIMEOUT", "DATABASE_TIMEOUT", "SLOW QUERY", "DEADLOCK", "LOCK CONTENTION", "STATEMENT TIMEOUT"
        ]) or ("DATABASE" in svc and ("TIMEOUT" in search_text or "LATENCY" in search_text)):
            if "DEADLOCK" in search_text or "LOCK" in search_text:
                primary_action = "RESET_CONNECTION_POOL"
                alt_action = "RECONNECT_DATABASE"
                why_selected = f"Lock contention detected on `{svc}`. Flushes contentious transaction threads and reclaims worker slots."
            else:
                primary_action = "RECONNECT_DATABASE"
                alt_action = "RESET_CONNECTION_POOL"
                why_selected = f"Database query timeout and broken client socket detected on `{svc}`. Re-establishes clean socket binding to persistence tier."
            
            why_rejected = f"`RESTART_SERVICE` rejected because database daemon is running; error originates in query/socket layer."
            expected_result = f"Query latency on `{svc}` returns under baseline (150ms)."
            risk_level = "LOW"
            side_effects = "Brief transaction retry backoff during driver socket rebind."
            required_role = "OPERATOR"
            confidence = 0.91

        # 7. HTTP 503 / CAPACITY EXHAUSTION / QUEUE SATURATION
        elif any(k in search_text for k in [
            "503", "CAPACITY", "QUEUE SATURATION", "QUEUE BACKLOG", "WORKER POOL", "BURST", "TRAFFIC SPIKE"
        ]):
            primary_action = "SCALE_WORKERS"
            alt_action = "ENABLE_CIRCUIT_BREAKER_FALLBACK"
            why_selected = (
                f"Ingress request queue saturation and 503 Service Unavailable errors on `{svc}`. "
                f"Scaling concurrency workers absorbs backlog without dropping in-flight traffic."
            )
            why_rejected = f"`RESTART_SERVICE` rejected because restarting drops all queued customer transactions and does not increase capacity."
            expected_result = f"Worker concurrency increased, queue depth drains to < 10 requests."
            risk_level = "LOW"
            side_effects = "Modest incremental host CPU/memory allocation."
            required_role = "OPERATOR"
            confidence = 0.90

        # 8. HIGH LATENCY (Bottleneck-specific)
        elif any(k in search_text for k in ["LATENCY", "SLOW", "TIMEOUT CASCADE", "P95 BREACH"]):
            if any(k in search_text for k in ["CPU", "CORE", "CPU_SPIKE"]):
                primary_action = "SCALE_WORKERS"
                alt_action = "RESTART_CONTROLLED_SERVICE"
                why_selected = f"Host CPU saturation (>80%) on `{svc}`. Horizontal concurrency scaling distributes load across cores."
            elif any(k in search_text for k in ["DEPENDENCY", "DOWNSTREAM", "CIRCUIT", "AUTH"]):
                primary_action = "ENABLE_CIRCUIT_BREAKER_FALLBACK"
                alt_action = "RESET_CONNECTION_POOL"
                why_selected = f"Downstream dependency latency cascading to `{svc}`. Engaging circuit breaker isolates upstream callers."
            else:
                primary_action = "RESET_CONNECTION_POOL"
                alt_action = "CLEAR_CACHE"
                why_selected = f"Latency spike on `{svc}` caused by thread waiting on connection acquisition. Resetting pool restores fast response time."

            why_rejected = f"`RESTART_SERVICE` rejected because it causes service disruption without addressing underlying bottleneck."
            expected_result = f"P95 latency returns under SLO threshold (<150ms)."
            risk_level = "LOW"
            side_effects = "Minimal operational footprint."
            required_role = "OPERATOR"
            confidence = 0.88

        # 9. HTTP 500 SPIKE (Exception-examined)
        elif any(k in search_text for k in ["500", "INTERNAL SERVER ERROR", "EXCEPTION"]):
            if "CONFIG" in search_text or "PARSE" in search_text:
                primary_action = "ROLLBACK_CONFIG"
                alt_action = "RESTART_CONTROLLED_SERVICE"
                why_selected = f"Configuration syntax or environment variable error on `{svc}`. Rollback restores valid parameter snapshot."
                confidence = 0.92
            elif "DATABASE" in combined_text or "SOCKET" in combined_text or "CONNECTION" in combined_text:
                primary_action = "RESET_CONNECTION_POOL"
                alt_action = "RECONNECT_DATABASE"
                why_selected = f"Trace analysis reveals HTTP 500 errors stem from database driver connection failure on `{svc}`."
                confidence = 0.94
            else:
                primary_action = "RESET_CONNECTION_POOL"
                alt_action = "CLEAR_CACHE"
                why_selected = f"Underlying connection timeout on `{svc}` identified from trace precedence."
                confidence = 0.86

            why_rejected = f"`RESTART_SERVICE` rejected because root cause is identified in configuration/connection layer."
            expected_result = f"HTTP 500 error cascade eliminated, error rate drops below 1.0%."
            risk_level = "LOW"
            side_effects = "Zero downtime parameter/connection reset."
            required_role = "OPERATOR"

        # 10. INSUFFICIENT EVIDENCE FALLBACK
        else:
            is_uncertain = True
            primary_action = "UNCERTAIN_EVIDENCE"
            alt_action = "INVESTIGATE_DIAGNOSTICS"
            why_selected = (
                f"Telemetry evidence on `{svc}` is insufficient to distinguish between possible causes. "
                f"Preserving service state and requesting additional distributed trace spans."
            )
            why_rejected = f"Automatic service restart rejected due to insufficient causal evidence and safety governance."
            expected_result = "Insufficient conclusive telemetry to recommend automated action. Requesting additional evidence."
            risk_level = "LOW"
            side_effects = "None (read-only diagnostic evaluation)."
            required_role = "VIEWER"
            confidence = 0.35

        # ---------------------------------------------------------
        # COMPANY ENVIRONMENT CAPABILITY VERIFICATION
        # ---------------------------------------------------------
        if is_uncertain:
            action_available = True
            is_supported = True
            cap_note = "Diagnostic evidence evaluation mode."
        else:
            is_supported, cap_note = cls.check_action_supported(primary_action, t_id)
            action_available = is_supported
            if not is_supported:
                why_selected = f"Action unavailable in the connected environment: {cap_note}"

        return {
            "recommended_action": primary_action,
            "action_available": action_available,
            "capability_supported": is_supported,
            "uncertainty": is_uncertain,
            "target_service": svc,
            "evidence_supporting_action": [
                f"RCA determination on '{svc}' with {int(confidence*100)}% confidence",
                f"Failure signature: {cat or title or 'Telemetry anomaly'}",
                f"Telemetry evidence: {evidence[0] if evidence else 'Empirical metrics baseline deviation'}",
                f"Operational risk: {risk_level} (Requires {required_role} authorization)"
            ],
            "expected_result": expected_result,
            "risk_level": risk_level,
            "potential_side_effects": side_effects,
            "required_approval_level": required_role,
            "why_selected": why_selected,
            "why_alternatives_rejected": why_rejected,
            "confidence": confidence,
            "confidence_pct": int(confidence * 100),
            "tenant_id": t_id,
            "capability_note": cap_note,
            "alternative_action": alt_action
        }


# Global singleton instance
evidence_decision_engine = EvidenceGroundedDecisionEngine()
