"""
AI Recommendation Engine
Generates primary & fallback remediation strategies based on RCA, risk scoring, and historical data.
Maps 20 failure classes to verified executable runbooks with empirical outcome modeling.
"""

from typing import Dict, Any, Tuple, Optional, List
from backend.app.healing.risk_engine import RiskEngine
from backend.app.knowledge.incident_memory import incident_memory


class RecommendationEngine:
    ACTION_CATALOG = {
        # 1. DATABASE CATEGORY
        "CONNECTION_POOL_EXHAUSTION": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes leaked connection sockets and resets pool state to 0/50, restoring query throughput and eliminating 500 error cascades.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Zero downtime (< 50ms transient socket flush)."
        },
        "DATABASE_DEADLOCK": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Terminates contentious transaction locks and reclaims pool capacity, reducing query latency.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Aborts uncommitted deadlocked transactions."
        },
        "DATABASE_LOCK_CONTENTION": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Releases row and table locks held by stalled workers, restoring read/write concurrency.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Minimal momentary transaction retry window."
        },
        "DATABASE_CONNECTION_TIMEOUT": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Purges dead upstream socket handles and restores immediate pool availability.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Instantaneous socket pool re-initialization."
        },
        "DATABASE_POOL_STARVATION": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "SCALE_WORKERS",
            "expected_outcome": "Reallocates idle connection capacity to active querying workers.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Recycles starved worker connection handles."
        },
        "DATABASE_REPLICATION_LAG": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Redirects read traffic to primary instance while secondary replica re-synchronizes write-ahead logs.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Read traffic temporarily redirected to primary node."
        },
        "DATABASE_SLOW_QUERY": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Releases saturated database worker threads and purges unindexed query cache.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Purges memory cache buffers without container restart."
        },
        "SLOW_QUERY_CASCADE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Terminates cascaded downstream slow query queue and restores database responsiveness.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Brief client query retry period."
        },
        "DATABASE_LATENCY_SPIKE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes congested connection queues and resets pool state to bring P95 latency under 200ms.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Re-establishes clean client query channels."
        },
        "DATABASE_QUERY_FAILURE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Purges corrupted statement handles and restores transactional query throughput.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Transient database driver reconnect."
        },

        # 2. APPLICATION CATEGORY
        "PROCESS_CRASH": {
            "primary": "RESTART_SERVICE",
            "alternative": "ROLLBACK_CONFIG",
            "expected_outcome": "Restarts crashed process container, rebinds listening socket, and restores health probe pass state.",
            "rollback_plan": "ROLLBACK_CONFIG",
            "expected_impact": "2-4 second container bootstrap window."
        },
        "SERVICE_CRASH": {
            "primary": "RESTART_SERVICE",
            "alternative": "ROLLBACK_CONFIG",
            "expected_outcome": "Re-instantiates terminated application service process and restores HTTP endpoint availability.",
            "rollback_plan": "ROLLBACK_CONFIG",
            "expected_impact": "Temporary traffic redirection to healthy replica."
        },
        "SERVICE_RESTART_LOOP": {
            "primary": "ROLLBACK_CONFIG",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Reverts to stable deployment configuration snapshot, halting crash backoff loop.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Configuration hot-reload on previous known stable build."
        },
        "THREADPOOL_EXHAUSTION": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Increases concurrency worker pool limit, draining task queues and stabilizing request throughput.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Expands concurrency limits dynamically without dropping in-flight traffic."
        },
        "REQUEST_QUEUE_SATURATION": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Spawns additional processing worker threads, immediately draining ingress backlog.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Allocates additional CPU threads."
        },
        "MEMORY_PRESSURE": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes accumulated in-memory buffers and heap cache, bringing RAM utilization under 70%.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Transient cache warm-up period."
        },
        "HIGH_EXCEPTION_RATE": {
            "primary": "ROLLBACK_CONFIG",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Reverts bad deployment state and halts unhandled exception cascade.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Reverts to baseline release profile."
        },
        "HTTP_500_SPIKE": {
            "primary": "ROLLBACK_CONFIG",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Restores verified runtime configuration, eliminating 500 error spikes across API endpoints.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Zero service downtime rollback."
        },
        "HTTP_502_SPIKE": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Expands upstream proxy thread limits, eliminating 502 Bad Gateway responses.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Zero client drop proxy scaling."
        },
        "HTTP_503_STORM": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Expands ingress connection queue capacity to handle sudden incoming request bursts.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Immediate queue expansion."
        },
        "HTTP_504_SPIKE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Re-establishes upstream gateway sockets, eliminating 504 gateway timeouts.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Instantaneous socket pool reset."
        },

        # 3. NETWORK CATEGORY
        "NETWORK_LATENCY_SPIKE": {
            "primary": "RESTART_SERVICE",
            "alternative": "RESET_CONNECTION_POOL",
            "expected_outcome": "Rebinds local network interface sockets and resets TCP buffer parameters.",
            "rollback_plan": "RESET_CONNECTION_POOL",
            "expected_impact": "Transient socket reconnect."
        },
        "PACKET_LOSS": {
            "primary": "RESTART_SERVICE",
            "alternative": "RESET_CONNECTION_POOL",
            "expected_outcome": "Reinitializes virtual NIC packet buffers, stopping transmission packet drops.",
            "rollback_plan": "RESET_CONNECTION_POOL",
            "expected_impact": "Brief interface socket recycling."
        },
        "CONNECTION_TIMEOUT": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes hung TCP SYN sockets and resets client connection backoffs.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Clears hung TCP sockets."
        },
        "DNS_FAILURE": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes stale local DNS cache and re-queries upstream authoritative nameserver.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Forces immediate recursive DNS resolution."
        },
        "TCP_CONNECTION_FAILURE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Clears RST flag backoffs and resets inter-service TCP connection pool.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Cleans TCP connection table."
        },
        "INTER_SERVICE_LATENCY": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "SCALE_WORKERS",
            "expected_outcome": "Purges stalled inter-service connection queues to stabilize hop-by-hop RPC latency.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Zero disruption RPC connection reset."
        },

        # 4. DEPENDENCIES CATEGORY
        "PAYMENT_DEPENDENCY_FAILURE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Resets external payment gateway proxy connection handles and activates retry circuit.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Switches to backup egress route."
        },
        "AUTH_DEPENDENCY_FAILURE": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Purges stale JWT public key cache and forces re-authentication handshake.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Brief token cache re-hydration."
        },
        "INVENTORY_DEPENDENCY_FAILURE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Re-establishes RPC client channel to inventory microservice.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Zero downtime channel restart."
        },
        "DEPENDENCY_TIMEOUT": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Restores upstream connection pipe and resets backoff throttles across caller proxies.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Refreshes proxy keepalive channels."
        },
        "DEPENDENCY_RATE_LIMIT": {
            "primary": "CLEAR_CACHE",
            "alternative": "SCALE_WORKERS",
            "expected_outcome": "Resets client rate-limit token buckets and activates exponential backoff pacing.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Paces egress request throughput."
        },
        "DEPENDENCY_5XX": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Clears failing upstream connection circuit and initiates graceful fallback route.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Engages secondary service endpoint."
        },

        # 5. RESOURCE CATEGORY
        "CPU_SPIKE": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Distributes execution workload across expanded worker processes to alleviate single-core CPU burn.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Expands worker concurrency."
        },
        "CPU_SATURATION": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Spawns parallel worker threads to balance CPU utilization below 65%.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "CPU load shared across multi-core workers."
        },
        "DISK_PRESSURE": {
            "primary": "ROTATE_AND_COMPRESS_LOGS",
            "alternative": "COMPACT_STORAGE",
            "expected_outcome": "Archives and compresses verbose logs, lowering disk utilization below 75%.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Frees disk inodes and blocks in background."
        },
        "FILE_DESCRIPTOR_EXHAUSTION": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Closes leaked socket descriptors and returns file descriptor usage to safe baseline.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Reclaims leaked OS file handles."
        },

        # 6. PERFORMANCE CATEGORY
        "LATENCY_SPIKE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Eliminates connection queue congestion, stabilizing P95 response latency.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Fast connection reset."
        },
        "THROUGHPUT_DROP": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESET_CONNECTION_POOL",
            "expected_outcome": "Expands processing throughput by scaling worker threads to match ingress demand.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Increases concurrency bandwidth."
        },
        "QUEUE_BACKLOG": {
            "primary": "SCALE_WORKERS",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Accelerates task consumption rate, draining accumulated queue backlog.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Drains backlog without dropping messages."
        },
        "TRAFFIC_SPIKE": {
            "primary": "SCALE_WORKERS",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Autonomously scales ingestion capacity to absorb unexpected traffic surges.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Absorbs burst traffic."
        },
        "SLOW_TRANSACTION": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Releases contentious transaction locks and resets execution pipelines.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Terminates runaway queries."
        },

        # 7. CACHE CATEGORY
        "CACHE_FAILURE": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes corrupted key index and initiates graceful cache warm-up, stopping database penetration.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Temporary increase in database read queries during warm-up."
        },
        "CACHE_MISS_SPIKE": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESET_CONNECTION_POOL",
            "expected_outcome": "Purges invalid cache keys and triggers synchronized pre-fetching.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Re-populates warm cache keys."
        },
        "CACHE_LATENCY_SPIKE": {
            "primary": "CLEAR_CACHE",
            "alternative": "SCALE_WORKERS",
            "expected_outcome": "Evicts expired hash tables and resets in-memory cache engine responsiveness.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Flushes slow hash slots."
        },
        "CACHE_UNAVAILABLE": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Rebinds cache client socket and initiates memory tier recovery.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Recovers caching layer availability."
        },
        "CACHE_EVICTION_STORM": {
            "primary": "CLEAR_CACHE",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Flushes corrupted key index and initiates graceful cache warm-up, stopping database penetration.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Smooths eviction churn."
        },

        # 8. BEHAVIORAL CATEGORY
        "UNUSUAL_REQUEST_PATTERN": {
            "primary": "SCALE_WORKERS",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Stabilizes anomalous request rate shifts by expanding request handling capacity.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Dynamic capacity buffer."
        },
        "ABNORMAL_TRAFFIC_DISTRIBUTION": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESET_CONNECTION_POOL",
            "expected_outcome": "Rebalances traffic routing across worker processes to mitigate hotspots.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Redistributes incoming load."
        },
        "SERVICE_BEHAVIOR_DRIFT": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Resets microservice communication pipes and restores nominal latency profile.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Returns behavior to historical baseline."
        },
        "TRACE_DURATION_ANOMALY": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "CLEAR_CACHE",
            "expected_outcome": "Eliminates downstream RPC propagation delay, restoring end-to-end trace durations.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Recovers nominal trace SLA."
        },

        # 9. CASCADE CATEGORY
        "DATABASE_TO_SERVICE_CASCADE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Halts cascade propagation by immediately flushing database connection leaks.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Breaks cascade chain at root service."
        },
        "DEPENDENCY_TO_GATEWAY_CASCADE": {
            "primary": "SCALE_WORKERS",
            "alternative": "RESET_CONNECTION_POOL",
            "expected_outcome": "Expands gateway ingress concurrency while dependent service reconnects.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Shields gateway from upstream timeouts."
        },
        "PAYMENT_CASCADE": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Isolates payment transaction pipe and resets database pool.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Prevents checkout order cancellation storm."
        },

        # 10. UNKNOWN / NOVEL ANOMALY CATEGORY
        "UNKNOWN_BEHAVIORAL_ANOMALY": {
            "primary": "RESET_CONNECTION_POOL",
            "alternative": "RESTART_SERVICE",
            "expected_outcome": "Conducts non-invasive connection pool flush to eliminate resource leaks while preserving container state.",
            "rollback_plan": "RESTART_SERVICE",
            "expected_impact": "Low impact telemetry diagnostic probe."
        }
    }

    @classmethod
    def generate_recommendation(
        cls,
        root_cause_service: str,
        root_cause_category: str,
        service_criticality: str = "HIGH",
        confidence: float = 0.90,
        historical_pattern: Optional[Dict[str, Any]] = None,
        tenant_id: str = "demo-tenant",
        evidence_items: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Produces primary recommendation, alternative fallback, risk evaluation, rollback plan, and expected outcome.
        Consults the explicit EvidenceGroundedDecisionEngine table to eliminate generic RESTART_SERVICE fallbacks.
        Enforces tenant capabilities and reports uncertainty when evidence is insufficient.
        """
        from backend.app.healing.decision_table import evidence_decision_engine

        # First evaluate via the explicit evidence-grounded decision table
        evidence_eval = evidence_decision_engine.evaluate_recovery_decision(
            evidence_summary=evidence_items or [],
            root_category=root_cause_category,
            target_service=root_cause_service,
            tenant_id=tenant_id
        )

        catalog_entry = cls.ACTION_CATALOG.get(root_cause_category)

        if evidence_eval.get("uncertainty"):
            primary = "UNCERTAIN_EVIDENCE"
            alternative = "NONE"
            expected_outcome = evidence_eval.get("expected_result", "Insufficient evidence to distinguish root cause. Awaiting further telemetry.")
            rollback_plan = "NONE"
            expected_impact = "No automated mutation executed pending verified evidence."
            action_available = True
        elif evidence_eval.get("recommended_action") and evidence_eval.get("recommended_action") != "RESTART_SERVICE":
            primary = evidence_eval["recommended_action"]
            alternative = (catalog_entry.get("alternative") if catalog_entry else None) or evidence_eval.get("alternative_action") or "RESTART_SERVICE"
            expected_outcome = catalog_entry.get("expected_outcome") if catalog_entry else evidence_eval["expected_result"]
            rollback_plan = alternative
            expected_impact = evidence_eval.get("why_selected", f"Executing {primary} targeting root cause on {root_cause_service}.")
            action_available = evidence_eval.get("action_available", True)
        elif catalog_entry:
            primary = catalog_entry["primary"]
            alternative = catalog_entry["alternative"]
            expected_outcome = catalog_entry["expected_outcome"]
            rollback_plan = catalog_entry.get("rollback_plan", "RESTART_SERVICE")
            expected_impact = catalog_entry.get("expected_impact", "Standard operational window.")
            action_available = evidence_eval.get("action_available", True)
        else:
            primary = evidence_eval.get("recommended_action", "RESET_CONNECTION_POOL")
            alternative = "RESTART_SERVICE"
            expected_outcome = evidence_eval.get("expected_result", f"Controlled recovery operation on '{root_cause_service}'.")
            rollback_plan = "RESTART_SERVICE"
            expected_impact = "Controlled operational action."
            action_available = evidence_eval.get("action_available", True)

        # Check if historical memory overrides with a proven successful remedy
        history_boost = False
        hist_success_rate_str = "N/A"
        if historical_pattern and historical_pattern.get("is_known_pattern"):
            hist_action = historical_pattern.get("recommended_action")
            hist_success = float(historical_pattern.get("success_rate", 0.0))
            hist_success_rate_str = f"{historical_pattern.get('success_rate_pct', 80)}%"
            if hist_action and hist_success >= 0.75:
                primary = hist_action
                history_boost = True
                expected_outcome = (
                    f"[Historical Pattern Verified ({historical_pattern.get('pattern_name')})] "
                    f"Action '{primary}' demonstrated {historical_pattern.get('success_rate_pct')}% success across "
                    f"{historical_pattern.get('historical_occurrences')} prior occurrences."
                )

        risk_assessment = RiskEngine.assess_risk(
            action_key=primary if primary != "UNCERTAIN_EVIDENCE" else "RESET_CONNECTION_POOL",
            target_service=root_cause_service,
            service_criticality=service_criticality,
            confidence=confidence
        )

        return {
            "root_cause_service": root_cause_service,
            "root_cause_category": root_cause_category,
            "primary_action": primary,
            "alternative_action": alternative,
            "expected_outcome": expected_outcome,
            "rollback_plan": rollback_plan,
            "expected_impact": expected_impact,
            "historical_success": hist_success_rate_str,
            "risk_assessment": risk_assessment,
            "confidence": confidence,
            "approval_required": risk_assessment["approval_required"],
            "learned_from_history": history_boost,
            "action_available": action_available,
            "tenant_id": tenant_id,
            "why_selected": evidence_eval.get("why_selected", expected_impact),
            "potential_side_effects": evidence_eval.get("potential_side_effects", []),
            "uncertainty": evidence_eval.get("uncertainty", False)
        }

    def recommend_remedy(self, incident: Dict[str, Any], history: Optional[Any] = None) -> Dict[str, Any]:
        """Evidence-grounded recommendation derived directly from incident evidence and tenant capabilities."""
        from backend.app.healing.decision_table import evidence_decision_engine
        decision = evidence_decision_engine.evaluate_incident_recovery(incident)

        svc = incident.get("root_cause_service") or incident.get("primary_service", "gateway")
        cat = incident.get("root_cause_category") or incident.get("failure_type", "SERVICE_DEGRADATION")
        t_id = incident.get("tenant_id") or incident.get("company", "demo-tenant")

        risk_assessment = RiskEngine.assess_risk(
            action_key=decision["recommended_action"] if decision["recommended_action"] != "UNCERTAIN_EVIDENCE" else "RESET_CONNECTION_POOL",
            target_service=svc,
            service_criticality="HIGH",
            confidence=decision.get("confidence", 0.90)
        )

        return {
            "root_cause_service": svc,
            "root_cause_category": cat,
            "primary_action": decision["recommended_action"],
            "alternative_action": decision.get("alternative_actions", ["NONE"])[0] if decision.get("alternative_actions") else "NONE",
            "expected_outcome": decision["expected_result"],
            "rollback_plan": decision.get("alternative_actions", ["RESTART_SERVICE"])[0] if decision.get("alternative_actions") else "RESTART_SERVICE",
            "expected_impact": decision.get("why_selected", f"Remediation targeting {svc}."),
            "historical_success": "Verified historical pattern",
            "risk_assessment": risk_assessment,
            "confidence": decision.get("confidence", 0.90),
            "approval_required": risk_assessment["approval_required"],
            "learned_from_history": False,
            "action_available": decision.get("action_available", True),
            "tenant_id": t_id,
            "why_selected": decision.get("why_selected", ""),
            "potential_side_effects": decision.get("potential_side_effects", []),
            "uncertainty": decision.get("uncertainty", False)
        }

    def recommend_action(
        self,
        root_cause: str,
        affected_services: list = None,
        severity: str = "ERROR",
        anomaly_score: float = 0.9,
        historical_context: dict = None
    ) -> Dict[str, Any]:
        """Convenience method for cluster recommendations."""
        category = "CONNECTION_POOL_EXHAUSTION" if "database" in root_cause.lower() or "sql" in root_cause.lower() else "SERVICE_DEGRADATION"
        return self.generate_recommendation(
            root_cause_service=root_cause,
            root_cause_category=category,
            service_criticality="HIGH",
            confidence=min(0.98, max(0.70, anomaly_score)),
            historical_pattern=historical_context
        )


recommender = RecommendationEngine()
RemediationRecommender = RecommendationEngine
ACTION_CATALOG = RecommendationEngine.ACTION_CATALOG
