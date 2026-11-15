# Research Deliverable 01: Research Question Formulation and Scientific Contribution Analysis

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Audit & Peer Review Assessment  
**Auditor Role:** Senior Research Scientist in Distributed Systems & Reliability Engineering  
**Date:** October 31, 2026  

---

## 1. Primary Research Question Formulation

The central scientific inquiry investigated by the AegisOps AI project is formulated as follows:

$$\mathbf{RQ_0}:\ \text{\textit{Does execution-based recovery validation and evidence-guided recovery refinement improve recovery correctness compared with one-shot recovery approaches in distributed software systems?}}$$

### 1.1 Decomposition into Granular Operational Research Questions

To make this high-level question empirically testable, it is decomposed into four formal sub-questions:

1. **$\mathbf{RQ_1}$ (Recovery Correctness & False Declarations):**  
   Does an independent, multi-criteria execution validation oracle significantly reduce false-positive recovery declarations ($\text{FRR}$) compared to unverified one-shot remediation that equates command execution success with system health restoration?
2. **$\mathbf{RQ_2}$ (Refinement Convergence & Effectiveness):**  
   Does iteratively utilizing observed failure telemetry and side-effect evidence to re-rank and adjust subsequent candidate recovery actions yield higher overall recovery success ($\text{RSR}$) than static or unguided retries?
3. **$\mathbf{RQ_3}$ (Overhead & Latency Trade-Off):**  
   What is the quantitative cost—measured in additional recovery attempts ($\text{ARA}$), execution latency ($\text{TTVR}$), and resource utilization—incurred by closed-loop replica execution and validation relative to one-shot execution?
4. **$\mathbf{RQ_4}$ (Fault-Class Heterogeneity):**  
   How does the efficacy of evidence-guided refinement vary across distinct distributed failure modes (e.g., transient pool exhaustion vs. hard process crashes vs. non-transient configuration corruptions)?

---

## 2. Granular Implementation and Verification Status Matrix

A rigorous research audit requires distinguishing between code that merely exists in a repository, code that runs, code that has been experimentally benchmarked, and claims backed by statistical inference.

| Subsystem / Capability | Implemented in Source | Executed Successfully | Experimentally Evaluated | Compared to Baselines | Statistically Significant Evidence | Detailed Code & Runtime Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Controlled Replica Sandbox** | **YES** | **YES** | **YES** | **YES** | **PRELIMINARY** | `backend/app/replica/controlled_environment.py`: 8 failure models with pre/post telemetry injection. |
| **8-Point Empirical Validation** | **YES** | **YES** | **YES** | **YES** | **PRELIMINARY** | `backend/app/validation/validator.py`: Predicates $P_1-P_8$, side-effect detection, error resolution checks. |
| **Candidate Solution Generator** | **YES** | **YES** | **YES** | **NO** | **NO** | `backend/app/healing/solution_generator.py`: Generates ranked solutions with prerequisites and risk scores. |
| **Evidence-Guided Refinement** | **YES** | **YES** | **YES** | **PRELIMINARY** | **UNVERIFIED** | `closed_loop_engine.py`: Re-ranks remaining candidates based on observed failure analysis. |
| **Bounded Iterations ($k \le 3$)** | **YES** | **YES** | **YES** | **YES** | **PRELIMINARY** | `closed_loop_engine.py`: Enforces max 3 iterations, terminating in `UNRESOLVED` and escalation. |
| **Historical Incident Memory** | **YES** | **YES** | **PRELIMINARY**| **NO** | **NO** | `backend/app/knowledge/incident_memory.py`: Vector and category indexing of validated recovery plans. |
| **Comparative Benchmark Suite** | **PARTIAL** | **YES** | **PRELIMINARY**| **PRELIMINARY** | **UNVERIFIED** | 8 scenarios run across closed-loop; standalone automated 3-strategy harness missing from disk. |

---

## 3. Scientific Categorization of the Research Contribution

In scholarly peer review, a project must not be labeled "novel" simply because it integrates existing open-source frameworks. The contribution must be precisely classified according to standard ACM/IEEE computer science taxonomy:

