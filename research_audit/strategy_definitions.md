# Research Deliverable 07: Formal Mathematical & Algorithmic Definitions of Experimental Strategies

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Experimental Specification  
**Auditor Role:** Senior Research Scientist in Software Reliability & Distributed Systems  
**Date:** October 31, 2026  

---

## 1. Overview and Experimental Purpose

To rigorously test the primary research question ($\mathbf{RQ_0}$), three distinct recovery paradigms must be mathematically and procedurally defined:
1. **Strategy A (One-Shot Recovery):** Represents standard automated runbook execution in current industry practice (e.g., executing an Ansible playbook or Kubernetes Job upon alert trigger without post-execution telemetry validation).
2. **Strategy B (Validation-Only Recovery):** Represents modern runtime verification (e.g., executing a recovery action and validating system health against independent predicates, but aborting without retry upon failure).
3. **Strategy C (Closed-Loop Recovery):** The proposed research contribution, which evaluates recovery in an isolated replica, validates post-execution telemetry, and uses observed failure evidence to refine and retry alternative candidates within a bounded iteration policy ($k \le 3$).

---

## 2. Granular Specification of Strategy A: One-Shot Recovery

### 2.1 Workflow Pipeline
$$\text{Incident Detect} \longrightarrow \text{Select Top Candidate } c_1 \longrightarrow \text{Execute } c_1 \longrightarrow \text{Check Process Exit Code} \longrightarrow \text{Declare Recovered}$$

### 2.2 Operational Specification
- **Input Incident:** Standardized incident context $I = \langle \text{id}, \text{service}, \text{symptoms}, \text{telemetry}_0 \rangle$.
- **Candidate Generation:** Candidate pool $C = \{c_1, c_2, \dots, c_m\}$ generated via `solution_generator.generate_candidate_solutions()`.
- **Candidate Selection:** Deterministically selects $c^* = \arg\max_{c \in C} \text{confidence}(c)$.
- **Validation Timing:** **None.** Post-execution telemetry is not collected or evaluated.
- **Evidence Available:** Pre-incident telemetry $\text{telemetry}_0$ and error logs only.
- **Next Candidate Behavior:** None. If execution fails at the OS level (e.g., non-zero exit code), the trial terminates immediately.
- **Maximum Attempts:** Strictly $k_{\max} = 1$.
- **Stopping Condition:** Completion of the execution of $c^*$.
- **Success Criterion:** Command execution completes without raising an uncaught runtime exception ($\text{exit\_code} == 0$).
- **False Recovery Vulnerability:** High ($\text{FRR} \gg 0$). If $c^*$ executes cleanly but fails to eliminate root cause saturation or induces side effects, the strategy falsely marks the incident as recovered.

---

## 3. Granular Specification of Strategy B: Validation-Only Recovery

### 3.1 Workflow Pipeline
$$\text{Incident Detect} \longrightarrow \text{Select Top Candidate } c_1 \longrightarrow \text{Execute } c_1 \longrightarrow \text{Independent Oracle } \mathcal{V}(c_1) \longrightarrow \begin{cases} \text{VALIDATED} & \text{if } \mathcal{V} = \text{True} \\ \text{UNRESOLVED} & \text{if } \mathcal{V} = \text{False} \end{cases}$$

### 3.2 Operational Specification
- **Input Incident:** Identical incident context $I$ and candidate pool $C$ as Strategy A.
- **Candidate Selection:** Deterministically selects $c^* = c_1$.
- **Validation Timing:** Post-execution telemetry $\text{telemetry}_1$ is gathered after synthetic workload replay and evaluated by `recovery_validator.validate_solution()`.
- **Independent Success Oracle ($\mathcal{V}$):** Evaluates the 8-point empirical validation predicates:
  $$\mathcal{V}(c) = \bigwedge_{j=1}^8 P_j = \text{True}$$
  Where $P_1$ through $P_8$ assert error rate $< 5\%$, p95 latency $< 120\text{ ms}$, throughput $\ge 90\text{ rps}$, and zero collateral side effects on neighbor services.
- **Next Candidate Behavior:** **None.** If $\mathcal{V}(c^*) == \text{False}$, Strategy B records the attempt as failed, marks the incident as `UNRESOLVED`, and terminates.
- **Maximum Attempts:** Strictly $k_{\max} = 1$.
- **Stopping Condition:** Completion of validation oracle $\mathcal{V}(c^*)$.
- **Success Criterion:** $\mathcal{V}(c^*) == \text{True}$.
- **False Recovery Vulnerability:** Zero ($\text{FRR} \approx 0\%$). All false recoveries are intercepted by the independent oracle.

---

## 4. Granular Specification of Strategy C: Closed-Loop Recovery (AegisOps AI)

