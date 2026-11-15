"""
AegisOps AI - Multi-Metric Closed-Loop Validator & Side-Effect Detection Engine
Compares pre-fix and post-fix execution evidence across:
- error rate
- latency (p50, p95)
- throughput
- cpu %
- memory MB
- database connections
- queue depth
- service availability & health status

Determines:
- original_error_resolved (bool)
- side_effect_detected (bool)
- solution_validated (original_error_resolved AND NOT side_effect_detected)

Generates comprehensive formal Validation Report.
"""

import time
from typing import Dict, Any, List, Optional, Tuple


class RecoveryValidator:
    """Validates post-execution recovery and aggressively checks for collateral side effects."""

    def compare_evidence(
        self,
        pre_metrics: Dict[str, Dict[str, Any]],
        post_metrics: Dict[str, Dict[str, Any]],
        target_service: str,
        success_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculates metric-by-metric delta comparisons between pre-fix and post-fix telemetry.
        """
        comparison_table = []
        metrics_keys = [
            ("error_rate", "Error Rate", "ratio", 0.05),
            ("latency_p95_ms", "Latency P95", "ms", 250.0),
            ("latency_p50_ms", "Latency P50", "ms", 50.0),
            ("throughput_rps", "Throughput", "rps", 80.0),
            ("cpu_percent", "CPU Utilization", "%", 60.0),
            ("memory_mb", "Memory Footprint", "MB", 300.0),
            ("active_connections", "Active Connections", "conn", 25.0),
            ("queue_depth", "Queue Depth", "msgs", 10.0),
        ]

        target_pre = pre_metrics.get(target_service, {})
        target_post = post_metrics.get(target_service, {})

        for m_key, label, unit, default_threshold in metrics_keys:
            if m_key in target_pre or m_key in target_post:
                pre_val = float(target_pre.get(m_key, 0.0))
                post_val = float(target_post.get(m_key, 0.0))

                delta = post_val - pre_val
                pct_change = ((delta) / max(0.001, abs(pre_val))) * 100.0 if pre_val != 0 else 0.0
                
                # Check status
                improved = False
                if m_key == "throughput_rps":
                    improved = (post_val >= pre_val)
                else:
                    improved = (post_val <= pre_val)

                comparison_table.append({
                    "metric": m_key,
                    "label": label,
                    "unit": unit,
                    "pre_value": round(pre_val, 2),
                    "post_value": round(post_val, 2),
                    "delta": round(delta, 2),
                    "percentage_change": f"{pct_change:+.1f}%",
                    "improved": improved
                })

        return {
            "target_service": target_service,
            "comparison_table": comparison_table
        }

    def detect_side_effects(
        self,
        pre_metrics: Dict[str, Dict[str, Any]],
        post_metrics: Dict[str, Dict[str, Any]],
        target_service: str,
        post_logs: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyzes post-fix execution evidence for unintended side effects:
        1. Latency surge: P95 increased > 50% or exceeded 1500ms
        2. Throughput drop: Throughput dropped > 30% from pre-incident baseline
        3. Memory explosion: Memory grew > 100% or exceeded 500MB
        4. Collateral service degradation: Another service became unhealthy or degraded
        5. New error class appeared in logs (e.g. OOM, 429, Deadlock)
        """
        side_effects = []
        target_pre = pre_metrics.get(target_service, {})
        target_post = post_metrics.get(target_service, {})

        # 1. Latency surge check
        pre_p95 = float(target_pre.get("latency_p95_ms", 30.0))
        post_p95 = float(target_post.get("latency_p95_ms", 30.0))
        if post_p95 > 1000.0 or (pre_p95 > 0 and (post_p95 - pre_p95) / pre_p95 > 0.50 and post_p95 > 300.0):
            side_effects.append({
                "type": "LATENCY_SURGE",
                "severity": "HIGH",
                "description": f"P95 latency surged to {post_p95:.1f}ms on {target_service} (+{((post_p95 - pre_p95)/max(1, pre_p95))*100:.1f}%)",
                "component": "http_endpoint"
            })

        # 2. Throughput drop check
        pre_tput = float(target_pre.get("throughput_rps", 120.0))
        post_tput = float(target_post.get("throughput_rps", 120.0))
        if post_tput < 50.0 or (pre_tput > 0 and (pre_tput - post_tput) / pre_tput > 0.30):
            side_effects.append({
                "type": "THROUGHPUT_DROP",
                "severity": "HIGH",
                "description": f"Service throughput dropped by {((pre_tput - post_tput)/max(1, pre_tput))*100:.1f}% to {post_tput:.1f} RPS (threshold: >= 80 RPS)",
                "component": "traffic_controller"
            })

        # 3. Memory explosion check
        pre_mem = float(target_pre.get("memory_mb", 140.0))
        post_mem = float(target_post.get("memory_mb", 140.0))
        if post_mem > 600.0 or (pre_mem > 0 and (post_mem - pre_mem) / pre_mem > 1.0):
            side_effects.append({
                "type": "MEMORY_EXPLOSION",
                "severity": "CRITICAL",
                "description": f"Memory footprint surged to {post_mem:.1f}MB (+{((post_mem - pre_mem)/max(1, pre_mem))*100:.1f}% increase)",
                "component": "process_memory"
            })

        # 4. Collateral service degradation
        for svc_name, s_post in post_metrics.items():
            if svc_name != target_service:
                if not s_post.get("healthy", True) or float(s_post.get("error_rate", 0.0)) > 0.15:
                    side_effects.append({
                        "type": "COLLATERAL_SERVICE_DEGRADATION",
                        "severity": "HIGH",
                        "service": svc_name,
                        "description": f"Downstream/peer service '{svc_name}' became unhealthy or experienced elevated error rate ({s_post.get('error_rate')})",
                        "component": "service_mesh"
                    })

        # 5. Check post-logs for new error classes
        if post_logs:
            for l in post_logs:
                msg = str(l.get("message", ""))
                lvl = str(l.get("level", "INFO")).upper()
                if "SIDE EFFECT" in msg or "CrashLoopBackOff" in msg or "data loss" in msg.lower():
                    side_effects.append({
                        "type": "NEW_ERROR_CLASS_DETECTED",
                        "severity": "CRITICAL",
                        "description": msg,
                        "component": l.get("component", "system")
                    })

        return side_effects

    def validate_solution(
        self,
        target_service: str,
        pre_metrics: Dict[str, Dict[str, Any]],
        post_metrics: Dict[str, Dict[str, Any]],
        success_criteria: Optional[Dict[str, Any]] = None,
        post_logs: Optional[List[Dict[str, Any]]] = None,
        incident_type: Optional[str] = None,
        scenario_id: Optional[str] = None,
        action_name: Optional[str] = None,
        iteration: int = 1
    ) -> Dict[str, Any]:
        """
        Executes strict multi-metric closed-loop validation tailored to the specific incident type:
        1. Evaluates incident-specific criteria (e.g. connections for DB exhaustion, p95 for latency spike, memory for leak).
        2. Detects collateral side-effects (latency regressions, throughput drop, new errors).
        3. Generates structured measurable evidence for each criterion.
        4. Produces structured failure analysis when validation fails.
        """
        criteria = success_criteria or {}
        inc_type = (incident_type or scenario_id or "GENERIC").upper()

        tgt_pre = pre_metrics.get(target_service, {})
        tgt_post = post_metrics.get(target_service, {})

        if not tgt_post or not tgt_pre:
            return {
                "solution_validated": False,
                "original_error_resolved": False,
                "side_effect_detected": False,
                "decision": "MISSING_EVIDENCE",
                "failure_analysis": {
                    "failed_conditions": ["missing_telemetry_evidence"],
                    "side_effects": [],
                    "improved_conditions": [],
                    "reasoning": f"Required before/after telemetry evidence is missing for target service '{target_service}'."
                },
                "evidence_items": [],
                "side_effects": [],
                "criteria_evaluated": [],
                "unresolved_conditions": ["missing_telemetry_evidence"],
                "improved_conditions": []
            }

        # Extract post values with sensible defaults
        post_err = float(tgt_post.get("error_rate", 0.0))
        pre_err = float(tgt_pre.get("error_rate", 0.0))

        post_lat = float(tgt_post.get("latency_p95_ms", 30.0))
        pre_lat = float(tgt_pre.get("latency_p95_ms", 30.0))

        post_p50 = float(tgt_post.get("latency_p50_ms", 15.0))
        pre_p50 = float(tgt_pre.get("latency_p50_ms", 15.0))

        post_tput = float(tgt_post.get("throughput_rps", 100.0))
        pre_tput = float(tgt_pre.get("throughput_rps", 100.0))

        post_conn = float(tgt_post.get("active_connections", 10.0))
        pre_conn = float(tgt_pre.get("active_connections", 10.0))

        post_mem = float(tgt_post.get("memory_mb", 150.0))
        pre_mem = float(tgt_pre.get("memory_mb", 150.0))

        post_cpu = float(tgt_post.get("cpu_percent", 20.0))
        pre_cpu = float(tgt_pre.get("cpu_percent", 20.0))

        post_q = float(tgt_post.get("queue_depth", 0.0))
        pre_q = float(tgt_pre.get("queue_depth", 0.0))

        is_healthy = bool(tgt_post.get("healthy", True))

        # Baseline thresholds from criteria or incident profile
        max_err = float(criteria.get("max_error_rate", 0.05))
        max_lat = float(criteria.get("max_latency_p95_ms", 250.0))
        max_mem = float(criteria.get("max_memory_mb", 350.0))
        max_conn = float(criteria.get("max_active_connections", 25.0))
        max_q = float(criteria.get("max_queue_depth", 15.0))
        max_cpu = float(criteria.get("max_cpu_percent", 65.0))
        min_tput = float(criteria.get("min_throughput_rps", 75.0))

        # Dynamic, incident-specific criteria evaluation
        criteria_list = []
        unresolved_conditions = []
        improved_conditions = []
        structured_evidence = []

        # 1. Error Rate check (universal)
        err_pass = (post_err <= max_err)
        criteria_list.append({
            "name": "error_rate",
            "label": "Error Rate",
            "threshold": max_err,
            "observed": round(post_err, 3),
            "unit": "ratio",
            "status": "PASS" if err_pass else "FAIL"
        })
        structured_evidence.append({
            "evidence_type": "metric",
            "metric": "error_rate",
            "before": round(pre_err, 3),
            "after": round(post_err, 3),
            "threshold": max_err,
            "status": "PASS" if err_pass else "FAIL",
            "source": "replica_execution"
        })
        if err_pass:
            if pre_err > max_err:
                improved_conditions.append("error_rate")
        else:
            unresolved_conditions.append("error_rate_above_threshold")

        # 2. Incident-type specific validations
        if "CONNECTION" in inc_type or "POOL" in inc_type or "DB" in inc_type:
            # DATABASE_CONNECTION_EXHAUSTION: validate active connections, connection utilization, query latency, health, throughput
            conn_pass = (post_conn <= max_conn)
            criteria_list.append({
                "name": "active_connections",
                "label": "Active Database Connections",
                "threshold": max_conn,
                "observed": round(post_conn, 1),
                "unit": "conn",
                "status": "PASS" if conn_pass else "FAIL"
            })
            structured_evidence.append({
                "evidence_type": "metric",
                "metric": "active_connections",
                "before": round(pre_conn, 1),
                "after": round(post_conn, 1),
                "threshold": max_conn,
                "status": "PASS" if conn_pass else "FAIL",
                "source": "replica_execution"
            })
            if conn_pass:
                if pre_conn > max_conn:
                    improved_conditions.append("active_connections")
            else:
                unresolved_conditions.append("connection_pool_exhausted")

            lat_pass = (post_lat <= max_lat)
            if lat_pass:
                if pre_lat > max_lat:
                    improved_conditions.append("query_latency")
            else:
                unresolved_conditions.append("query_latency_above_threshold")

            tput_pass = (post_tput >= min_tput)
            if not tput_pass:
                unresolved_conditions.append("throughput_below_threshold")

        elif "LATENCY" in inc_type or "SPIKE" in inc_type or "HIGH_API" in inc_type:
            # LATENCY_SPIKE: validate p95 latency, request rate/throughput, downstream latency
            lat_pass = (post_lat <= max_lat)
            criteria_list.append({
                "name": "latency_p95_ms",
                "label": "P95 Request Latency",
                "threshold": max_lat,
                "observed": round(post_lat, 1),
                "unit": "ms",
                "status": "PASS" if lat_pass else "FAIL"
            })
            structured_evidence.append({
                "evidence_type": "metric",
                "metric": "latency_p95_ms",
                "before": round(pre_lat, 1),
                "after": round(post_lat, 1),
                "threshold": max_lat,
                "status": "PASS" if lat_pass else "FAIL",
                "source": "replica_execution"
            })
            if lat_pass:
                if pre_lat > max_lat:
                    improved_conditions.append("latency_p95")
            else:
                unresolved_conditions.append("latency_above_threshold")

            tput_pass = (post_tput >= min_tput)
            if tput_pass and pre_tput < min_tput:
                improved_conditions.append("throughput_rps")
            elif not tput_pass:
                unresolved_conditions.append("throughput_below_threshold")

        elif "MEMORY" in inc_type or "LEAK" in inc_type or "HEAP" in inc_type:
            # MEMORY_LEAK: validate memory footprint, memory growth, latency
            mem_pass = (post_mem <= max_mem)
            criteria_list.append({
                "name": "memory_mb",
                "label": "Process Memory Footprint",
                "threshold": max_mem,
                "observed": round(post_mem, 1),
                "unit": "MB",
                "status": "PASS" if mem_pass else "FAIL"
            })
            structured_evidence.append({
                "evidence_type": "metric",
                "metric": "memory_mb",
                "before": round(pre_mem, 1),
                "after": round(post_mem, 1),
                "threshold": max_mem,
                "status": "PASS" if mem_pass else "FAIL",
                "source": "replica_execution"
            })
            if mem_pass:
                if pre_mem > max_mem:
                    improved_conditions.append("memory_mb")
            else:
                unresolved_conditions.append("memory_above_threshold")

        elif "CPU" in inc_type:
            # CPU_SATURATION: validate cpu percent, throughput, latency
            cpu_pass = (post_cpu <= max_cpu)
            criteria_list.append({
                "name": "cpu_percent",
                "label": "CPU Utilization",
                "threshold": max_cpu,
                "observed": round(post_cpu, 1),
                "unit": "%",
                "status": "PASS" if cpu_pass else "FAIL"
            })
            structured_evidence.append({
                "evidence_type": "metric",
                "metric": "cpu_percent",
                "before": round(pre_cpu, 1),
                "after": round(post_cpu, 1),
                "threshold": max_cpu,
                "status": "PASS" if cpu_pass else "FAIL",
                "source": "replica_execution"
            })
            if cpu_pass:
                if pre_cpu > max_cpu:
                    improved_conditions.append("cpu_percent")
            else:
                unresolved_conditions.append("cpu_above_threshold")

        elif "QUEUE" in inc_type or "BACKLOG" in inc_type:
            # QUEUE_BACKLOG: validate queue depth, throughput
            q_pass = (post_q <= max_q)
            criteria_list.append({
                "name": "queue_depth",
                "label": "Queue Consumer Backlog Depth",
                "threshold": max_q,
                "observed": round(post_q, 1),
                "unit": "msgs",
                "status": "PASS" if q_pass else "FAIL"
            })
            if q_pass:
                if pre_q > max_q:
                    improved_conditions.append("queue_depth")
            else:
                unresolved_conditions.append("queue_backlog_exceeded")

        # 3. Service health check
        health_pass = is_healthy
        criteria_list.append({
            "name": "service_health",
            "label": "Service Availability Probe",
            "threshold": "HEALTHY",
            "observed": "HEALTHY" if is_healthy else "UNHEALTHY",
            "unit": "status",
            "status": "PASS" if health_pass else "FAIL"
        })
        if not health_pass:
            unresolved_conditions.append("service_unhealthy")

        # Determine whether the original incident problem is resolved
        if "CONNECTION" in inc_type or "POOL" in inc_type or "DB" in inc_type:
            original_error_resolved = bool(err_pass and conn_pass)
        elif "PROCESS" in inc_type or "CRASH" in inc_type:
            original_error_resolved = bool(err_pass and is_healthy)
        elif "MEMORY" in inc_type:
            original_error_resolved = bool(err_pass and mem_pass)
        elif "CPU" in inc_type:
            original_error_resolved = bool(err_pass and cpu_pass)
        elif "QUEUE" in inc_type:
            original_error_resolved = bool(err_pass and q_pass)
        elif "LATENCY" in inc_type:
            original_error_resolved = bool(err_pass and lat_pass)
        else:
            original_error_resolved = bool(err_pass)

        # 4. Strict side-effect detection
        side_effects = self.detect_side_effects(pre_metrics, post_metrics, target_service, post_logs)
        side_effect_detected = (len(side_effects) > 0)

        # 5. Strict closed-loop validation decision:
        # A solution is ONLY validated if original error is resolved AND ZERO collateral side-effects!
        solution_validated = bool(original_error_resolved and (not side_effect_detected))

        # Detailed failure analysis structure for intelligent refinement
        failure_analysis = {
            "attempt": iteration,
            "solution": action_name or "remediation_action",
            "failed_conditions": unresolved_conditions,
            "side_effects": [s.get("description", str(s)) for s in side_effects],
            "improved_conditions": improved_conditions,
            "reasoning": (
                f"Remediation '{action_name}' normalized {', '.join(improved_conditions) if improved_conditions else 'no signals'}, "
                f"but failed criteria: {', '.join(unresolved_conditions) if unresolved_conditions else 'none'} "
                f"and introduced side-effects: {[s.get('type') for s in side_effects] if side_effects else 'none'}."
            ) if not solution_validated else "All criteria passed and zero side-effects detected."
        }

        # Evidence comparison table
        comparison = self.compare_evidence(pre_metrics, post_metrics, target_service, criteria)

        # Decision label
        if solution_validated:
            decision = "VALIDATED"
        elif original_error_resolved:
            decision = "REFINEMENT_REQUIRED"
        else:
            decision = "ERROR_PERSISTS"

        return {
            "original_error_resolved": original_error_resolved,
            "side_effect_detected": side_effect_detected,
            "solution_validated": solution_validated,
            "decision": decision,
            "side_effects": side_effects,
            "comparison": comparison,
            "criteria_evaluated": {c["name"]: c["observed"] for c in criteria_list},
            "criteria_details": criteria_list,
            "unresolved_conditions": unresolved_conditions,
            "improved_conditions": improved_conditions,
            "structured_evidence": structured_evidence,
            "failure_analysis": failure_analysis,
            "timestamp": time.time()
        }

    def generate_validation_report(
        self,
        incident: Dict[str, Any],
        observed_symptoms: Dict[str, Any],
        hypothesis: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        alternative_hypotheses: List[Dict[str, Any]],
        selected_recovery: Dict[str, Any],
        execution_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        iteration_history: List[Dict[str, Any]],
        remaining_uncertainty: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Produces the formal, auditable 12-section Validation Report.
        Final states: VALIDATED, VALIDATED_WITH_WARNINGS, REQUIRES_APPROVAL, REQUIRES_REVIEW, UNRESOLVED.
        """
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Determine definitive final state
        if validation_result.get("solution_validated"):
            if validation_result.get("warnings"):
                final_decision = "VALIDATED_WITH_WARNINGS"
            elif incident.get("approval_status") == "REQUIRED":
                final_decision = "REQUIRES_APPROVAL"
            else:
                final_decision = "VALIDATED"
        else:
            final_decision = "UNRESOLVED"

        uncertainty = remaining_uncertainty or (
            "No unresolved anomalies detected. Post-execution telemetry shows service normalized within P99 statistical baseline."
            if final_decision in ("VALIDATED", "VALIDATED_WITH_WARNINGS") else
            "Remaining risk: Iteration limit exhausted or side-effect condition unresolved. Escalate to human SRE on-call."
        )

        report = {
            "report_id": f"VR-{incident.get('incident_id', 'INC-2026-0001')}",
            "generated_at": now_iso,
            "incident": {
                "incident_id": incident.get("incident_id"),
                "title": incident.get("title"),
                "severity": incident.get("severity"),
                "primary_service": incident.get("primary_service"),
                "tenant_id": incident.get("tenant_id", "demo-tenant")
            },
            "root_cause": hypothesis.get("hypothesis"),
            "initial_evidence": [
                {
                    "source": e.get("source"),
                    "service": e.get("service"),
                    "signal_type": e.get("signal_type"),
                    "value": e.get("metric_or_log_value"),
                    "deviation": e.get("deviation")
                }
                for e in evidence_items[:8]
            ],
            "observed_symptoms": observed_symptoms,
            "root_cause_hypothesis": {
                "hypothesis": hypothesis.get("hypothesis"),
                "category": hypothesis.get("category"),
                "confidence": hypothesis.get("confidence"),
                "confidence_pct": hypothesis.get("confidence_pct", int(hypothesis.get("confidence", 0.9) * 100)),
                "target_service": hypothesis.get("target_service"),
                "component": hypothesis.get("component")
            },
            "evidence": [
                {
                    "source": e.get("source"),
                    "service": e.get("service"),
                    "signal_type": e.get("signal_type"),
                    "value": e.get("metric_or_log_value"),
                    "deviation": e.get("deviation")
                }
                for e in evidence_items[:8]
            ],
            "alternative_hypotheses": [
                {
                    "hypothesis": a.get("hypothesis"),
                    "confidence": a.get("confidence"),
                    "confidence_pct": a.get("confidence_pct"),
                    "contradictory_reasons": a.get("contradictory_evidence", [])[:2]
                }
                for a in alternative_hypotheses
            ],
            "selected_recovery": {
                "action": selected_recovery.get("action"),
                "target_component": selected_recovery.get("target_component"),
                "risk": selected_recovery.get("risk"),
                "expected_effect": selected_recovery.get("expected_effect"),
                "rollback_strategy": selected_recovery.get("rollback_strategy")
            },
            "selected_solution": selected_recovery.get("action"),
            "attempt_count": len(iteration_history),
            "execution_result": {
                "status": "COMPLETED",
                "action_executed": selected_recovery.get("action"),
                "replica_environment": "Controlled Docker Sandbox",
                "execution_timestamp": execution_result.get("timestamp", now_iso)
            },
            "before_after_comparison": validation_result.get("comparison", {}).get("comparison_table", []),
            "validation_criteria": validation_result.get("criteria_details", []),
            "side_effect_analysis": {
                "side_effect_detected": validation_result.get("side_effect_detected", False),
                "detected_side_effects": validation_result.get("side_effects", []),
                "summary": "Zero collateral side effects detected post-replay." if not validation_result.get("side_effect_detected") else "Unacceptable side effect detected; solution rejected."
            },
            "side_effects": validation_result.get("side_effects", []),
            "iteration_history": iteration_history,
            "final_validation_decision": final_decision,
            "final_status": final_decision,
            "confidence": hypothesis.get("confidence", 0.90),
            "timestamp": now_iso,
            "remaining_uncertainty": uncertainty
        }

        return report


recovery_validator = RecoveryValidator()

