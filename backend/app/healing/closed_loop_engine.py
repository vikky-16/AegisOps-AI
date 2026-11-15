"""
AegisOps AI - Closed-Loop Recovery Validation Orchestrator
Coordinates the 14-state Incident lifecycle state machine, replica execution,
scenario replay, pre/post evidence comparison, side-effect detection, solution refinement,
and historical memory indexing.
"""

import time
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.ai.anomaly_engine import anomaly_engine
from backend.app.rca.hypothesis_engine import hypothesis_engine
from backend.app.healing.solution_generator import solution_generator
from backend.app.replica.controlled_environment import replica_environment
from backend.app.validation.validator import recovery_validator
from backend.app.knowledge.incident_memory import incident_memory
from backend.app.models.incident import Incident, IncidentAttempt
from backend.app.models.evidence import EvidenceItem
from backend.app.core.database import AsyncSessionLocal


LIFECYCLE_STATES = [
    "INCIDENT_DETECTED",
    "DETECTED",
    "EVIDENCE_COLLECTED",
    "CLASSIFIED",
    "RCA_COMPLETED",
    "SOLUTIONS_GENERATED",
    "SOLUTION_SELECTED",
    "REPLICA_PREPARED",
    "REPLICA_EXECUTION",
    "SOLUTION_EXECUTED",
    "SCENARIO_REPLAY",
    "SCENARIO_REPLAYED",
    "POST_EXECUTION_ANALYSIS",
    "EVIDENCE_COMPARED",
    "VALIDATION",
    "VALIDATING",
    "SIDE_EFFECT_ANALYSIS",
    "REFINEMENT",
    "REFINEMENT_REQUIRED",
    "RETRY",
    "VALIDATED",
    "UNRESOLVED"
]


