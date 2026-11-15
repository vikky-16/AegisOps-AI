import csv
import os

output_path = os.path.join("report_audit", "quantitative_values_inventory.csv")

records = [
    # Database and code metrics
    {"metric": "Total Managed Database Tables", "value": "48", "unit": "tables", "source": "aegisops.db / sqlite_master", "how_measured": "Queried sqlite_master for table count", "meaning": "Scope of persistent entities across incidents, approvals, replicas, and telemetry", "evidence_quality": "Measured runtime value"},
    {"metric": "Database File Size", "value": "8.08", "unit": "megabytes (MB)", "source": "aegisops.db", "how_measured": "os.path.getsize('aegisops.db')", "meaning": "Current footprint of active SQLite database with WAL journal", "evidence_quality": "Measured runtime value"},
    {"metric": "Total Registered FastAPI Endpoints", "value": "367", "unit": "endpoints", "source": "backend/app/main.py", "how_measured": "len(app.routes) with HTTP method filtering", "meaning": "Complete REST API surface across 40 router modules", "evidence_quality": "Measured runtime value"},
    {"metric": "Total Backend Python Modules", "value": "180+", "unit": "modules", "source": "backend/app/**/*.py", "how_measured": "Filesystem search excluding virtual environments", "meaning": "Backend modular architecture across 24 packages", "evidence_quality": "Measured runtime value"},
    {"metric": "Frontend React Page Components", "value": "27", "unit": "views", "source": "frontend/src/pages/*.tsx", "how_measured": "Count of TSX page components in frontend/src/pages", "meaning": "Total user-facing screens and dashboards in application", "evidence_quality": "Measured runtime value"},
    {"metric": "Total Discovered Pytest Test Functions", "value": "399", "unit": "test functions", "source": "backend/tests/test_*.py", "how_measured": "pytest --collect-only across 57 test files", "meaning": "Automated verification test suite coverage", "evidence_quality": "Measured runtime value"},
    {"metric": "Frontend Vite Build Time", "value": "3.42", "unit": "seconds (s)", "source": "npm --prefix frontend run build", "how_measured": "Measured via Vite production compiler (2,404 modules)", "meaning": "Client bundle compilation performance with Rolldown", "evidence_quality": "Measured runtime value"},
    
    # Anomaly Detection & Telemetry Thresholds
    {"metric": "Z-Score Anomaly Threshold", "value": "3.0", "unit": "standard deviations (sigma)", "source": "backend/app/ai/detectors/zscore_detector.py", "how_measured": "Configured constant in ZScoreDetector", "meaning": "Statistical deviation limit for triggering metric anomaly episodes", "evidence_quality": "Configured constant"},
    {"metric": "EWMA Smoothing Alpha Factor", "value": "0.3", "unit": "factor (0.0-1.0)", "source": "backend/app/ai/detectors/ewma_detector.py", "how_measured": "Configured constant in EWMADetector", "meaning": "Weight assigned to latest metric sample in moving average", "evidence_quality": "Configured constant"},
    {"metric": "Consecutive Cycle Breach Count", "value": "3", "unit": "cycles", "source": "backend/app/ai/detectors/consecutive_breach_detector.py", "how_measured": "Configured threshold in ConsecutiveBreachDetector", "meaning": "Required consecutive breached windows before declaring confirmed anomaly to prevent flapping", "evidence_quality": "Configured constant"},
    {"metric": "IQR Outlier Multiplier", "value": "1.5", "unit": "IQR multiplier", "source": "backend/app/ai/detectors/iqr_detector.py", "how_measured": "Configured constant in IQRDetector", "meaning": "Tukey boxplot fence multiplier for non-parametric outlier detection", "evidence_quality": "Configured constant"},
    {"metric": "Isolation Forest Contamination Rate", "value": "0.05", "unit": "proportion (5%)", "source": "backend/app/ai/detectors/isolation_forest_detector.py", "how_measured": "Scikit-learn model hyperparameter", "meaning": "Expected fraction of anomalous vectors in unsupervised telemetry baseline", "evidence_quality": "Configured constant"},
    {"metric": "Telemetry Streaming Poll Interval", "value": "1000", "unit": "milliseconds (ms)", "source": "frontend/src/pages/SettingsPage.tsx", "how_measured": "Default UI pollInterval state", "meaning": "Client polling frequency for dashboard telemetry bus", "evidence_quality": "Configured constant"},
    {"metric": "Storage Warning Threshold", "value": "95.0", "unit": "percent (%)", "source": "backend/app/storage/manager.py", "how_measured": "Configured ceiling in storage manager", "meaning": "Disk capacity threshold triggering automatic compression and cold tiering", "evidence_quality": "Configured constant"},

    # AI Reasoning & LLM Parameters
    {"metric": "Gemini Preferred Default Model", "value": "gemini-3.8-flash", "unit": "model identifier", "source": "backend/app/ai/gemini_provider.py", "how_measured": "GeminiProvider.DEFAULT_MODEL", "meaning": "Official Google Gemini multimodal model prioritized for SRE operations", "evidence_quality": "Configured constant"},
    {"metric": "Reasoning Low Thinking Budget", "value": "0", "unit": "thinking tokens", "source": "backend/app/ai/gemini_provider.py", "how_measured": "REASONING_BUDGET_MAP['low']", "meaning": "Thinking token budget for latency-sensitive probes and fast triage", "evidence_quality": "Configured constant"},
    {"metric": "Reasoning Medium Thinking Budget", "value": "2048", "unit": "thinking tokens", "source": "backend/app/ai/gemini_provider.py", "how_measured": "REASONING_BUDGET_MAP['medium']", "meaning": "Balanced thinking token budget for routine RCA and remediation", "evidence_quality": "Configured constant"},
    {"metric": "Reasoning High Thinking Budget", "value": "8192", "unit": "thinking tokens", "source": "backend/app/ai/gemini_provider.py", "how_measured": "REASONING_BUDGET_MAP['high']", "meaning": "Deep thinking token budget for complex multi-step RCA and Replica Lab trials", "evidence_quality": "Configured constant"},
    {"metric": "Model Discovery Cache TTL", "value": "300", "unit": "seconds (s)", "source": "backend/app/ai/gemini_provider.py", "how_measured": "Cache expiry delta in discover_models()", "meaning": "In-memory cache duration for GET /v1beta/models to avoid quota exhaustion", "evidence_quality": "Configured constant"},
    {"metric": "Gemini Connection Probe Max Tokens", "value": "3", "unit": "tokens", "source": "backend/app/ai/gemini_provider.py", "how_measured": "generationConfig.maxOutputTokens in test_connection()", "meaning": "Minimal output token allocation for sub-second connection verification", "evidence_quality": "Configured constant"},
    {"metric": "Gemini RCA Generation Max Output Tokens", "value": "1200", "unit": "tokens", "source": "backend/app/ai/gemini_provider.py", "how_measured": "generate_response default argument", "meaning": "Maximum output length for structured root cause JSON responses", "evidence_quality": "Configured constant"},

    # Recovery, Sandbox & Empirical Validation
    {"metric": "Maximum Recovery Attempts (Ceiling)", "value": "3", "unit": "iterations", "source": "backend/app/api/ai_config.py", "how_measured": "get_max_recovery_attempts() / MAX_RECOVERY_ATTEMPTS", "meaning": "Bounded refinement limit preventing infinite recovery retry storms", "evidence_quality": "Configured constant"},
    {"metric": "Empirical Validation Layers", "value": "8", "unit": "validation criteria", "source": "backend/app/healing/sandbox_engine.py", "how_measured": "run_empirical_validation() criteria list", "meaning": "Multi-dimensional empirical check verifying error rate, latency, health, and side-effects", "evidence_quality": "Configured constant"},
    {"metric": "Replica Lab Lifecycle Stages", "value": "17", "unit": "stages", "source": "backend/app/replica/remediation_lab.py", "how_measured": "RemediationLab.run_experiment() logged stages", "meaning": "Controlled scientific experiment lifecycle stages from allocation to validation", "evidence_quality": "Configured constant"},
    {"metric": "Synthetic Workload Requests Per Experiment", "value": "2500", "unit": "requests", "source": "backend/app/replica/remediation_lab.py", "how_measured": "test_workload_json configuration", "meaning": "Stress workload replayed against replica to reproduce failure and verify fix", "evidence_quality": "Simulated value"},
    {"metric": "Synthetic Workload Concurrency", "value": "50", "unit": "concurrent workers", "source": "backend/app/replica/remediation_lab.py", "how_measured": "test_workload_json configuration", "meaning": "Simulated concurrency for replica stress testing", "evidence_quality": "Simulated value"},
    {"metric": "Independent Validation AI Timeout", "value": "10.0", "unit": "seconds (s)", "source": "backend/app/api/ai_config.py", "how_measured": "VALIDATION_AI_TIMEOUT_SEC in store", "meaning": "Timeout ceiling for independent peer model validation", "evidence_quality": "Configured constant"},

    # Measured Performance Timings (from benchmark_results.json)
    {"metric": "Approval Center Initial Load Time", "value": "103.13", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() over GET /api/approvals", "meaning": "Measured API latency for operator approval center", "evidence_quality": "Measured runtime value"},
    {"metric": "Approval Stats Aggregation Time", "value": "2.58", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() over GET /api/approvals/stats", "meaning": "Fast SQL aggregation latency across approval states", "evidence_quality": "Measured runtime value"},
    {"metric": "Incidents List Load Time", "value": "160.39", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() over GET /api/incidents", "meaning": "Time to retrieve and serialize 100 incident records", "evidence_quality": "Measured runtime value"},
    {"metric": "Incident Detail Load Time", "value": "21.31", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() over GET /api/incidents/{id}", "meaning": "Time to fetch single incident with full evidence JSON", "evidence_quality": "Measured runtime value"},
    {"metric": "Recovery Planning Time (DB Pool)", "value": "0.032", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() in EvidenceGroundedDecisionEngine", "meaning": "Rule-based and evidence-guided recovery evaluation latency", "evidence_quality": "Measured runtime value"},
    {"metric": "Recovery Planning Time (Cache)", "value": "0.021", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() in EvidenceGroundedDecisionEngine", "meaning": "Decision table evaluation for cache saturation", "evidence_quality": "Measured runtime value"},
    {"metric": "Sandbox Initialization Time", "value": "0.113", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() in initialize_sandbox()", "meaning": "Time to allocate and bind isolated digital twin state", "evidence_quality": "Measured runtime value"},
    {"metric": "Recovery Step Execution Time", "value": "501.45", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() executing connection pool reset", "meaning": "Target service action invocation and telemetry delta capture", "evidence_quality": "Measured runtime value"},
    {"metric": "8-Point Empirical Validation Time", "value": "402.32", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() across 8 validation criteria", "meaning": "Full post-recovery empirical verification latency", "evidence_quality": "Measured runtime value"},
    {"metric": "Simulation Scenario Load Time", "value": "3.33", "unit": "milliseconds (ms)", "source": "benchmark_results.json", "how_measured": "time.perf_counter() over GET /api/testing-lab/scenarios", "meaning": "Retrieval latency for fault injection scenario catalog", "evidence_quality": "Measured runtime value"},

    # High-Throughput Load Benchmark (scripts/load_benchmark.py)
    {"metric": "Target Telemetry Throughput Tier 1", "value": "100", "unit": "events per second (EPS)", "source": "scripts/load_benchmark.py", "how_measured": "High-frequency synthetic streamer", "meaning": "Baseline telemetry ingestion rate", "evidence_quality": "Experiment-derived value"},
    {"metric": "Target Telemetry Throughput Tier 2", "value": "500", "unit": "events per second (EPS)", "source": "scripts/load_benchmark.py", "how_measured": "High-frequency synthetic streamer", "meaning": "Medium enterprise load telemetry ingestion rate", "evidence_quality": "Experiment-derived value"},
    {"metric": "Target Telemetry Throughput Tier 3", "value": "1000", "unit": "events per second (EPS)", "source": "scripts/load_benchmark.py", "how_measured": "High-frequency synthetic streamer", "meaning": "Peak burst load telemetry ingestion rate", "evidence_quality": "Experiment-derived value"},
    {"metric": "Synthetic Anomaly Injection Ratio", "value": "5.0", "unit": "percent (%)", "source": "scripts/load_benchmark.py", "how_measured": "i % 20 == 0 in event generator", "meaning": "Controlled anomaly injection frequency during load tests", "evidence_quality": "Configured constant"}
]

fieldnames = ["metric", "value", "unit", "source", "how_measured", "meaning", "evidence_quality"]

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)

print(f"Wrote {len(records)} quantitative parameters to {output_path}")

