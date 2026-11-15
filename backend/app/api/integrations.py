"""
Telemetry Integrations & Ingestion API Endpoints
Receives live OpenTelemetry, Syslog, Webhooks, Prometheus, DB, Payment, and Data Pipeline signals.
"""

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from backend.app.integrations.manager import integration_manager
from backend.app.monitoring.collector import collector

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class ToggleConnectorRequest(BaseModel):
    enabled: bool


@router.get("")
async def list_integrations():
    """Returns status, metadata, and event rate metrics for all authorized connectors."""
    return integration_manager.list_connectors()


@router.post("/{connector_id}/ingest")
async def ingest_telemetry(
    connector_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None)
):
    """
    Ingests live telemetry payload through specified connector, normalizes it,
    and dispatches it through the real-time stream processing pipeline.
    """
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            raw_payload = await request.json()
        else:
            raw_payload = (await request.body()).decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload encoding: {str(e)}")

    headers = dict(request.headers)
    auth_token = authorization or x_api_key

    try:
        events = integration_manager.ingest_payload(
            connector_id=connector_id,
            payload=raw_payload,
            headers=headers,
            auth_token=auth_token
        )

        # Feed normalized events into the central monitoring collector
        for event in events:
            collector.ingest_normalized_event(event)

        return {
            "success": True,
            "connector_id": connector_id,
            "events_normalized": len(events),
            "status": "ACCEPTED"
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/{connector_id}/test")
async def test_connector(connector_id: str):
    """Dispatches a test operational heartbeat through the selected connector."""
    sample_payloads = {
        "otel-collector": {
            "events": [{
                "service": "payment-api",
                "severity": "INFO",
                "event_type": "OTEL_HEARTBEAT",
                "message": "OpenTelemetry collector test ping verified."
            }]
        },
        "syslog-receiver": "<13>1 2026-08-18T12:00:00Z app-server-01 syslogd 123 - - Syslog ingestion heartbeat test",
        "webhook-receiver": [{
            "service": "api-gateway",
            "level": "INFO",
            "event_type": "WEBHOOK_PING",
            "message": "Webhook connector health test received."
        }],
        "prometheus-gateway": {
            "service": "database-service",
            "metrics": {"http_requests_total": 450, "cpu_seconds_total": 12.4}
        },
        "database-monitor": {
            "database_name": "database-service",
            "pool_utilization": 0.35,
            "active_connections": 7,
            "max_connections": 20,
            "avg_query_latency_ms": 14.5
        },
        "payment-system-monitor": {
            "component": "payment-api",
            "anonymized_transaction_id": "txn-test-01",
            "event_type": "PAYMENT_HEARTBEAT",
            "latency_ms": 22.0,
            "failure_rate": 0.0
        },
        "datapipeline-monitor": {
            "pipeline_name": "executive-data-mart",
            "status": "SUCCESS",
            "delay_minutes": 0,
            "duration_seconds": 94.0,
            "records_processed": 154000
        }
    }

    connector = integration_manager.get_connector(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Unknown connector '{connector_id}'")

    payload = sample_payloads.get(connector_id, {"message": "Test ping"})
    events = connector.normalize(payload)
    for ev in events:
        collector.ingest_normalized_event(ev)

    return {
        "success": True,
        "connector_id": connector_id,
        "message": f"Successfully verified connector '{connector.name}'. Received {len(events)} normalized events.",
        "sample_event": events[0].dict() if events else {}
    }


@router.post("/{connector_id}/toggle")
async def toggle_connector(connector_id: str, req: ToggleConnectorRequest):
    """Enables or disables an authorized telemetry connector."""
    connector = integration_manager.get_connector(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Unknown connector '{connector_id}'")

    connector.enabled = req.enabled
    return {"success": True, "connector_id": connector_id, "enabled": connector.enabled}
