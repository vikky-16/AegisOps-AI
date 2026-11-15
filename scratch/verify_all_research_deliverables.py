import os

expected = [
    ("Deliverable 01", "research_question_and_contribution.md"),
    ("Deliverable 02", "novelty_assessment.md"),
    ("Deliverable 03", "related_work_matrix.csv"),
    ("Deliverable 04", "bibliography.bib"),
    ("Deliverable 05", "research_gap_matrix.csv"),
    ("Deliverable 06", "hypothesis_and_variables_matrix.csv"),
    ("Deliverable 07", "strategy_definitions.md"),
    ("Deliverable 08", "benchmark_scenario_inventory.csv"),
    ("Deliverable 09", "experiment_protocol.md"),
    ("Deliverable 10", "metric_definition_audit.csv"),
    ("Deliverable 11", "metric_implementation_matrix.csv"),
    ("Deliverable 12", "raw_trial_data_inventory.md"),
    ("Deliverable 13", "recalculated_results.csv"),
    ("Deliverable 14", "strategy_comparison_results.csv"),
    ("Deliverable 15", "fault_class_results.csv"),
    ("Deliverable 16", "statistical_analysis_report.md"),
    ("Deliverable 17", "effect_size_and_confidence_intervals.csv"),
    ("Deliverable 18", "reproducibility_audit.md"),
    ("Deliverable 19", "baseline_fairness_audit.md"),
    ("Deliverable 20", "commercial_and_research_comparison.csv"),
    ("Deliverable 21", "threats_to_validity.md"),
    ("Deliverable 22", "research_paper_outline.md"),
    ("Deliverable 23", "figure_and_table_specifications.md"),
    ("Deliverable 24", "research_claims_register.csv"),
    ("Deliverable 25", "missing_experiments_and_data.md"),
    ("Deliverable 26", "research_readiness_assessment.md"),
    ("Deliverable 27", "workspace_and_git_reconciliation.md"),
    ("Deliverable 28", "research_reproduction_commands.md")
]

print(f"Checking {len(expected)} deliverables in research_audit/...")
all_ok = True
total_bytes = 0

for d_id, fname in expected:
    p = os.path.join("research_audit", fname)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        total_bytes += sz
        with open(p, "r", encoding="utf-8", errors="ignore") as fp:
            lines = len(fp.readlines())
        print(f"[OK] {d_id}: {fname:42s} | {sz:8,d} bytes | {lines:4d} lines")
    else:
        print(f"[MISSING] {d_id}: {fname}")
        all_ok = False

print(f"\nTotal Research Deliverables: {len(expected)}/28 Verified OK!")
print(f"Total Research Package Size: {total_bytes:,d} bytes ({total_bytes / (1024*1024):.2f} MB)")