class ClosedLoopValidationEngine:
    """Central engine executing the closed-loop recovery validation lifecycle."""

    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations

    def record_transition(
        self,
        incident: Dict[str, Any],
        to_state: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records a timestamped state transition in the incident's state machine."""
        now_ts = time.time()
        now_str = time.strftime("%H:%M:%S", time.localtime(now_ts))
        
        from_state = incident.get("lifecycle_state", "INCIDENT_DETECTED")
        transition_record = {
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": now_ts,
            "time_str": now_str,
            "reason": reason,
            "metadata": metadata or {}
        }

        transitions = incident.setdefault("state_transitions", [])
        transitions.append(transition_record)
        incident["lifecycle_state"] = to_state
        incident["status"] = to_state  # Synchronize with legacy status field

        # Timeline event formatted as "12:04:01 anomaly detected"
        incident.setdefault("timeline", []).append({
            "timestamp": now_str,
            "event": f"{to_state.lower().replace('_', ' ')}",
            "message": reason,
            "phase": to_state
        })

        return transition_record

    async def execute_closed_loop(
        self,
        scenario_id: str = "db_connection_exhaustion",
        incident_id: Optional[str] = None,
        tenant_id: str = "demo-tenant",
        forced_first_action: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the full end-to-end closed-loop recovery validation cycle:
        1. INCIDENT_DETECTED: Error occurs
        2. EVIDENCE_COLLECTED: Collects pre-fix evidence (metrics, logs, traces)
        3. CLASSIFIED: Categorizes error
        4. RCA_COMPLETED: Root-cause analysis & confidence estimation
        5. SOLUTIONS_GENERATED: Generates multiple candidate solutions
        6. SOLUTION_SELECTED: Selects concrete candidate
        7. REPLICA_EXECUTION: Prepares & applies solution in isolated sandbox
        8. SCENARIO_REPLAY: Replays original error scenario
        9. POST_EXECUTION_ANALYSIS: Collects post-fix evidence
        10. VALIDATION: Incident-specific criteria evaluation
        11. SIDE_EFFECT_ANALYSIS: Collateral regression detection
        12. REFINEMENT & RETRY: If failed, re-ranks remaining candidates based on failure analysis
        13. VALIDATED / UNRESOLVED: Generates report and indexes verified memory
        """
        inc_id = incident_id or f"INC-VAL-{uuid.uuid4().hex[:8].upper()}"
        scen = replica_environment.get_scenario(scenario_id) or replica_environment.get_scenario("db_connection_exhaustion")
        target_service = scen["target_service"]

        # 1. State: DETECTED & INCIDENT_DETECTED
        incident_data: Dict[str, Any] = {
            "incident_id": inc_id,
            "title": f"{scen['name']} on {target_service}",
            "description": scen["ground_truth_root_cause"],
            "severity": "CRITICAL",
            "primary_service": target_service,
            "tenant_id": tenant_id,
            "scenario_id": scenario_id,
            "lifecycle_state": "DETECTED",
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "state_transitions": [],
            "timeline": [],
            "execution_history": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.record_transition(incident_data, "DETECTED", f"Error anomaly detected on {target_service} matching scenario {scenario_id}")
        self.record_transition(incident_data, "INCIDENT_DETECTED", f"Incident confirmed on {target_service}")

        # Inject fault into replica to produce initial failure telemetry
        fault_bundle = replica_environment.inject_fault(scenario_id)
        pre_metrics = fault_bundle["service_metrics"]
        pre_logs = fault_bundle["error_logs"]

        # 2. State: EVIDENCE_COLLECTED
        anomaly_res = anomaly_engine.evaluate_telemetry_snapshot(
            incident_id=inc_id,
            service_metrics=pre_metrics,
            logs=pre_logs,
            iteration=0,
            before_after_state="BEFORE",
            tenant_id=tenant_id
        )
        pre_evidence = anomaly_res["evidence_items"]
        self.record_transition(
            incident_data,
            "EVIDENCE_COLLECTED",
            f"Collected {len(pre_evidence)} telemetry evidence items across {len(anomaly_res['services_affected'])} services using Z-score and Isolation Forest",
            {"evidence_count": len(pre_evidence)}
        )

        # 3. State: CLASSIFIED
        self.record_transition(
            incident_data,
            "CLASSIFIED",
            f"Categorized incident as {scenario_id.upper()} on component {scen['target_component']}"
        )

        # 4. State: RCA_COMPLETED
        rca_res = hypothesis_engine.evaluate_hypotheses(
            evidence_items=pre_evidence,
            affected_services=anomaly_res["services_affected"]
        )
        primary_hyp = rca_res["primary_hypothesis"]
        alt_hyps = rca_res["alternative_hypotheses"]
        incident_data["hypotheses"] = rca_res
        incident_data["root_cause"] = primary_hyp["hypothesis"]
        incident_data["rca_confidence"] = primary_hyp["confidence"]
        self.record_transition(
            incident_data,
            "RCA_COMPLETED",
            f"Primary hypothesis identified: '{primary_hyp['hypothesis']}' ({primary_hyp['confidence_pct']}% confidence). {rca_res['why_selected'][:120]}...",
            {"primary_hypothesis": primary_hyp["hypothesis"], "confidence": primary_hyp["confidence"]}
        )

        # 5. State: SOLUTIONS_GENERATED
        candidate_solutions = solution_generator.generate_candidate_solutions(
            hypothesis=primary_hyp,
            scenario_id=scenario_id,
            tenant_id=tenant_id
        )
        incident_data["candidate_solutions"] = candidate_solutions
        self.record_transition(
            incident_data,
            "SOLUTIONS_GENERATED",
            f"Generated {len(candidate_solutions)} candidate recovery solutions with risk and rollback strategies"
        )

        # -------------------------------------------------------------
        # ITERATION & EVIDENCE-DRIVEN REFINEMENT LOOP (up to max_iterations)
        # -------------------------------------------------------------
        iteration = 0
        validation_passed = False
        final_validation_result: Dict[str, Any] = {}
        execution_history: List[Dict[str, Any]] = []

        # Maintain available candidates for refinement
        remaining_candidates = list(candidate_solutions)

        # If a specific action was forced for testing (e.g. forced bad action to test side effect)
        if forced_first_action and remaining_candidates:
            matched = next((c for c in remaining_candidates if c["action"] == forced_first_action), None)
            if matched:
                remaining_candidates.remove(matched)
                remaining_candidates.insert(0, matched)
            else:
                remaining_candidates.insert(0, {
                    "id": f"sol_{forced_first_action.lower()}",
                    "action": forced_first_action,
                    "target_component": f"{target_service}:{scen['target_component']}",
                    "expected_effect": f"Apply forced action {forced_first_action}",
                    "risk": "HIGH",
                    "prerequisites": [],
                    "rollback_strategy": "Rollback",
                    "confidence": 0.50
                })

        while iteration < self.max_iterations and not validation_passed:
            iteration += 1
            incident_data["iteration_count"] = iteration

            if not remaining_candidates:
                # No more solutions to try!
                break

            # 6. State: SOLUTION_SELECTED
            selected_solution = remaining_candidates.pop(0)
            incident_data["selected_solution"] = selected_solution
            action_name = selected_solution["action"]
            solution_id = selected_solution.get("id", f"sol_{action_name.lower()}")
            attempt_id = f"ATT-{inc_id[-8:]}-{iteration}"

            self.record_transition(
                incident_data,
                "SOLUTION_SELECTED",
                f"[Iteration {iteration}/{self.max_iterations}] Selected candidate solution: {action_name} (Confidence: {int(selected_solution.get('confidence', 0.8)*100)}%, Risk: {selected_solution.get('risk')})",
                {"solution_id": solution_id, "action": action_name, "iteration": iteration, "attempt_id": attempt_id}
            )

            # 7. State: REPLICA_PREPARED & REPLICA_EXECUTION
            replica_prep = replica_environment.prepare_replica(scenario_id)
            self.record_transition(
                incident_data,
                "REPLICA_PREPARED",
                f"Prepared isolated Docker sandbox {replica_prep['replica_id']}"
            )
            self.record_transition(
                incident_data,
                "REPLICA_EXECUTION",
                f"Applying recovery action '{action_name}' to component {selected_solution['target_component']} in replica"
            )

            # 8. State: SOLUTION_EXECUTED & SCENARIO_REPLAY
            replay_output = replica_environment.execute_solution_and_replay(
                scenario_id=scenario_id,
                action=action_name,
                iteration=iteration
            )
            self.record_transition(
                incident_data,
                "SOLUTION_EXECUTED",
                f"Recovery action '{action_name}' applied in replica container"
            )
            self.record_transition(
                incident_data,
                "SCENARIO_REPLAYED",
                f"Replayed identical failure workload against replica; capturing post-fix execution evidence"
            )
            self.record_transition(
                incident_data,
                "SCENARIO_REPLAY",
                f"Workload replay completed; collecting post-execution telemetry"
            )

            # 9. State: EVIDENCE_COMPARED & POST_EXECUTION_ANALYSIS
            post_metrics = replay_output["post_metrics"]
            post_logs = replay_output["post_logs"]
            
            # Extract post-evidence items
            post_anomaly_res = anomaly_engine.evaluate_telemetry_snapshot(
                incident_id=inc_id,
                service_metrics=post_metrics,
                logs=post_logs,
                iteration=iteration,
                before_after_state="AFTER",
                tenant_id=tenant_id
            )
            post_evidence = post_anomaly_res["evidence_items"]

            self.record_transition(
                incident_data,
                "EVIDENCE_COMPARED",
                f"Comparing pre-fix and post-fix evidence: error rate, latency, throughput, CPU, memory, DB connections"
            )
            self.record_transition(
                incident_data,
                "POST_EXECUTION_ANALYSIS",
                f"Post-execution telemetry analysis completed across {len(post_evidence)} evidence signals"
            )

            # 10. State: VALIDATING & VALIDATION (Incident-specific criteria)
            self.record_transition(
                incident_data,
                "VALIDATING",
                f"Evaluating whether original error resolved and checking for unacceptable side effects"
            )
            self.record_transition(
                incident_data,
                "VALIDATION",
                f"Evaluating incident-specific criteria for {scenario_id.upper()} on {target_service}"
            )

            val_res = recovery_validator.validate_solution(
                target_service=target_service,
                pre_metrics=pre_metrics,
                post_metrics=post_metrics,
                success_criteria=scen["success_criteria"],
                post_logs=post_logs,
                incident_type=scenario_id,
                scenario_id=scenario_id,
                action_name=action_name,
                iteration=iteration
            )
            final_validation_result = val_res

            # Structured Attempt Record with all 14 required fields
            attempt_record = {
                "attempt_id": attempt_id,
                "incident_id": inc_id,
                "iteration": iteration,
                "solution_id": solution_id,
                "solution_tested": selected_solution,
                "action": action_name,
                "target_component": selected_solution.get("target_component"),
                "timestamp": time.time(),
                "pre_execution_metrics": pre_metrics,
                "post_execution_metrics": post_metrics,
                "execution_logs": post_logs,
                "execution_result": replay_output.get("execution_result", {"status": "SUCCESS", "action": action_name}),
                "validation_result": val_res,
                "original_error_resolved": val_res["original_error_resolved"],
                "side_effect_detected": val_res["side_effect_detected"],
                "solution_validated": val_res["solution_validated"],
                "decision": val_res["decision"],
                "unresolved_conditions": val_res.get("unresolved_conditions", []),
                "side_effects": val_res.get("side_effects", []),
                "improved_conditions": val_res.get("improved_conditions", []),
                "comparison_table": val_res["comparison"]["comparison_table"],
                "confidence": selected_solution.get("confidence", 0.8),
                "reasoning": val_res.get("failure_analysis", {}).get("reasoning", ""),
                "next_action": "VALIDATED" if val_res["solution_validated"] else ("RETRY_NEXT_CANDIDATE" if (iteration < self.max_iterations and remaining_candidates) else "UNRESOLVED_ESCALATE")
            }
            execution_history.append(attempt_record)
            incident_data["execution_history"] = execution_history

            # 11. State: VALIDATED or SIDE_EFFECT_ANALYSIS -> REFINEMENT_REQUIRED / REFINEMENT -> RETRY
            if val_res["solution_validated"]:
                validation_passed = True
                self.record_transition(
                    incident_data,
                    "VALIDATED",
                    f"Solution '{action_name}' VALIDATED! Original error resolved and ZERO side effects detected.",
                    {"decision": "VALIDATED", "attempt_id": attempt_id}
                )

                # Generate comprehensive Validation Report
                report = recovery_validator.generate_validation_report(
                    incident=incident_data,
                    observed_symptoms=scen["expected_symptoms"],
                    hypothesis=primary_hyp,
                    evidence_items=pre_evidence,
                    alternative_hypotheses=alt_hyps,
                    selected_recovery=selected_solution,
                    execution_result={"timestamp": time.time(), "action": action_name},
                    validation_result=val_res,
                    iteration_history=execution_history
                )
                incident_data["validation_report"] = report

                # Store verified result in Historical Incident Memory
                try:
                    failed_sols = [att["action"] for att in execution_history if not att["solution_validated"]]
                    all_side_effects = [s for att in execution_history for s in att.get("side_effects", [])]
                    incident_memory.record_incident({
                        "tenant_id": tenant_id,
                        "incident_id": inc_id,
                        "root_cause_service": target_service,
                        "remediation_action": action_name,
                        "success": True,
                        "failure_signature": {
                            "scenario": scenario_id,
                            "symptoms": list(scen["expected_symptoms"].keys())
                        },
                        "incident_type": scenario_id,
                        "root_cause": primary_hyp["hypothesis"],
                        "evidence": [e.get("metric_or_log_value") for e in pre_evidence[:6]],
                        "successful_solution": action_name,
                        "failed_solutions": failed_sols,
                        "side_effects": all_side_effects,
                        "validation_metrics": val_res["comparison"]["comparison_table"],
                        "number_of_attempts": iteration,
                        "final_outcome": "VALIDATED"
                    }, tenant_id=tenant_id)
                except Exception:
                    pass

            else:
                # Validation failed! (Either original error persisted, or side effect occurred)
                if val_res["side_effect_detected"]:
                    self.record_transition(
                        incident_data,
                        "SIDE_EFFECT_ANALYSIS",
                        f"Detected {len(val_res['side_effects'])} collateral side effect(s) post-execution: {', '.join([s.get('type') for s in val_res['side_effects']])}",
                        {"side_effects": val_res["side_effects"]}
                    )

                if iteration < self.max_iterations and remaining_candidates:
                    # Intelligently refine and re-rank remaining candidates using failure evidence
                    remaining_candidates = solution_generator.refine_and_rerank_solutions(
                        remaining_candidates=remaining_candidates,
                        failure_analysis=val_res.get("failure_analysis", {}),
                        incident_type=scenario_id,
                        target_service=target_service,
                        tenant_id=tenant_id
                    )

                    next_candidate = remaining_candidates[0]
                    self.record_transition(
                        incident_data,
                        "REFINEMENT_REQUIRED",
                        f"[Attempt {iteration} Failed] Failure condition or collateral side effect detected; refinement required."
                    )
                    self.record_transition(
                        incident_data,
                        "REFINEMENT",
                        f"[Attempt {iteration} Failed] {val_res.get('failure_analysis', {}).get('reasoning')[:140]}... "
                        f"Refined rankings: penalized '{action_name}', promoted '{next_candidate['action']}' ({int(next_candidate['confidence']*100)}% confidence).",
                        {"failure_analysis": val_res.get("failure_analysis", {}), "reranked_candidates": [c["action"] for c in remaining_candidates]}
                    )

                    self.record_transition(
                        incident_data,
                        "RETRY",
                        f"Queuing alternative candidate '{next_candidate['action']}' for execution in replica Sandbox."
                    )
                else:
                    # Maximum iterations reached!
                    self.record_transition(
                        incident_data,
                        "UNRESOLVED",
                        f"Maximum iteration limit ({self.max_iterations}) reached without safe resolution. Escalating to human SRE.",
                        {"side_effects": val_res.get("side_effects", [])}
                    )
                    incident_data["unresolved_explanation"] = (
                        f"AegisOps AI evaluated {iteration} candidate recovery attempts across isolated replicas. "
                        f"All candidate solutions either failed to eliminate the root cause symptoms or generated unacceptable "
                        f"collateral side effects ({', '.join([s.get('description', '') for s in val_res.get('side_effects', [])])}). "
                        f"In accordance with safety invariants, autonomous remediation was rejected."
                    )
                    # Generate report explaining failure
                    report = recovery_validator.generate_validation_report(
                        incident=incident_data,
                        observed_symptoms=scen["expected_symptoms"],
                        hypothesis=primary_hyp,
                        evidence_items=pre_evidence,
                        alternative_hypotheses=alt_hyps,
                        selected_recovery=selected_solution,
                        execution_result={"timestamp": time.time(), "action": action_name},
                        validation_result=val_res,
                        iteration_history=execution_history,
                        remaining_uncertainty=incident_data["unresolved_explanation"]
                    )
                    incident_data["validation_report"] = report

        # Persist incident, evidence, and attempts in Database asynchronously if session available
        try:
            async with AsyncSessionLocal() as session:
                new_inc = Incident(
                    incident_id=incident_data["incident_id"],
                    title=incident_data["title"],
                    description=incident_data["description"],
                    severity=incident_data["severity"],
                    status=incident_data["lifecycle_state"],
                    lifecycle_state=incident_data["lifecycle_state"],
                    primary_service=incident_data["primary_service"],
                    affected_services_json=json.dumps(anomaly_res.get("services_affected", [target_service])),
                    affected_dependencies_json=json.dumps(rca_res.get("dependency_path", [])),
                    error_rate=float(scen["expected_symptoms"].get("error_rate", 0.85)),
                    root_cause=incident_data.get("root_cause"),
                    root_cause_service=target_service,
                    root_cause_confidence=float(incident_data.get("rca_confidence", 0.9)),
                    rca_confidence=float(incident_data.get("rca_confidence", 0.9)),
                    recommended_action=incident_data.get("selected_solution", {}).get("action"),
                    state_transitions_json=json.dumps(incident_data.get("state_transitions", [])),
                    hypotheses_json=json.dumps(incident_data.get("hypotheses", {})),
                    candidate_solutions_json=json.dumps(incident_data.get("candidate_solutions", [])),
                    selected_solution_json=json.dumps(incident_data.get("selected_solution", {})),
                    iteration_count=incident_data.get("iteration_count", 0),
                    max_iterations=incident_data.get("max_iterations", 3),
                    scenario_id=scenario_id,
                    execution_history_json=json.dumps(incident_data.get("execution_history", [])),
                    validation_report_json=json.dumps(incident_data.get("validation_report", {})),
                    side_effects_detected_json=json.dumps(final_validation_result.get("side_effects", [])),
                    unresolved_explanation=incident_data.get("unresolved_explanation"),
                    timeline_json=json.dumps(incident_data.get("timeline", [])),
                    tenant_id=tenant_id
                )
                session.add(new_inc)

                # Persist Evidence items with structured metric values
                for ev in pre_evidence:
                    db_ev = EvidenceItem(
                        incident_id=inc_id,
                        timestamp=ev.get("timestamp", time.time()),
                        source=ev.get("source", "detector"),
                        service=ev.get("service", target_service),
                        component=ev.get("component", "system"),
                        signal_type=ev.get("signal_type", "METRIC"),
                        evidence_type=ev.get("signal_type", "metric").lower(),
                        metric_name=ev.get("component", "metric"),
                        metric_or_log_value=str(ev.get("metric_or_log_value", "")),
                        baseline=str(ev.get("baseline", "")),
                        deviation=str(ev.get("deviation", "")),
                        correlation_info_json=json.dumps(ev.get("correlation_info", {})),
                        execution_iteration=0,
                        before_after_state="BEFORE",
                        status="PASS",
                        tenant_id=tenant_id
                    )
                    session.add(db_ev)

                # Persist dedicated IncidentAttempt records
                for att in execution_history:
                    db_att = IncidentAttempt(
                        attempt_id=att["attempt_id"],
                        incident_id=inc_id,
                        iteration=att["iteration"],
                        solution_id=att.get("solution_id"),
                        action=att["action"],
                        target_component=att.get("target_component"),
                        timestamp=att.get("timestamp", time.time()),
                        pre_execution_metrics_json=json.dumps(att.get("pre_execution_metrics", {})),
                        post_execution_metrics_json=json.dumps(att.get("post_execution_metrics", {})),
                        execution_logs_json=json.dumps(att.get("execution_logs", [])),
                        execution_result_json=json.dumps(att.get("execution_result", {})),
                        validation_result_json=json.dumps(att.get("validation_result", {})),
                        original_error_resolved=att.get("original_error_resolved", False),
                        side_effect_detected=att.get("side_effect_detected", False),
                        solution_validated=att.get("solution_validated", False),
                        unresolved_conditions_json=json.dumps(att.get("unresolved_conditions", [])),
                        side_effects_json=json.dumps(att.get("side_effects", [])),
                        improved_conditions_json=json.dumps(att.get("improved_conditions", [])),
                        confidence=float(att.get("confidence", 0.8)),
                        reasoning=att.get("reasoning"),
                        next_action=att.get("next_action", "VALIDATED"),
                        tenant_id=tenant_id
                    )
                    session.add(db_att)

                await session.commit()
        except Exception as exc:
            pass

        return incident_data


closed_loop_engine = ClosedLoopValidationEngine()
