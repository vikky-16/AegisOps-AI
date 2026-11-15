"""
Central Integrations & Ingestion Manager
Registers authorized telemetry connectors, validates security tokens, and feeds normalized events into stream pipeline.
"""

from typing import Dict, Any, List, Optional
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent
from backend.app.integrations.otel import OpenTelemetryConnector
from backend.app.integrations.syslog import SyslogConnector
from backend.app.integrations.webhook import WebhookConnector
from backend.app.integrations.prometheus import PrometheusConnector
from backend.app.integrations.database_connector import DatabaseTelemetryConnector
from backend.app.integrations.payment_connector import PaymentSystemConnector
from backend.app.integrations.datapipeline_connector import DataPipelineConnector


class IntegrationManager:
    def __init__(self):
        self.connectors: Dict[str, BaseConnector] = {}
        self._register_default_connectors()

    def _register_default_connectors(self):
        self.register(OpenTelemetryConnector())
        self.register(SyslogConnector())
        self.register(WebhookConnector())
        self.register(PrometheusConnector())
        self.register(DatabaseTelemetryConnector())
        self.register(PaymentSystemConnector())
        self.register(DataPipelineConnector())

    def register(self, connector: BaseConnector):
        self.connectors[connector.connector_id] = connector

    def get_connector(self, connector_id: str) -> Optional[BaseConnector]:
        return self.connectors.get(connector_id)

    def list_connectors(self) -> List[Dict[str, Any]]:
        return [c.get_status_summary() for c in self.connectors.values()]

    def ingest_payload(
        self,
        connector_id: str,
        payload: Any,
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None
    ) -> List[NormalizedTelemetryEvent]:
        connector = self.connectors.get(connector_id)
        if not connector:
            raise ValueError(f"Unknown integration connector '{connector_id}'")

        if not connector.enabled:
            raise PermissionError(f"Connector '{connector_id}' is disabled by administrative policy.")

        # Validate authentication
        if headers is None:
            headers = {}
        if not connector.validate_auth(headers, auth_token):
            connector.error_count += 1
            connector.last_error = "Unauthorized: Invalid or missing API credential header."
            raise PermissionError(connector.last_error)

        try:
            events = connector.normalize(payload, headers)
            return events
        except Exception as e:
            connector.error_count += 1
            connector.last_error = str(e)
            raise e


# Global Singleton Integration Manager Instance
integration_manager = IntegrationManager()
