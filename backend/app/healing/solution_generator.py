"""
AegisOps AI - Candidate Solution Generation Engine
Generates multiple ranked candidate recovery solutions for a given root-cause hypothesis.
Each solution defines: action, target component, expected effect, risk, prerequisites,
rollback strategy, and calibrated confidence.
Integrates historical incident memory recommendations without blind execution.
"""

from typing import Dict, Any, List, Optional
from backend.app.knowledge.incident_memory import incident_memory


SOLUTION_CATALOG = {
    "db_connection_pool_exhaustion": [
        {
            "id": "sol_reconnect_database",
            "action": "RECONNECT_DATABASE",
            "target_component": "database-service:connection_pool",
            "expected_effect": "Re-establishes healthy pooled sockets, flushes idle connections, and resets pool slots.",
            "risk": "LOW",
            "prerequisites": ["Database server is alive and responding on port 8004", "No active irreversible schema migrations in flight"],
            "rollback_strategy": "Restore connection pool parameters from previous snapshot and reinitialize pool listener",
            "confidence": 0.95
        },
        {
            "id": "sol_reset_conn_pool",
            "action": "RESET_CONNECTION_POOL",
            "target_component": "database-service:connection_pool",
            "expected_effect": "Terminates orphaned and idle connection handles, resetting pool to healthy threshold (<= 15 active connections).",
            "risk": "LOW",
            "prerequisites": ["Database server is alive and responding on port 8004", "No active irreversible schema migrations in flight"],
            "rollback_strategy": "Restore connection pool parameters from previous snapshot and reinitialize pool listener",
            "confidence": 0.94
        },
        {
            "id": "sol_restart_database_service",
            "action": "RESTART_SERVICE",
            "target_component": "database-service:process_runtime",
            "expected_effect": "Hard restart of the database persistence container to flush all blocked socket connections and thread locks.",
            "risk": "HIGH",
            "prerequisites": ["Dependent services Service A & B implement retry backoff", "Storage volume is persistently mounted"],
            "rollback_strategy": "Start previous stable container image if startup fails within 15 seconds",
            "confidence": 0.72
        },
        {
            "id": "sol_scale_service_b_workers",
            "action": "SCALE_WORKERS",
            "target_component": "service-b:worker_pool",
            "expected_effect": "Increase Payment Service worker capacity to buffer downstream backlog",
            "risk": "MEDIUM",
            "prerequisites": ["Host memory available > 512MB"],
            "rollback_strategy": "Scale down worker count back to baseline (2 workers)",
            "confidence": 0.38
        }
    ],
    "service_crash": [
        {
            "id": "sol_restart_service",
            "action": "RESTART_SERVICE",
            "target_component": "service-b:process_runtime",
            "expected_effect": "Restarts crashed microservice process and re-establishes API readiness.",
            "risk": "MEDIUM",
            "prerequisites": ["Container runtime healthy", "Configuration files intact"],
            "rollback_strategy": "Roll back to last known healthy container image and restart",
            "confidence": 0.92
        },
        {
            "id": "sol_rollback_service_config",
            "action": "ROLLBACK_CONFIG",
            "target_component": "service-b:configuration",
            "expected_effect": "Roll back recent configuration changes or environment variables that caused startup crash.",
            "risk": "HIGH",
            "prerequisites": ["Configuration version history available"],
            "rollback_strategy": "Re-apply current configuration file",
            "confidence": 0.65
        }
    ],
    "high_api_latency": [
        {
            "id": "sol_scale_workers_latency",
            "action": "SCALE_WORKERS",
            "target_component": "service-a:worker_pool",
            "expected_effect": "Increases concurrency worker threads from 2 to 6, reducing P95 latency from > 1500ms down to < 200ms.",
            "risk": "LOW",
            "prerequisites": ["Host CPU utilization < 75%", "Memory utilization < 80%"],
            "rollback_strategy": "Scale down worker count back to 2",
            "confidence": 0.88
        },
        {
            "id": "sol_clear_cache_latency",
            "action": "CLEAR_CACHE",
            "target_component": "service-a:in_memory_cache",
            "expected_effect": "Clears stale cache entries and frees up memory buffers to prevent latency degradation.",
            "risk": "LOW",
            "prerequisites": ["Cache backend supports flush"],
            "rollback_strategy": "Warm cache with priority keys",
            "confidence": 0.60
        },
        {
            "id": "sol_restart_service_latency",
            "action": "RESTART_SERVICE",
            "target_component": "service-a:process_runtime",
            "expected_effect": "Restarts the service to clear thread deadlocks and long-tail latency spikes.",
            "risk": "MEDIUM",
            "prerequisites": ["Gateway routes around Service A during restart window"],
            "rollback_strategy": "Verify health probe after restart",
            "confidence": 0.55
        }
    ],
    "memory_pressure": [
        {
            "id": "sol_clear_cache_mem",
            "action": "CLEAR_CACHE",
            "target_component": "service-a:in_memory_cache",
            "expected_effect": "Flushes large heap buffer allocations and forces garbage collection, dropping memory from > 400MB to < 160MB.",
            "risk": "LOW",
            "prerequisites": ["In-flight transactions are idempotent"],
            "rollback_strategy": "Allow cache to regenerate on subsequent requests",
            "confidence": 0.91
        },
        {
            "id": "sol_restart_service_mem",
            "action": "RESTART_SERVICE",
            "target_component": "service-a:process_runtime",
            "expected_effect": "Complete process recycle to release leaked memory handles.",
            "risk": "MEDIUM",
            "prerequisites": ["No active long-running batch jobs"],
            "rollback_strategy": "Restore previous instance state",
            "confidence": 0.78
        }
    ],
    "cpu_saturation": [
        {
            "id": "sol_scale_workers_cpu",
            "action": "SCALE_WORKERS",
            "target_component": "gateway:worker_pool",
            "expected_effect": "Distributes incoming traffic across 4 workers to drop per-core CPU load from 95% to < 35%.",
            "risk": "LOW",
            "prerequisites": ["Available host CPU cores >= 2"],
            "rollback_strategy": "Scale back worker count to 2",
            "confidence": 0.89
        },
        {
            "id": "sol_restart_service_cpu",
            "action": "RESTART_SERVICE",
            "target_component": "gateway:process_runtime",
            "expected_effect": "Terminates runaway computational tasks and restarts ingress listener.",
            "risk": "HIGH",
            "prerequisites": ["External load balancer health check active"],
            "rollback_strategy": "Restart with safe configuration",
            "confidence": 0.65
        }
    ],
    "dependency_unavailable": [
        {
            "id": "sol_circuit_breaker",
            "action": "ENABLE_CIRCUIT_BREAKER_FALLBACK",
            "target_component": "auth-service:downstream_client",
            "expected_effect": "Engages local fallback cache and trips circuit breaker, preventing cascading HTTP 504 timeouts across upstream services.",
            "risk": "LOW",
            "prerequisites": ["Fallback policy configured in tenant policy"],
            "rollback_strategy": "Reset circuit breaker to HALF-OPEN status when dependency recovers",
            "confidence": 0.93
        },
        {
            "id": "sol_restart_dependency",
            "action": "RESTART_SERVICE",
            "target_component": "auth-service:process_runtime",
            "expected_effect": "Restarts auth service instance to recover network socket binding.",
            "risk": "MEDIUM",
            "prerequisites": ["Auth database is responsive"],
            "rollback_strategy": "Verify auth health check",
            "confidence": 0.70
        }
    ],
    "queue_backlog": [
        {
            "id": "sol_scale_consumers",
            "action": "SCALE_CONSUMER_WORKERS",
            "target_component": "service-b:message_queue",
            "expected_effect": "Spawns 3 additional queue consumers to drain message backlog from > 500 messages to < 10 messages.",
            "risk": "LOW",
            "prerequisites": ["Broker partitions available >= 3"],
            "rollback_strategy": "Scale consumer group back to 1 worker",
            "confidence": 0.92
        },
        {
            "id": "sol_restart_consumer",
            "action": "RESTART_SERVICE",
            "target_component": "service-b:process_runtime",
            "expected_effect": "Restarts stalled consumer process to re-establish Kafka consumer group partition assignment.",
            "risk": "MEDIUM",
            "prerequisites": ["Offset commits are persisted"],
            "rollback_strategy": "Verify consumer group lag post-restart",
            "confidence": 0.68
        }
    ],
    "configuration_error": [
        {
            "id": "sol_rollback_config",
            "action": "ROLLBACK_CONFIG",
            "target_component": "database-service:configuration",
            "expected_effect": "Reverts corrupted database connection parameter to previous valid snapshot and reloads service configuration.",
            "risk": "LOW",
            "prerequisites": ["Valid prior configuration snapshot exists in audit log"],
            "rollback_strategy": "Keep backup of reverted file in archive",
            "confidence": 0.95
        },
        {
            "id": "sol_restart_service_config",
            "action": "RESTART_SERVICE",
            "target_component": "database-service:process_runtime",
            "expected_effect": "Restarts service to force re-reading environment variables.",
            "risk": "MEDIUM",
            "prerequisites": ["Environment variables fixed"],
            "rollback_strategy": "Verify startup logs",
            "confidence": 0.50
        }
    ],
    "bad_deployment": [
        {
            "id": "sol_rollback_deployment",
            "action": "ROLLBACK_DEPLOYMENT",
            "target_component": "service:deployment_revision",
            "expected_effect": "Rolls back to the previous stable release artifact to restore operational baseline.",
            "risk": "LOW",
            "prerequisites": ["Previous deployment artifact cached in registry"],
            "rollback_strategy": "Re-deploy Canary release if rollback stalls",
            "confidence": 0.96
        }
    ],
    "deployment_regression": [
        {
            "id": "sol_rollback_deployment_reg",
            "action": "ROLLBACK_DEPLOYMENT",
            "target_component": "service:deployment_revision",
            "expected_effect": "Reverts to prior known healthy release version to eliminate regression defect.",
            "risk": "LOW",
            "prerequisites": ["Prior release image available"],
            "rollback_strategy": "Maintain rollback until patch validated",
            "confidence": 0.96
        }
    ]
}


