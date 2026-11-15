# Research Deliverable 25: Missing Experiments, Open Data Gaps, and Experimental Roadmap

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Gap Analysis & Experimental Action Plan  
**Target Standard:** Top-Tier Systems Conference Review Standards (OSDI / SOSP / ATC / DSN)  
**Date:** October 31, 2026  

---

## 1. Executive Summary & Experimental Deficit

While AegisOps AI possesses a fully functional codebase and demonstrates compelling pilot benchmark results ($87.5\%$ recovery vs. $25.0\%$ baseline), several crucial empirical evaluations must be conducted before submitting to an A* / top-tier systems conference.

$$\mathbf{Experimental\ Deficit:\ 4\ CRITICAL\ MISSING\ EXPERIMENTS}$$
1. **Multi-Seed Confirmatory Benchmark ($N=240$):** Moving beyond the single-seed $N=8$ pilot smoke run.
2. **Component Ablation Study:** Empirically isolating the individual contribution of Replica Sandboxing, Evidence Re-ranking, and Multi-Metric Validation.
3. **Hyperparameter Sensitivity Analysis:** Testing variation in iteration limits ($k=1,2,3,4,5$) and reasoning budgets (`thinkingBudget`).
4. **Physical Container / Cluster Validation:** Demonstrating recovery against real Linux Docker containers / Kubernetes pods under Linux kernel fault injection (`tc netem`, SIGSTOP, cgroup pressure).

---

## 2. Granular Specification of Missing Experiments

### Experiment 1: The 240-Trial Confirmatory Experiment
- **Current Status:** Not executed (only $N=8$ pilot run executed with seed 12345).
- **Why Required:** Elevates statistical conclusion validity from exploratory ($p = 0.063$ two-tailed) to definitive ($p < 0.0001$).
- **Experimental Plan:** Execute all 8 scenarios across 3 strategies with 10 independent random seeds ($8 \times 3 \times 10 = 240$ trials) using the protocol in Deliverable 9.

### Experiment 2: Formal Factorial Ablation Analysis
To prove *why* the closed-loop policy succeeds, a paper must isolate each architectural layer:

| Ablation Configuration | Replica Sandbox | Validation Oracle | Evidence Refinement | Attempt Budget | What It Isolates |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Full System (Strategy C)** | YES | 8-Point Oracle | Active Re-ranking | $k=3$ | Complete proposed architecture |
| **Ablation 1: Blind Retries** | YES | 8-Point Oracle | **NONE (Repeats Action 1)** | $k=3$ | Proves refinement is necessary, not just retries |
| **Ablation 2: Shallow Health** | YES | **HTTP 200 Only**| Active Re-ranking | $k=3$ | Proves 8-point oracle is superior to shallow /health |
| **Ablation 3: No Replica** | **NO (Live Host)**| 8-Point Oracle | Active Re-ranking | $k=3$ | Measures host disruption and side-effect blast radius |
| **Ablation 4: No Memory** | YES | 8-Point Oracle | Re-ranking (**No KB**)| $k=3$ | Measures cold-start candidate ranking latency |

### Experiment 3: Parameter Sensitivity Analysis
- **Iteration Bound ($k_{\max}$):** Evaluate $k \in \{1, 2, 3, 4, 5\}$.
  - *Expected Finding:* Diminishing returns beyond $k=3$. Shows that unresolvable faults (like malformed syntax) consume unnecessary latency without improving recovery if $k > 3$.
- **Anomaly Consensus Voting Rule:** Evaluate 1-of-3 vs. 2-of-3 vs. 3-of-3 consensus.
  - *Expected Finding:* 2-of-3 balances sensitivity and false alarm rejection (42.6% reduction).
- **Gemini Reasoning Budget (`thinkingBudget`):** Evaluate $0$ vs. $2048$ vs. $8192$ tokens.
  - *Expected Finding:* $2048$ tokens achieves the optimal Pareto frontier between reasoning depth and sub-second latency ($0.58\text{ s}$).

### Experiment 4: Physical Kubernetes / Containerized Testbed
- **Current Status:** Scenarios execute against in-memory microservice state models (`controlled_environment.py`).
- **Why Required:** Systems reviewers will demand proof that the replica environment translates to real Linux namespaces, cgroups, and network bridges.
- **Experimental Plan:** Spin up a local `kind` (Kubernetes in Docker) or Minikube cluster running the FinCore banking services, and inject faults using Chaos Mesh (`pod-failure`, `network-loss`, `memory-stress`).

---

## 3. Prioritized Implementation Roadmap for Academic Submission

```
[Phase 1: Immediate - 1 Week]
  └── Implement scripts/run_research_benchmark.py CLI harness
  └── Execute and serialize the 240-trial confirmatory dataset to disk
  └── Recompute McNemar and Wilcoxon statistics across the 240 trials

[Phase 2: Intermediate - 2 Weeks]
  └── Implement and run the 4-way ablation benchmark (Blind Retries vs Refinement)
  └── Generate Figure 3 (RSR/FRR) and Figure 4 (Overhead) from confirmatory data
  └── Draft Sections 6, 7, and 8 of the research manuscript

[Phase 3: Final Polish - 3 Weeks]
  └── Run containerized Kubernetes validation on a local Minikube cluster
  └── Package artifact into a self-contained Docker evaluation image
  └── Submit manuscript to USENIX ATC / IEEE DSN
```

