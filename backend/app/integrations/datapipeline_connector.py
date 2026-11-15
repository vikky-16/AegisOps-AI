"""
Data Mart & ETL / ELT Data Pipeline Telemetry Connector
Monitors scheduled data warehouse syncs, data freshness, job durations, and data mart refresh delays.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class DataPipelineConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="datapipeline-monitor",
            name="Data Mart & Pipeline Connector",
            connector_type="DATA_PIPELINE",
            description="Operational monitoring for ETL/ELT pipelines, Data Warehouse syncs, and Data Mart refresh schedules.",
            auth_required=False,
            enabled=True
        )

    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        events: List[NormalizedTelemetryEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        if isinstance(raw_payload, dict):
            items = [raw_payload]
        elif isinstance(raw_payload, list):
            items = raw_payload
        else:
            items = []

        for item in items:
            pipeline_name = item.get("pipeline_name") or item.get("job_name") or "data-mart-sync"
            job_status = (item.get("status") or "SUCCESS").upper()
            delay_minutes = int(item.get("delay_minutes", 0))
            job_duration_sec = float(item.get("duration_seconds", 120.0))
            records_processed = int(item.get("records_processed", 0))

            sev = TelemetrySeverity.INFO
            evt_type = "PIPELINE_SUCCESS"
            msg = f"Data Mart '{pipeline_name}' completed successfully in {job_duration_sec:.1f}s ({records_processed:,} rows)."

            if job_status in ["FAILED", "ERROR"]:
                sev = TelemetrySeverity.ERROR
                evt_type = "DATA_PIPELINE_FAILED"
                msg = f"ERROR: Data Mart '{pipeline_name}' ETL job failed. Reason: {item.get('error_reason', 'Upstream DB connection timeout')}."
            elif delay_minutes >= 30 or job_status == "DELAYED":
                sev = TelemetrySeverity.WARNING
                evt_type = "DATA_MART_REFRESH_DELAYED"
                msg = f"WARNING: Data mart refresh for '{pipeline_name}' delayed by {delay_minutes} minutes."
            elif job_duration_sec > 1800.0:
                sev = TelemetrySeverity.WARNING
                evt_type = "ETL_EXECUTION_STALLED"
                msg = f"WARNING: ETL job duration ({job_duration_sec/60:.1f}m) exceeded expected SLA baseline."

            events.append(NormalizedTelemetryEvent(
                timestamp=item.get("timestamp") or now_iso,
                source=f"etl-{pipeline_name}",
                environment="demo",
                service="data-mart-service",
                type=TelemetryType.DATA_PIPELINE_SIGNAL,
                severity=sev,
                event_type=evt_type,
                message=msg,
                metrics={
                    "delay_minutes": float(delay_minutes),
                    "duration_seconds": job_duration_sec,
                    "records_processed": float(records_processed)
                },
                metadata={
                    "pipeline_name": pipeline_name,
                    "upstream_data_source": item.get("upstream_source", "database-service"),
                    "target_mart": item.get("target_mart", "executive_analytics")
                }
            ))

        self.record_ingest(len(events))
        return events
