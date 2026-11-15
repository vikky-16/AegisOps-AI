import csv

comparisons = [
    # Research Prototypes
    {
        "Work": "MicroRCA (Wu et al.)",
        "Type": "Research Prototype",
        "Year": "2020",
        "Problem": "Root cause localization in dynamic microservices without code instrumentation",
        "Approach": "Graph modeling of metrics and PageRank anomaly diffusion",
        "Validation Method": "None (Diagnostic localization only)",
        "Feedback / Refinement": "None",
        "Safety Constraints": "Read-only metric collection",
        "Benchmark": "Sock Shop, Train-Ticket on Kubernetes",
        "Metrics": "Top-k Accuracy, Precision, Recall",
        "Key Limitations": "Does not propose, execute, or validate recovery actions",
        "Difference from AegisOps": "AegisOps AI couples RCA to automated replica testing and closed-loop recovery refinement"
    },
    {
        "Work": "DéjàVu (Zhang et al.)",
        "Type": "Research Prototype",
        "Year": "2022",
        "Problem": "Recurring incident diagnosis in cloud microservices",
        "Approach": "GNN-based historical incident memory retrieval",
        "Validation Method": "None (Offline diagnosis)",
        "Feedback / Refinement": "None",
        "Safety Constraints": "Read-only telemetry retrieval",
        "Benchmark": "Commercial bank telemetry + Sock Shop",
        "Metrics": "Top-k Recall, MRR, Diagnosis Time",
        "Key Limitations": "Passive historical matching; does not test remedies before application",
        "Difference from AegisOps": "AegisOps AI tests retrieved historical remedies in isolated shadow twins prior to production"
    },
    {
        "Work": "Sieve (Sun et al.)",
        "Type": "Research Prototype",
        "Year": "2021",
        "Problem": "Testing self-healing controllers and recovery bugs in microservices",
        "Approach": "State-machine guided fault injection during recovery",
        "Validation Method": "Post-injection state assertion against controller invariants",
        "Feedback / Refinement": "None (Testing/bug-finding tool)",
        "Safety Constraints": "Local testbed only",
        "Benchmark": "10 Production Kubernetes Operators",
        "Metrics": "Bugs detected, Silent recovery failure count",
        "Key Limitations": "Offline testing framework; not an operational incident recovery system",
        "Difference from AegisOps": "AegisOps AI performs runtime incident recovery and refinement during live operations"
    },
    {
        "Work": "Gandalf (Li et al.)",
        "Type": "Research Prototype / Deployed System",
        "Year": "2020",
        "Problem": "Safe software and configuration rollout in cloud infrastructure",
        "Approach": "Multi-tier sliding window anomaly detection and progressive canary gating",
        "Validation Method": "Canary step-metric regression analysis",
        "Feedback / Refinement": "Single-step automated rollback (no multi-candidate refinement)",
        "Safety Constraints": "Canary blast-radius limits, automated abort",
        "Benchmark": "Microsoft Azure compute platform",
        "Metrics": "Precision, Recall, Detection Latency, Rollback Accuracy",
        "Key Limitations": "Limited to deployment rollback; cannot diagnose or remediate runtime state corruptions",
        "Difference from AegisOps": "AegisOps AI generates and refines multi-action recovery plans for runtime state failures"
    },
    {
        "Work": "D-Bot (Zhou et al.)",
        "Type": "Research Prototype",
        "Year": "2024",
        "Problem": "Database performance anomaly diagnosis and parameter tuning",
        "Approach": "LLM agent with database tool calling and tree-of-thought prompt reasoning",
        "Validation Method": "SQL query latency evaluation post-tuning",
        "Feedback / Refinement": "Multi-turn prompt reflection",
        "Safety Constraints": "Offline test database or human prompt review",
        "Benchmark": "PostgreSQL, MySQL, openGauss under TPC-C",
        "Metrics": "Diagnosis Accuracy, Query Latency, Time to Resolve",
        "Key Limitations": "Lacks isolated replica twin testing and deterministic termination bounds",
        "Difference from AegisOps": "AegisOps AI wraps LLM reasoning in replica execution and strict bounded refinement (k<=3)"
    },
    {
        "Work": "DevOps-GPT (Ahmed et al.)",
        "Type": "Research Prototype",
        "Year": "2024",
        "Problem": "Automated software operations via multi-agent LLM collaboration",
        "Approach": "Cooperative role-playing agents (Triage, SRE, QA)",
        "Validation Method": "Conversational self-reflection and QA agent review",
        "Feedback / Refinement": "Natural language prompt retry",
        "Safety Constraints": "Token budget limits",
        "Benchmark": "Synthetic microservice incident logs",
        "Metrics": "Resolution Rate, Time to Remediate, Token Count",
        "Key Limitations": "Susceptible to ungrounded LLM hallucination and non-deterministic retry loops",
        "Difference from AegisOps": "AegisOps AI uses mathematical empirical validation predicates (P1-P8) and deterministic re-ranking"
    },

    # Commercial Platforms (Publicly Documented Capabilities)
    {
        "Work": "Shoreline.io",
        "Type": "Commercial Product",
        "Year": "2024",
        "Problem": "Incident automation and interactive distributed debugging at scale",
        "Approach": "Fleet-wide distributed agent, expressive Op language, automated runbook actions",
        "Validation Method": "Post-action alarm clearance check (Single metric threshold)",
        "Feedback / Refinement": "None (Fails runbook or invokes secondary fallback runbook)",
        "Safety Constraints": "Execution limits, approval gates, command allowlists",
        "Benchmark": "Proprietary customer workloads (Public benchmarks unavailable)",
        "Metrics": "MTTR, Alarm reduction percentage (Vendor reported)",
        "Key Limitations": "Relies on pre-authored deterministic runbooks; lacks shadow replica pre-execution",
        "Difference from AegisOps": "AegisOps AI synthesizes candidate plans and refines them in digital replica twins before host execution"
    },
    {
        "Work": "Dynatrace Davis AI",
        "Type": "Commercial Product",
        "Year": "2024",
        "Problem": "Enterprise observability, causation-based anomaly detection, and auto-remediation",
        "Approach": "Deterministic dependency topology graph (Smartscape) + causal AI engine",
        "Validation Method": "Problem closure tracking via Davis AI root-cause state",
        "Feedback / Refinement": "External webhook triggers Ansible / ServiceNow workflows",
        "Safety Constraints": "Read-only by default; execution delegated to external automation",
        "Benchmark": "Proprietary enterprise customer clouds",
        "Metrics": "Problem detection lead time, event noise reduction",
        "Key Limitations": "Execution is delegated to external runbook engines; lacks internal replica testing lab",
        "Difference from AegisOps": "AegisOps AI tightly couples diagnosis, replica simulation, and closed-loop refinement internally"
    },
    {
        "Work": "PagerDuty AIOps",
        "Type": "Commercial Product",
        "Year": "2024",
        "Problem": "Event correlation, noise reduction, and automated incident routing",
        "Approach": "Machine learning incident clustering, past-incident lookups, Runbook Automation",
        "Validation Method": "Human responder confirmation or external monitoring alert clearance",
        "Feedback / Refinement": "None (Alert re-triggers if problem persists)",
        "Safety Constraints": "Role-based access control, incident escalation policies",
        "Benchmark": "Proprietary enterprise operational data",
        "Metrics": "Alert compression ratio, incident escalation latency",
        "Key Limitations": "Focused on incident triage and human orchestration; lacks empirical recovery verification",
        "Difference from AegisOps": "AegisOps AI provides autonomous replica testing and evidence-guided recovery refinement"
    },

    # Open Source Frameworks
    {
        "Work": "OpenTelemetry + Prometheus + Alertmanager",
        "Type": "Open Source Standard",
        "Year": "2024",
        "Problem": "Standardized distributed telemetry collection and static alert threshold routing",
        "Approach": "Vendor-neutral metrics, traces, and logs collection pipeline",
        "Validation Method": "Alert expression evaluation (PromQL boolean rules)",
        "Feedback / Refinement": "None (Alert routing only)",
        "Safety Constraints": "N/A (Passive monitoring framework)",
        "Benchmark": "CNCF community standard microservice benchmarks",
        "Metrics": "Ingestion throughput, CPU/memory overhead, scraping latency",
        "Key Limitations": "Pure telemetry pipeline; zero autonomous diagnosis, recovery, or refinement capabilities",
        "Difference from AegisOps": "AegisOps AI uses OpenTelemetry as its perception layer and builds autonomous closed-loop recovery above it"
    }
]

csv_path = "research_audit/commercial_and_research_comparison.csv"
fieldnames = list(comparisons[0].keys())

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for c in comparisons:
        writer.writerow(c)

print(f"Generated {csv_path} with {len(comparisons)} research and commercial systems.")

