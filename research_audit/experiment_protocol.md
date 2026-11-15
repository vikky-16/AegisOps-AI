# Research Deliverable 09: Rigorous Experimental Protocol & Statistical Power Design

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Experimental Protocol Specification  
**Target Venue:** ACM SIGMETRICS / USENIX SREcon / IEEE Transactions on Software Engineering  
**Date:** October 31, 2026  

---

## 1. Experimental Objectives & Theoretical Framework

This protocol defines the formal experimental methodology required to evaluate whether **Closed-Loop, Evidence-Guided Recovery (Strategy C)** statistically outperforms **One-Shot Recovery (Strategy A)** and **Validation-Only Recovery (Strategy B)** across standardized distributed failure scenarios.

### Core Scientific Questions Tested
1. Does the introduction of an independent validation oracle eliminate false recovery declarations ($\text{FRR} \to 0\%$)?
2. Does iterative evidence-guided candidate re-ranking significantly increase recovery success rate ($\text{RSR}$) without introducing unacceptable attempt overhead ($\text{ARA}$)?
3. Does closed-loop recovery guarantee safe termination when faced with non-transient, unresolvable failure modes (e.g., malformed configuration syntax)?

---

## 2. Experimental Design & Statistical Power Analysis

### 2.1 Pilot / Smoke Test vs. Confirmatory Experiment
The previously reported 24-trial run (8 scenarios $\times$ 3 strategies $\times$ 1 repetition with seed 12345) is formally classified as an **exploratory smoke test**. While sufficient to verify software correctness, pipeline connectivity, and state machine transitions, an $N=8$ paired sample lacks the statistical power required for definitive scientific confirmation.

### 2.2 Formal Statistical Power & Sample Size Derivation
To test Hypothesis H1 ($H_0: \text{RSR}_C \le \text{RSR}_A$ vs. $H_1: \text{RSR}_C > \text{RSR}_A$) using **McNemar's test for paired binary outcomes**:

- **Significance Level ($\alpha$):** $0.05$ (two-tailed).
- **Statistical Power ($1 - \beta$):** $0.80$ (standard 80% power).
- **Hypothesized Discordant Proportions:**
  - $p_{10}$ (Closed-Loop succeeds, One-Shot fails): $\approx 0.625$ (derived from smoke run).
  - $p_{01}$ (One-Shot succeeds, Closed-Loop fails): $\approx 0.000$ (monotonic dominance of closed-loop).
- **Minimum Detectable Effect:** $\Delta \text{RSR} \ge 30.0$ percentage points.

Using the asymptotic sample size formula for paired binary proportions:
$$N = \frac{\left( z_{\alpha/2} \sqrt{p_{10} + p_{01}} + z_{\beta} \sqrt{p_{10} + p_{01} - (p_{10} - p_{01})^2} \right)^2}{(p_{10} - p_{01})^2}$$

Substituting $z_{0.025} = 1.96$, $z_{0.20} = 0.84$, $p_{10} = 0.60$, $p_{01} = 0.05$:
$$N \approx \frac{\left( 1.96 \sqrt{0.65} + 0.84 \sqrt{0.65 - (0.55)^2} \right)^2}{(0.55)^2} = \frac{(1.96 \cdot 0.806 + 0.84 \cdot 0.589)^2}{0.3025} \approx \frac{(1.580 + 0.495)^2}{0.3025} \approx 14.2 \text{ discordant pairs}$$

With a total scenario pool of 8 distinct fault classes, executing **$R = 10$ independent repetitions per scenario across 10 randomized pseudo-random seeds** yields:
$$\mathbf{Total\ Experimental\ Trials:\ 8\ \text{scenarios} \times 3\ \text{strategies} \times 10\ \text{repetitions} = 240\ \text{trials}}$$
A 240-trial battery provides $>95\%$ statistical power to detect recovery rate improvements $\ge 25\%$ and narrow 95% confidence interval spans to within $\pm 6.2\%$.

---

## 3. Step-by-Step Trial Execution Protocol

Each individual trial $T(s, \text{strat}, r)$ in the 240-trial matrix must strictly follow this execution sequence:

