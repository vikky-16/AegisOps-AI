import csv

metrics = [
    {
        "Metric Name": "Recovery Success Rate",
        "Symbol": "RSR",
        "Exact Numerator": "Number of eligible incidents achieving independently verified recovery (Oracle V == True)",
        "Exact Denominator": "Total eligible incidents initiated under the strategy",
        "Unit": "Percentage (%)",
        "Formula": "RSR = (N_verified / N_total) * 100",
        "Direction": "Higher is better",
        "Unresolved Incidents": "Counted in denominator (penalizes RSR)",
        "False Recoveries": "Excluded from numerator (does not credit false recovery)",
        "Timeouts & Crashes": "Counted in denominator as failed",
        "Retries Impact": "Single incident with multiple retries counts as exactly 1 unit in denominator",
        "Unsafe Actions": "Fails validation oracle, counted as failed recovery",
        "Source Module": "backend/app/validation/validator.py",
        "Ambiguity / Finding": "Clear at incident level; prior smoke run correctly counted 2/8 (25%) and 7/8 (87.5%)."
    },
    {
        "Metric Name": "False Recovery Rate",
        "Symbol": "FRR",
        "Exact Numerator": "Number of incidents declared recovered that failed independent oracle validation",
        "Exact Denominator": "Total incidents declared recovered by the strategy",
        "Unit": "Percentage (%)",
        "Formula": "FRR = (N_false_declared / N_total_declared) * 100",
        "Direction": "Lower is better",
        "Unresolved Incidents": "Excluded from denominator if declared unresolved",
        "False Recoveries": "Primary numerator",
        "Timeouts & Crashes": "N/A (not declared recovered)",
        "Retries Impact": "Evaluated at final declared state of incident",
        "Unsafe Actions": "Treated as false recovery if strategy declared success despite side effect",
        "Source Module": "backend/app/validation/validator.py",
        "Ambiguity / Finding": "Critical finding: In One-Shot, 6 of 8 declared recoveries were false (FRR=75%). In Closed-Loop, FRR=0%."
    },
    {
        "Metric Name": "Failed Attempt Rate (or False Anomaly Rate)",
        "Symbol": "FARR",
        "Exact Numerator": "Number of recovery attempts that failed validation or produced side effects",
        "Exact Denominator": "Total recovery attempts executed",
        "Unit": "Percentage (%)",
        "Formula": "FARR = (N_failed_attempts / N_total_attempts) * 100",
        "Direction": "Lower is better",
        "Unresolved Incidents": "All attempts for unresolved incidents counted as failed",
        "False Recoveries": "Counted in numerator as failed attempt",
        "Timeouts & Crashes": "Counted in numerator as failed attempt",
        "Retries Impact": "Evaluated per attempt (Attempt-level metric, NOT incident-level)",
        "Unsafe Actions": "Counted in numerator as failed attempt",
        "Source Module": "backend/app/healing/closed_loop_engine.py",
        "Ambiguity / Finding": "Historical report listed 25% across all three strategies, but acronym meaning was undocumented."
    },
    {
        "Metric Name": "Effective Recovery Rate (Historical Acronym ERR)",
        "Symbol": "ERR",
        "Exact Numerator": "Number of incidents successfully resolved (identical to RSR)",
        "Exact Denominator": "Total eligible incidents started",
        "Unit": "Percentage (%)",
        "Formula": "ERR = (N_resolved / N_total) * 100",
        "Direction": "Higher is better",
        "Unresolved Incidents": "Counted in denominator",
        "False Recoveries": "Excluded from numerator",
        "Timeouts & Crashes": "Counted in denominator",
        "Retries Impact": "Incident-level unit",
        "Unsafe Actions": "Excluded from numerator",
        "Source Module": "Historical smoke report / closed_loop_engine.py",
        "Ambiguity / Finding": "CRITICAL DISCREPANCY: Historical table reported ERR=87.5% for closed-loop (7/8). In standard SRE literature, ERR means Escalation Rate (which was 1/8=12.5%). Historical report used ERR as 'Effective Recovery Rate'."
    },
    {
        "Metric Name": "Average Recovery Attempts",
        "Symbol": "ARA",
        "Exact Numerator": "Total recovery attempt executions across all evaluated incidents",
        "Exact Denominator": "Total incidents evaluated (or total recovered incidents)",
        "Unit": "Attempts / Incident",
        "Formula": "ARA_all = Total_Attempts / N_all; ARA_rec = Total_Attempts_Rec / N_rec",
        "Direction": "Lower is better (given equivalent RSR)",
        "Unresolved Incidents": "Included in ARA_all (counts all 3 attempts); excluded in ARA_rec",
        "False Recoveries": "Counted as 1 attempt",
        "Timeouts & Crashes": "Counted as 1 attempt",
        "Retries Impact": "Directly measures the attempt overhead of iterative refinement",
        "Unsafe Actions": "Counted as an attempt",
        "Source Module": "backend/app/healing/closed_loop_engine.py",
        "Ambiguity / Finding": "CONFIRMED: Closed-loop executed 15 total attempts across 8 incidents (ARA_all = 15/8 = 1.875). Among the 7 recovered, 12 attempts were run (ARA_rec = 12/7 = 1.714). Matches reported values."
    },
    {
        "Metric Name": "Time to Validated Recovery",
        "Symbol": "TTVR",
        "Exact Numerator": "Elapsed wall-clock time from incident detection to validated recovery",
        "Exact Denominator": "Single incident duration (or mean across recovered incidents)",
        "Unit": "Seconds (s)",
        "Formula": "TTVR = t_validation_passed - t_incident_detected",
        "Direction": "Lower is better",
        "Unresolved Incidents": "Right-censored at timeout / max iterations (cannot use simple arithmetic mean)",
        "False Recoveries": "Excluded (never reached validated recovery)",
        "Timeouts & Crashes": "Right-censored",
        "Retries Impact": "Sum of execution and validation latencies across all attempted iterations",
        "Unsafe Actions": "Increases TTVR due to rollback and retry delay",
        "Source Module": "backend/app/replica/controlled_environment.py",
        "Ambiguity / Finding": "Must use survival analysis / Kaplan-Meier estimator or report median of recovered to avoid censoring bias."
    },
    {
        "Metric Name": "Safe Execution Rate",
        "Symbol": "SER",
        "Exact Numerator": "Number of executions that completed without triggering collateral side effects",
        "Exact Denominator": "Total incidents (or total attempts executed)",
        "Unit": "Percentage (%)",
        "Formula": "SER = (N_safe / N_total) * 100",
        "Direction": "Higher is better",
        "Unresolved Incidents": "Evaluated based on whether executed actions triggered side effects",
        "False Recoveries": "Unsafe if side effect occurred; safe if error simply persisted without new harm",
        "Timeouts & Crashes": "Counted as safe unless crash caused cascade",
        "Retries Impact": "CRITICAL DENOMINATOR MISMATCH: Strategy A used N=8 incidents; Strategy C used N=15 attempts",
        "Unsafe Actions": "Primary numerator decrement",
        "Source Module": "backend/app/validation/validator.py",
        "Ambiguity / Finding": "CONFIRMED DENOMINATOR BIAS: In closed-loop, SER was calculated over 15 attempts (5/15 = 33.3%), while in one-shot it was calculated over 8 incidents (5/8 = 62.5%). Mixing attempts and incidents distorted SER."
    }
]

