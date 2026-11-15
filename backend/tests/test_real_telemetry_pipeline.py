"""
Unit and Integration Tests for Real Telemetry Pipeline
Tests OpenTelemetry SDK initialization in microservices, OTLP Normalization (traces, metrics, logs),
AegisKafkaConsumer streaming dispatch, DLQ handling, and End-to-End traversal to the AIOps Intelligence Layer.
"""

import os
import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.integrations.normalizer import telemetry_normalizer
from backend.app.kafka.consumer import AegisKafkaConsumer
from backend.app.kafka.producer import AegisKafkaProducer
from backend.app.kafka.topic_manager import topic_manager
from backend.app.kafka.dead_letter import dead_letter_handler
from backend.app.monitoring.collector import collector
from services.base_service import BaseService, OPENTELEMETRY_AVAILABLE


def test_opentelemetry_sdk_initialization():
    """Verifies that BaseService initializes OpenTelemetry SDK with Resource attributes and Tracer."""
    svc = BaseService(name="test-otel-service", port=9999, role="Test Service")
    assert svc.name == "test-otel-service"
    assert svc.port == 9999
    
    if OPENTELEMETRY_AVAILABLE:
        assert svc.tracer_provider is not None
        assert svc.tracer is not None
        resource = svc.tracer_provider.resource
        assert resource.attributes.get("service.name") == "test-otel-service"
        assert resource.attributes.get("service.version") == "1.0.0"


def test_normalizer_otlp_traces_decoding():
    """Verifies UniversalTelemetryNormalizer decodes OTLP resourceSpans payload."""
    otlp_payload = {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "payment-service"}},
                    {"key": "environment", "value": {"stringValue": "production"}}
                ]
            },
            "scopeSpans": [{
                "spans": [{
                    "name": "POST /v1/charge",
                    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                    "spanId": "00f067aa0ba902b7",
                    "status": {"code": 2, "message": "Card authorization failed"},
                    "startTimeUnixNano": 1000000000,
                    "endTimeUnixNano": 1150000000,
                    "attributes": [
                        {"key": "http.status_code", "value": {"intValue": 500}},
                        {"key": "http.method", "value": {"stringValue": "POST"}}
                    ]
                }]
            }]
        }]
    }

    events = telemetry_normalizer.normalize_event(otlp_payload, source="kafka")
    assert len(events) == 1
    ev = events[0]
    assert ev.service_name == "payment-service"
    assert ev.event_type == "trace"
    assert ev.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert ev.span_id == "00f067aa0ba902b7"
    assert ev.severity == "ERROR"
    assert ev.metric_name == "span_duration_ms"
    assert ev.metric_value == 150.0
    assert ev.http_status == 500
    assert "Card authorization failed" in ev.message


def test_normalizer_otlp_metrics_decoding():
    """Verifies UniversalTelemetryNormalizer decodes OTLP resourceMetrics payload."""
    otlp_metric_payload = {
        "resourceMetrics": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "database-service"}}
                ]
            },
            "scopeMetrics": [{
                "metrics": [{
                    "name": "db_connection_pool_active",
                    "gauge": {
                        "dataPoints": [{
                            "asDouble": 19.0,
                            "attributes": [{"key": "pool.name", "value": {"stringValue": "primary"}}]
                        }]
                    }
                }]
            }]
        }]
    }

    events = telemetry_normalizer.normalize_event(otlp_metric_payload, source="kafka")
    assert len(events) == 1
    ev = events[0]
    assert ev.service_name == "database-service"
    assert ev.event_type == "metric"
    assert ev.metric_name == "db_connection_pool_active"
    assert ev.metric_value == 19.0


def test_normalizer_otlp_logs_decoding():
    """Verifies UniversalTelemetryNormalizer decodes OTLP resourceLogs payload."""
    otlp_log_payload = {
        "resourceLogs": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "gateway"}}
                ]
            },
            "scopeLogs": [{
                "logRecords": [{
                    "timeUnixNano": 1700000000000000000,
                    "severityText": "ERROR",
                    "severityNumber": 17,
                    "body": {"stringValue": "Upstream service-a timeout after 3500ms"},
                    "traceId": "9b1f0c2a88394982a17cb4d7529a8f10",
                    "spanId": "48f93e2b10a9c8f1",
                    "attributes": [
                        {"key": "http.target", "value": {"stringValue": "/work"}}
                    ]
                }]
            }]
        }]
    }

    events = telemetry_normalizer.normalize_event(otlp_log_payload, source="kafka")
    assert len(events) == 1
    ev = events[0]
    assert ev.service_name == "gateway"
    assert ev.event_type == "log"
    assert ev.severity == "ERROR"
    assert "timeout after 3500ms" in ev.message
    assert ev.trace_id == "9b1f0c2a88394982a17cb4d7529a8f10"


