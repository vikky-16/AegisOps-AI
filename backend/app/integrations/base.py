"""
Base Connector Interface for Ingestion Layer
All telemetry sources (OTel, Syslog, Prometheus, Webhooks, DB, Payments, ETL) implement this.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import time
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class BaseConnector(ABC):
    def __init__(
        self,
        connector_id: str,
        name: str,
        connector_type: str,
        description: str,
        auth_required: bool = False,
        enabled: bool = True
    ):
        self.connector_id = connector_id
        self.name = name
        self.connector_type = connector_type
        self.description = description
        self.auth_required = auth_required
        self.enabled = enabled
        self.status = "HEALTHY"
        self.total_events_received = 0
        self.last_event_timestamp: Optional[str] = None
        self.error_count = 0
        self.last_error: Optional[str] = None
        self._rate_window: List[float] = []

    def validate_auth(self, headers: Dict[str, str], token: Optional[str] = None) -> bool:
        """Validates incoming authorization header or token if auth is required."""
        if not self.auth_required:
            return True
        auth_header = headers.get("authorization") or headers.get("x-api-key") or token
        return bool(auth_header and len(auth_header) >= 8)

    @abstractmethod
    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        """Parses and normalizes raw vendor/protocol payload into standard NormalizedTelemetryEvent objects."""
        pass

    def record_ingest(self, count: int = 1):
        """Updates internal telemetry metrics and rate tracking."""
        now = time.time()
        self.total_events_received += count
        self.last_event_timestamp = datetime.now(timezone.utc).isoformat()
        self._rate_window.append(now)
        # Keep recent 60 seconds in window
        self._rate_window = [t for t in self._rate_window if now - t <= 60]

    def get_event_rate_per_second(self) -> float:
        """Calculates moving 60-second events/sec ingestion rate."""
        now = time.time()
        self._rate_window = [t for t in self._rate_window if now - t <= 60]
        return round(len(self._rate_window) / 60.0, 2)

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns connector health metadata for management console."""
        return {
            "connector_id": self.connector_id,
            "name": self.name,
            "type": self.connector_type,
            "description": self.description,
            "enabled": self.enabled,
            "status": self.status,
            "auth_required": self.auth_required,
            "total_events": self.total_events_received,
            "event_rate_eps": self.get_event_rate_per_second(),
            "last_event_at": self.last_event_timestamp,
            "error_count": self.error_count,
            "last_error": self.last_error
        }
