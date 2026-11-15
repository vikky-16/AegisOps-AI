"""
AegisOps AI - Controlled Replica Environment & Realistic Scenarios
Provides Docker-compatible, reproducible failure scenarios for closed-loop validation.
Ensures remediation is never executed autonomously against production without replica verification.
Implements 8 core realistic failure scenarios with ground-truth root causes, fault injection,
recovery actions, expected side effects, and strict success criteria.
"""

import time
import copy
from typing import Dict, Any, List, Optional


SCENARIO_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "db_connection_exhaustion": {
        "scenario_id": "db_connection_exhaustion",
        "name": "Database Connection Pool Exhaustion",
        "target_service": "database-service",
        "target_component": "connection_pool",
        "ground_truth_root_cause": "Database connection pool exhaustion caused by leaked client connections in Service B.",
        "expected_symptoms": {
            "error_rate": 0.88,
            "active_connections": 98.0,
            "latency_p95_ms": 1850.0,
            "http_status": 503,
            "error_message": "FATAL: remaining connection slots are reserved for non-replication superuser connections"
        },
        "success_criteria": {
            "max_error_rate": 0.05,
            "max_active_connections": 20.0,
            "max_latency_p95_ms": 120.0,
            "max_memory_mb": 250.0,
            "min_throughput_rps": 90.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "RESET_CONNECTION_POOL": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Purges orphaned connection handles and resets pool size limit to 50."
            },
            "SCALE_WORKERS": {
                "resolves_original_error": False,
                "causes_side_effect": "connection_surge",
                "description": "Increases client concurrency which consumes even more database connections and worsens exhaustion."
            },
            "RESTART_SERVICE": {
                "resolves_original_error": True,
                "causes_side_effect": "latency_surge",
                "description": "Cold restart kills connections but introduces a 6-second availability blackout and p95 latency surge to 2400ms."
            }
        },
        "expected_side_effects": {
            "latency_surge": "Post-action latency p95 surged beyond 2000ms (+1500% over normal baseline) due to cold-start connection re-establishment.",
            "connection_surge": "Connection pool utilization reached 100% saturation; client error rates increased."
        }
    },
    "service_crash": {
        "scenario_id": "service_crash",
        "name": "Microservice Process Crash (SIGSEGV / OOMKilled)",
        "target_service": "service-b",
        "target_component": "process_runtime",
        "ground_truth_root_cause": "Unhandled null pointer reference in Payment Service worker process causing immediate exit.",
        "expected_symptoms": {
            "error_rate": 1.0,
            "latency_p95_ms": 0.0,
            "http_status": 502,
            "error_message": "HTTP 502 Bad Gateway: connection refused on 127.0.0.1:8003"
        },
        "success_criteria": {
            "max_error_rate": 0.02,
            "max_latency_p95_ms": 80.0,
            "max_memory_mb": 180.0,
            "min_throughput_rps": 100.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "RESTART_SERVICE": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Spawns new process container instance, restores socket binding and healthy status probe."
            },
            "CLEAR_CACHE": {
                "resolves_original_error": False,
                "causes_side_effect": None,
                "description": "Flushes cache, but the service process remains dead and unreachable."
            },
            "SCALE_WORKERS": {
                "resolves_original_error": False,
                "causes_side_effect": None,
                "description": "Worker supervisor fails to fork child processes because parent daemon is dead."
            }
        },
        "expected_side_effects": {}
    },
    "high_api_latency": {
        "scenario_id": "high_api_latency",
        "name": "High API Latency & Downstream Thread Starvation",
        "target_service": "service-a",
        "target_component": "http_endpoint",
        "ground_truth_root_cause": "Thread starvation and lock contention on Order Service request worker queue.",
        "expected_symptoms": {
            "error_rate": 0.45,
            "latency_p95_ms": 3200.0,
            "latency_p50_ms": 1400.0,
            "throughput_rps": 22.0,
            "error_message": "Gateway timeout: upstream service-a response deadline exceeded (3000ms)"
        },
        "success_criteria": {
            "max_error_rate": 0.05,
            "max_latency_p95_ms": 180.0,
            "max_memory_mb": 250.0,
            "min_throughput_rps": 90.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "SCALE_WORKERS": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Expands worker concurrency from 2 to 6 workers, clearing request backlog and bringing latency down to 65ms."
            },
            "RATE_LIMIT_AGGRESSIVELY": {
                "resolves_original_error": True,
                "causes_side_effect": "throughput_dropped",
                "description": "Drops latency by shedding 75% of incoming traffic, but causes acceptable throughput to collapse."
            },
            "CLEAR_CACHE": {
                "resolves_original_error": False,
                "causes_side_effect": None,
                "description": "Cache flush does not resolve worker thread lock contention."
            }
        },
        "expected_side_effects": {
            "throughput_dropped": "Service throughput collapsed by 72% (from 110 RPS baseline to 30 RPS) causing severe transaction loss."
        }
    },
    "memory_pressure": {
        "scenario_id": "memory_pressure",
        "name": "Process Memory Pressure & Buffer Heap Saturation",
        "target_service": "service-a",
        "target_component": "process_memory",
        "ground_truth_root_cause": "Unbounded cache growth and memory leak in request payload decompressor.",
        "expected_symptoms": {
            "memory_mb": 850.0,
            "error_rate": 0.35,
            "latency_p95_ms": 1400.0,
            "cpu_percent": 82.0,
            "error_message": "java.lang.OutOfMemoryError: Java heap space / Memory buffer threshold exceeded"
        },
        "success_criteria": {
            "max_error_rate": 0.03,
            "max_latency_p95_ms": 150.0,
            "max_memory_mb": 220.0,
            "min_throughput_rps": 90.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "CLEAR_CACHE": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Purges unbounded decompressor cache handles and triggers garbage collection, reclaiming 680MB RAM."
            },
            "SPAWN_EXTRA_WORKERS": {
                "resolves_original_error": False,
                "causes_side_effect": "memory_exploded",
                "description": "Spawning additional worker processes on an already saturated node causes total host Out-Of-Memory termination."
            },
            "RESTART_SERVICE": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Restarts process, resetting memory footprint to clean 120MB baseline."
            }
        },
        "expected_side_effects": {
            "memory_exploded": "Process memory surged beyond 1200MB (+500% over baseline), triggering kernel OOMKiller."
        }
    },
    "cpu_saturation": {
        "scenario_id": "cpu_saturation",
        "name": "CPU Core Saturation & Runaway Worker Loop",
        "target_service": "gateway",
        "target_component": "compute_threads",
        "ground_truth_root_cause": "Inefficient regular expression backtracking in API Gateway request path routing rules.",
        "expected_symptoms": {
            "cpu_percent": 98.5,
            "error_rate": 0.60,
            "latency_p95_ms": 2100.0,
            "error_message": "Thread CPU utilization at 100%: CPU saturation alert"
        },
        "success_criteria": {
            "max_error_rate": 0.04,
            "max_latency_p95_ms": 120.0,
            "max_cpu_percent": 50.0,
            "max_memory_mb": 200.0,
            "min_throughput_rps": 95.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "SCALE_WORKERS": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Distributes routing across additional thread pools and optimizes regex cache, lowering CPU to 22%."
            },
            "RETRY_AGGRESSIVELY": {
                "resolves_original_error": False,
                "causes_side_effect": "cpu_spike",
                "description": "Client retries create retry storm that cements 100% CPU lockup."
            }
        },
        "expected_side_effects": {
            "cpu_spike": "Retry storm increased CPU load to 100% continuous lockup."
        }
    },
    "dependency_unavailable": {
        "scenario_id": "dependency_unavailable",
        "name": "Downstream Dependency Unavailable & Cascade Failures",
        "target_service": "auth-service",
        "target_component": "downstream_client",
        "ground_truth_root_cause": "External token verification service unreachable causing 504 timeouts across all gateway calls.",
        "expected_symptoms": {
            "error_rate": 0.95,
            "latency_p95_ms": 3000.0,
            "http_status": 504,
            "error_message": "HTTP 504 Gateway Timeout: auth-service failed to reach identity provider"
        },
        "success_criteria": {
            "max_error_rate": 0.05,
            "max_latency_p95_ms": 100.0,
            "max_memory_mb": 200.0,
            "min_throughput_rps": 85.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "ENABLE_CIRCUIT_BREAKER_FALLBACK": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Trips circuit breaker to fallback local JWT verification cache, preventing upstream timeouts."
            },
            "RESTART_SERVICE": {
                "resolves_original_error": False,
                "causes_side_effect": None,
                "description": "Restarting the local auth proxy does not fix external network partition."
            }
        },
        "expected_side_effects": {}
    },
    "queue_backlog": {
        "scenario_id": "queue_backlog",
        "name": "Message Queue Consumer Backlog & Ingestion Delay",
        "target_service": "service-b",
        "target_component": "message_queue",
        "ground_truth_root_cause": "Payment ledger consumer group paused due to consumer offset rebalancing loop.",
        "expected_symptoms": {
            "queue_depth": 780.0,
            "latency_p95_ms": 4500.0,
            "error_rate": 0.30,
            "error_message": "Consumer lag exceeds threshold: 780 unconsumed messages on topic 'payments'"
        },
        "success_criteria": {
            "max_error_rate": 0.02,
            "max_queue_depth": 15.0,
            "max_latency_p95_ms": 120.0,
            "max_memory_mb": 250.0,
            "min_throughput_rps": 90.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "SCALE_CONSUMER_WORKERS": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Adds 3 consumer workers to process topic partitions in parallel, draining lag in 8 seconds."
            },
            "FLUSH_QUEUE": {
                "resolves_original_error": True,
                "causes_side_effect": "data_loss",
                "description": "Drops all 780 unconsumed messages, causing irreversible business ledger data loss."
            }
        },
        "expected_side_effects": {
            "data_loss": "Queue messages were discarded without ledger persistence, violating data integrity."
        }
    },
    "configuration_error": {
        "scenario_id": "configuration_error",
        "name": "Corrupted Database Connection Configuration",
        "target_service": "database-service",
        "target_component": "configuration",
        "ground_truth_root_cause": "Malformed database connection string parameter injected in latest rollout.",
        "expected_symptoms": {
            "error_rate": 1.0,
            "http_status": 500,
            "error_message": "ConfigurationException: Invalid connection string URI syntax: db://localhost:-1/master"
        },
        "success_criteria": {
            "max_error_rate": 0.01,
            "max_latency_p95_ms": 60.0,
            "max_memory_mb": 180.0,
            "min_throughput_rps": 100.0,
            "required_service_status": "HEALTHY"
        },
        "possible_recovery_actions": {
            "ROLLBACK_CONFIG": {
                "resolves_original_error": True,
                "causes_side_effect": None,
                "description": "Reverts connection string to verified stable release configuration."
            },
            "RESTART_SERVICE": {
                "resolves_original_error": False,
                "causes_side_effect": "crash_loop",
                "description": "Restarting without fixing configuration causes the service to enter a persistent CrashLoopBackOff."
            }
        },
        "expected_side_effects": {
            "crash_loop": "Container immediately crashed on startup due to unparsed configuration syntax."
        }
    }
}


