import csv
import os

# Deliverable 16: feature_comparison_matrix.csv
feature_matrix_path = os.path.join("report_audit", "feature_comparison_matrix.csv")

capabilities = [
    {
        "capability": "Unified Multi-Modal Telemetry Ingestion (Metrics, Logs, Traces)",
        "aegisops": "Yes",
        "datadog": "Yes",
        "dynatrace": "Yes",
        "new_relic": "Yes",
        "pagerduty": "Partial",
        "shoreline": "Partial",
        "prometheus_grafana_otel": "Yes",
        "evidence_source": "AegisOps: backend/app/integrations/normalizer.py; Datadog Docs (2026); Dynatrace OneAgent Docs (2026); OTel Spec v1.34",
        "confidence": "HIGH"
    },
    {
        "capability": "Unsupervised & Statistical Anomaly Detection (EWMA, Z-Score, Isolation Forest)",
        "aegisops": "Yes",
        "datadog": "Yes",
        "dynatrace": "Yes",
        "new_relic": "Yes",
        "pagerduty": "No documented evidence",
        "shoreline": "Partial",
        "prometheus_grafana_otel": "Partial",
        "evidence_source": "AegisOps: backend/app/ai/detectors/; Datadog Watchdog (2026); Dynatrace Davis AI (2026); Prometheus PromQL alerts only",
        "confidence": "HIGH"
    },
    {
        "capability": "Multi-Service Event & Incident Correlation",
        "aegisops": "Yes",
        "datadog": "Yes",
        "dynatrace": "Yes",
        "new_relic": "Yes",
        "pagerduty": "Yes",
        "shoreline": "No documented evidence",
        "prometheus_grafana_otel": "Partial",
        "evidence_source": "AegisOps: backend/app/services/event_correlator.py; PagerDuty Event Intelligence Docs (2026); Dynatrace Davis Causation Engine (2026)",
        "confidence": "HIGH"
    },
    {
        "capability": "15-Question Structured Evidence Root Cause Analysis (RCA)",
        "aegisops": "Yes",
        "datadog": "Partial",
        "dynatrace": "Partial",
        "new_relic": "Partial",
        "pagerduty": "No documented evidence",
        "shoreline": "No documented evidence",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/rca/evidence_package.py; Commercial tools report topological causal graphs but lack structured 15-question evidence contracts",
        "confidence": "HIGH"
    },
    {
        "capability": "Dual-Solution Synthesis (AI LLM vs Curated Knowledge Base Consensus)",
        "aegisops": "Yes",
        "datadog": "No documented evidence",
        "dynatrace": "No documented evidence",
        "new_relic": "No documented evidence",
        "pagerduty": "No documented evidence",
        "shoreline": "No documented evidence",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/rca/dual_solution_engine.py; Novel research feature comparing LLM with verified runbooks and flagging consensus vs conflict",
        "confidence": "HIGH"
    },
    {
        "capability": "Dynamic Service Dependency Graph & Blast Radius Analysis",
        "aegisops": "Yes",
        "datadog": "Yes",
        "dynatrace": "Yes",
        "new_relic": "Yes",
        "pagerduty": "Partial",
        "shoreline": "Partial",
        "prometheus_grafana_otel": "Partial",
        "evidence_source": "AegisOps: backend/app/services/dependency_graph.py; Dynatrace Smartscape (2026); Datadog Service Map (2026)",
        "confidence": "HIGH"
    },
    {
        "capability": "Automated Allowlisted Remediation Actions",
        "aegisops": "Yes",
        "datadog": "Partial",
        "dynatrace": "Partial",
        "new_relic": "Partial",
        "pagerduty": "Partial",
        "shoreline": "Yes",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/healing/actions.py; Shoreline.io Incident Automation Platform (2026); PagerDuty Runbook Automation (2026)",
        "confidence": "HIGH"
    },
    {
        "capability": "Pre-Execution Digital Twin Replica Sandbox Testing (17-Step Lifecycle)",
        "aegisops": "Yes",
        "datadog": "No documented evidence",
        "dynatrace": "No documented evidence",
        "new_relic": "No documented evidence",
        "pagerduty": "No documented evidence",
        "shoreline": "No documented evidence",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/replica/remediation_lab.py; Commercial SRE platforms execute remediation directly in production or staging without isolated twin pre-validation",
        "confidence": "HIGH"
    },
    {
        "capability": "Independent Post-Recovery Validation (Empirical 8-Point Verification)",
        "aegisops": "Yes",
        "datadog": "Partial",
        "dynatrace": "Partial",
        "new_relic": "Partial",
        "pagerduty": "No documented evidence",
        "shoreline": "Partial",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/healing/sandbox_engine.py & backend/app/validation/; Commercial platforms check basic service health check, not multi-dimensional empirical criteria",
        "confidence": "HIGH"
    },
    {
        "capability": "Evidence-Guided Bounded Recovery Refinement (Retry Ceiling)",
        "aegisops": "Yes",
        "datadog": "No documented evidence",
        "dynatrace": "No documented evidence",
        "new_relic": "No documented evidence",
        "pagerduty": "No documented evidence",
        "shoreline": "Partial",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/healing/closed_loop_engine.py; Core research contribution preventing infinite retry storms via bounded iteration limits and escalating on failure",
        "confidence": "HIGH"
    },
    {
        "capability": "Persistent Incident Memory & Verified Pattern Learning",
        "aegisops": "Yes",
        "datadog": "Partial",
        "dynatrace": "Yes",
        "new_relic": "Partial",
        "pagerduty": "Yes",
        "shoreline": "No documented evidence",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/models/knowledge.py & verified_recovery_patterns; PagerDuty Past Incidents (2026); Dynatrace Davis Problem Archive (2026)",
        "confidence": "HIGH"
    },
    {
        "capability": "Human-in-the-Loop Governance & Role-Based Approval Center",
        "aegisops": "Yes",
        "datadog": "Partial",
        "dynatrace": "No documented evidence",
        "new_relic": "No documented evidence",
        "pagerduty": "Yes",
        "shoreline": "Yes",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/healing/approval_manager.py & frontend/src/pages/ApprovalsPage.tsx; Shoreline Approvals (2026); PagerDuty Change Requests (2026)",
        "confidence": "HIGH"
    },
    {
        "capability": "Dynamic LLM Model Discovery & Configurable Reasoning Effort (Gemini 3.8 Flash)",
        "aegisops": "Yes",
        "datadog": "Partial",
        "dynatrace": "Partial",
        "new_relic": "Partial",
        "pagerduty": "No documented evidence",
        "shoreline": "No documented evidence",
        "prometheus_grafana_otel": "No documented evidence",
        "evidence_source": "AegisOps: backend/app/ai/gemini_provider.py; Commercial AI assistants use proprietary blackbox models without client-configurable reasoning budgets or dynamic discovery",
        "confidence": "HIGH"
    },
    {
        "capability": "Multi-Tenant Data Isolation & Tenant-Scoped Policies",
        "aegisops": "Yes",
        "datadog": "Yes",
        "dynatrace": "Yes",
        "new_relic": "Yes",
        "pagerduty": "Yes",
        "shoreline": "Yes",
        "prometheus_grafana_otel": "Partial",
        "evidence_source": "AegisOps: backend/app/models/tenant.py & tenant_policies; Standard commercial SaaS feature; self-hosted Prometheus requires multi-tenant Cortex/Thanos",
        "confidence": "HIGH"
    }
]

