"""
Unit and Integration Tests for Real-Time Telemetry Connectors & Declarative Runbooks
Verifies OpenTelemetry, Syslog, Webhooks, Prometheus, DB, Payments, ETL, and Runbook Dry-Runs.
"""

import pytest
from backend.app.integrations.manager import integration_manager
from backend.app.runbooks.engine import runbook_engine
from backend.app.integrations.models import TelemetryType, TelemetrySeverity


def test_opentelemetry_connector_normalization():
    otel_conn = integration_manager.get_connector("otel-collector")
    assert otel_conn is not None

    raw_otel = {
        "resourceSpans": [{
            "resource": {
                "attributes": [{"key": "service.name", "value": {"stringValue": "payment-api"}}]
            },
            "scopeSpans": [{
                "spans": [{
                    "name": "POST /v1/charge",
                    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                    "spanId": "00f067aa0ba902b7",
                    "status": {"code": 2},
                    "startTimeUnixNano": 1000000,
                    "endTimeUnixNano": 5000000
                }]
            }]
        }]
    }

    events = otel_conn.normalize(raw_otel)
    assert len(events) == 1
    assert events[0].service == "payment-api"
    assert events[0].type == TelemetryType.TRACE
    assert events[0].severity == TelemetrySeverity.ERROR
    assert events[0].trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_syslog_connector_normalization():
    syslog_conn = integration_manager.get_connector("syslog-receiver")
    assert syslog_conn is not None

    raw_syslog = "<34>1 2026-08-18T12:00:00Z app-server-01 nginx 4512 - - Connection pool timeout to database"
    events = syslog_conn.normalize(raw_syslog)
    assert len(events) == 1
    assert events[0].type == TelemetryType.LOG
    assert events[0].host == "app-server-01"
    assert "timeout to database" in events[0].message


def test_webhook_connector_normalization():
    webhook_conn = integration_manager.get_connector("webhook-receiver")
    assert webhook_conn is not None

    raw_webhook = {
        "service": "order-api",
        "severity": "CRITICAL",
        "event_type": "THREAD_DEADLOCK",
        "message": "Thread pool exhaustion in order checkout worker",
        "trace_id": "trace-9912",
        "metrics": {"active_threads": 250.0}
    }

    events = webhook_conn.normalize(raw_webhook)
    assert len(events) == 1
    assert events[0].service == "order-api"
    assert events[0].severity == TelemetrySeverity.CRITICAL
    assert events[0].event_type == "THREAD_DEADLOCK"
    assert events[0].metrics["active_threads"] == 250.0


def test_database_connector_pool_saturation():
    db_conn = integration_manager.get_connector("database-monitor")
    assert db_conn is not None

    raw_db = {
        "database_name": "database-service",
        "pool_utilization": 0.95,
        "active_connections": 20,
        "max_connections": 20,
        "avg_query_latency_ms": 3200.0,
        "lock_wait_seconds": 12.5
    }

    events = db_conn.normalize(raw_db)
    assert len(events) == 1
    assert events[0].severity == TelemetrySeverity.CRITICAL
    assert events[0].event_type == "CONNECTION_POOL_EXHAUSTION"
    assert "pool exhausted" in events[0].message.lower()


def test_payment_system_gateway_timeout():
    pay_conn = integration_manager.get_connector("payment-system-monitor")
    assert pay_conn is not None

    raw_pay = {
        "component": "payment-gateway",
        "anonymized_transaction_id": "txn-anon-789",
        "gateway_status": "UNAVAILABLE",
        "latency_ms": 5200.0,
        "failure_rate": 0.85
    }

    events = pay_conn.normalize(raw_pay)
    assert len(events) == 1
    assert events[0].severity == TelemetrySeverity.CRITICAL
    assert events[0].event_type == "PAYMENT_GATEWAY_UNAVAILABLE"
    # Verify zero cardholder data
    assert "card" not in str(events[0].metadata)
    assert "cvv" not in str(events[0].metadata)


def test_datapipeline_refresh_delay():
    pipe_conn = integration_manager.get_connector("datapipeline-monitor")
    assert pipe_conn is not None

    raw_etl = {
        "pipeline_name": "executive-data-mart",
        "status": "DELAYED",
        "delay_minutes": 42,
        "duration_seconds": 2100.0,
        "records_processed": 0
    }

    events = pipe_conn.normalize(raw_etl)
    assert len(events) == 1
    assert events[0].severity == TelemetrySeverity.WARNING
    assert events[0].event_type == "DATA_MART_REFRESH_DELAYED"
    assert "delayed by 42 minutes" in events[0].message


def test_runbook_catalog_and_dry_run():
    runbooks = runbook_engine.list_runbooks()
    assert len(runbooks) >= 7

    # Test Dry Run for reset_connection_pool
    dry_res = runbook_engine.execute_dry_run("reset_connection_pool", "database-service")
    assert dry_res["success"] is True
    assert dry_res["runbook_id"] == "reset_connection_pool"
    assert dry_res["data_loss_risk"] == "NONE"
    assert dry_res["expected_downtime_sec"] == 0
    assert dry_res["dry_run_passed"] is True

    # Test Dry Run for restart_service
    dry_restart = runbook_engine.execute_dry_run("restart_service", "service-b")
    assert dry_restart["success"] is True
    assert dry_restart["risk_level"] == "MEDIUM"
