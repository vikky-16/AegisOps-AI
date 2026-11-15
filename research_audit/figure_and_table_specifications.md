# Research Deliverable 23: Publication-Grade Figure and Table Technical Specifications

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Visualization & Manuscript Figure Specifications  
**Target Standard:** IEEE / ACM Formatting Guidelines for Systems Research Papers  
**Date:** October 31, 2026  

---

## 1. Overview and Visualization Standards

To ensure academic rigor, all figures and tables in the research paper must be generated strictly from verified data in `research_audit/recalculated_results.csv` and `research_audit/effect_size_and_confidence_intervals.csv`. **No fabricated data points, smoothing curves, or unmeasured latency points are permitted.**

Every figure specification below includes its exact academic purpose, required data columns, axes, units, aggregation methods, uncertainty representations (95% confidence intervals), and source code references.

---

## 2. Granular Figure Technical Specifications

### Figure 1: Three-Strategy Operational Workflow Comparison
- **Visual Type:** Directed Process Flowchart / Swimlane Diagram (Mermaid or TikZ).
- **Purpose:** Visually contrast how Strategy A (One-Shot), Strategy B (Validation-Only), and Strategy C (Closed-Loop) handle detection, execution, validation, and failure.
- **Components:**
  - *Lane 1 (One-Shot):* Trigger $\to$ Select $c_1 \to$ Execute $\to$ Check Exit Code $0 \to$ Declare Recovered (Highlighting vulnerability to false recovery).
  - *Lane 2 (Validation-Only):* Trigger $\to$ Select $c_1 \to$ Execute $\to$ Oracle $\mathcal{V}(c_1) \to$ Terminate (Validated or Unresolved).
  - *Lane 3 (Closed-Loop):* Trigger $\to$ Select $c_k \to$ Replica Sandbox Replay $\to$ Oracle $\mathcal{V}(c_k) \to$ Feedback Failure Delta $\to$ Re-rank $C_{k+1} \to$ Bounded Retry ($k \le 3$) $\to$ Verified Recovery or Escalation.
- **Source Reference:** `research_audit/strategy_definitions.md`.

### Figure 2: AegisOps AI System Architecture & Feedback Data Flow
- **Visual Type:** Block Architectural Diagram.
- **Purpose:** Illustrate the 3-tier architecture (Perception, Cognition, Execution) and the isolated feedback channel from the Replica Sandbox to the Candidate Refinement Engine.
- **Components:** OpenTelemetry sliding buffers, 7-factor RCA engine, Gemini 3.8 Flash provider, Digital Replica Lab, 8-point validation oracle, and HMAC approval center.
- **Source Reference:** `report_audit/architecture_diagrams.md`, Figure 1.

### Figure 3: Recovery Success Rate (RSR) vs. False Recovery Rate (FRR) Across Strategies
- **Visual Type:** Grouped Bar Chart with Asymmetric Error Bars.
- **Purpose:** Primary empirical result demonstrating that Strategy C achieves superior recovery while eliminating false recoveries.
- **Data Source:** `research_audit/strategy_comparison_results.csv` & `effect_size_and_confidence_intervals.csv`.
- **X-Axis:** Recovery Strategy (`One-Shot`, `Validation-Only`, `Closed-Loop`).
- **Y-Axis:** Percentage ($0\%$ to $100\%$).
- **Series 1 (RSR):** One-Shot ($25.0\%$, CI: $[7.1\%, 59.1\%]$), Validation-Only ($25.0\%$, CI: $[7.1\%, 59.1\%]$), Closed-Loop ($87.5\%$, CI: $[52.9\%, 97.8\%]$).
- **Series 2 (FRR):** One-Shot ($75.0\%$, CI: $[40.9\%, 92.9\%]$), Validation-Only ($0.0\%$, CI: $[0.0\%, 65.8\%]$), Closed-Loop ($0.0\%$, CI: $[0.0\%, 35.4\%]$).
- **Uncertainty Representation:** 95% Wilson Score Binomial Confidence Intervals plotted as asymmetric error bars.

### Figure 4: Recovery Attempt Overhead Distribution ($\text{ARA}$)
- **Visual Type:** Stacked / Segmented Horizontal Bar Chart.
- **Purpose:** Quantify the computational trade-off of closed-loop refinement by showing the attempt count breakdown across all 8 evaluated scenarios.
- **Data Source:** `research_audit/recalculated_results.csv`.
- **Categories:** Attempt 1 Success (2 scenarios), Attempt 2 Success (5 scenarios), Attempt 3 Escalated (1 scenario).
- **Annotation:** Mean Attempts $= 1.875$ (All Incidents) / $1.714$ (Recovered Only). Cliff's Delta $d = +0.875$ ($p = 0.026$).

### Figure 5: Stratified Performance Across Distributed Fault Classes
- **Visual Type:** Grouped Horizontal Bar Chart or Dot-Plot.
- **Purpose:** Test Hypothesis H5 by showing recovery outcomes categorized by underlying failure mode.
- **Data Source:** `research_audit/fault_class_results.csv`.
- **Y-Axis (Fault Classes):** Resource Exhaustion ($n=3$), Process Crash ($n=1$), Thread Starvation ($n=1$), Dependency Cascade ($n=1$), Queue Backlog ($n=1$), Configuration Syntax ($n=1$).
- **X-Axis:** Validated Recovery Status ($100\%$ vs $0\%$).
- **Key Insight Highlighted:** Strategy C achieves $100\%$ resolution on all 5 transient/resource fault classes, while safely terminating and escalating on Configuration Syntax Error without false recovery.

---

## 3. Granular Table Specifications for Manuscript

| Table Number | Table Title | Data Columns | Primary Scientific Finding Communicated |
| :---: | :--- | :--- | :--- |
| **Table 1** | Strategy Comparison across 8 Scenarios | Scenario ID, Fault Class, Strategy A Outcome, Strategy B Outcome, Strategy C Outcome, Attempts, Escalation | Full trial-by-trial ground truth performance (Deliverable 13). |
| **Table 2** | Aggregate Performance & Statistical Tests | Metric, Strategy A, Strategy B, Strategy C, Absolute Difference, Effect Size, Statistical Test, $p$-value | Formal hypothesis evaluation summary (Deliverable 16). |
| **Table 3** | Per-Fault-Class Performance Breakdown | Fault Class, Number of Scenarios, One-Shot RSR, Closed-Loop RSR, Mean Attempts, Recovery Mechanism | Proves fault-class heterogeneity and safety termination (Deliverable 15). |
| **Table 4** | Related Work Comparative Matrix | System Name, Year, Problem, RCA Method, Sandbox Pre-Testing, Validation Oracle, Bounded Refinement | Positions AegisOps AI against 10 prior systems (Deliverable 20). |
| **Table 5** | Metric Definition and Denominator Audit | Metric Name, Symbol, Numerator, Denominator, Treatment of Unresolved, Treatment of Retries | Prevents denominator confounding and resolves ERR ambiguity (Deliverable 10). |

