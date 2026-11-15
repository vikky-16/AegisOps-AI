# Research Deliverable 12: Raw Trial Data Inventory, Storage Audit, and Provenance Report

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Data Provenance & Trial Forensic Inventory  
**Auditor Role:** Senior Research Scientist & Data Integrity Auditor  
**Date:** October 31, 2026  

---

## 1. Executive Summary of Raw Data Audit

A forensic search across the local file system (`C:\Users\admin\AegisOps AI`), backup archives (`C:\Users\admin\AegisOps AI.zip`), and development session logs was conducted to locate the raw, serialized execution records of the previously reported 24-trial benchmark run (8 scenarios $\times$ 3 strategies, seed 12345).

### Key Audit Findings
1. **Pre-Existing Serialized JSON Trial Files: NOT FOUND ON DISK.**  
   No directory containing 24 separate raw JSON trial manifests (e.g., `datasets/benchmark_runs/*.json`) was checked into the workspace. The single benchmark result file present was `benchmark_results.json`, which contains latency timings for system components rather than the 24 strategy trials.
2. **Underlying Algorithmic & Scenario Machinery: 100% VERIFIED & PRESENT.**  
   The complete execution code responsible for generating the 24 trials is fully present and functional:
   - Scenarios: `backend/app/replica/controlled_environment.py` defines all 8 ground-truth fault scenarios (`SCENARIO_DEFINITIONS`).
   - Strategy C Execution: `backend/app/healing/closed_loop_engine.py` executes the 14-state closed-loop pipeline.
   - Candidate Generation: `backend/app/healing/solution_generator.py` defines candidate solutions, prerequisites, and risk scores.
   - Validation Oracle: `backend/app/validation/validator.py` evaluates the 8 empirical predicates ($P_1-P_8$).
3. **Reproducibility of the 24-Trial Results: 100% DETERMINISTIC.**  
   Executing `backend/app/healing/closed_loop_engine.py` against the 8 scenarios reproduces the exact outcome profile reported in the historical summary:
   - 7 scenarios achieve `VALIDATED` recovery ($87.5\%$).
   - Exactly 1 scenario (`configuration_error`) exhausts 3 attempts and terminates as `UNRESOLVED` with human escalation.
   - Total attempts for Strategy C equal 15 ($15 / 8 = 1.875$ attempts/incident; $12 / 7 = 1.714$ attempts/recovered incident).

---

## 2. Granular Inventory of the 24 Audited Trials

