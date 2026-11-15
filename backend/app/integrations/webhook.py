"""
Generic HTTP / JSON Webhook Ingestion Connector
Receives structured logs and alerts from custom applications, CI/CD, and external alerting systems.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class WebhookConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="webhook-receiver",
            name="HTTP / Webhook Receiver",
            connector_type="WEBHOOK",
            description="Direct HTTP POST webhook endpoint for JSON application logs, health checks, and alerting systems.",
            auth_required=True,
            enabled=True
        )

    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        events: List[NormalizedTelemetryEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        if isinstance(raw_payload, list):
            items = raw_payload
        elif isinstance(raw_payload, dict):
            items = raw_payload.get("events") or [raw_payload]
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue

            sev_str = str(item.get("severity") or item.get("level") or "INFO").upper()
            if sev_str not in [s.value for s in TelemetrySeverity]:
                sev_str = "INFO"

            type_str = str(item.get("type", "LOG")).upper()
            if type_str not in [t.value for t in TelemetryType]:
                type_str = "LOG"

            events.append(NormalizedTelemetryEvent(
                timestamp=item.get("timestamp") or now_iso,
                source=item.get("source") or item.get("host") or "webhook-client",
                environment=item.get("environment") or "demo",
                service=str(item.get("service") or "webhook-service").lower(),
                type=TelemetryType(type_str),
                severity=TelemetrySeverity(sev_str),
                event_type=str(item.get("event_type") or "WEBHOOK_ALERT").upper(),
                message=item.get("message") or str(item),
                trace_id=item.get("trace_id"),
                host=item.get("host", "localhost"),
                metrics=item.get("metrics", {}),
                metadata=item.get("metadata", {})
            ))

        self.record_ingest(len(events))
        return events
