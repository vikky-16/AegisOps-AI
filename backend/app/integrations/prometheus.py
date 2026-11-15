"""
Prometheus Metrics Ingestion & Push Gateway Connector
Parses Prometheus text/JSON expositions into normalized metric signals.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class PrometheusConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="prometheus-gateway",
            name="Prometheus Metrics Ingest",
            connector_type="PROMETHEUS",
            description="Ingests timeseries metric expositions and Alertmanager webhook alerts.",
            auth_required=False,
            enabled=True
        )

    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        events: List[NormalizedTelemetryEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Handle Alertmanager Webhook Payload
        if isinstance(raw_payload, dict) and "alerts" in raw_payload:
            for alert in raw_payload.get("alerts", []):
                labels = alert.get("labels", {})
                annotations = alert.get("annotations", {})
                status = alert.get("status", "firing")
                svc = labels.get("service") or labels.get("job") or "prometheus-target"
                alertname = labels.get("alertname", "PrometheusAlert")

                sev = TelemetrySeverity.CRITICAL if labels.get("severity") == "critical" else TelemetrySeverity.WARNING
                
                events.append(NormalizedTelemetryEvent(
                    timestamp=alert.get("startsAt", now_iso),
                    source=f"prometheus-{svc}",
                    environment="demo",
                    service=svc.lower(),
                    type=TelemetryType.METRIC,
                    severity=sev if status == "firing" else TelemetrySeverity.INFO,
                    event_type=f"PROM_{alertname.upper()}",
                    message=annotations.get("description") or annotations.get("summary") or f"Alert {alertname} is {status}",
                    metadata={"labels": labels, "status": status}
                ))

        # Handle direct JSON metric dictionary
        elif isinstance(raw_payload, dict):
            svc = raw_payload.get("service", "prom-service")
            metrics = raw_payload.get("metrics", {})
            events.append(NormalizedTelemetryEvent(
                timestamp=now_iso,
                source=f"prometheus-{svc}",
                environment="demo",
                service=svc.lower(),
                type=TelemetryType.METRIC,
                severity=TelemetrySeverity.INFO,
                event_type="PROMETHEUS_METRIC_SCRAPE",
                message=f"Scraped {len(metrics)} timeseries metrics from {svc}",
                metrics=metrics,
                metadata=raw_payload.get("labels", {})
            ))

        self.record_ingest(len(events))
        return events
