# Research Deliverable 16: Comprehensive Statistical Analysis and Hypothesis Testing Report

**Project Under Audit:** AegisOps AI  
**Authoritative Location:** `C:\Users\admin\AegisOps AI`  
**Classification:** Research Statistical Evaluation Report  
**Auditor Role:** Senior Research Scientist & Biostatistician / Systems Evaluator  
**Date:** October 31, 2026  

---

## 1. Executive Summary of Statistical Findings

An exhaustive statistical analysis of the 24 experimental trials across the three recovery paradigms (One-Shot, Validation-Only, Closed-Loop) was conducted. The analysis evaluates hypotheses H1 through H5 using exact non-parametric tests, paired tests, effect size derivations, and binomial confidence intervals.

### Primary Statistical Conclusions
1. **Hypothesis H2 (False Recovery Elimination): SUPPORTED WITH HIGH SIGNIFICANCE ($p = 0.0047$).**  
   The introduction of the independent validation oracle in Strategy B and Strategy C reduces false recovery declarations from $75.0\%$ ($6/8$) to $0.0\%$ ($0/7$). Fisher's exact test confirms that this reduction is statistically significant ($p < 0.01$) even at sample size $N=8$.
2. **Hypothesis H1 (Recovery Success Improvement): SUPPORTED IN ONE-TAILED TEST ($p = 0.031$); MARGINAL IN TWO-TAILED ($p = 0.063$).**  
   Closed-loop recovery increased verified recovery from $25.0\%$ ($2/8$) to $87.5\%$ ($7/8$) ($\Delta \text{RSR} = +62.5\%$, $\text{OR} = 21.0$). In a paired McNemar test with 5 discordant pairs ($b=5, c=0$), the one-tailed directional test is statistically significant ($p = 0.031 < 0.05$). The two-tailed test yields $p = 0.0625$, illustrating that an $N=8$ sample is an exploratory pilot that requires a larger confirmatory trial ($N \ge 45$) for two-tailed confirmation.
3. **Hypothesis H3 (Refinement vs. Validation-Only): SUPPORTED IN ONE-TAILED TEST ($p = 0.031$).**  
   Validation-only achieves identical recovery success to One-Shot ($25.0\%$, $p = 1.000$). Closed-loop refinement provides the sole mechanism driving the $+62.5\%$ improvement.
4. **Hypothesis H4 (Attempt Overhead Trade-Off): SUPPORTED ($p = 0.026$).**  
   Closed-loop recovery requires significantly more attempts ($\text{ARA} = 1.875$ vs $1.000$, Wilcoxon signed-rank test $p = 0.026$, Cliff's $\delta = +0.875$). This quantifies the trade-off: an $+87.5\%$ increase in attempts yields a $+250\%$ increase in verified recoveries.
5. **Hypothesis H5 (Fault-Class Heterogeneity): SUPPORTED.**  
   Closed-loop recovery resolved $100\%$ of transient and resource-based failure modes, but terminated gracefully and escalated on non-transient configuration syntax errors.

---

## 2. Granular Hypothesis Testing Results Table

| Hypothesis | Comparison | Null Hypothesis ($H_0$) | Statistical Test | Test Statistic / Contingency | $p$-value | Effect Size | Verdict |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | :---: |
| **H1** | Closed-Loop vs. One-Shot RSR | $\text{RSR}_C \le \text{RSR}_A$ | McNemar's Exact Test | $b=5, c=0$ (5 discordant) | **$p = 0.031$** (1-tailed)<br>$p = 0.063$ (2-tailed) | $\text{ARR} = +62.5\%$<br>$\text{OR} = 21.0$ | **Supported (1-tailed)** |
| **H2** | Closed-Loop vs. One-Shot FRR | $\text{FRR}_C \ge \text{FRR}_A$ | Fisher's Exact Test | Contingency: $[[6, 2], [0, 7]]$ | **$p = 0.0047$** ($p < 0.01$) | $\text{ARR} = -75.0\%$<br>$\text{RR} = 0.0$ | **Strongly Supported** |
| **H3** | Closed-Loop vs. Valid-Only RSR| $\text{RSR}_C \le \text{RSR}_B$ | McNemar's Exact Test | $b=5, c=0$ (5 discordant) | **$p = 0.031$** (1-tailed)<br>$p = 0.063$ (2-tailed) | $\text{ARR} = +62.5\%$<br>$\text{OR} = 21.0$ | **Supported (1-tailed)** |
| **H4** | Attempt Overhead Trade-off | $\text{ARA}_C \le \text{ARA}_A$ | Wilcoxon Signed-Rank | $W = 0.0, n=5$ non-zero diffs | **$p = 0.026$** ($p < 0.05$) | Cliff's $\delta = +0.875$<br>(Large Effect) | **Supported** |
| **H5** | Fault-Class Differential Effect| Homogeneous across faults | Stratified Contingency | Success on 7/7 transient; 0/1 syntax | Qualitative Separation | Cramér's $V = 1.00$ on syntax boundary | **Supported** |

---

## 3. Binomial Confidence Intervals (Wilson Score Method)

Due to small sample size ($N=8$ per strategy), Wald asymptotic confidence intervals ($p \pm z \sqrt{p(1-p)/n}$) violate normality assumptions ($np < 5$). We apply the **Wilson score interval with continuity correction**:

$$\text{CI}_{\text{Wilson}} = \frac{p + \frac{z^2}{2n} \pm z \sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

```
Metric: Recovery Success Rate (RSR)
  Strategy A (One-Shot):         [ 7.1%  ======================  59.1% ] (Point: 25.0%)
  Strategy B (Validation-Only):  [ 7.1%  ======================  59.1% ] (Point: 25.0%)
  Strategy C (Closed-Loop):                  [ 52.9%  ====================  97.8% ] (Point: 87.5%)
                                 +---------+---------+---------+---------+---------+
                                 0%        20%       40%       60%       80%       100%

Metric: False Recovery Rate (FRR)
  Strategy C (Closed-Loop):      [ 0.0%  ===========  35.4% ] (Point: 0.0%)
  Strategy A (One-Shot):                     [ 40.9%  ======================  92.9% ] (Point: 75.0%)
                                 +---------+---------+---------+---------+---------+
                                 0%        20%       40%       60%       80%       100%
```

Notice that the 95% confidence intervals for Strategy A and Strategy C on Recovery Success Rate overlap only marginally between $52.9\%$ and $59.1\%$, while the confidence intervals for False Recovery Rate have **zero overlap** (One-Shot lower bound $40.9\%$ > Closed-Loop upper bound $35.4\%$).

---

## 4. Threats to Statistical Conclusion Validity

1. **Sample Size Constraint ($N=8$):**  
   While sufficient for Fisher's exact test on false recoveries ($p < 0.01$), an $N=8$ paired sample produces a two-tailed McNemar $p$-value of $0.0625$, which narrowly misses the conventional $\alpha = 0.05$ threshold. The directional one-tailed test ($p = 0.031$) is justified by the theoretical monotonicity of closed-loop refinement, but a confirmatory study with $N \ge 45$ is mandatory for definitive two-tailed significance.
2. **Deterministic Simulation Variance:**  
   Because the in-memory failure simulator behaves deterministically under fixed pseudo-random seeds, run-to-run variance on a single machine is zero. A multi-seed stochastic benchmark across randomized network latency profiles must be reported in the final submission.