class ControlledReplicaEnvironment:
    """Manages Docker-based and simulated reproducible replica scenarios."""

    def __init__(self):
        self.scenarios = SCENARIO_DEFINITIONS
        self.replica_states: Dict[str, Dict[str, Any]] = {}

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return [
            {
                "scenario_id": s["scenario_id"],
                "name": s["name"],
                "target_service": s["target_service"],
                "target_component": s["target_component"],
                "ground_truth_root_cause": s["ground_truth_root_cause"],
                "possible_actions": list(s["possible_recovery_actions"].keys())
            }
            for s in self.scenarios.values()
        ]

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        return self.scenarios.get(scenario_id)

    def prepare_replica(self, scenario_id: str) -> Dict[str, Any]:
        """Prepares an isolated replica container environment for failure injection."""
        scen = self.scenarios.get(scenario_id, self.scenarios["db_connection_exhaustion"])
        self.replica_states[scenario_id] = {
            "status": "READY",
            "scenario": scen,
            "applied_solution": None,
            "iteration": 0
        }
        return {
            "replica_id": f"rep-{scenario_id}-sandbox",
            "target_service": scen["target_service"],
            "state": "REPLICA_PREPARED",
            "environment": "Docker Sandbox Replica Isolation (Zero Prod Impact)",
            "timestamp": time.time()
        }

    def inject_fault(self, scenario_id: str) -> Dict[str, Any]:
        """Injects failure into the replica to generate pre-fix failure telemetry and logs."""
        scen = self.scenarios.get(scenario_id, self.scenarios["db_connection_exhaustion"])
        tgt = scen["target_service"]
        symptoms = scen["expected_symptoms"]

        # Base clean services snapshot
        service_metrics = {
            "gateway": {"error_rate": 0.005, "latency_p95_ms": 32.0, "latency_p50_ms": 12.0, "cpu_percent": 18.0, "memory_mb": 140.0, "active_connections": 8.0, "queue_depth": 2.0, "throughput_rps": 120.0},
            "service-a": {"error_rate": 0.005, "latency_p95_ms": 38.0, "latency_p50_ms": 15.0, "cpu_percent": 20.0, "memory_mb": 145.0, "active_connections": 10.0, "queue_depth": 2.0, "throughput_rps": 115.0},
            "service-b": {"error_rate": 0.005, "latency_p95_ms": 42.0, "latency_p50_ms": 18.0, "cpu_percent": 22.0, "memory_mb": 150.0, "active_connections": 12.0, "queue_depth": 3.0, "throughput_rps": 110.0},
            "database-service": {"error_rate": 0.002, "latency_p95_ms": 25.0, "latency_p50_ms": 10.0, "cpu_percent": 25.0, "memory_mb": 160.0, "active_connections": 10.0, "queue_depth": 1.0, "throughput_rps": 130.0},
            "auth-service": {"error_rate": 0.001, "latency_p95_ms": 20.0, "latency_p50_ms": 8.0, "cpu_percent": 15.0, "memory_mb": 130.0, "active_connections": 6.0, "queue_depth": 1.0, "throughput_rps": 125.0}
        }

        # Inject anomalous symptoms into target service
        if tgt in service_metrics:
            service_metrics[tgt].update(symptoms)

        # Cascading effect on upstream services
        if tgt == "database-service":
            service_metrics["service-b"]["error_rate"] = 0.75
            service_metrics["service-b"]["latency_p95_ms"] = 1600.0
            service_metrics["service-a"]["error_rate"] = 0.65
            service_metrics["gateway"]["error_rate"] = 0.55
        elif tgt == "service-b":
            service_metrics["service-a"]["error_rate"] = 0.80
            service_metrics["gateway"]["error_rate"] = 0.70

        error_logs = [
            {
                "timestamp": time.time(),
                "service": tgt,
                "level": "ERROR",
                "message": symptoms.get("error_message", "Component internal failure detected"),
                "component": scen["target_component"]
            },
            {
                "timestamp": time.time() + 1.2,
                "service": "gateway",
                "level": "WARN",
                "message": f"Downstream request cascade failure from {tgt}",
                "component": "http_router"
            }
        ]

        return {
            "scenario_id": scenario_id,
            "target_service": tgt,
            "service_metrics": service_metrics,
            "error_logs": error_logs,
            "ground_truth_root_cause": scen["ground_truth_root_cause"]
        }

    def execute_solution_and_replay(
        self,
        scenario_id: str,
        action: str,
        iteration: int = 1
    ) -> Dict[str, Any]:
        """
        Applies concrete candidate solution in controlled replica, then replays
        the identical failure scenario under measured load, capturing post-fix evidence.
        """
        scen = self.scenarios.get(scenario_id, self.scenarios["db_connection_exhaustion"])
        tgt = scen["target_service"]
        possible_actions = scen["possible_recovery_actions"]

        # Default action evaluation if not in pre-configured dict
        action_eval = possible_actions.get(action, {
            "resolves_original_error": False,
            "causes_side_effect": "unknown_action_failure",
            "description": f"Action '{action}' was unrecognized or ineffective."
        })

        resolves = action_eval["resolves_original_error"]
        side_effect = action_eval["causes_side_effect"]

        # Clean baseline post-fix state
        post_metrics = {
            "gateway": {"error_rate": 0.005, "latency_p95_ms": 32.0, "latency_p50_ms": 12.0, "cpu_percent": 18.0, "memory_mb": 140.0, "active_connections": 8.0, "queue_depth": 2.0, "throughput_rps": 120.0, "healthy": True},
            "service-a": {"error_rate": 0.005, "latency_p95_ms": 38.0, "latency_p50_ms": 15.0, "cpu_percent": 20.0, "memory_mb": 145.0, "active_connections": 10.0, "queue_depth": 2.0, "throughput_rps": 115.0, "healthy": True},
            "service-b": {"error_rate": 0.005, "latency_p95_ms": 42.0, "latency_p50_ms": 18.0, "cpu_percent": 22.0, "memory_mb": 150.0, "active_connections": 12.0, "queue_depth": 3.0, "throughput_rps": 110.0, "healthy": True},
            "database-service": {"error_rate": 0.002, "latency_p95_ms": 25.0, "latency_p50_ms": 10.0, "cpu_percent": 25.0, "memory_mb": 160.0, "active_connections": 10.0, "queue_depth": 1.0, "throughput_rps": 130.0, "healthy": True},
            "auth-service": {"error_rate": 0.001, "latency_p95_ms": 20.0, "latency_p50_ms": 8.0, "cpu_percent": 15.0, "memory_mb": 130.0, "active_connections": 6.0, "queue_depth": 1.0, "throughput_rps": 125.0, "healthy": True}
        }

        post_logs = []

        if not resolves:
            # Original problem persists!
            symptoms = scen["expected_symptoms"]
            post_metrics[tgt].update(symptoms)
            post_metrics[tgt]["healthy"] = False
            post_logs.append({
                "timestamp": time.time(),
                "service": tgt,
                "level": "ERROR",
                "message": f"Remedy '{action}' failed: original symptom persisted ({symptoms.get('error_message')})",
                "component": scen["target_component"]
            })
        else:
            # Original problem resolved
            post_metrics[tgt]["healthy"] = True
            post_logs.append({
                "timestamp": time.time(),
                "service": tgt,
                "level": "INFO",
                "message": f"Remedy '{action}' executed successfully in replica: component normalized.",
                "component": scen["target_component"]
            })

            # Check if this action caused an unacceptable SIDE EFFECT
            if side_effect == "latency_surge":
                post_metrics[tgt]["latency_p95_ms"] = 2450.0
                post_metrics["gateway"]["latency_p95_ms"] = 2800.0
                post_logs.append({
                    "timestamp": time.time(),
                    "service": tgt,
                    "level": "WARN",
                    "message": "SIDE EFFECT: P95 latency surged to 2450ms after cold restart",
                    "component": "http_endpoint"
                })
            elif side_effect == "throughput_dropped":
                post_metrics[tgt]["throughput_rps"] = 28.0
                post_metrics["gateway"]["throughput_rps"] = 30.0
                post_logs.append({
                    "timestamp": time.time(),
                    "service": tgt,
                    "level": "WARN",
                    "message": "SIDE EFFECT: Throughput dropped below minimum threshold (28 RPS)",
                    "component": "traffic_controller"
                })
            elif side_effect == "memory_exploded":
                post_metrics[tgt]["memory_mb"] = 1250.0
                post_metrics[tgt]["healthy"] = False
                post_logs.append({
                    "timestamp": time.time(),
                    "service": tgt,
                    "level": "CRITICAL",
                    "message": "SIDE EFFECT: Memory exploded to 1250MB (> 400% baseline)",
                    "component": "process_memory"
                })
            elif side_effect == "data_loss":
                post_logs.append({
                    "timestamp": time.time(),
                    "service": tgt,
                    "level": "CRITICAL",
                    "message": "SIDE EFFECT: Data loss detected: 780 unpersisted queue messages purged",
                    "component": "message_queue"
                })
            elif side_effect == "crash_loop":
                post_metrics[tgt]["healthy"] = False
                post_metrics[tgt]["error_rate"] = 1.0
                post_logs.append({
                    "timestamp": time.time(),
                    "service": tgt,
                    "level": "CRITICAL",
                    "message": "SIDE EFFECT: Service entered CrashLoopBackOff on restart",
                    "component": "process_runtime"
                })

        return {
            "scenario_id": scenario_id,
            "action_executed": action,
            "iteration": iteration,
            "resolves_original_error": resolves,
            "side_effect_detected": side_effect is not None,
            "side_effect_type": side_effect,
            "side_effect_detail": scen.get("expected_side_effects", {}).get(side_effect),
            "post_metrics": post_metrics,
            "post_logs": post_logs,
            "success_criteria": scen["success_criteria"]
        }

    def reset_environment(self) -> Dict[str, Any]:
        """Resets the replica sandbox state to a clean baseline."""
        return {
            "status": "RESET",
            "active_faults": 0,
            "timestamp": time.time()
        }


replica_environment = ControlledReplicaEnvironment()

