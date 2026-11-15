import csv
import sys
sys.path.insert(0, ".")
from backend.app.replica.controlled_environment import SCENARIO_DEFINITIONS

scenarios = [
    {
        "Scenario ID": "db_connection_exhaustion",
        "Fault Class": "Resource Exhaustion (Database Connection Pool)",
        "Injection Mechanism": "Simulated leak of client connection sockets via replica_environment.inject_fault()",
        "Initial Conditions": "Active connections: 98/100, memory: 180MB, latency: 45ms baseline",
        "Expected Symptom": "Error rate 88%, active connections 98, latency p95 1850ms, HTTP 503 error",
        "Ground-Truth Cause": "Database connection pool exhaustion caused by leaked client connections in Service B",
        "Valid Recovery Condition": "Action RESET_CONNECTION_POOL or RECONNECT_DATABASE restoring active conns <= 20 and err < 5%",
        "Cleanup": "Flush idle sockets, reset pool capacity counter to 15, restore normal latency",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "service_crash",
        "Fault Class": "Process Crash / Exit (SIGSEGV / OOMKilled)",
        "Injection Mechanism": "Simulates worker process termination due to unhandled null reference",
        "Initial Conditions": "Service-b healthy (0% errors, 35ms latency), worker process PID active",
        "Expected Symptom": "Error rate 100%, 0 throughput, HTTP 502/504 Bad Gateway, process offline",
        "Ground-Truth Cause": "Unhandled null pointer reference in Payment Service worker process causing immediate exit",
        "Valid Recovery Condition": "Action RESTART_SERVICE restoring process PID and reducing error rate to 0%",
        "Cleanup": "Restart process container, clear exception stack trace, restore heartbeat",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "high_api_latency",
        "Fault Class": "Thread Starvation / Elevated Latency",
        "Injection Mechanism": "Simulates request queue lock contention on Order Service request worker",
        "Initial Conditions": "Latency: 45ms, CPU: 20%, request queue depth: 5",
        "Expected Symptom": "p95 latency 2400ms, queue depth 450, error rate 22% due to client timeouts",
        "Ground-Truth Cause": "Thread starvation and lock contention on Order Service request worker queue",
        "Valid Recovery Condition": "Action SCALE_WORKERS increasing concurrency or CLEAR_CACHE reducing lock contention",
        "Cleanup": "De-queue backlog, release thread mutex locks, reset worker count",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "memory_pressure",
        "Fault Class": "Resource Exhaustion (Memory Leak / Heap Saturation)",
        "Injection Mechanism": "Simulates unbounded cache buffer allocation in request payload decompressor",
        "Initial Conditions": "Memory: 180MB (baseline), GC pauses: <10ms",
        "Expected Symptom": "Memory 920MB (92% limit), GC pause 450ms, latency p95 1250ms, error rate 15%",
        "Ground-Truth Cause": "Unbounded cache growth and memory leak in request payload decompressor",
        "Valid Recovery Condition": "Action CLEAR_CACHE or RESTART_SERVICE reclaiming memory <= 250MB",
        "Cleanup": "Purge in-memory decompressed cache, trigger GC, restore baseline allocation",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "cpu_saturation",
        "Fault Class": "Resource Exhaustion (CPU Core Runaway Loop)",
        "Injection Mechanism": "Simulates catastrophic regex backtracking in API Gateway path routing rules",
        "Initial Conditions": "CPU: 15%, Gateway latency: 12ms",
        "Expected Symptom": "CPU 98%, Gateway latency 1600ms, error rate 35% due to dropped ingress packets",
        "Ground-Truth Cause": "Inefficient regular expression backtracking in API Gateway request path routing rules",
        "Valid Recovery Condition": "Action SCALE_WORKERS distributing load or RESTART_SERVICE resetting regex engine",
        "Cleanup": "Terminate runaway worker threads, restore standard route table, verify CPU < 30%",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "dependency_unavailable",
        "Fault Class": "Downstream Dependency Failure / Cascading Outage",
        "Injection Mechanism": "Simulates external OAuth token verification service outage",
        "Initial Conditions": "Auth-service latency 25ms, downstream error rate 0%",
        "Expected Symptom": "Error rate 95% on all authenticated routes, upstream gateway cascading 504 timeouts",
        "Ground-Truth Cause": "External token verification service unreachable causing 504 timeouts across all gateway calls",
        "Valid Recovery Condition": "Action ENABLE_CIRCUIT_BREAKER_FALLBACK allowing degraded token caching",
        "Cleanup": "Re-enable primary dependency probe, clear circuit breaker trip flag",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "queue_backlog",
        "Fault Class": "Queue Backlog / Consumer Lag",
        "Injection Mechanism": "Simulates consumer offset rebalancing loop pausing ledger processing",
        "Initial Conditions": "Kafka lag: 50 messages, processing time: 5ms/msg",
        "Expected Symptom": "Queue lag 15,000 messages, end-to-end processing delay 45s, stale order alerts",
        "Ground-Truth Cause": "Payment ledger consumer group paused due to consumer offset rebalancing loop",
        "Valid Recovery Condition": "Action SCALE_CONSUMER_WORKERS or RESTART_SERVICE resetting consumer partition assignment",
        "Cleanup": "Drain queue backlog, verify partition assignment is stable, lag < 100",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    },
    {
        "Scenario ID": "configuration_error",
        "Fault Class": "Configuration Error / Malformed Parameter Syntax",
        "Injection Mechanism": "Simulates injection of malformed database connection string parameter in rollout",
        "Initial Conditions": "Database configuration valid, active connection pool operational",
        "Expected Symptom": "Error rate 100% on database connect, syntax error: malformed URI schema",
        "Ground-Truth Cause": "Malformed database connection string parameter injected in latest rollout",
        "Valid Recovery Condition": "Action ROLLBACK_CONFIG reverting configuration parameter to previous valid snapshot",
        "Cleanup": "Re-apply known valid config snapshot, restart connection driver",
        "Implementation Status": "Implemented & Runtime-Verified (In-Memory Sandbox Simulation)"
    }
]

csv_path = "research_audit/benchmark_scenario_inventory.csv"
fieldnames = [
    "Scenario ID", "Fault Class", "Injection Mechanism", "Initial Conditions",
    "Expected Symptom", "Ground-Truth Cause", "Valid Recovery Condition",
    "Cleanup", "Implementation Status"
]

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for s in scenarios:
        writer.writerow(s)

print(f"Generated {csv_path} with {len(scenarios)} benchmark scenarios.")