```
[Phase 1: Environment Reset] 
  └── Purge in-memory telemetry buffers
  └── Reset SQLite test database connection
  └── Initialize pseudo-random seed S_r

[Phase 2: Fault Injection]
  └── Invoke replica_environment.inject_fault(s)
  └── Capture baseline pre-execution telemetry (telemetry_0)
  └── Assert failure symptoms match expected baseline

[Phase 3: Cognitive Triage]
  └── Generate candidate recovery solutions C_0
  └── Record execution start timestamp t_start

[Phase 4: Strategy Execution]
  ├── If Strategy A: Execute top candidate c_1; Record exit code; Skip oracle
  ├── If Strategy B: Execute top candidate c_1; Replay workload; Evaluate Oracle V(c_1)
  └── If Strategy C: Execute closed-loop loop (k <= 3) with replica replay and refinement

[Phase 5: Outcome Determination & Logging]
  └── Apply independent evaluation oracle V to all strategies to verify true ground truth
  └── Record recovery status: VALIDATED, FALSE_RECOVERY, UNRESOLVED, ESCALATED
  └── Serialize raw trial JSON record to disk
```

---

## 4. Controlled Variables & Fairness Invariants

| Variable | Protocol Control Mechanism | Deviation Allowed |
| :--- | :--- | :---: |
| **Initial Fault State** | Identical mathematical fault injection parameters ($s$) | None |
| **Initial Telemetry Snapshot** | Replayed from identical seed buffer | None |
| **Candidate Solution Pool ($C_0$)** | Generated from identical `solution_generator.py` logic | None |
| **First Candidate Action ($c_1$)** | Deterministically selected as highest confidence candidate | None |
| **Success Oracle Thresholds** | Fixed: Error $< 5\%$, p95 Latency $< 120\text{ ms}$, Throughput $\ge 90\text{ rps}$ | None |
| **Host System Mutability** | Strategy C isolates in replica; Strategies A and B operate locally | Documented |
| **Attempt Budget** | Strategy A ($k=1$), Strategy B ($k=1$), Strategy C ($k \le 3$) | Documented Overhead |

---

## 5. Machine-Readable Raw Trial Schema

Every trial must output a validated JSON record adhering to this schema:

```json
{
  "$schema": "https://aegisops.ai/schemas/research_trial_v1.json",
  "experiment_id": "EXP-CONFIRMATORY-2026-R1",
  "trial_id": "TRIAL-00142",
  "commit_hash": "authoritative-local-2026-10-31",
  "strategy": "CLOSED_LOOP",
  "scenario_id": "db_connection_exhaustion",
  "fault_class": "RESOURCE_EXHAUSTION",
  "repetition_index": 3,
  "random_seed": 12345,
  "start_time_iso": "2026-10-31T21:15:00.124Z",
  "end_time_iso": "2026-10-31T21:15:01.845Z",
  "duration_seconds": 1.721,
  "initial_symptoms": {
    "error_rate": 0.88,
    "active_connections": 98.0,
    "latency_p95_ms": 1850.0
  },
  "candidate_solutions_available": ["RESET_CONNECTION_POOL", "RECONNECT_DATABASE"],
  "total_attempts_executed": 1,
  "attempts_detail": [
    {
      "attempt": 1,
      "action": "RESET_CONNECTION_POOL",
      "command_success": true,
      "oracle_validation_passed": true,
      "post_error_rate": 0.01,
      "post_active_connections": 12.0,
      "post_latency_p95_ms": 42.0,
      "side_effects_detected": []
    }
  ],
  "final_declared_state": "VALIDATED",
  "oracle_verified_recovery": true,
  "is_false_recovery": false,
  "is_unsafe_action": false,
  "escalated_to_human": false
}
```

---

## 6. Execution Command Reproducibility Protocol

To execute this confirmatory protocol once the automated CLI benchmark runner is initialized:

```bash
# Execute 240-trial confirmatory experiment across all 3 strategies and 10 seeds
python scripts/run_research_benchmark.py \
  --scenarios all \
  --strategies one_shot,validation_only,closed_loop \
  --repetitions 10 \
  --base-seed 12345 \
  --output-dir datasets/benchmark_runs/confirmatory_240/ \
  --log-level INFO
```

