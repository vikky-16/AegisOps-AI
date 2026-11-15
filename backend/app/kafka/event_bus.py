"""
AegisOps AI - Unified Event Streaming Bus
Bridges producers, Kafka brokers, consumers, and internal processing pipelines.
"""

import asyncio
from typing import Dict, Any, Union, Callable
from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.kafka.producer import kafka_producer
from backend.app.kafka.consumer import kafka_consumer
from backend.app.kafka.topic_manager import topic_manager
from backend.app.kafka.health import kafka_health_tracker


class AegisEventBus:
    def __init__(self):
        self.producer = kafka_producer
        self.consumer = kafka_consumer
        self.topic_manager = topic_manager
        self.health = kafka_health_tracker

    async def start(self):
        await self.producer.start()
        await self.consumer.start()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()

    def subscribe(self, callback: Callable[[UnifiedTelemetryEvent], None]):
        """Subscribes an event handler to the streaming bus."""
        self.consumer.register_event_handler(callback)

    async def emit(self, event: Union[UnifiedTelemetryEvent, Dict[str, Any]], topic: str = None) -> bool:
        """Publishes an event to the bus and dispatches immediately to consumers."""
        success = await self.producer.publish(event, topic=topic)
        # In-process bridge ensures immediate processing
        if success:
            await self.consumer.dispatch_incoming_message(event, topic=topic or "telemetry.raw")
        return success


event_bus = AegisEventBus()
