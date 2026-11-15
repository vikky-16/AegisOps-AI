"""
Unit and Integration Tests for Kafka Streaming Pipeline
Tests producer, consumer, topic management, dead-letter routing, and health tracking.
"""

import pytest
import asyncio
from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.kafka.producer import AegisKafkaProducer
from backend.app.kafka.consumer import AegisKafkaConsumer
from backend.app.kafka.topic_manager import topic_manager
from backend.app.kafka.health import KafkaHealthTracker
from backend.app.kafka.dead_letter import DeadLetterHandler
from backend.app.kafka.event_bus import AegisEventBus


@pytest.mark.asyncio
async def test_topic_manager_standard_topics():
    topics = topic_manager.get_standard_topics()
    assert "telemetry.raw" in topics
    assert "telemetry.logs" in topics
    assert "telemetry.metrics" in topics
    assert "telemetry.traces" in topics
    assert "telemetry.anomalies" in topics
    assert "incidents" in topics
    assert "remediation.actions" in topics
    assert "remediation.results" in topics
    assert "telemetry.deadletter" in topics


@pytest.mark.asyncio
async def test_dead_letter_routing():
    dlq = DeadLetterHandler(max_retained=50)
    res = dlq.route_to_dlq(
        raw_message="malformed json content {{{",
        error_reason="JSONDecodeError: expecting property name",
        topic="telemetry.raw"
    )
    assert res["dlq_id"].startswith("DLQ-")
    assert res["original_topic"] == "telemetry.raw"
    assert "expecting property name" in res["error_reason"]
    
    recent = dlq.get_recent_dlq(10)
    assert len(recent) == 1
    assert recent[0]["dlq_id"] == res["dlq_id"]


@pytest.mark.asyncio
async def test_kafka_health_tracker():
    health = KafkaHealthTracker()
    health.set_connection_status(True, "localhost:9092")
    health.record_received(10)
    health.record_processed(8, latency_ms=1.2)
    health.record_failed(2)
    health.set_lag(0)

    summary = health.get_metrics_summary()
    assert summary["is_connected"] is True
    assert summary["events_received"] == 10
    assert summary["events_processed"] == 8
    assert summary["events_failed"] == 2
    assert summary["consumer_lag"] == 0
    assert summary["avg_processing_latency_ms"] == 1.2


@pytest.mark.asyncio
async def test_kafka_producer_consumer_bus():
    bus = AegisEventBus()
    await bus.start()

    received_events = []
    def handler(event: UnifiedTelemetryEvent):
        received_events.append(event)

    bus.subscribe(handler)

    test_event = UnifiedTelemetryEvent(
        source="otel-agent",
        service_name="payment-service",
        event_type="metric",
        metric_name="http_request_duration",
        metric_value=450.0,
        message="Payment processing normal"
    )

    success = await bus.emit(test_event, topic="telemetry.metrics")
    assert success is True
    assert len(received_events) == 1
    assert received_events[0].service_name == "payment-service"
    assert received_events[0].metric_value == 450.0

    await bus.stop()