```
                            [AegisOps AI Contribution Profile]
                                           |
      +------------------------------------+-----------------------------------+
      |                                    |                                   |
[Algorithmic Innovation]         [Systems Integration]              [Policy & Methodology]
- 7-Factor RCA Scoring           - FastAPI + SQLite WAL             - Bounded Closed-Loop Refinement
- 8-Point Empirical Validation   - OpenTelemetry Ingestion          - Replica Pre-Testing Policy
(Incremental Adaptation)         - React SRE Dashboard              - Failure-Driven Candidate Re-ranking
                                 (Solid Engineering,               (PRIMARY RESEARCH CONTRIBUTION)
                                  Not Scientific Novelty)
```

### 3.1 Primary Research Contribution: A Closed-Loop Feedback-Guided Recovery Policy
The genuine scientific novelty of AegisOps AI does **not** reside in its statistical anomaly detectors (EWMA, Z-Score, IQR are classical algorithms) or in its use of LLMs (Gemini 3.8 Flash is an external commercial foundation model).

Rather, the defensible research contribution is **the formalization and empirical evaluation of an Evidence-Guided Closed-Loop Recovery Policy for distributed systems**. 
Specifically:
1. **Pre-Flight Execution Validation in Shadow Replicas:** Demonstrating that validating candidate actions against injected failure workloads in an isolated replica before applying them to the operational environment eliminates false-positive recovery declarations ($\text{FRR} \to 0\%$).
2. **Evidence-Driven Refinement Semantics:** Establishing that when an initial recovery candidate fails (either by failing to extinguish root symptoms or by triggering collateral regressions/side effects), passing the structured failure delta back into candidate generation yields higher recovery rates than static retries or one-shot attempts.
3. **Safety-Bounded Iteration Invariant ($k \le 3$):** Providing an empirical proof that unconstrained self-healing produces secondary outages, whereas bounded iteration coupled with immutable escalation guarantees system safety.

### 3.2 Secondary Contribution: An Open Empirical Benchmark for Incident Recovery
AegisOps AI formalizes **8 reproducible, ground-truth distributed failure scenarios** (`SCENARIO_DEFINITIONS`) with explicit mathematical success criteria and side-effect detection boundaries. This provides an evaluation testbed for comparing automated SRE recovery strategies.

---

## 4. Distinction from Closest Prior Art

| Dimension | Classical Runbook Automation (Ansible, SaltStack) | 1st-Gen Self-Healing (Kubernetes Restart Policies) | ML/Causal RCA (MicroRCA, DéjàVu) | Frontier LLM Agents (DevOps-GPT, D-Bot) | **AegisOps AI (Proposed Contribution)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution Trigger** | Manual or static alert threshold | Container exit code / probe failure | Anomaly graph inference | Text prompt / LLM tool-calling | **Consensus multi-detector anomaly + 7-factor RCA** |
| **Pre-Flight Testing** | None (direct execution) | None (blind container reboot) | None (purely diagnostic) | Rare / unconstrained sandbox | **Isolated Replica Twin workload replay** |
| **Validation Mechanism**| Exit code $0$ from shell script | Kubelet liveness probe | None | LLM self-reflection on stdout | **8-point multi-metric empirical oracle ($P_1-P_8$)** |
| **Refinement Behavior**| None (script terminates on error)| Exponential backoff reboot loop | None (re-runs diagnosis) | Stochastic multi-turn prompt retry | **Deterministic failure-evidence candidate re-ranking** |
| **Side-Effect Guard** | None | Blind restart can trigger boot storms | None | None | **Explicit collateral degradation check across neighbor services** |
| **Termination Safety** | Unbounded if automated | CrashLoopBackOff | N/A | Variable / token limit | **Strict bounded iterations ($k \le 3$) + human escalation** |

---

## 5. Summary Verdict on Research Contribution

The contribution of AegisOps AI is scientifically defensible **if and only if** it is framed as a **rigorous empirical evaluation of closed-loop, evidence-guided recovery policies versus one-shot and validation-only baselines**. Claims that AegisOps AI invented automated remediation, root cause analysis, or digital twins are indefensible and must be firmly rejected.