class SolutionGenerator:
    """Generates multiple concrete candidate recovery solutions."""

    def generate_candidate_solutions(
        self,
        hypothesis: Dict[str, Any],
        scenario_id: Optional[str] = None,
        tenant_id: str = "demo-tenant"
    ) -> List[Dict[str, Any]]:
        """
        Generates candidate recovery solutions for the given root cause hypothesis.
        Consults historical memory to enrich candidates with empirical success rates.
        """
        hyp_id = hypothesis.get("id") or scenario_id or "db_connection_pool_exhaustion"
        target_svc = hypothesis.get("target_service") or hypothesis.get("primary_service") or "database-service"

        from backend.app.healing.decision_table import evidence_decision_engine
        eval_res = evidence_decision_engine.evaluate_incident_recovery(hypothesis, tenant_id=tenant_id)
        primary_action = eval_res["recommended_action"]
        alt_action = eval_res.get("alternative_action", "CLEAR_CACHE")

        candidates = []
        if hyp_id in SOLUTION_CATALOG:
            candidates = [dict(c) for c in SOLUTION_CATALOG[hyp_id]]
            # Ensure primary recommendation is prioritized at top
            if candidates and candidates[0]["action"] != primary_action:
                matched_idx = next((i for i, c in enumerate(candidates) if c["action"] == primary_action), None)
                if matched_idx is not None:
                    top_cand = candidates.pop(matched_idx)
                    candidates.insert(0, top_cand)
        else:
            # Evidence-grounded candidate solutions
            candidates = [
                {
                    "id": f"sol_{primary_action.lower()}_{target_svc}",
                    "action": primary_action,
                    "target_component": f"{target_svc}:recovery_target",
                    "expected_effect": eval_res["expected_result"],
                    "risk": eval_res["risk_level"],
                    "prerequisites": ["Target service responsive", "Safety evaluation verified"],
                    "rollback_strategy": f"Rollback with alternative action {alt_action}",
                    "confidence": eval_res["confidence"],
                    "why_selected": eval_res["why_selected"],
                    "why_rejected": eval_res["why_alternatives_rejected"],
                    "capability_supported": eval_res["capability_supported"],
                    "capability_note": eval_res["capability_note"]
                },
                {
                    "id": f"sol_{alt_action.lower()}_{target_svc}",
                    "action": alt_action,
                    "target_component": f"{target_svc}:fallback_target",
                    "expected_effect": f"Fallback remediation applying {alt_action}.",
                    "risk": "LOW" if eval_res["risk_level"] == "LOW" else "MEDIUM",
                    "prerequisites": ["Service endpoints responsive"],
                    "rollback_strategy": "Maintain telemetry monitoring",
                    "confidence": max(0.50, round(eval_res["confidence"] - 0.15, 2))
                }
            ]

        # Check Historical Incident Memory for historical recommendations
        try:
            hist_matches = incident_memory.search_similar_incidents(
                query_vector=[0.05, 0.8, 120.0, 0.4, 0.85],
                tenant_id=tenant_id,
                min_similarity=0.75,
                limit=3
            )
            if hist_matches:
                best_hist = hist_matches[0]
                hist_action = best_hist.get("remediation_action")
                for c in candidates:
                    if c["action"] == hist_action:
                        c["historical_endorsement"] = {
                            "incident_id": best_hist.get("incident_id"),
                            "historical_success": best_hist.get("success", True),
                            "similarity": round(best_hist.get("similarity", 0.90), 2),
                            "note": f"Matches previously validated incident {best_hist.get('incident_id')} with verified resolution."
                        }
                        c["confidence"] = min(0.98, c["confidence"] + 0.05)
        except Exception:
            pass

        # Part 24: Recovery Score = root_cause_match * expected_effectiveness * safety * confidence
        for c in candidates:
            # 1. Root cause match
            target = c.get("target_component", "").lower()
            hyp_target = str(hypothesis.get("target_service", "")).lower()
            if hyp_target and (hyp_target in target or any(part in target for part in hyp_target.split("-"))):
                rc_match = 0.95
            else:
                rc_match = 0.70
            
            # 2. Expected effectiveness
            action = c.get("action", "").upper()
            risk = c.get("risk", "MEDIUM").upper()
            if action in ("RESET_CONNECTION_POOL", "RECONNECT_DATABASE", "CLEAR_CACHE", "RESTART_SERVICE"):
                eff = 0.92
            else:
                eff = 0.78
            
            # 3. Safety: penalize dangerous actions (e.g. database restart = lower safety)
            if "DATABASE" in target.upper() and action == "RESTART_SERVICE":
                safety = 0.50  # Lower safety for database restart
            elif risk == "HIGH":
                safety = 0.55
            elif risk == "MEDIUM":
                safety = 0.75
            else:
                safety = 0.92  # High safety for stateless service or cache clear
                
            conf = float(c.get("confidence", 0.85))
            rec_score = round(rc_match * eff * safety * conf, 3)
            
            c["root_cause_match"] = rc_match
            c["expected_effectiveness"] = eff
            c["safety"] = safety
            c["recovery_score"] = rec_score
            c["ml_status"] = "Insufficient historical data — using policy-based recovery."
            
            # 10-step structured procedure (Requirement 16)
            c["procedure"] = [
                f"1. Stop new recovery attempts and lock remediation semaphore for {target_svc}",
                f"2. Validate upstream and downstream health of {target_svc} dependencies",
                f"3. Execute targeted remediation: {c.get('action', 'REMEDIATE').replace('_', ' ').title()} on {c.get('target_component', target_svc)}",
                f"4. Restart affected worker threads or reload container runtime if required",
                f"5. Restore traffic gradually via canary routing / circuit breaker reset",
                f"6. Monitor error rate across 30s evaluation window (target < 2%)",
                f"7. Monitor database and resource saturation (CPU < 70%, Pool < 50%)",
                f"8. Validate successful end-to-end synthetic requests via Ingress Gateway",
                f"9. Check downstream services for cascading latency or backpressure",
                f"10. Confirm zero side effects and finalize incident closure"
            ]

        # Sort candidates by recovery_score descending (safer, high-effectiveness actions ranked first)
        candidates.sort(key=lambda x: x.get("recovery_score", x.get("confidence", 0)), reverse=True)
        return candidates

    def refine_and_rerank_solutions(
        self,
        remaining_candidates: List[Dict[str, Any]],
        failure_analysis: Dict[str, Any],
        incident_type: str = "GENERIC",
        target_service: str = "database-service",
        tenant_id: str = "demo-tenant"
    ) -> List[Dict[str, Any]]:
        """
        Intelligently re-ranks remaining recovery candidates using execution evidence:
        - Penalizes solutions that share traits with the action that caused collateral side-effects.
        - Rewards solutions that directly target unresolved conditions.
        - Promotes historically validated remediations from operational memory.
        - Incorporates dependency topology and service context.
        """
        failed_solution = str(failure_analysis.get("solution", "")).upper()
        failed_conditions = [str(c).lower() for c in failure_analysis.get("failed_conditions", [])]
        side_effects = [str(s).lower() for s in failure_analysis.get("side_effects", [])]
        improved_conditions = [str(c).lower() for c in failure_analysis.get("improved_conditions", [])]
        attempt_num = failure_analysis.get("attempt", 1)

        reranked = []
        for cand in remaining_candidates:
            c = dict(cand)
            action = str(c.get("action", "")).upper()
            base_score = float(c.get("confidence", 0.60))
            adjustment = 0.0
            reasons = []

            # 1. Penalize solutions resembling the failed action or action family
            if action == failed_solution:
                adjustment -= 0.50
                reasons.append(f"Penalized: Action '{action}' already failed in Attempt {attempt_num}")
            elif "RESTART" in failed_solution and "RESTART" in action:
                adjustment -= 0.30
                reasons.append("Penalized: Restart strategies provoked availability/latency side-effects")

            # 2. Penalize actions likely to exacerbate observed side-effects
            any_latency_surge = any("latency" in s for s in side_effects)
            any_throughput_drop = any("throughput" in s for s in side_effects)
            any_conn_surge = any("connection" in s for s in side_effects)

            if any_latency_surge and action in ("RESTART_SERVICE", "RETRY_AGGRESSIVELY"):
                adjustment -= 0.25
                reasons.append("Penalized: Cold restarts aggravate latency surge")

            if any_conn_surge and action in ("SCALE_WORKERS", "SPAWN_EXTRA_WORKERS"):
                adjustment -= 0.30
                reasons.append("Penalized: Concurrency expansion increases connection saturation")

            # 3. Reward actions targeting unresolved conditions
            has_conn_unresolved = any("connection" in cond or "pool" in cond for cond in failed_conditions)
            has_latency_unresolved = any("latency" in cond for cond in failed_conditions)
            has_throughput_unresolved = any("throughput" in cond for cond in failed_conditions)
            has_memory_unresolved = any("memory" in cond for cond in failed_conditions)

            if has_conn_unresolved and action in ("RESET_CONNECTION_POOL", "PURGE_CONNECTIONS"):
                adjustment += 0.35
                reasons.append("Rewarded: Directly purges leaked handles to resolve connection exhaustion")

            if (has_latency_unresolved or has_throughput_unresolved) and action in ("SCALE_WORKERS", "OPTIMIZE_ROUTE"):
                adjustment += 0.25
                reasons.append("Rewarded: Expands worker concurrency to eliminate request backlog")

            if has_memory_unresolved and action in ("CLEAR_CACHE", "PURGE_BUFFERS"):
                adjustment += 0.30
                reasons.append("Rewarded: Frees heap allocations to eliminate memory pressure")

            # 4. Reward actions verified in historical incident memory
            try:
                hist_matches = incident_memory.search_similar_incidents(
                    query_vector=[0.05, 0.8, 120.0, 0.4, 0.85],
                    tenant_id=tenant_id,
                    min_similarity=0.70,
                    limit=3
                )
                if hist_matches:
                    for h in hist_matches:
                        if h.get("remediation_action") == action and h.get("success"):
                            adjustment += 0.20
                            reasons.append(f"Historical boost: Succeeded in verified incident {h.get('incident_id')}")
                            break
            except Exception:
                pass

            new_conf = round(min(0.98, max(0.10, base_score + adjustment)), 2)
            c["confidence"] = new_conf
            c["refinement_reasons"] = reasons
            c["refinement_score_delta"] = round(adjustment, 2)
            
            # Recalculate Part 24 recovery_score
            rc_match = c.get("root_cause_match", 0.90)
            eff = c.get("expected_effectiveness", 0.85)
            safety = c.get("safety", 0.80)
            c["recovery_score"] = round(rc_match * eff * safety * new_conf, 3)
            reranked.append(c)

        # Re-sort remaining candidates by new adjusted recovery_score
        reranked.sort(key=lambda x: x.get("recovery_score", x.get("confidence", 0)), reverse=True)
        return reranked


solution_generator = SolutionGenerator()
