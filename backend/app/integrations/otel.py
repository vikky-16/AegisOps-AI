"""
OpenTelemetry (OTel) Collector Integration
Ingests traces, spans, and metrics in OTel JSON format.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class OpenTelemetryConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="otel-collector",
            name="OpenTelemetry Collector",
            connector_type="OPENTELEMETRY",
            description="High-performance trace and metric ingestion from OpenTelemetry SDKs and agents.",
            auth_required=True,
            enabled=True
        )

    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        events: List[NormalizedTelemetryEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Handle ResourceSpans / Trace payloads
        if isinstance(raw_payload, dict):
            resource_spans = raw_payload.get("resourceSpans", [])
            for rs in resource_spans:
                service_name = "unknown-otel-service"
                resource_attrs = rs.get("resource", {}).get("attributes", [])
                for attr in resource_attrs:
                    if attr.get("key") == "service.name":
                        service_name = attr.get("value", {}).get("stringValue", service_name)

                for scope_span in rs.get("scopeSpans", []):
                    for span in scope_span.get("spans", []):
                        name = span.get("name", "span")
                        trace_id = span.get("traceId", "")
                        span_id = span.get("spanId", "")
                        status_code = span.get("status", {}).get("code", 0)
                        
                        is_error = status_code == 2 or "error" in name.lower()
                        severity = TelemetrySeverity.ERROR if is_error else TelemetrySeverity.INFO
                        
                        events.append(NormalizedTelemetryEvent(
                            timestamp=now_iso,
                            source="otel-agent",
                            environment="production" if not headers or "demo" not in str(headers) else "demo",
                            service=service_name,
                            type=TelemetryType.TRACE,
                            severity=severity,
                            event_type=f"SPAN_{name.upper()}",
                            message=f"Span '{name}' completed with status code {status_code}",
                            trace_id=trace_id,
                            span_id=span_id,
                            metadata={"duration_nano": span.get("endTimeUnixNano", 0) - span.get("startTimeUnixNano", 0)}
                        ))

            # Handle direct JSON list
            if "events" in raw_payload:
                for item in raw_payload["events"]:
                    events.append(NormalizedTelemetryEvent(
                        timestamp=item.get("timestamp", now_iso),
                        source=item.get("source", "otel-agent"),
                        environment=item.get("environment", "demo"),
                        service=item.get("service", "otel-service"),
                        type=TelemetryType.LOG,
                        severity=TelemetrySeverity(item.get("severity", "INFO")),
                        event_type=item.get("event_type", "OTEL_EVENT"),
                        message=item.get("message", ""),
                        trace_id=item.get("trace_id"),
                        metadata=item.get("metadata", {})
                    ))

        self.record_ingest(len(events))
        return events
