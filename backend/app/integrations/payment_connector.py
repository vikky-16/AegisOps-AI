"""
Domain-Aware Payment System Telemetry Connector
Monitors Payment API, Payment Gateway, Payment Processor, and Ledger operational metrics.
STRICT SECURITY: Contains ZERO cardholder data, CVVs, or payment credentials. Uses anonymous IDs only.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class PaymentSystemConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="payment-system-monitor",
            name="Payment Ecosystem Telemetry Connector",
            connector_type="PAYMENT_SYSTEM",
            description="Domain-aware telemetry for Payment API, Payment Gateway, and Transaction Processing pipelines.",
            auth_required=True,
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
            component = item.get("component") or item.get("service") or "payment-api"
            txn_id = item.get("anonymized_transaction_id") or item.get("transaction_id") or "txn-anon"
            event_code = item.get("event_type") or "TRANSACTION_EVENT"
            latency_ms = float(item.get("latency_ms", 15.0))
            failure_rate = float(item.get("failure_rate", 0.0))
            gateway_status = item.get("gateway_status", "ONLINE")

            sev = TelemetrySeverity.INFO
            msg = f"Payment component '{component}' operating normally (latency: {latency_ms:.1f}ms)."

            if gateway_status == "UNAVAILABLE" or event_code == "GATEWAY_UNAVAILABLE":
                sev = TelemetrySeverity.CRITICAL
                event_code = "PAYMENT_GATEWAY_UNAVAILABLE"
                msg = f"CRITICAL: Upstream payment gateway unavailable. Inbound transaction dispatch failing."
            elif failure_rate >= 0.15 or event_code == "TRANSACTION_FAILURE_SPIKE":
                sev = TelemetrySeverity.ERROR
                event_code = "TRANSACTION_FAILURE_SPIKE"
                msg = f"ERROR: Payment failure rate surged to {failure_rate*100:.1f}%. Downstream ledger timeouts."
            elif latency_ms > 2000.0 or event_code == "PAYMENT_LATENCY_SPIKE":
                sev = TelemetrySeverity.WARNING
                event_code = "PAYMENT_LATENCY_SPIKE"
                msg = f"WARNING: Payment processing latency degraded to {latency_ms:.1f}ms."

            events.append(NormalizedTelemetryEvent(
                timestamp=item.get("timestamp") or now_iso,
                source=f"payment-{component}",
                environment="demo",
                service=component.lower(),
                type=TelemetryType.PAYMENT_SIGNAL,
                severity=sev,
                event_type=event_code,
                message=msg,
                trace_id=item.get("trace_id") or f"trace-{txn_id}",
                metrics={
                    "latency_ms": latency_ms,
                    "failure_rate": failure_rate
                },
                metadata={
                    "anonymized_txn_ref": txn_id,
                    "gateway_status": gateway_status,
                    "processor_region": item.get("region", "us-east-1")
                }
            ))

        self.record_ingest(len(events))
        return events