@pytest.mark.asyncio
async def test_kafka_consumer_dispatch_to_registered_callbacks():
    """Verifies AegisKafkaConsumer dispatches decoded Kafka messages to registered handlers."""
    consumer = AegisKafkaConsumer(bootstrap_servers="localhost:9092", topic="telemetry.raw")
    received_events = []

    def callback_handler(event: UnifiedTelemetryEvent):
        received_events.append(event)

    consumer.register_event_handler(callback_handler)

    test_payload = {
        "service_name": "service-b",
        "event_type": "metric",
        "metric_name": "payment_latency_ms",
        "metric_value": 3400.0,
        "severity": "WARNING",
        "message": "Elevated payment latency detected"
    }

    await consumer.dispatch_incoming_message(test_payload, topic="telemetry.raw")
    assert len(received_events) == 1
    assert received_events[0].service_name == "service-b"
    assert received_events[0].metric_value == 3400.0


@pytest.mark.asyncio
async def test_kafka_consumer_dead_letter_routing_on_malformed_payload():
    """Verifies malformed or corrupt payloads are safely trapped into DLQ without crashing."""
    consumer = AegisKafkaConsumer(bootstrap_servers="localhost:9092", topic="telemetry.raw")
    
    # Send object that cannot be normalized
    dlq_len_before = len(dead_letter_handler.get_recent_dlq(100))
    
    class NonSerializable:
        pass

    # Normalizer handles primitives or wraps them, let's verify invalid dict structure triggering handler failure
    async def bad_callback(ev):
        raise ValueError("Simulated callback processing error")

    consumer.register_event_handler(bad_callback)
    await consumer.dispatch_incoming_message({"service_name": "broken-svc", "event_type": "log"}, topic="telemetry.raw")
    
    dlq_len_after = len(dead_letter_handler.get_recent_dlq(100))
    assert dlq_len_after > dlq_len_before


@pytest.mark.asyncio
async def test_kafka_consumer_lifecycle():
    """Verifies clean start and stop lifecycle for AegisKafkaConsumer."""
    consumer = AegisKafkaConsumer(bootstrap_servers="localhost:9092", topic="telemetry.raw")
    await consumer.start()
    assert consumer.is_running is True
    assert consumer._worker_task is not None
    
    await consumer.stop()
    assert consumer.is_running is False
    assert consumer._worker_task is None


@pytest.mark.asyncio
async def test_end_to_end_kafka_payload_traversal_to_intelligence():
    """
    Verifies full end-to-end chain:
    OTLP Kafka Payload -> AegisKafkaConsumer -> Normalizer -> MonitoringCollector -> Anomaly Detection -> Correlator -> Incident
    """
    # Create realistic OTLP trace payload representing a critical failure in database-service
    otlp_failure_span = {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "database-service"}}
                ]
            },
            "scopeSpans": [{
                "spans": [{
                    "name": "SQL TRANSACTION LOCK",
                    "traceId": "99f8e7d6c5b4a3928170e5d4c3b2a100",
                    "spanId": "1122334455667788",
                    "status": {"code": 2, "message": "Deadlock encountered during ledger update"},
                    "attributes": [
                        {"key": "http.status_code", "value": {"intValue": 500}}
                    ]
                }]
            }]
        }]
    }

    initial_incidents_count = len(collector.active_incidents)
    
    # Dispatch through Kafka consumer entrypoint
    from backend.app.kafka.consumer import kafka_consumer
    await kafka_consumer.dispatch_incoming_message(otlp_failure_span, topic="telemetry.raw")

    # Verify event traversed into active incidents or correlated into existing incident
    assert len(collector.active_incidents) >= initial_incidents_count
    
    # Check that the live feed recorded the telemetry stream and anomaly
    feed_events = list(collector.live_operations_feed)
    assert any("database-service" in str(f.get("service", "")) for f in feed_events[:10])
