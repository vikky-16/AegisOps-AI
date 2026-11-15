import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import time
from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.analytics.incident_pipeline import incident_pipeline
from backend.app.analytics.feature_extractor import feature_extractor
from backend.app.analytics.anomaly_detector import anomaly_detector
from backend.app.analytics.baseline_engine import baseline_engine
from backend.app.monitoring.collector import collector

async def run_diag():
    print("Baseline warmup:", baseline_engine.warmup_seconds)
    baseline_engine.set_warmup_seconds(0.0)
    print("New warmup:", baseline_engine.warmup_seconds)

    # Simulate Gateway receiving 503 error
    evt = UnifiedTelemetryEvent(
        tenant_id="shopsphere",
        service_name="api-gateway",
        severity="ERROR",
        http_status=503,
        latency=8040.0,
        message="Gateway failed to reach Order Service: ReadTimeout",
        trace_id="trace-test-123"
    )
    incident_pipeline.record_telemetry_event(evt)

    # Simulate Order Service database latency
    evt2 = UnifiedTelemetryEvent(
        tenant_id="shopsphere",
        service_name="order-service",
        severity="INFO",
        http_status=200,
        latency=7200.0,
        message="Persisted order ord-123 to PostgreSQL in 7100ms",
        trace_id="trace-test-123"
    )
    incident_pipeline.record_telemetry_event(evt2)

    print("Active services:", feature_extractor.get_all_active_services())
    for t, s in feature_extractor.get_all_active_services():
        f = feature_extractor.get_features(t, s, 30.0)
        print(f"Features for {s}:", {k: f[k] for k in ["requests_per_second", "error_rate", "timeout_rate", "http_5xx_rate", "p95_latency", "database_latency"]})
        anom = anomaly_detector.evaluate(t, s, f)
        print(f"Anomaly for {s}: is_anom={anom.get('is_anomaly')}, score={anom.get('combined_score')}, triggers={anom.get('detectors_triggered')}")

    print("\nEvaluating operational mesh...")
    try:
        await incident_pipeline.evaluate_operational_mesh()
        print("evaluate_operational_mesh executed without error!")
    except Exception as e:
        import traceback
        traceback.print_exc()

    print("\nActive incidents in pipeline:", incident_pipeline._active_incidents)
    print("Active incidents in collector:", len(collector.active_incidents))
    for inc in collector.active_incidents:
        print("Collector Incident:", inc.get("incident_id"), inc.get("title"), inc.get("severity"))

if __name__ == "__main__":
    asyncio.run(run_diag())
