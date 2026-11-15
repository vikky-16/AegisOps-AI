"""
AegisOps AI - Customer Incident Webhook Notification Dispatcher
Dispatches real-time structured incident notifications to customer webhooks (Slack, PagerDuty, custom APIs).
Enforces zero secret leakage and operates asynchronously with non-blocking timeouts.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import httpx

from backend.app.core.pii_masker import pii_masker

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """Asynchronously dispatches incident webhook notifications to customer endpoints."""

    def __init__(self, timeout_sec: float = 3.0):
        self.timeout_sec = timeout_sec
        self.delivery_history: list = []

    def build_payload(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs a clean, scrubbed webhook notification payload."""
        now_iso = datetime.now(timezone.utc).isoformat()
        raw_payload = {
            "incident_id": incident.get("id") or incident.get("incident_id"),
            "tenant_id": incident.get("tenant_id", "demo-tenant"),
            "severity": incident.get("severity", "CRITICAL"),
            "service": incident.get("root_cause_service") or incident.get("service") or "system",
            "root_cause": incident.get("summary") or incident.get("root_cause_category") or "SERVICE_DEGRADATION",
            "confidence": float(incident.get("rca_confidence") or incident.get("confidence") or 0.85),
            "blast_radius": float(incident.get("blast_radius") or 0.0),
            "status": incident.get("status", "OPEN"),
            "timestamp": incident.get("started_at") or incident.get("timestamp") or now_iso
        }
        # Scrub any potential secrets
        return pii_masker.mask_dict(raw_payload)

    async def notify_incident(
        self,
        incident: Dict[str, Any],
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sends non-blocking HTTP POST notification to the target webhook."""
        if not webhook_url:
            return {"status": "SKIPPED", "message": "No webhook URL configured for tenant"}

        payload = self.build_payload(incident)
        t0 = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"User-Agent": "AegisOps-AI-Alert-Dispatcher/2.0", "Content-Type": "application/json"}
                )
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                success = (200 <= res.status_code < 300)
                record = {
                    "incident_id": payload["incident_id"],
                    "tenant_id": payload["tenant_id"],
                    "url": webhook_url,
                    "status_code": res.status_code,
                    "success": success,
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                self.delivery_history.append(record)
                return record
        except Exception as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            logger.warning(f"Webhook dispatch error for {webhook_url}: {exc}")
            record = {
                "incident_id": payload["incident_id"],
                "tenant_id": payload["tenant_id"],
                "url": webhook_url,
                "status_code": 0,
                "success": False,
                "error": str(exc),
                "latency_ms": latency_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.delivery_history.append(record)
            return record


webhook_notifier = WebhookNotifier()