# Write Deliverable 10: metric_definition_audit.csv
csv_path = "research_audit/metric_definition_audit.csv"
fieldnames = [
    "Metric Name", "Symbol", "Exact Numerator", "Exact Denominator", "Unit",
    "Formula", "Direction", "Unresolved Incidents", "False Recoveries",
    "Timeouts & Crashes", "Retries Impact", "Unsafe Actions", "Source Module",
    "Ambiguity / Finding"
]

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for m in metrics:
        writer.writerow(m)

print(f"Generated {csv_path} with {len(metrics)} audited metrics.")

# Write Deliverable 11: metric_implementation_matrix.csv
impl_rows = [
    {"Metric": "RSR", "Implemented in Source": "YES", "Function / File": "validator.py:validate_solution()", "Unit Test Covered": "YES (test_closed_loop_recovery_validation.py)", "Status": "Mathematically Sound"},
    {"Metric": "FRR", "Implemented in Source": "YES", "Function / File": "validator.py:validate_solution()", "Unit Test Covered": "YES", "Status": "Mathematically Sound"},
    {"Metric": "FARR", "Implemented in Source": "PARTIAL", "Function / File": "closed_loop_engine.py:execute_history", "Unit Test Covered": "NO", "Status": "Ambiguous Acronym; Needs Standardization"},
    {"Metric": "ERR", "Implemented in Source": "AMBIGUOUS", "Function / File": "closed_loop_engine.py", "Unit Test Covered": "NO", "Status": "Conflicted: Effective Recovery Rate vs Escalation Rate"},
    {"Metric": "ARA", "Implemented in Source": "YES", "Function / File": "closed_loop_engine.py:iteration_count", "Unit Test Covered": "YES", "Status": "Mathematically Sound (Distinguish All vs Recovered)"},
    {"Metric": "TTVR", "Implemented in Source": "YES", "Function / File": "benchmark_and_verify.py:timings", "Unit Test Covered": "YES", "Status": "Requires Censoring Correction for Unresolved"},
    {"Metric": "SER", "Implemented in Source": "YES", "Function / File": "validator.py:side_effect_detected", "Unit Test Covered": "YES", "Status": "Denominator Mismatch: Standardize to Incident Denominator"}
]

csv_path2 = "research_audit/metric_implementation_matrix.csv"
fieldnames2 = ["Metric", "Implemented in Source", "Function / File", "Unit Test Covered", "Status"]

with open(csv_path2, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames2)
    writer.writeheader()
    for r in impl_rows:
        writer.writerow(r)

print(f"Generated {csv_path2}")