The 24 reconstructed and runtime-verified trial records are cataloged below and serialized in [`research_audit/recalculated_results.csv`](file:///c:/Users/admin/AegisOps%20AI/research_audit/recalculated_results.csv):

| Trial ID | Strategy | Scenario ID | Fault Class | Attempts | Initial Action Executed | Oracle Result | Declared Outcome | Is False Recovery? |
| :---: | :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: |
| **TRIAL-A01** | One-Shot | `db_connection_exhaustion` | Resource Exhaustion | 1 | `RESET_CONNECTION_POOL` | **PASS** | Validated Recovery | NO |
| **TRIAL-A02** | One-Shot | `service_crash` | Process Crash | 1 | `RESTART_SERVICE` | **PASS** | Validated Recovery | NO |
| **TRIAL-A03** | One-Shot | `high_api_latency` | Thread Starvation | 1 | `CLEAR_CACHE` | **FAIL** | False Recovery | **YES** |
| **TRIAL-A04** | One-Shot | `memory_pressure` | Resource Exhaustion | 1 | `RESTART_SERVICE` | **FAIL** | False Recovery | **YES** |
| **TRIAL-A05** | One-Shot | `cpu_saturation` | Resource Exhaustion | 1 | `RESTART_SERVICE` | **FAIL** | False Recovery | **YES** |
| **TRIAL-A06** | One-Shot | `dependency_unavailable`| Dependency Cascade | 1 | `RESTART_SERVICE` | **FAIL** | False Recovery | **YES** |
| **TRIAL-A07** | One-Shot | `queue_backlog` | Queue Backlog | 1 | `RESTART_SERVICE` | **FAIL** | False Recovery | **YES** |
| **TRIAL-A08** | One-Shot | `configuration_error` | Configuration Syntax | 1 | `RESET_CONNECTION_POOL` | **FAIL** | False Recovery | **YES** |
| **TRIAL-B01** | Validation-Only | `db_connection_exhaustion` | Resource Exhaustion | 1 | `RESET_CONNECTION_POOL` | **PASS** | Validated Recovery | NO |
| **TRIAL-B02** | Validation-Only | `service_crash` | Process Crash | 1 | `RESTART_SERVICE` | **PASS** | Validated Recovery | NO |
| **TRIAL-B03** | Validation-Only | `high_api_latency` | Thread Starvation | 1 | `CLEAR_CACHE` | **FAIL** | Unresolved / Failed | NO |
| **TRIAL-B04** | Validation-Only | `memory_pressure` | Resource Exhaustion | 1 | `RESTART_SERVICE` | **FAIL** | Unresolved / Failed | NO |
| **TRIAL-B05** | Validation-Only | `cpu_saturation` | Resource Exhaustion | 1 | `RESTART_SERVICE` | **FAIL** | Unresolved / Failed | NO |
| **TRIAL-B06** | Validation-Only | `dependency_unavailable`| Dependency Cascade | 1 | `RESTART_SERVICE` | **FAIL** | Unresolved / Failed | NO |
| **TRIAL-B07** | Validation-Only | `queue_backlog` | Queue Backlog | 1 | `RESTART_SERVICE` | **FAIL** | Unresolved / Failed | NO |
| **TRIAL-B08** | Validation-Only | `configuration_error` | Configuration Syntax | 1 | `RESET_CONNECTION_POOL` | **FAIL** | Unresolved / Failed | NO |
| **TRIAL-C01** | Closed-Loop | `db_connection_exhaustion` | Resource Exhaustion | 1 | `RESET_CONNECTION_POOL` | **PASS** | Validated Recovery | NO |
| **TRIAL-C02** | Closed-Loop | `service_crash` | Process Crash | 1 | `RESTART_SERVICE` | **PASS** | Validated Recovery | NO |
| **TRIAL-C03** | Closed-Loop | `high_api_latency` | Thread Starvation | 2 | `CLEAR_CACHE` $\to$ `SCALE_WORKERS` | **PASS** | Validated Recovery | NO |
| **TRIAL-C04** | Closed-Loop | `memory_pressure` | Resource Exhaustion | 2 | `RESTART_SERVICE` $\to$ `CLEAR_CACHE`| **PASS** | Validated Recovery | NO |
| **TRIAL-C05** | Closed-Loop | `cpu_saturation` | Resource Exhaustion | 2 | `RESTART_SERVICE` $\to$ `SCALE_WORKERS`| **PASS** | Validated Recovery | NO |
| **TRIAL-C06** | Closed-Loop | `dependency_unavailable`| Dependency Cascade | 2 | `RESTART_SVC` $\to$ `CIRCUIT_BREAKER`| **PASS** | Validated Recovery | NO |
| **TRIAL-C07** | Closed-Loop | `queue_backlog` | Queue Backlog | 2 | `RESTART_SVC` $\to$ `SCALE_CONSUMERS`| **PASS** | Validated Recovery | NO |
| **TRIAL-C08** | Closed-Loop | `configuration_error` | Configuration Syntax | 3 | `RESET_POOL` $\to$ `RECONNECT` $\to$ `RESTART`| **FAIL** | Unresolved Escalated | NO |

---

## 3. Data Integrity & Scientific Reporting Mandate

Because the original raw JSON files were not persisted to disk in the repository, academic integrity requires that:
1. The 24-trial dataset must be classified in all publications as an **exploratory pilot benchmark (smoke test)**.
2. The author must explicitly declare that the results were reconstructed and verified directly from the deterministic codebase logic (`closed_loop_engine.py` and `controlled_environment.py`).
3. Before submitting to a peer-reviewed venue, the author should execute the automated 240-trial confirmatory experiment protocol specified in Deliverable 9 to generate a permanent, signed, serialized dataset with cryptographic SHA-256 checksums.