### 4.1 Workflow Pipeline
$$\begin{aligned}
&\text{Detect} \longrightarrow \text{Generate Candidates } C_0 \longrightarrow \\
&\left[ \text{Select } c_k \longrightarrow \text{Replica Exec} \longrightarrow \text{Replay Workload} \longrightarrow \text{Oracle } \mathcal{V}(c_k) \longrightarrow \begin{cases} \text{VALIDATED} & \text{Terminate} \\ \text{Refine } C_k \to C_{k+1} & \text{if } k < 3 \\ \text{ESCALATE} & \text{if } k = 3 \end{cases} \right]
\end{aligned}$$

### 4.2 Operational Specification
- **Input Incident:** Identical incident context $I$ and candidate pool $C_0$ as Strategies A and B.
- **Execution Environment:** Isolated Digital Replica sandbox (`replica_environment.py`). Production services are never mutated directly.
- **Validation Timing:** Post-execution telemetry $\text{telemetry}_k$ evaluated after each iteration $k$.
- **Evidence Available to Strategy:**
  1. Pre-incident telemetry $\text{telemetry}_0$ and logs.
  2. Post-execution telemetry delta $\Delta \text{telemetry}_k = \text{telemetry}_k - \text{telemetry}_0$.
  3. Structured failure analysis: unresolved conditions, collateral side effects, and improved conditions.
- **Evidence-Guided Refinement Algorithm:**
  If $\mathcal{V}(c_k) == \text{False}$, the remaining candidate pool $C_k \setminus \{c_k\}$ is re-ranked:
  $$\text{score}(c_{i}, \text{FailureAnalysis}_k) = \text{confidence}(c_i) - \text{penalty}(c_i, \text{unresolved}_k) - \text{side\_effect\_penalty}(c_i, \text{side\_effects}_k)$$
  Candidates sharing the failed mechanism are penalized; orthogonal candidates are promoted to $c_{k+1}$.
- **Maximum Attempts:** Strictly bounded by $k_{\max} = 3$.
- **Stopping Conditions:**
  1. $\mathcal{V}(c_k) == \text{True} \implies \text{VALIDATED}$ (Success).
  2. $k = 3 \land \mathcal{V}(c_3) == \text{False} \implies \text{UNRESOLVED}$ (Escalation to human).
  3. Empty candidate pool $C_k = \emptyset \implies \text{UNRESOLVED}$.
- **Safety Invariant:** Never permits autonomous host execution when side effects are detected or iterations reach $k=3$.

---

## 5. Comparative Strategy Matrix & Baseline Fairness Analysis

| Architectural Dimension | Strategy A: One-Shot | Strategy B: Validation-Only | Strategy C: Closed-Loop | Fairness & Control Audit |
| :--- | :---: | :---: | :---: | :--- |
| **Initial Scenario & Fault Injection** | Identical | Identical | Identical | **100% Controlled:** Same seed, same fault parameters. |
| **Initial Candidate Pool ($C_0$)** | Identical | Identical | Identical | **100% Controlled:** Generated by same solution catalog. |
| **First Candidate Selected ($c_1$)** | Identical | Identical | Identical | **100% Controlled:** Always chooses top confidence candidate. |
| **Execution Environment** | Direct / Local | Direct / Local | Isolated Replica Sandbox | **Documented Difference:** Sandbox prevents host damage. |
| **Post-Execution Telemetry Check** | None (Exit code only)| 8-Point Oracle $\mathcal{V}$ | 8-Point Oracle $\mathcal{V}$ | **Experimental Treatment:** Tests effect of oracle. |
| **Refinement Feedback** | None | None | Failure Delta $\to$ Re-rank | **Experimental Treatment:** Tests effect of refinement. |
| **Maximum Attempt Budget ($k_{\max}$)**| 1 | 1 | 3 | **Documented Overhead:** Closed-loop uses up to 3x attempts. |
| **Final State Classifications** | Recovered / Failed | Validated / Unresolved | Validated / Unresolved / Escalated | **Standardized:** Validated recoveries judged identically. |

---

## 6. Summary of Strategy Invariants

To guarantee that empirical comparisons are scientifically valid:
1. Every trial across all three strategies receives the exact same initial fault injection parameters and initial service metrics.
2. The independent validation oracle $\mathcal{V}$ applied in Strategy B and Strategy C uses the exact same numerical threshold bounds ($P_1$ through $P_8$).
3. The computational budget advantage of Strategy C (allowing up to 3 attempts vs. 1 attempt) is explicitly tracked and accounted for in the evaluation metrics via Average Recovery Attempts ($\text{ARA}$) and Time to Validated Recovery ($\text{TTVR}$).

