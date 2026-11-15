import csv

hypotheses = [
    {
        "Hypothesis ID": "H1",
        "Statement": "Closed-loop recovery achieves a higher recovery success rate than one-shot recovery.",
        "Independent Variable": "Recovery Strategy (One-Shot vs. Closed-Loop)",
        "Dependent Variable": "Recovery Success Rate (RSR)",
        "Controlled Variables": "Initial fault injection, service topology, telemetry buffer length, resource limits",
        "Experimental Unit": "Incident Trial (scenario execution under assigned strategy)",
        "Scenario Population": "8 standardized microservice failure scenarios in SCENARIO_DEFINITIONS",
        "Null Hypothesis (H0)": "RSR(Closed-Loop) <= RSR(One-Shot)",
        "Alternative Hypothesis (H1)": "RSR(Closed-Loop) > RSR(One-Shot)",
        "Expected Direction": "Positive (Closed-Loop > One-Shot)",
        "Statistical Test": "McNemar's test (paired binary outcomes) or Fisher's Exact Test",
        "Effect-Size Measure": "Odds Ratio (OR) and Absolute Risk Reduction (ARR)",
        "Confidence Interval Method": "Wilson Score Interval or Bootstrap 95% CI",
        "Practical Significance Criterion": "Absolute RSR improvement >= 20.0 percentage points",
        "Confounders & Threats": "Candidate solution ordering in solution catalog; simulation fidelity"
    },
    {
        "Hypothesis ID": "H2",
        "Statement": "Closed-loop recovery produces fewer false recovery declarations than one-shot recovery.",
        "Independent Variable": "Recovery Strategy (One-Shot vs. Closed-Loop)",
        "Dependent Variable": "False Recovery Rate (FRR)",
        "Controlled Variables": "Success oracle criteria, pre/post evaluation window, replay workload intensity",
        "Experimental Unit": "Declared Recovered Incidents",
        "Scenario Population": "8 standardized microservice failure scenarios",
        "Null Hypothesis (H0)": "FRR(Closed-Loop) >= FRR(One-Shot)",
        "Alternative Hypothesis (H1)": "FRR(Closed-Loop) < FRR(One-Shot)",
        "Expected Direction": "Negative (Closed-Loop < One-Shot)",
        "Statistical Test": "Fisher's Exact Test (small sample contingency table)",
        "Effect-Size Measure": "Relative Risk (RR) and Absolute Difference in FRR",
        "Confidence Interval Method": "Clopper-Pearson exact binomial CI",
        "Practical Significance Criterion": "FRR reduction >= 50.0 percentage points",
        "Confounders & Threats": "Definition of false recovery (command exit code vs multi-metric satisfaction)"
    },
    {
        "Hypothesis ID": "H3",
        "Statement": "Closed-loop recovery achieves a higher recovery success rate than validation-only recovery.",
        "Independent Variable": "Refinement Capability (Validation-Only vs. Closed-Loop)",
        "Dependent Variable": "Recovery Success Rate (RSR)",
        "Controlled Variables": "Validation criteria, candidate solution pool, execution environment",
        "Experimental Unit": "Incident Trial",
        "Scenario Population": "8 standardized microservice failure scenarios",
        "Null Hypothesis (H0)": "RSR(Closed-Loop) <= RSR(Validation-Only)",
        "Alternative Hypothesis (H1)": "RSR(Closed-Loop) > RSR(Validation-Only)",
        "Expected Direction": "Positive (Closed-Loop > Validation-Only)",
        "Statistical Test": "McNemar's Test for paired nominal data",
        "Effect-Size Measure": "Absolute Difference in Proportions (Risk Difference)",
        "Confidence Interval Method": "Agresti-Min Paired Difference 95% CI",
        "Practical Significance Criterion": "RSR improvement >= 25.0 percentage points",
        "Confounders & Threats": "Presence of multi-attempt solvable scenarios in test population"
    },
    {
        "Hypothesis ID": "H4",
        "Statement": "Evidence-guided refinement increases recovery attempts and latency, but improves final correctness.",
        "Independent Variable": "Refinement Capability (Static One-Shot vs. Evidence Refinement)",
        "Dependent Variable": "Average Recovery Attempts (ARA) and Time to Validated Recovery (TTVR)",
        "Controlled Variables": "Retry backoff time, replica provisioning latency, scenario difficulty",
        "Experimental Unit": "Incident Trial",
        "Scenario Population": "8 standardized microservice failure scenarios",
        "Null Hypothesis (H0)": "ARA(Closed-Loop) <= ARA(One-Shot) OR RSR(Closed-Loop) <= RSR(One-Shot)",
        "Alternative Hypothesis (H1)": "ARA(Closed-Loop) > ARA(One-Shot) AND RSR(Closed-Loop) > RSR(One-Shot)",
        "Expected Direction": "Trade-off: Higher attempts/latency yielding higher correctness",
        "Statistical Test": "Wilcoxon Signed-Rank Test (paired attempts) & paired t-test",
        "Effect-Size Measure": "Cliff's Delta (non-parametric ordinal effect size)",
        "Confidence Interval Method": "BCa (Bias-Corrected Accelerated) Bootstrap 95% CI",
        "Practical Significance Criterion": "Latency increase < 5x initial execution time; RSR gain >= 30%",
        "Confounders & Threats": "Replica container cold-start delay vs in-process simulated delay"
    },
    {
        "Hypothesis ID": "H5",
        "Statement": "The effect of closed-loop recovery varies significantly by fault class and recovery difficulty.",
        "Independent Variable": "Fault Class (Resource Saturation, Process Crash, Configuration Error, Dependency)",
        "Dependent Variable": "Recovery Success Rate and Attempt Count by Fault Category",
        "Controlled Variables": "Strategy logic, timeout policies, evaluation criteria",
        "Experimental Unit": "Scenario Sub-population",
        "Scenario Population": "Stratified fault classes in SCENARIO_DEFINITIONS",
        "Null Hypothesis (H0)": "RSR effect is invariant across all fault classes",
        "Alternative Hypothesis (H1)": "RSR effect is heterogeneous (transient faults succeed; syntax faults fail)",
        "Expected Direction": "Differential: High recovery on resource faults; bounded termination on syntax",
        "Statistical Test": "Cochran-Mantel-Haenszel (CMH) test for stratified categorical data",
        "Effect-Size Measure": "Cramér's V (strength of association across categories)",
        "Confidence Interval Method": "Stratified Bootstrap 95% CI",
        "Practical Significance Criterion": "Identifiable failure mode boundary where automated recovery escalates",
        "Confounders & Threats": "Small sample size per fault stratum (1-2 scenarios per class in smoke suite)"
    }
]

csv_path = "research_audit/hypothesis_and_variables_matrix.csv"
fieldnames = [
    "Hypothesis ID", "Statement", "Independent Variable", "Dependent Variable",
    "Controlled Variables", "Experimental Unit", "Scenario Population",
    "Null Hypothesis (H0)", "Alternative Hypothesis (H1)", "Expected Direction",
    "Statistical Test", "Effect-Size Measure", "Confidence Interval Method",
    "Practical Significance Criterion", "Confounders & Threats"
]

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for h in hypotheses:
        writer.writerow(h)

print(f"Generated {csv_path} with {len(hypotheses)} formal research hypotheses.")