with open(feature_matrix_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "capability", "aegisops", "datadog", "dynatrace", "new_relic",
        "pagerduty", "shoreline", "prometheus_grafana_otel", "evidence_source", "confidence"
    ])
    writer.writeheader()
    writer.writerows(capabilities)

print(f"Wrote {len(capabilities)} rows to {feature_matrix_path}")

# Deliverable 15: existing_system_comparison.csv
system_comparison_path = os.path.join("report_audit", "existing_system_comparison.csv")

systems = [
    {
        "system_name": "Datadog",
        "primary_domain": "Cloud-Scale Observability & APM",
        "core_strengths": "Massive integration ecosystem (600+ integrations), unified metric/log/trace exploration, Watchdog anomaly detection, synthetic monitoring.",
        "key_limitations": "Remediation is primarily webhook or third-party dispatched; lacks digital twin replica testing and evidence-guided closed-loop refinement.",
        "incident_remediation_paradigm": "Detect & Alert -> Third-Party Orchestration (Runbooks / Webhooks / PagerDuty)",
        "license_deployment": "Proprietary Commercial SaaS (Per-host / Per-GB billing)",
        "official_reference": "Datadog Product Documentation (https://docs.datadoghq.com, Accessed Oct 2026)",
        "comparability_with_aegisops": "Complementary: AegisOps ingests Datadog-style telemetry but specializes in downstream autonomous closed-loop diagnosis and replica validation."
    },
    {
        "system_name": "Dynatrace",
        "primary_domain": "Application Performance Management & AIOps",
        "core_strengths": "OneAgent automated deployment, Davis AI deterministic root-cause causation engine, Smartscape topological service dependency mapping.",
        "key_limitations": "Closed proprietary causation engine; automated recovery actions execute directly against target infrastructure without isolated digital twin verification.",
        "incident_remediation_paradigm": "Deterministic Davis AI Root Cause -> AutomationEngine Workflow Execution",
        "license_deployment": "Proprietary Commercial SaaS / Managed (Davis Data Unit consumption)",
        "official_reference": "Dynatrace Documentation (https://docs.dynatrace.com, Accessed Oct 2026)",
        "comparability_with_aegisops": "Direct architectural benchmark for topology and causation; AegisOps adds pre-deployment replica isolation and dual-solution consensus."
    },
    {
        "system_name": "Shoreline.io",
        "primary_domain": "Incident Automation & Runbook Remediation",
        "core_strengths": "Fleet-wide distributed action execution, sub-second Op packs, explicit safety checks, human-in-the-loop approvals, allowlisted CLI actions.",
        "key_limitations": "Executes remediation scripts directly on target hosts without digital twin pre-validation; lacks multi-detector anomaly and dual-solution RCA.",
        "incident_remediation_paradigm": "Automated Execution on Live Hosts via Shoreline Agents",
        "license_deployment": "Proprietary Commercial SaaS (Per-node pricing)",
        "official_reference": "Shoreline Documentation (https://docs.shoreline.io, Accessed Oct 2026)",
        "comparability_with_aegisops": "Closest commercial analog for allowlisted actions and approvals; AegisOps extends this with safe replica pre-execution and bounded refinement."
    },
    {
        "system_name": "PagerDuty",
        "primary_domain": "Incident Management, Alert Aggregation & On-Call",
        "core_strengths": "Industry-standard on-call alerting, incident escalation policies, Event Intelligence noise reduction, Runbook Automation (Rundeck).",
        "key_limitations": "Relies on external monitoring systems for telemetry; does not synthesize deep telemetry evidence or conduct autonomous empirical validation.",
        "incident_remediation_paradigm": "Incident Alerting & Human Escalation -> Runbook Automation Execution",
        "license_deployment": "Proprietary Commercial SaaS (Per-user seat pricing)",
        "official_reference": "PagerDuty Documentation (https://support.pagerduty.com, Accessed Oct 2026)",
        "comparability_with_aegisops": "AegisOps integrates with PagerDuty webhook dispatching for SLA alerts while serving as the autonomous diagnostic and recovery engine."
    },
    {
        "system_name": "OpenTelemetry + Prometheus + Grafana",
        "primary_domain": "Open-Source Observability & Metrics Infrastructure",
        "core_strengths": "Vendor-neutral open standard (CNCF), zero licensing fee, massive community adoption, flexible PromQL alerting.",
        "key_limitations": "Raw telemetry collection and visualization only; lacks automated root cause inference, remediation planning, replica testing, and recovery memory.",
        "incident_remediation_paradigm": "Passive Ingestion & Dashboarding (No native recovery capability)",
        "license_deployment": "Open Source (Apache 2.0 / AGPL / Self-Hosted or Cloud Managed)",
        "official_reference": "OpenTelemetry Documentation (https://opentelemetry.io/docs, Accessed Oct 2026)",
        "comparability_with_aegisops": "Foundational layer: AegisOps implements standard OTel receivers (`customer_otel_collector.py`) and builds autonomous SRE intelligence on top."
    },
    {
        "system_name": "AegisOps AI (Proposed Prototype)",
        "primary_domain": "Autonomous SRE & Closed-Loop Validated Recovery Platform",
        "core_strengths": "Digital Twin Replica Lab (17-step lifecycle), Dual-Solution RCA (Gemini 3.8 Flash vs KB consensus), 8-point empirical validation, bounded refinement ceiling.",
        "key_limitations": "Prototype implementation with synthetic/container adapters for local testbed; requires cloud provider adapters for large-scale enterprise production fleets.",
        "incident_remediation_paradigm": "Detect -> 15-Q RCA -> Dual-Solution -> Replica Twin Test -> Approved Safe Execution -> Empirical Validation -> Memory",
        "license_deployment": "Academic / Open Research Prototype (FastAPI, React, SQLite/PostgreSQL)",
        "official_reference": "AegisOps AI Source Code & Research Documentation (Oct 2026)",
        "comparability_with_aegisops": "Subject of audit: Bridges gap between observability alerts and safe, verified, execution-backed recovery."
    }
]

with open(system_comparison_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "system_name", "primary_domain", "core_strengths", "key_limitations",
        "incident_remediation_paradigm", "license_deployment", "official_reference", "comparability_with_aegisops"
    ])
    writer.writeheader()
    writer.writerows(systems)

print(f"Wrote {len(systems)} rows to {system_comparison_path}")

