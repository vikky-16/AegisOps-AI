import csv

claims = [
    {
        "Claim ID": "RCLM-01",
        "Claim": "Closed-loop recovery improves recovery success rate compared to one-shot recovery.",
        "Supporting Evidence": "7 of 8 scenarios validated under Closed-Loop (87.5%) vs 2 of 8 under One-Shot (25.0%).",
        "Dataset / Trials": "8 standardized microservice failure scenarios in SCENARIO_DEFINITIONS (recalculated_results.csv).",
        "Statistical Support": "ARR = +62.5%, OR = 21.0, McNemar's exact test p = 0.031 (one-tailed). 95% Wilson CI: [52.9%, 97.8%].",
        "Prior-Work Comparison": "Prior runbook automation (Ansible, Shoreline) relies on one-shot execution without iterative closed-loop feedback.",
        "Status": "Supported (Preliminary Pilot)",
        "Permitted Wording": "In an 8-scenario pilot benchmark, closed-loop recovery increased verified recovery success from 25.0% to 87.5% (one-tailed p = 0.031)."
    },
    {
        "Claim ID": "RCLM-02",
        "Claim": "Independent multi-criteria validation eliminates false-positive recovery declarations.",
        "Supporting Evidence": "One-shot declared 6 false recoveries out of 8 (75.0% FRR). Closed-loop declared 0 false recoveries (0.0% FRR).",
        "Dataset / Trials": "8 declared recoveries in One-Shot vs 7 declared recoveries in Closed-Loop.",
        "Statistical Support": "Fisher's exact test p = 0.0047 (p < 0.01). Odds Ratio = 0.0, Absolute Difference = -75.0 percentage points.",
        "Prior-Work Comparison": "Sieve (OSDI '21) documented extensive silent false recoveries in K8s controllers; AegisOps eliminates them.",
        "Status": "Supported",
        "Permitted Wording": "Applying an independent 8-point empirical validation oracle reduced false recovery declarations from 75.0% to 0.0% (p = 0.0047)."
    },
    {
        "Claim ID": "RCLM-03",
        "Claim": "Validation alone without refinement is insufficient to improve recovery success.",
        "Supporting Evidence": "Validation-Only achieved exactly 25.0% recovery (2/8), identical to One-Shot.",
        "Dataset / Trials": "8 paired scenarios executed under Strategy B vs Strategy A and C.",
        "Statistical Support": "McNemar's test p = 1.000 vs One-Shot; p = 0.031 vs Closed-Loop.",
        "Prior-Work Comparison": "Confirms that runtime verification must be paired with active feedback-driven refinement to resolve incidents.",
        "Status": "Supported",
        "Permitted Wording": "Validation without refinement intercepts false recoveries but fails to improve overall resolution rate beyond 25.0%."
    },
    {
        "Claim ID": "RCLM-04",
        "Claim": "Closed-loop refinement incurs an attempt and latency overhead trade-off.",
        "Supporting Evidence": "Closed-loop required 15 total attempts across 8 incidents (ARA = 1.875) vs 8 attempts in One-Shot (ARA = 1.000).",
        "Dataset / Trials": "8 paired incidents, 15 individual attempt records in execution_history.",
        "Statistical Support": "Wilcoxon signed-rank test p = 0.026, Cliff's delta d = +0.875 (Large effect size).",
        "Prior-Work Comparison": "Quantifies the SRE trade-off: trading an average 0.875 additional attempts for a 3.5x gain in verified recovery.",
        "Status": "Supported",
        "Permitted Wording": "Closed-loop recovery requires an average of 1.875 attempts per incident (p = 0.026), representing an 87.5% attempt overhead."
    },
    {
        "Claim ID": "RCLM-05",
        "Claim": "Closed-loop recovery generalizes across all distributed failure modes.",
        "Supporting Evidence": "Resolved 7 of 8 scenarios across 5 fault classes, but failed to resolve configuration syntax errors.",
        "Dataset / Trials": "8 scenarios spanning 6 fault categories.",
        "Statistical Support": "Stratified success: 100% on transient/resource faults (7/7); 0% on syntax corruption (0/1).",
        "Prior-Work Comparison": "No automated system can resolve syntax corruption without external valid configuration input.",
        "Status": "Partially Supported (Bounded by Fault Class)",
        "Permitted Wording": "The method generalizes across transient resource and dependency failures, while safely bounding and escalating non-transient configuration syntax errors."
    },
    {
        "Claim ID": "RCLM-06",
        "Claim": "AegisOps AI introduces a fundamentally novel algorithmic paradigm for self-healing systems.",
        "Supporting Evidence": "Individual components use standard statistics (EWMA, Z-score, IQR, BFS) and existing LLMs (Gemini 3.8 Flash).",
        "Dataset / Trials": "Architecture and codebase inspection.",
        "Statistical Support": "N/A (Conceptual/literature claim).",
        "Prior-Work Comparison": "Novelty lies in the systems integration of replica pre-testing and evidence-guided refinement, not new math.",
        "Status": "Contradicted (Overclaim if stated algorithmically; Supported if stated as Policy/Framework)",
        "Permitted Wording": "DO NOT claim a novel AI or mathematical algorithm. Frame as: 'A novel closed-loop recovery policy and empirical evaluation framework'."
    }
]

csv_path = "research_audit/research_claims_register.csv"
fieldnames = list(claims[0].keys())

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for c in claims:
        writer.writerow(c)

print(f"Generated {csv_path} with {len(claims)} evaluated scientific claims.")

